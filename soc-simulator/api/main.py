"""FastAPI backend placeholder with health and WebSocket stub."""

import os
from contextlib import asynccontextmanager

import psycopg
import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

_redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client
    _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    _redis_client.ping()
    yield
    if _redis_client:
        _redis_client.close()


app = FastAPI(title="SOC Simulator API", lifespan=lifespan)


@app.get("/")
def root():
    return {"service": "soc-simulator-api", "status": "ok"}


@app.get("/health")
def health():
    db_ok = False
    if DATABASE_URL:
        try:
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False
    redis_ok = False
    if _redis_client:
        try:
            _redis_client.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
    return {"status": "ok", "redis": redis_ok, "database": db_ok}


@app.websocket("/ws/")
async def websocket_stub(websocket: WebSocket):
    await websocket.accept()
    try:
        await websocket.send_json({"type": "hello", "message": "SOC API WebSocket placeholder"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        pass
