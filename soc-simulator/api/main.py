"""SOC Simulator FastAPI backend."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis

from database import close_pool, get_pool, init_pool
from models import (
    AlertOut,
    AlertsListResponse,
    HealthResponse,
    HourBucket,
    InjectAttackResponse,
    LogOut,
    LogsListResponse,
    SeverityBucket,
    SeverityHeatmapResponse,
    StatsResponse,
    TopSourceIp,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
ALERT_CHANNEL = "alerts:live"
LOGS_STREAM_KEY = "logs:raw"
STATS_CACHE_KEY = "soc:stats:v1"
STATS_CACHE_TTL_SEC = 30

redis_client: aioredis.Redis | None = None
_broadcast_task: asyncio.Task | None = None


class ConnectionManager:
    """Tracks WebSocket clients for Redis alert fan-out."""

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    def register(self, ws: WebSocket) -> None:
        self._clients.append(ws)

    def unregister(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, message: str) -> None:
        stale: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.unregister(ws)


ws_manager = ConnectionManager()


async def redis_subscriber_loop() -> None:
    if redis_client is None:
        return
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(ALERT_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, bytes):
                data = data.decode()
            if data:
                try:
                    payload = json.loads(data)
                    if isinstance(payload, dict):
                        data = json.dumps(
                            alert_db_row_to_client_json(payload), default=str
                        )
                except json.JSONDecodeError:
                    pass
                if redis_client is not None:
                    try:
                        await redis_client.delete(STATS_CACHE_KEY)
                    except Exception:
                        pass
                await ws_manager.broadcast(data)
    except asyncio.CancelledError:
        raise
    finally:
        try:
            await pubsub.unsubscribe(ALERT_CHANNEL)
            await pubsub.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, _broadcast_task
    load_dotenv()
    await init_pool()
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    _broadcast_task = asyncio.create_task(redis_subscriber_loop())
    yield
    if _broadcast_task:
        _broadcast_task.cancel()
        try:
            await _broadcast_task
        except asyncio.CancelledError:
            pass
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
    await close_pool()


app = FastAPI(title="SOC Simulator API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _record_to_dict(r) -> dict:
    d = dict(r)
    if isinstance(d.get("raw_context"), str):
        d["raw_context"] = json.loads(d["raw_context"])
    return d


def _iso_timestamp(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def alert_db_row_to_client_json(record: dict[str, Any]) -> dict[str, Any]:
    """
    Map a Postgres alerts row or Redis JSON (snake_case) to camelCase for WebSocket clients.
    """
    raw = record.get("raw_context")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass

    out: dict[str, Any] = {}
    if record.get("id") is not None:
        out["id"] = str(record["id"])
    if "log_id" in record:
        out["logId"] = str(record["log_id"]) if record.get("log_id") else None
    if "timestamp" in record:
        out["timestamp"] = _iso_timestamp(record.get("timestamp"))
    if "severity" in record and record["severity"] is not None:
        out["severity"] = int(record["severity"])
    if "anomaly_score" in record and record["anomaly_score"] is not None:
        out["anomalyScore"] = float(record["anomaly_score"])
    if "model_used" in record:
        out["modelUsed"] = record.get("model_used")
    if "event_type" in record:
        out["eventType"] = record.get("event_type")
    if "source_ip" in record:
        out["sourceIp"] = record.get("source_ip")
    if "mitre_tactic" in record:
        out["mitreTactic"] = record.get("mitre_tactic")
    if "mitre_technique" in record:
        out["mitreTechnique"] = record.get("mitre_technique")
    if "technique_id" in record:
        out["techniqueId"] = record.get("technique_id")
    if "confidence" in record:
        out["confidence"] = (
            float(record["confidence"])
            if record.get("confidence") is not None
            else None
        )
    if "recommended_action" in record:
        out["recommendedAction"] = record.get("recommended_action")
    if "explanation" in record:
        out["explanation"] = record.get("explanation")
    if raw is not None or "raw_context" in record:
        out["rawContext"] = raw
    if "acknowledged" in record and record["acknowledged"] is not None:
        out["acknowledged"] = bool(record["acknowledged"])
    if "created_at" in record:
        out["createdAt"] = _iso_timestamp(record.get("created_at"))
    return out


@app.get("/api/health", response_model=HealthResponse)
async def api_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/alerts", response_model=AlertsListResponse)
async def list_alerts(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    severity_min: int = Query(0, ge=0, le=10),
    acknowledged: Optional[bool] = None,
    since: Optional[str] = None,
) -> AlertsListResponse:
    pool = await get_pool()
    where: list[str] = ["severity >= $1"]
    args: list[Any] = [severity_min]
    i = 2
    if acknowledged is not None:
        where.append(f"acknowledged = ${i}")
        args.append(acknowledged)
        i += 1
    if since:
        parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
        where.append(f"timestamp >= ${i}")
        args.append(parsed_since)
        i += 1
    wh = " AND ".join(where)
    total = await pool.fetchval(f"SELECT COUNT(*) FROM alerts WHERE {wh}", *args)
    args.extend([limit, offset])
    lim_p, off_p = i, i + 1
    rows = await pool.fetch(
        f"SELECT * FROM alerts WHERE {wh} ORDER BY timestamp DESC LIMIT ${lim_p} OFFSET ${off_p}",
        *args,
    )
    alerts = [AlertOut.model_validate(_record_to_dict(r)) for r in rows]
    return AlertsListResponse(alerts=alerts, total=int(total or 0))
    

@app.get("/api/alerts/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: UUID) -> AlertOut:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT * FROM alerts WHERE id = $1", alert_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertOut.model_validate(_record_to_dict(row))


@app.patch("/api/alerts/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(alert_id: UUID) -> AlertOut:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE alerts SET acknowledged = true WHERE id = $1 RETURNING *",
        alert_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertOut.model_validate(_record_to_dict(row))


@app.get("/api/logs", response_model=LogsListResponse)
async def list_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    source_ip: Optional[str] = None,
    q: Optional[str] = None,
) -> LogsListResponse:
    pool = await get_pool()
    q_clean = (q or "").strip()[:200]
    conditions: list[str] = []
    args: list[Any] = []
    i = 1
    if source_ip:
        conditions.append(f"source_ip = ${i}")
        args.append(source_ip)
        i += 1
    if q_clean:
        conditions.append(f"raw_message ILIKE ${i}")
        args.append(f"%{q_clean}%")
        i += 1
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    total = await pool.fetchval(f"SELECT COUNT(*) FROM logs{where_sql}", *args)
    lim_p, off_p = i, i + 1
    rows = await pool.fetch(
        f"SELECT * FROM logs{where_sql} ORDER BY timestamp DESC LIMIT ${lim_p} OFFSET ${off_p}",
        *args,
        limit,
        offset,
    )
    logs = [LogOut.model_validate(_record_to_dict(r)) for r in rows]
    return LogsListResponse(logs=logs, total=int(total or 0))


async def _compute_stats() -> StatsResponse:
    pool = await get_pool()
    total_alerts_24h = await pool.fetchval(
        """SELECT COUNT(*) FROM alerts WHERE timestamp >= NOW() - INTERVAL '24 hours'"""
    )
    critical_alerts_24h = await pool.fetchval(
        """SELECT COUNT(*) FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours' AND severity >= 8"""
    )
    active_sources_24h = await pool.fetchval(
        """SELECT COUNT(DISTINCT source_ip) FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours' AND source_ip IS NOT NULL"""
    )
    top_rows = await pool.fetch(
        """SELECT source_ip AS ip, COUNT(*)::int AS count FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours' AND source_ip IS NOT NULL
           GROUP BY source_ip ORDER BY count DESC LIMIT 5"""
    )
    top_source_ips = [TopSourceIp(ip=r["ip"], count=r["count"]) for r in top_rows]
    hour_rows = await pool.fetch(
        """SELECT date_trunc('hour', timestamp) AS h, COUNT(*)::int AS count
           FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours'
           GROUP BY 1 ORDER BY 1"""
    )
    alerts_by_hour = [
        HourBucket(hour=r["h"].isoformat() if r["h"] else "", count=r["count"])
        for r in hour_rows
    ]
    sev_rows = await pool.fetch(
        """SELECT severity, COUNT(*)::int AS count FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours'
           GROUP BY severity ORDER BY severity"""
    )
    severity_distribution = [
        SeverityBucket(severity=int(r["severity"]), count=r["count"]) for r in sev_rows
    ]
    return StatsResponse(
        total_alerts_24h=int(total_alerts_24h or 0),
        critical_alerts_24h=int(critical_alerts_24h or 0),
        active_sources_24h=int(active_sources_24h or 0),
        top_source_ips=top_source_ips,
        alerts_by_hour=alerts_by_hour,
        severity_distribution=severity_distribution,
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    if redis_client is not None:
        try:
            cached = await redis_client.get(STATS_CACHE_KEY)
            if cached:
                return StatsResponse.model_validate_json(cached)
        except Exception:
            pass
    stats = await _compute_stats()
    if redis_client is not None:
        try:
            await redis_client.set(
                STATS_CACHE_KEY,
                stats.model_dump_json(),
                ex=STATS_CACHE_TTL_SEC,
            )
        except Exception:
            pass
    return stats


@app.get("/api/stats/heatmap", response_model=SeverityHeatmapResponse)
async def get_stats_heatmap() -> SeverityHeatmapResponse:
    pool = await get_pool()
    top_ips_rows = await pool.fetch(
        """SELECT source_ip AS ip FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours' AND source_ip IS NOT NULL
           GROUP BY source_ip ORDER BY COUNT(*) DESC LIMIT 10"""
    )
    ips = [str(r["ip"]) for r in top_ips_rows]
    if not ips:
        return SeverityHeatmapResponse(source_ips=[], matrix=[])

    rows = await pool.fetch(
        """
        SELECT a.source_ip AS ip,
               EXTRACT(HOUR FROM a.timestamp AT TIME ZONE 'UTC')::int AS hr,
               MAX(a.severity)::int AS max_sev
        FROM alerts a
        WHERE a.timestamp >= NOW() - INTERVAL '24 hours'
          AND a.source_ip = ANY($1::text[])
        GROUP BY a.source_ip, hr
        """,
        ips,
    )
    by_ip_hr: dict[str, dict[int, int]] = {ip: {} for ip in ips}
    for r in rows:
        ip = str(r["ip"])
        hr = int(r["hr"])
        if 0 <= hr <= 23:
            by_ip_hr.setdefault(ip, {})[hr] = int(r["max_sev"])

    matrix: list[list[int]] = []
    for ip in ips:
        row = [by_ip_hr.get(ip, {}).get(h, 0) for h in range(24)]
        matrix.append(row)

    return SeverityHeatmapResponse(source_ips=ips, matrix=matrix)


@app.post("/api/debug/inject-attack", response_model=InjectAttackResponse)
async def inject_attack() -> InjectAttackResponse:
    """Demo: push a high-signal attack-shaped log to Redis Stream logs:raw."""
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    log = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_ip": "203.0.113.77",
        "destination_ip": "10.0.0.5",
        "destination_port": 31337,
        "protocol": "TCP",
        "event_type": "port_scan",
        "bytes_transferred": 999_999_999,
        "username": None,
        "raw_message": "demo inject: multi-port scan + anomalous volume (portfolio)",
    }
    try:
        sid = await redis_client.xadd(
            LOGS_STREAM_KEY,
            {"data": json.dumps(log)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Redis XADD failed: {e}"
        ) from e
    return InjectAttackResponse(ok=True, stream_id=str(sid))


@app.get("/api/alerts/export")
async def export_alerts_csv() -> StreamingResponse:
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, timestamp, severity, anomaly_score, event_type, source_ip,
               mitre_tactic, mitre_technique, technique_id, acknowledged, explanation
        FROM alerts
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        ORDER BY timestamp DESC
        """
    )

    def generate() -> Any:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "id",
                "timestamp",
                "severity",
                "anomaly_score",
                "event_type",
                "source_ip",
                "mitre_tactic",
                "mitre_technique",
                "technique_id",
                "acknowledged",
                "explanation",
            ]
        )
        yield buf.getvalue()
        for r in rows:
            buf.seek(0)
            buf.truncate(0)
            w.writerow(
                [
                    str(r["id"]),
                    r["timestamp"].isoformat() if r["timestamp"] else "",
                    r["severity"],
                    r["anomaly_score"],
                    r["event_type"] or "",
                    r["source_ip"] or "",
                    r["mitre_tactic"] or "",
                    r["mitre_technique"] or "",
                    r["technique_id"] or "",
                    r["acknowledged"],
                    (r["explanation"] or "").replace("\n", " ").replace("\r", " "),
                ]
            )
            yield buf.getvalue()

    fn = f"alerts-export-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'},
    )


@app.websocket("/api/ws/alerts")
async def websocket_alerts(websocket: WebSocket) -> None:
    await websocket.accept()
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT * FROM alerts WHERE acknowledged = false
           ORDER BY timestamp DESC LIMIT 10"""
    )
    initial = [
        alert_db_row_to_client_json(_record_to_dict(r)) for r in rows
    ]
    await websocket.send_json({"type": "initial", "alerts": initial})
    ws_manager.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unregister(websocket)
