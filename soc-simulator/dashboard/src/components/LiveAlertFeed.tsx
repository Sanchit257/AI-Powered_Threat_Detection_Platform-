import { format, parseISO } from "date-fns";

import { ScrollArea } from "@/components/ui/scroll-area";
import { SeverityBadge } from "@/components/SeverityBadge";
import type { Alert } from "@/types/api";

export function LiveAlertFeed({ alerts }: { alerts: Alert[] }) {
  const last10 = alerts.slice(0, 10);

  if (last10.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted">
        Waiting for live alerts…
      </p>
    );
  }

  return (
    <ScrollArea className="h-[280px] pr-3">
      <ul className="space-y-2">
        {last10.map((a) => (
          <li
            key={a.id}
            className="rounded-md border border-border bg-background/50 px-3 py-2"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-data text-xs text-muted">
                {(() => {
                  try {
                    return format(parseISO(a.timestamp), "HH:mm:ss");
                  } catch {
                    return a.timestamp;
                  }
                })()}
              </span>
              <SeverityBadge severity={a.severity} />
            </div>
            <p className="mt-1 truncate font-data text-sm text-foreground">
              {a.source_ip ?? "—"}{" "}
              <span className="text-muted">{a.event_type ?? ""}</span>
            </p>
            {a.explanation && (
              <p className="mt-1 line-clamp-2 text-xs text-muted">
                {a.explanation}
              </p>
            )}
          </li>
        ))}
      </ul>
    </ScrollArea>
  );
}
