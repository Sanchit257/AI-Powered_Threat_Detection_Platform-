import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  ApiError,
  fetchSeverityHeatmap,
  fetchStats,
  injectDebugAttack,
} from "@/api/client";
import { AlertTimeline } from "@/components/AlertTimeline";
import { LiveAlertFeed } from "@/components/LiveAlertFeed";
import { SeverityHeatmap } from "@/components/SeverityHeatmap";
import { TopSourceIPs } from "@/components/TopSourceIPs";
import { Button } from "@/components/ui/button";
import { useAlertsStream } from "@/context/AlertsStreamContext";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { SeverityHeatmapResponse, StatsResponse } from "@/types/api";

export function Dashboard() {
  const { alerts, liveWsEvents } = useAlertsStream();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [heatmap, setHeatmap] = useState<SeverityHeatmapResponse | null>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [injecting, setInjecting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    function loadAggregates() {
      fetchStats()
        .then((s) => {
          if (!cancelled) {
            setStats(s);
            setError(null);
          }
        })
        .catch((e) => {
          if (!cancelled)
            setError(
              e instanceof ApiError ? e.message : "Failed to load stats"
            );
        });
      setHeatmapLoading(true);
      fetchSeverityHeatmap()
        .then((h) => {
          if (!cancelled) {
            setHeatmap(h);
            setHeatmapLoading(false);
          }
        })
        .catch(() => {
          if (!cancelled) setHeatmapLoading(false);
        });
    }
    loadAggregates();
    const t = setInterval(loadAggregates, 60_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (liveWsEvents === 0) return;
    const id = setTimeout(() => {
      fetchStats()
        .then((s) => setStats(s))
        .catch(() => {});
      setHeatmapLoading(true);
      fetchSeverityHeatmap()
        .then((h) => {
          setHeatmap(h);
          setHeatmapLoading(false);
        })
        .catch(() => setHeatmapLoading(false));
    }, 4_000);
    return () => clearTimeout(id);
  }, [liveWsEvents]);

  async function onSimulateAttack() {
    setInjecting(true);
    try {
      const r = await injectDebugAttack();
      toast.success("Simulate attack", {
        description: r.message ?? `Stream ${r.stream_id}`,
      });
    } catch (e) {
      toast.error("Inject failed", {
        description: e instanceof ApiError ? e.message : "Request failed",
      });
    } finally {
      setInjecting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Dashboard
          </h1>
          <p className="text-sm text-muted">
            Last 24 hours overview and live feed
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={injecting}
          onClick={() => void onSimulateAttack()}
          title="POST /api/debug/inject-attack — synthetic port_scan log"
        >
          {injecting ? "Injecting…" : "Simulate attack"}
        </Button>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-border bg-card">
          <CardHeader className="pb-2">
            <CardDescription>Total alerts (24h)</CardDescription>
            <CardTitle className="text-3xl tabular-nums text-foreground">
              {stats?.total_alerts_24h ?? "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-destructive/40 bg-destructive/5">
          <CardHeader className="pb-2">
            <CardDescription className="text-destructive">
              Critical (severity ≥ 8)
            </CardDescription>
            <CardTitle className="text-3xl tabular-nums text-destructive">
              {stats?.critical_alerts_24h ?? "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border bg-card">
          <CardHeader className="pb-2">
            <CardDescription>Active sources</CardDescription>
            <CardTitle className="text-3xl tabular-nums text-primary">
              {stats?.active_sources_24h ?? "—"}
            </CardTitle>
            <p className="text-xs text-muted">Unique source IPs (24h)</p>
          </CardHeader>
        </Card>
        <Card className="border-success/40 bg-success/5">
          <CardHeader className="pb-2">
            <CardDescription className="text-success">Detection</CardDescription>
            <CardTitle className="text-2xl font-bold tracking-wide text-success">
              LIVE
            </CardTitle>
            <p className="text-xs text-muted">Pipeline operational</p>
          </CardHeader>
        </Card>
      </div>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base">Severity heatmap</CardTitle>
          <CardDescription>
            Top sources × hour (UTC) — max severity per cell
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SeverityHeatmap data={heatmap} loading={heatmapLoading} />
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base">Alerts per hour</CardTitle>
          <CardDescription>Trailing 24 hours</CardDescription>
        </CardHeader>
        <CardContent>
          {stats ? (
            <AlertTimeline data={stats.alerts_by_hour} />
          ) : (
            <div className="flex h-72 items-center justify-center text-sm text-muted">
              Loading chart…
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base">Live alert feed</CardTitle>
            <CardDescription>Last 10 from WebSocket stream</CardDescription>
          </CardHeader>
          <CardContent>
            <LiveAlertFeed alerts={alerts} />
          </CardContent>
        </Card>
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base">Top source IPs</CardTitle>
            <CardDescription>By alert volume (24h)</CardDescription>
          </CardHeader>
          <CardContent>
            {stats ? (
              <TopSourceIPs data={stats.top_source_ips} />
            ) : (
              <div className="flex h-72 items-center justify-center text-sm text-muted">
                Loading…
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
