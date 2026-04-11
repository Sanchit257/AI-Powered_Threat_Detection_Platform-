import type {
  Alert,
  AlertsListResponse,
  InjectAttackResponse,
  LogsListResponse,
  SeverityHeatmapResponse,
  StatsResponse,
} from "@/types/api";

export const BASE_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new ApiError(
      `${res.status} ${res.statusText}`,
      res.status,
      text.slice(0, 500)
    );
  }
  if (!text) return {} as T;
  return JSON.parse(text) as T;
}

export interface FetchAlertsParams {
  limit?: number;
  offset?: number;
  severity_min?: number;
  acknowledged?: boolean;
  since?: string;
}

export function fetchAlerts(
  params: FetchAlertsParams = {}
): Promise<AlertsListResponse> {
  const search = new URLSearchParams();
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.offset != null) search.set("offset", String(params.offset));
  if (params.severity_min != null) {
    search.set("severity_min", String(params.severity_min));
  }
  if (params.acknowledged !== undefined) {
    search.set("acknowledged", String(params.acknowledged));
  }
  if (params.since) search.set("since", params.since);
  const q = search.toString();
  const path = q ? `/alerts?${q}` : "/alerts";
  return fetch(`${BASE_URL}${path}`).then((r) =>
    parseJson<AlertsListResponse>(r)
  );
}

export function fetchAlert(id: string): Promise<Alert> {
  return fetch(`${BASE_URL}/alerts/${encodeURIComponent(id)}`).then((r) =>
    parseJson<Alert>(r)
  );
}

export function acknowledgeAlert(id: string): Promise<Alert> {
  return fetch(
    `${BASE_URL}/alerts/${encodeURIComponent(id)}/acknowledge`,
    { method: "PATCH" }
  ).then((r) => parseJson<Alert>(r));
}

export function fetchStats(): Promise<StatsResponse> {
  return fetch(`${BASE_URL}/stats`).then((r) =>
    parseJson<StatsResponse>(r)
  );
}

export function fetchSeverityHeatmap(): Promise<SeverityHeatmapResponse> {
  return fetch(`${BASE_URL}/stats/heatmap`).then((r) =>
    parseJson<SeverityHeatmapResponse>(r)
  );
}

/** Demo: enqueue a synthetic high-signal log on `logs:raw` (processed by ml_engine). */
export function injectDebugAttack(): Promise<InjectAttackResponse> {
  return fetch(`${BASE_URL}/debug/inject-attack`, { method: "POST" }).then(
    (r) => parseJson<InjectAttackResponse>(r)
  );
}

/** Absolute URL for CSV download (last 24h alerts). Open or assign to `window.location`. */
export function getAlertsExportUrl(): string {
  return `${BASE_URL.replace(/\/$/, "")}/alerts/export`;
}

export interface FetchLogsParams {
  limit?: number;
  offset?: number;
  source_ip?: string;
  q?: string;
}

export function fetchLogs(params: FetchLogsParams = {}): Promise<LogsListResponse> {
  const search = new URLSearchParams();
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.offset != null) search.set("offset", String(params.offset));
  if (params.source_ip) search.set("source_ip", params.source_ip);
  if (params.q) search.set("q", params.q);
  const q = search.toString();
  const path = q ? `/logs?${q}` : "/logs";
  return fetch(`${BASE_URL}${path}`).then((r) =>
    parseJson<LogsListResponse>(r)
  );
}
