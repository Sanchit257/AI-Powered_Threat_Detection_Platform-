import { createContext, useContext, type ReactNode } from "react";

import { useWebSocket } from "@/hooks/useWebSocket";
import type { Alert } from "@/types/api";

type AlertsStreamValue = {
  alerts: Alert[];
  connected: boolean;
  liveWsEvents: number;
  initialLoaded: boolean;
};

const AlertsStreamContext = createContext<AlertsStreamValue | null>(null);

export function AlertsStreamProvider({ children }: { children: ReactNode }) {
  const value = useWebSocket();
  return (
    <AlertsStreamContext.Provider value={value}>
      {children}
    </AlertsStreamContext.Provider>
  );
}

export function useAlertsStream(): AlertsStreamValue {
  const ctx = useContext(AlertsStreamContext);
  if (!ctx) {
    throw new Error("useAlertsStream must be used within AlertsStreamProvider");
  }
  return ctx;
}
