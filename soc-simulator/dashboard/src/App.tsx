import { Navigate, Route, Routes } from "react-router-dom";

import { AlertsStreamProvider } from "@/context/AlertsStreamContext";
import { Layout } from "@/components/Layout";
import { Alerts } from "@/pages/Alerts";
import { Dashboard } from "@/pages/Dashboard";
import { Logs } from "@/pages/Logs";

export default function App() {
  return (
    <AlertsStreamProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="logs" element={<Logs />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AlertsStreamProvider>
  );
}
