/** Mirrors FastAPI Pydantic models (JSON). */

export interface Alert {
  id: string;
  log_id?: string | null;
  timestamp: string;
  severity: number;
  anomaly_score: number;
  model_used?: string | null;
  event_type?: string | null;
  source_ip?: string | null;
  mitre_tactic?: string | null;
  mitre_technique?: string | null;
  explanation?: string | null;
  raw_context?: Record<string, unknown> | null;
  acknowledged: boolean;
  created_at?: string | null;
}

/** Partial payloads from Redis / ml_engine publish. */
export type LiveAlertPayload = Partial<Alert> &
  Pick<Alert, "severity" | "anomaly_score"> & {
    source_ip?: string | null;
    event_type?: string | null;
    explanation?: string | null;
    mitre_tactic?: string | null;
    mitre_technique?: string | null;
  };

export interface AlertsListResponse {
  alerts: Alert[];
  total: number;
}

export interface Log {
  id: string;
  timestamp: string;
  source_ip: string;
  destination_ip?: string | null;
  destination_port?: number | null;
  protocol?: string | null;
  event_type: string;
  bytes_transferred?: number | null;
  username?: string | null;
  raw_message: string;
  created_at?: string | null;
}

export interface LogsListResponse {
  logs: Log[];
  total: number;
}

export interface TopSourceIp {
  ip: string;
  count: number;
}

export interface HourBucket {
  hour: string;
  count: number;
}

export interface SeverityBucket {
  severity: number;
  count: number;
}

export interface StatsResponse {
  total_alerts_24h: number;
  critical_alerts_24h: number;
  active_sources_24h: number;
  top_source_ips: TopSourceIp[];
  alerts_by_hour: HourBucket[];
  severity_distribution: SeverityBucket[];
}

export interface WsInitialMessage {
  type: "initial";
  alerts: Alert[];
}
