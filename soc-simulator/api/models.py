"""Pydantic models aligned with Postgres alerts/logs tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    log_id: Optional[UUID] = None
    timestamp: datetime
    severity: int = Field(ge=0, le=10)
    anomaly_score: float
    model_used: Optional[str] = None
    event_type: Optional[str] = None
    source_ip: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique: Optional[str] = None
    technique_id: Optional[str] = None
    confidence: Optional[float] = None
    recommended_action: Optional[str] = None
    explanation: Optional[str] = None
    raw_context: Optional[dict[str, Any]] = None
    acknowledged: bool = False
    created_at: Optional[datetime] = None


class AlertsListResponse(BaseModel):
    alerts: list[AlertOut]
    total: int


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
    source_ip: str
    destination_ip: Optional[str] = None
    destination_port: Optional[int] = None
    protocol: Optional[str] = None
    event_type: str
    bytes_transferred: Optional[int] = 0
    username: Optional[str] = None
    raw_message: str
    created_at: Optional[datetime] = None


class LogsListResponse(BaseModel):
    logs: list[LogOut]
    total: int


class TopSourceIp(BaseModel):
    ip: str
    count: int


class HourBucket(BaseModel):
    hour: str
    count: int


class SeverityBucket(BaseModel):
    severity: int
    count: int


class StatsResponse(BaseModel):
    total_alerts_24h: int
    critical_alerts_24h: int
    active_sources_24h: int
    top_source_ips: list[TopSourceIp]
    alerts_by_hour: list[HourBucket]
    severity_distribution: list[SeverityBucket]


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class SeverityHeatmapResponse(BaseModel):
    """Top 10 source IPs (rows) x hour UTC 0-23 (cols); cell = max severity in that bucket."""

    source_ips: list[str]
    hours: list[int] = Field(default_factory=lambda: list(range(24)))
    matrix: list[list[int]]


class InjectAttackResponse(BaseModel):
    ok: bool
    stream_id: str
    message: str = "Attack log injected to logs:raw"
