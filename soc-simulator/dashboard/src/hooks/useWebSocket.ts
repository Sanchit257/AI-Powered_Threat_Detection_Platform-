import { useCallback, useEffect, useRef, useState } from "react";

import { BASE_URL } from "@/api/client";
import type { Alert, WsInitialMessage } from "@/types/api";

const MAX_ALERTS = 200;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

function getField(
  obj: Record<string, unknown>,
  snake: string,
  camel: string
): unknown {
  if (
    snake in obj &&
    obj[snake] !== undefined &&
    obj[snake] !== null
  ) {
    return obj[snake];
  }
  if (
    camel in obj &&
    obj[camel] !== undefined &&
    obj[camel] !== null
  ) {
    return obj[camel];
  }
  return undefined;
}

function toNum(v: unknown, fallback: number): number {
  if (typeof v === "number" && !Number.isNaN(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (!Number.isNaN(n)) return n;
  }
  return fallback;
}

/** Normalize WebSocket alert payloads (camelCase from API) to internal Alert shape. */
function normalizeWsAlertPayload(o: Record<string, unknown>): Alert | null {
  const idVal = getField(o, "id", "id");
  const id = idVal != null ? String(idVal) : "";

  const tsVal = getField(o, "timestamp", "timestamp");
  const timestamp =
    tsVal != null ? String(tsVal) : new Date().toISOString();

  const severity = Math.max(
    0,
    Math.min(10, Math.round(toNum(getField(o, "severity", "severity"), 0)))
  );
  const anomaly_score = toNum(
    getField(o, "anomaly_score", "anomalyScore"),
    severity
  );

  const strOrNull = (v: unknown): string | null =>
    v == null || v === "" ? null : String(v);

  const ack = getField(o, "acknowledged", "acknowledged");
  const acknowledged =
    ack === true || ack === "true" || ack === 1 || ack === "1";

  const out: Alert = {
    id: id || crypto.randomUUID(),
    timestamp,
    severity,
    anomaly_score,
    model_used: strOrNull(getField(o, "model_used", "modelUsed")),
    event_type: strOrNull(getField(o, "event_type", "eventType")),
    source_ip: strOrNull(getField(o, "source_ip", "sourceIp")),
    mitre_tactic: strOrNull(getField(o, "mitre_tactic", "mitreTactic")),
    mitre_technique: strOrNull(
      getField(o, "mitre_technique", "mitreTechnique")
    ),
    technique_id: strOrNull(getField(o, "technique_id", "techniqueId")),
    confidence: (() => {
      const c = getField(o, "confidence", "confidence");
      if (c === undefined || c === null) return null;
      return toNum(c, 0);
    })(),
    recommended_action: strOrNull(
      getField(o, "recommended_action", "recommendedAction")
    ),
    explanation: strOrNull(getField(o, "explanation", "explanation")),
    raw_context:
      (getField(o, "raw_context", "rawContext") as Record<
        string,
        unknown
      > | null) ?? null,
    acknowledged,
    created_at: strOrNull(getField(o, "created_at", "createdAt")),
  };

  if (!id && !getField(o, "event_type", "eventType") && severity === 0) {
    return null;
  }
  return out;
}

function getWsBaseUrl(): string {
  const override = import.meta.env.VITE_WS_URL?.trim();
  if (override) return override.replace(/\/$/, "");

  const raw = BASE_URL.trim().replace(/\/$/, "");
  const u = new URL(raw.includes("://") ? raw : `http://${raw}`);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  return u.toString().replace(/\/$/, "");
}

function parseMessage(raw: string): Alert[] {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!data || typeof data !== "object") return [];

  const o = data as Record<string, unknown>;
  if (o.type === "initial" && Array.isArray(o.alerts)) {
    const msg = data as WsInitialMessage;
    const normalized: Alert[] = [];
    for (const item of msg.alerts) {
      if (item && typeof item === "object") {
        const a = normalizeWsAlertPayload(
          item as unknown as Record<string, unknown>
        );
        if (a) normalized.push(a);
      }
    }
    return normalized.slice(0, MAX_ALERTS);
  }

  const normalizedOne = normalizeWsAlertPayload(o);
  if (normalizedOne) return [normalizedOne];

  return [];
}

function mergePrepend(prev: Alert[], incoming: Alert[]): Alert[] {
  const seen = new Set<string>();
  const out: Alert[] = [];
  for (const a of [...incoming, ...prev]) {
    if (seen.has(a.id)) continue;
    seen.add(a.id);
    out.push(a);
    if (out.length >= MAX_ALERTS) break;
  }
  return out;
}

export function useWebSocket(): { alerts: Alert[]; connected: boolean } {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [connected, setConnected] = useState(false);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const stoppedRef = useRef(false);

  const connect = useCallback(() => {
    if (stoppedRef.current) return;

    const url = `${getWsBaseUrl()}/ws/alerts`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (stoppedRef.current) return;
      backoffRef.current = INITIAL_BACKOFF_MS;
      setConnected(true);
    };

    ws.onmessage = (ev) => {
      if (stoppedRef.current) return;
      const text = typeof ev.data === "string" ? ev.data : "";
      let data: unknown;
      try {
        data = JSON.parse(text);
      } catch {
        return;
      }
      if (!data || typeof data !== "object") return;
      const o = data as Record<string, unknown>;
      if (o.type === "initial" && Array.isArray(o.alerts)) {
        setAlerts(parseMessage(text));
        return;
      }
      const newOnes = parseMessage(text);
      if (newOnes.length === 0) return;
      setAlerts((prev) => mergePrepend(prev, newOnes));
    };

    ws.onerror = () => {
      // onclose will handle reconnect
    };

    ws.onclose = () => {
      wsRef.current = null;
      if (stoppedRef.current) return;
      setConnected(false);
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, []);

  useEffect(() => {
    stoppedRef.current = false;
    connect();
    return () => {
      stoppedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  return { alerts, connected };
}
