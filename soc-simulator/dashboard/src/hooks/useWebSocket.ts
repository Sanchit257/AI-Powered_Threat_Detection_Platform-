import { useCallback, useEffect, useRef, useState } from "react";

import { BASE_URL } from "@/api/client";
import type { Alert, WsInitialMessage } from "@/types/api";

const MAX_ALERTS = 200;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

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
    return msg.alerts.slice(0, MAX_ALERTS);
  }

  if (typeof o.id === "string" && typeof o.timestamp === "string") {
    return [data as Alert];
  }

  const id = crypto.randomUUID();
  const timestamp = new Date().toISOString();
  const partial: Alert = {
    id,
    timestamp,
    severity: Math.max(0, Math.min(10, Number(o.severity ?? 0))),
    anomaly_score: Number(o.anomaly_score ?? o.severity ?? 0),
    event_type: typeof o.event_type === "string" ? o.event_type : null,
    source_ip: typeof o.source_ip === "string" ? o.source_ip : null,
    mitre_tactic: typeof o.mitre_tactic === "string" ? o.mitre_tactic : null,
    mitre_technique: typeof o.mitre_technique === "string" ? o.mitre_technique : null,
    explanation: typeof o.explanation === "string" ? o.explanation : null,
    acknowledged: false,
    raw_context: null,
  };
  return [partial];
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
