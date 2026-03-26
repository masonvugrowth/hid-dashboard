/**
 * TrendChart — reusable line/bar chart using Recharts.
 * Props:
 *   data         array of objects
 *   xKey         string  (key for x axis)
 *   lines        array of { key, color, name }
 *   bars         array of { key, color, name }  (optional, stacked)
 *   title        string
 *   height       number (default 260)
 *   formatY      function (optional)
 *   formatTooltip function (optional)
 */
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

const DEFAULT_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#3b82f6"];

export default function TrendChart({
  data = [],
  xKey = "date",
  lines = [],
  bars = [],
  title,
  height = 260,
  formatY,
  formatTooltip,
}) {
  const yTickFmt = formatY || ((v) => new Intl.NumberFormat("en").format(Math.round(v)));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      {title && <p className="text-sm font-semibold text-gray-700 mb-3">{title}</p>}
      {data.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
          No data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tickFormatter={yTickFmt}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              formatter={formatTooltip || ((v, name) => [new Intl.NumberFormat("en").format(Math.round(v)), name])}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e5e7eb" }}
            />
            {(lines.length > 0 || bars.length > 0) && (
              <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
            )}
            {bars.map(({ key, color, name }, i) => (
              <Bar
                key={key}
                dataKey={key}
                name={name || key}
                fill={color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
                radius={[3, 3, 0, 0]}
                maxBarSize={40}
              />
            ))}
            {lines.map(({ key, color, name }, i) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={name || key}
                stroke={color || DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
