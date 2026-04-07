import { format, parseISO } from "date-fns";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HourBucket } from "@/types/api";

export function AlertTimeline({ data }: { data: HourBucket[] }) {
  const chartData = data.map((d) => ({
    ...d,
    label: d.hour
      ? format(parseISO(d.hour), "MMM d HH:mm")
      : "",
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#8b949e", fontSize: 11 }}
            interval="preserveStartEnd"
            minTickGap={32}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#8b949e", fontSize: 11 }}
            width={32}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#161b22",
              border: "1px solid #30363d",
              borderRadius: "6px",
              color: "#e6edf3",
            }}
          />
          <Line
            type="monotone"
            dataKey="count"
            stroke="#58a6ff"
            strokeWidth={2}
            dot={{ fill: "#58a6ff", r: 3 }}
            activeDot={{ r: 5 }}
            name="Alerts"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
