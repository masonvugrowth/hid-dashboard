/**
 * OCCHeatmap — shows daily OCC% as a calendar heatmap.
 * Props:
 *   data   array of { date: "YYYY-MM-DD", occ_pct: 0.0–1.0 }
 *   title  string
 */
import { useMemo } from "react";

function occColor(pct) {
  if (pct == null) return "#f3f4f6";
  if (pct >= 0.9)  return "#16a34a";
  if (pct >= 0.75) return "#4ade80";
  if (pct >= 0.6)  return "#fbbf24";
  if (pct >= 0.4)  return "#fb923c";
  return "#f87171";
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function OCCHeatmap({ data = [], title = "OCC Heatmap" }) {
  const byDate = useMemo(() => {
    const map = {};
    for (const d of data) map[d.date] = d.occ_pct;
    return map;
  }, [data]);

  // Build weeks from data date range
  const weeks = useMemo(() => {
    if (data.length === 0) return [];
    const dates = data.map((d) => d.date).sort();
    const start = new Date(dates[0]);
    const end   = new Date(dates[dates.length - 1]);

    // Align start to Monday
    const dayOfWeek = (start.getDay() + 6) % 7; // 0=Mon
    start.setDate(start.getDate() - dayOfWeek);

    const weeks = [];
    let week = [];
    const cur = new Date(start);
    while (cur <= end) {
      const iso = cur.toISOString().slice(0, 10);
      week.push({ date: iso, occ: byDate[iso] ?? null });
      if (week.length === 7) {
        weeks.push(week);
        week = [];
      }
      cur.setDate(cur.getDate() + 1);
    }
    if (week.length > 0) weeks.push(week);
    return weeks;
  }, [data, byDate]);

  if (weeks.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <p className="text-sm font-semibold text-gray-700 mb-2">{title}</p>
        <p className="text-sm text-gray-400">No data</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm overflow-x-auto">
      <p className="text-sm font-semibold text-gray-700 mb-3">{title}</p>
      <div className="flex gap-1">
        {/* Day labels */}
        <div className="flex flex-col gap-1 mr-1 justify-around">
          {DAYS.map((d) => (
            <span key={d} className="text-xs text-gray-400 w-7 text-right">{d}</span>
          ))}
        </div>
        {/* Weeks */}
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1">
            {week.map(({ date, occ }) => (
              <div
                key={date}
                title={`${date}: ${occ != null ? (occ * 100).toFixed(1) + "%" : "—"}`}
                className="w-4 h-4 rounded-sm cursor-default"
                style={{ backgroundColor: occColor(occ) }}
              />
            ))}
          </div>
        ))}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-2 mt-3 text-xs text-gray-400">
        <span>Low</span>
        {[0.3, 0.5, 0.65, 0.8, 0.95].map((v) => (
          <div key={v} className="w-3 h-3 rounded-sm" style={{ backgroundColor: occColor(v) }} />
        ))}
        <span>High</span>
      </div>
    </div>
  );
}
