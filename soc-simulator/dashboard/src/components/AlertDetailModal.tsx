import { useEffect, useState } from "react";

import { acknowledgeAlert, ApiError, fetchAlert } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { Alert } from "@/types/api";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

function SeverityGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(10, value));
  return (
    <div className="space-y-2">
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => {
          const filled = i < v;
          const tier =
            i < 3 ? "bg-zinc-600" : i < 6 ? "bg-amber-500" : i < 8 ? "bg-orange-500" : "bg-destructive";
          return (
            <div
              key={i}
              className={cn(
                "h-3 flex-1 rounded-sm",
                filled ? tier : "bg-border"
              )}
            />
          );
        })}
      </div>
      <p className="text-xs text-muted">
        Score {v}/10 — model-weighted anomaly severity
      </p>
    </div>
  );
}

function rawLogText(alert: Alert): string {
  if (alert.raw_context && typeof alert.raw_context === "object") {
    const log = alert.raw_context.log as Record<string, unknown> | undefined;
    if (log && typeof log.raw_message === "string") return log.raw_message;
    try {
      return JSON.stringify(alert.raw_context, null, 2);
    } catch {
      return String(alert.raw_context);
    }
  }
  return "No raw log attached.";
}

export function AlertDetailModal({
  alertId,
  open,
  onOpenChange,
  initialAlert,
  onAcknowledged,
}: {
  alertId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialAlert?: Alert | null;
  onAcknowledged?: (a: Alert) => void;
}) {
  const [alert, setAlert] = useState<Alert | null>(initialAlert ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acking, setAcking] = useState(false);

  useEffect(() => {
    if (!open || !alertId) {
      setError(null);
      return;
    }
    setAlert(initialAlert ?? null);
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchAlert(alertId)
      .then((a) => {
        if (!cancelled) setAlert(a);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof ApiError ? e.message : "Failed to load alert");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, alertId, initialAlert]);

  const display = alert;

  async function onAck() {
    if (!alertId) return;
    setAcking(true);
    setError(null);
    try {
      const a = await acknowledgeAlert(alertId);
      setAlert(a);
      onAcknowledged?.(a);
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Acknowledge failed");
    } finally {
      setAcking(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto border-border bg-card">
        <DialogHeader>
          <DialogTitle className="font-data text-lg text-primary">
            {display?.id ?? alertId ?? "Alert"}
          </DialogTitle>
          <DialogDescription className="font-data text-xs text-muted">
            {display?.timestamp
              ? format(new Date(display.timestamp), "yyyy-MM-dd HH:mm:ss.SSSxxx")
              : loading
                ? "Loading…"
                : ""}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        {display && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={display.severity} />
              {display.event_type && (
                <Badge variant="secondary">{display.event_type}</Badge>
              )}
              {display.source_ip && (
                <span className="font-data text-sm text-foreground">
                  {display.source_ip}
                </span>
              )}
            </div>

            <div>
              <p className="mb-2 text-xs font-medium uppercase text-muted">
                Severity
              </p>
              <SeverityGauge value={display.severity} />
            </div>

            <Separator />

            <div className="flex flex-wrap gap-2">
              {display.mitre_tactic && (
                <Badge className="border-primary/40 bg-primary/10 text-primary">
                  Tactic: {display.mitre_tactic}
                </Badge>
              )}
              {display.mitre_technique && (
                <Badge variant="outline" className="border-accent text-accent">
                  Technique: {display.mitre_technique}
                </Badge>
              )}
            </div>

            <div>
              <p className="mb-1 text-xs font-medium uppercase text-muted">
                AI explanation
              </p>
              <p className="text-sm leading-relaxed text-foreground/90">
                {display.explanation ?? "No explanation stored."}
              </p>
            </div>

            <div>
              <p className="mb-1 text-xs font-medium uppercase text-muted">
                Raw log / context
              </p>
              <pre className="max-h-48 overflow-auto rounded-md border border-border bg-background p-3 font-data text-xs text-muted-foreground">
                {rawLogText(display)}
              </pre>
            </div>

            <p className="text-xs text-muted">
              Anomaly score: {display.anomaly_score.toFixed(4)}
              {display.model_used ? ` · ${display.model_used}` : ""}
            </p>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
          <Button
            type="button"
            onClick={onAck}
            disabled={!display || display.acknowledged || acking}
          >
            {display?.acknowledged ? "Acknowledged" : acking ? "…" : "Acknowledge"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
