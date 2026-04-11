import { subHours } from "date-fns";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, fetchAlerts, getAlertsExportUrl } from "@/api/client";
import { AlertDetailModal } from "@/components/AlertDetailModal";
import { SeverityBadge } from "@/components/SeverityBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Alert } from "@/types/api";
import { format, parseISO } from "date-fns";
import { cn } from "@/lib/utils";

type SortKey =
  | "timestamp"
  | "source_ip"
  | "event_type"
  | "severity"
  | "mitre_tactic"
  | "acknowledged";
type SortDir = "asc" | "desc";

type AckFilter = "all" | "yes" | "no";

export function Alerts() {
  const [severityMin, setSeverityMin] = useState(0);
  const [ackFilter, setAckFilter] = useState<AckFilter>("all");
  const [rangeHours, setRangeHours] = useState<string>("24");
  const [rows, setRows] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const sinceIso = useMemo(() => {
    if (!rangeHours || rangeHours === "all") return undefined;
    const h = Number(rangeHours);
    if (Number.isNaN(h)) return undefined;
    return subHours(new Date(), h).toISOString();
  }, [rangeHours]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAlerts({
        limit: 500,
        offset: 0,
        severity_min: severityMin,
        acknowledged:
          ackFilter === "all" ? undefined : ackFilter === "yes",
        since: sinceIso,
      });
      setRows(res.alerts);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }, [severityMin, ackFilter, sinceIso]);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "timestamp":
          cmp =
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case "severity":
          cmp = a.severity - b.severity;
          break;
        case "acknowledged":
          cmp = Number(a.acknowledged) - Number(b.acknowledged);
          break;
        case "source_ip":
          cmp = (a.source_ip ?? "").localeCompare(b.source_ip ?? "");
          break;
        case "event_type":
          cmp = (a.event_type ?? "").localeCompare(b.event_type ?? "");
          break;
        case "mitre_tactic":
          cmp = (a.mitre_tactic ?? "").localeCompare(b.mitre_tactic ?? "");
          break;
        default:
          cmp = 0;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "timestamp" ? "desc" : "asc");
    }
  }

  function SortableHeader({
    col,
    children,
  }: {
    col: SortKey;
    children: ReactNode;
  }) {
    const active = sortKey === col;
    return (
      <TableHead>
        <button
          type="button"
          className="flex items-center gap-1 hover:text-foreground"
          onClick={() => toggleSort(col)}
        >
          {children}
          {active &&
            (sortDir === "asc" ? (
              <ArrowUp className="h-3 w-3" />
            ) : (
              <ArrowDown className="h-3 w-3" />
            ))}
        </button>
      </TableHead>
    );
  }

  const selectedAlert = rows.find((r) => r.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
          <p className="text-sm text-muted">
            Filter, sort, and drill into detections
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0 gap-2"
          onClick={() => {
            window.open(getAlertsExportUrl(), "_blank", "noopener,noreferrer");
          }}
        >
          <Download className="h-4 w-4" aria-hidden />
          Export CSV (24h)
        </Button>
      </div>

      <Card className="border-border bg-card">
        <CardHeader className="pb-4">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-6">
          <div className="grid gap-6 md:grid-cols-3">
            <div className="space-y-3">
              <Label>Min severity ({severityMin})</Label>
              <Slider
                value={[severityMin]}
                onValueChange={(v) => setSeverityMin(v[0] ?? 0)}
                min={0}
                max={10}
                step={1}
              />
            </div>
            <div className="space-y-2">
              <Label>Acknowledged</Label>
              <div className="flex flex-wrap gap-2">
                {(
                  [
                    ["all", "All"],
                    ["no", "Pending"],
                    ["yes", "Ack'd"],
                  ] as const
                ).map(([val, label]) => (
                  <Button
                    key={val}
                    type="button"
                    size="sm"
                    variant={ackFilter === val ? "default" : "outline"}
                    onClick={() => setAckFilter(val)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="range">Time range</Label>
              <select
                id="range"
                className={cn(
                  "flex h-9 w-full rounded-md border border-border bg-card px-3 text-sm text-foreground"
                )}
                value={rangeHours}
                onChange={(e) => setRangeHours(e.target.value)}
              >
                <option value="1">Last 1 hour</option>
                <option value="6">Last 6 hours</option>
                <option value="24">Last 24 hours</option>
                <option value="168">Last 7 days</option>
                <option value="all">All time</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <Card className="border-border bg-card">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHeader col="timestamp">Timestamp</SortableHeader>
                  <SortableHeader col="source_ip">Source IP</SortableHeader>
                  <SortableHeader col="event_type">Event</SortableHeader>
                  <SortableHeader col="severity">Severity</SortableHeader>
                  <SortableHeader col="mitre_tactic">MITRE tactic</SortableHeader>
                  <SortableHeader col="acknowledged">Ack</SortableHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-muted">
                      Loading…
                    </TableCell>
                  </TableRow>
                )}
                {!loading &&
                  sorted.map((a) => (
                    <TableRow
                      key={a.id}
                      className="cursor-pointer"
                      onClick={() => {
                        setSelectedId(a.id);
                        setModalOpen(true);
                      }}
                    >
                      <TableCell className="font-data text-xs text-muted">
                        {(() => {
                          try {
                            return format(
                              parseISO(a.timestamp),
                              "yyyy-MM-dd HH:mm:ss"
                            );
                          } catch {
                            return a.timestamp;
                          }
                        })()}
                      </TableCell>
                      <TableCell className="font-data text-sm">
                        {a.source_ip ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {a.event_type ?? "—"}
                      </TableCell>
                      <TableCell>
                        <SeverityBadge severity={a.severity} />
                      </TableCell>
                      <TableCell className="text-sm">
                        {a.mitre_tactic ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {a.acknowledged ? "Yes" : "No"}
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <AlertDetailModal
        alertId={selectedId}
        open={modalOpen}
        onOpenChange={setModalOpen}
        initialAlert={selectedAlert}
        onAcknowledged={() => void load()}
      />
    </div>
  );
}
