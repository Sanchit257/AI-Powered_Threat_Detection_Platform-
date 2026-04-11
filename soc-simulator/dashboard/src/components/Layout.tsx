import { Activity, LayoutDashboard, ScrollText, Shield } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useAlertsStream } from "@/context/AlertsStreamContext";
import { cn } from "@/lib/utils";
const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-primary/15 text-primary"
      : "text-muted hover:bg-card hover:text-foreground"
  );

export function Layout() {
  const { connected, liveWsEvents } = useAlertsStream();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card/50">
        <div className="flex items-center gap-2 border-b border-border px-4 py-4">
          <Shield className="h-8 w-8 text-primary" aria-hidden />
          <div>
            <div className="font-semibold tracking-tight text-foreground">
              SOC-AI
            </div>
            <div className="text-xs text-muted">Threat Detection</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          <NavLink to="/" end className={navClass}>
            <LayoutDashboard className="h-4 w-4" />
            Dashboard
          </NavLink>
          <NavLink to="/alerts" className={navClass}>
            <Activity className="h-4 w-4" />
            Alerts
          </NavLink>
          <NavLink to="/logs" className={navClass}>
            <ScrollText className="h-4 w-4" />
            Logs
          </NavLink>
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-border bg-card/30 px-4">
          <div
            className="font-data text-sm tabular-nums text-primary"
            title="WebSocket messages received (live counter)"
          >
            Live events:{" "}
            <span className="text-lg font-semibold text-foreground">
              {liveWsEvents.toLocaleString()}
            </span>
          </div>
          <span
            className="flex items-center gap-2 text-xs text-muted"
            title={connected ? "Live stream connected" : "Reconnecting…"}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                connected ? "bg-success shadow-[0_0_8px_var(--color-success)]" : "bg-destructive animate-pulse"
              )}
            />
            {connected ? "Live" : "Reconnecting"}
          </span>
        </header>
        <main className="min-h-0 flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
