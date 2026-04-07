import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TopSourceIp } from "@/types/api";

export function TopSourceIPs({ data }: { data: TopSourceIp[] }) {
  if (!data.length) {
    return (
      <p className="flex h-56 items-center justify-center text-sm text-muted">
        No source IP data (24h)
      </p>
    );
  }

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#30363d" horizontal={false} />
          <XAxis type="number" tick={{ fill: "#8b949e", fontSize: 11 }} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="ip"
            width={112}
            tick={{ fill: "#58a6ff", fontSize: 11, fontFamily: "var(--font-mono)" }}
          />
          <Tooltip
            cursor={{ fill: "#21262d" }}
            contentStyle={{
              backgroundColor: "#161b22",
              border: "1px solid #30363d",
              borderRadius: "6px",
              color: "#e6edf3",
            }}
          />
          <Bar dataKey="count" fill="#d29922" radius={[0, 4, 4, 0]} name="Alerts" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
