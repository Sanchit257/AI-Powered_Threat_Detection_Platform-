import { cn } from "@/lib/utils";
import type { SeverityHeatmapResponse } from "@/types/api";

function cellClass(sev: number): string {
  if (sev <= 0) return "bg-zinc-800/80";
  if (sev <= 3) return "bg-zinc-600";
  if (sev <= 5) return "bg-amber-700/90";
  if (sev <= 7) return "bg-orange-600";
  if (sev <= 8) return "bg-red-700";
  return "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.45)]";
}

type Props = {
  data: SeverityHeatmapResponse | null;
  loading?: boolean;
};

export function SeverityHeatmap({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted">
        Loading heatmap…
      </div>
    );
  }
  if (!data || data.source_ips.length === 0) {
    return (
      <p className="text-sm text-muted">
        No alert volume in the last 24 hours — run the simulator or inject a demo
        attack.
      </p>
    );
  }

  const hours = data.hours?.length ? data.hours : Array.from({ length: 24 }, (_, i) => i);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-[1] bg-card py-1 pr-2 text-left font-normal text-muted">
              Source IP
            </th>
            {hours.map((h) => (
              <th
                key={h}
                className="min-w-[1.25rem] px-0.5 py-1 text-center font-data font-normal text-muted"
                title={`UTC hour ${h}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.source_ips.map((ip, ri) => (
            <tr key={ip}>
              <td
                className="sticky left-0 z-[1] max-w-[10rem] truncate bg-card py-1 pr-2 font-data text-foreground"
                title={ip}
              >
                {ip}
              </td>
              {(data.matrix[ri] ?? []).map((sev, hi) => (
                <td key={`${ip}-${hours[hi] ?? hi}`} className="p-0.5">
                  <div
                    className={cn(
                      "h-6 w-full min-w-[1rem] rounded-sm",
                      cellClass(sev)
                    )}
                    title={`${ip} · UTC ${hours[hi] ?? hi}:00 · max severity ${sev}`}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">
        Rows: top source IPs by volume. Cells: max alert severity in that hour
        (UTC).
      </p>
    </div>
  );
}
