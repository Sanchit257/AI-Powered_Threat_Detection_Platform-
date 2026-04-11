import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { useAlertsStream } from "@/context/AlertsStreamContext";

/**
 * Shows bottom-right toasts when a new CRITICAL alert (severity >= 9) appears on the stream.
 */
export function CriticalToastBridge() {
  const { alerts, initialLoaded } = useAlertsStream();
  const boot = useRef(true);
  const seen = useRef(new Set<string>());

  useEffect(() => {
    if (!initialLoaded) return;
    if (boot.current) {
      for (const a of alerts) seen.current.add(a.id);
      boot.current = false;
      return;
    }
    for (const a of alerts) {
      if (a.severity >= 9 && !seen.current.has(a.id)) {
        seen.current.add(a.id);
        toast.error("CRITICAL ALERT", {
          description: `${a.event_type ?? "event"} · ${a.source_ip ?? "—"} · severity ${a.severity}`,
          duration: 12_000,
          position: "bottom-right",
        });
      }
    }
  }, [alerts, initialLoaded]);

  return null;
}
