"""SOC Simulator FastAPI backend."""

from __future__ import annotations

import asyncio
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
import redis.asyncio as aioredis

from database import close_pool, get_pool, init_pool
from models import (
    AlertOut,
    AlertsListResponse,
    HealthResponse,
    HourBucket,
    LogOut,
    LogsListResponse,
    SeverityBucket,
    StatsResponse,
    TopSourceIp,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
ALERT_CHANNEL = "alerts:live"

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


def _record_to_dict(r: Any) -> dict[str, Any]:
    return {k: r[k] for k in r.keys()}


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
        where.append(f"timestamp >= ${i}::timestamptz")
        args.append(since)
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
) -> LogsListResponse:
    pool = await get_pool()
    if source_ip:
        total = await pool.fetchval(
            "SELECT COUNT(*) FROM logs WHERE source_ip = $1",
            source_ip,
        )
        rows = await pool.fetch(
            "SELECT * FROM logs WHERE source_ip = $1 ORDER BY timestamp DESC LIMIT $2 OFFSET $3",
            source_ip,
            limit,
            offset,
        )
    else:
        total = await pool.fetchval("SELECT COUNT(*) FROM logs")
        rows = await pool.fetch(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT $1 OFFSET $2",
            limit,
            offset,
        )
    logs = [LogOut.model_validate(_record_to_dict(r)) for r in rows]
    return LogsListResponse(logs=logs, total=int(total or 0))


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    pool = await get_pool()
    total_alerts_24h = await pool.fetchval(
        """SELECT COUNT(*) FROM alerts WHERE timestamp >= NOW() - INTERVAL '24 hours'"""
    )
    critical_alerts_24h = await pool.fetchval(
        """SELECT COUNT(*) FROM alerts
           WHERE timestamp >= NOW() - INTERVAL '24 hours' AND severity >= 8"""
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
        top_source_ips=top_source_ips,
        alerts_by_hour=alerts_by_hour,
        severity_distribution=severity_distribution,
    )


@app.websocket("/api/ws/alerts")
async def websocket_alerts(websocket: WebSocket) -> None:
    await websocket.accept()
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT * FROM alerts WHERE acknowledged = false
           ORDER BY timestamp DESC LIMIT 10"""
    )
    initial = [AlertOut.model_validate(_record_to_dict(r)).model_dump(mode="json") for r in rows]
    await websocket.send_json({"type": "initial", "alerts": initial})
    ws_manager.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.unregister(websocket)
