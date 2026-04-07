import { format, parseISO } from "date-fns";
import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchLogs } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Log } from "@/types/api";

const PAGE_SIZE = 50;
const RAW_MAX = 120;

export function Logs() {
  const [logs, setLogs] = useState<Log[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sourceIp, setSourceIp] = useState("");
  const [sourceIpApplied, setSourceIpApplied] = useState("");
  const [search, setSearch] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchLogs({
        limit: PAGE_SIZE,
        offset,
        source_ip: sourceIpApplied || undefined,
        q: searchApplied || undefined,
      });
      setLogs(res.logs);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }, [offset, sourceIpApplied, searchApplied]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const t = setTimeout(() => setSearchApplied(search.trim()), 350);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [searchApplied]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function destDisplay(log: Log) {
    const ip = log.destination_ip ?? "—";
    const port =
      log.destination_port != null ? `:${log.destination_port}` : "";
    return `${ip}${port}`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Logs</h1>
        <p className="text-sm text-muted">
          Raw events from the datastore
        </p>
      </div>

      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base">Search & filter</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:flex-wrap">
          <div className="min-w-[200px] flex-1 space-y-2">
            <Label htmlFor="q">Search message</Label>
            <Input
              id="q"
              placeholder="Substring match…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </div>
          <div className="min-w-[180px] space-y-2">
            <Label htmlFor="sip">Source IP</Label>
            <Input
              id="sip"
              className="font-data"
              placeholder="e.g. 10.0.0.1"
              value={sourceIp}
              onChange={(e) => setSourceIp(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  setSourceIpApplied(sourceIp.trim());
                  setOffset(0);
                }
              }}
            />
          </div>
          <div className="flex items-end gap-2">
            <Button
              type="button"
              onClick={() => {
                setSourceIpApplied(sourceIp.trim());
                setOffset(0);
              }}
            >
              Apply IP filter
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setSourceIp("");
                setSourceIpApplied("");
                setOffset(0);
              }}
            >
              Clear IP
            </Button>
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
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Source IP</TableHead>
                  <TableHead>Dest IP:port</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Bytes</TableHead>
                  <TableHead>Raw message</TableHead>
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
                  logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap font-data text-xs text-muted">
                        {(() => {
                          try {
                            return format(
                              parseISO(log.timestamp),
                              "yyyy-MM-dd HH:mm:ss"
                            );
                          } catch {
                            return log.timestamp;
                          }
                        })()}
                      </TableCell>
                      <TableCell className="font-data text-sm">
                        {log.source_ip}
                      </TableCell>
                      <TableCell className="font-data text-sm">
                        {destDisplay(log)}
                      </TableCell>
                      <TableCell className="text-sm">{log.event_type}</TableCell>
                      <TableCell className="font-data text-sm tabular-nums">
                        {log.bytes_transferred ?? "—"}
                      </TableCell>
                      <TableCell
                        className="max-w-md truncate font-data text-xs text-muted"
                        title={log.raw_message}
                      >
                        {log.raw_message.length > RAW_MAX
                          ? `${log.raw_message.slice(0, RAW_MAX)}…`
                          : log.raw_message}
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border p-4">
            <p className="text-xs text-muted">
              {total.toLocaleString()} total · Page {page} / {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={offset === 0 || loading}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= total || loading}
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
