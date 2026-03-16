/**
 * Weekly Report — Phase 3
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";

function fmt(val, currency) {
  if (val == null) return "—";
  const sym = CURRENCY_SYMBOLS[currency] || "";
  if (Math.abs(val) >= 1_000_000_000) return sym + (val / 1_000_000_000).toFixed(1) + "B";
  if (Math.abs(val) >= 1_000_000) return sym + (val / 1_000_000).toFixed(1) + "M";
  if (Math.abs(val) >= 1_000) return sym + (val / 1_000).toFixed(0) + "K";
  return sym + Math.round(val).toLocaleString();
}

function WoWBadge({ pct }) {
  if (pct == null) return <span className="text-gray-400">—</span>;
  const cls = pct >= 0 ? "text-green-600" : "text-red-500";
  return <span className={cls + " font-semibold text-sm"}>{pct >= 0 ? "+" : ""}{pct}%</span>;
}

function AchievementBar({ pct }) {
  if (pct == null) return null;
  const color = pct >= 100 ? "bg-green-500" : pct >= 80 ? "bg-yellow-400" : "bg-red-400";
  const width = Math.min(pct, 100);
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
        <div className={color + " h-1.5 rounded-full"} style={{ width: width + "%" }} />
      </div>
      <span className="text-xs font-medium text-gray-600 w-10 text-right">{Math.round(pct)}%</span>
    </div>
  );
}

export default function Report() {
  const { selected, isAll } = useBranch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (!isAll && selected) params.set("branch_id", selected);
    axios.get("/api/report/weekly?" + params)
      .then(r => setData(r.data.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [selected, isAll]);

  if (loading) return <div className="p-8 text-center text-gray-400 animate-pulse">Generating report…</div>;
  if (!data) return <div className="p-8 text-center text-red-400">Failed to generate report.</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Weekly Report</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            Week {data.period.week_start} → {data.period.week_end}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="px-3 py-1.5 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50">Refresh</button>
          <button onClick={() => window.print()} className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">Print / PDF</button>
        </div>
      </div>

      {data.branches.length === 0 && (
        <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No branch data available.</div>
      )}

      {data.branches.map(b => (
        <div key={b.branch_id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-800">{b.branch_name}</h2>
              <p className="text-xs text-gray-400 mt-0.5">{b.currency}</p>
            </div>
            {b.achievement_pct != null && (
              <div className="text-right">
                <p className="text-xs text-gray-400">KPI Achievement</p>
                <p className={"text-xl font-bold " + (b.achievement_pct >= 100 ? "text-green-600" : b.achievement_pct >= 80 ? "text-yellow-600" : "text-red-500")}>
                  {Math.round(b.achievement_pct)}%
                </p>
              </div>
            )}
          </div>

          <div className="p-5 space-y-5">
            {/* Revenue MTD */}
            <div>
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-2">Revenue MTD</p>
              <div className="flex items-end gap-3">
                <p className="text-2xl font-bold text-gray-800">{fmt(b.mtd_revenue, b.currency)}</p>
                {b.target_revenue != null && (
                  <p className="text-sm text-gray-400 pb-1">/ {fmt(b.target_revenue, b.currency)} target</p>
                )}
              </div>
              <AchievementBar pct={b.achievement_pct} />
            </div>

            {/* WoW bookings */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">This Week Bookings</p>
                <p className="text-xl font-bold text-gray-800">{b.this_week_bookings}</p>
                <div className="flex items-center gap-2 mt-1">
                  <WoWBadge pct={b.wow_booking_pct} />
                  <span className="text-xs text-gray-400">vs last week ({b.last_week_bookings})</span>
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">This Week Revenue</p>
                <p className="text-xl font-bold text-gray-800">{fmt(b.this_week_revenue, b.currency)}</p>
                <div className="flex items-center gap-2 mt-1">
                  <WoWBadge pct={b.wow_revenue_pct} />
                  <span className="text-xs text-gray-400">vs last week</span>
                </div>
              </div>
            </div>

            {/* Top countries */}
            {b.top_countries && b.top_countries.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-2">Top Countries This Week</p>
                <div className="flex gap-3">
                  {b.top_countries.map((c, i) => (
                    <div key={c.country_code || i} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2">
                      <span className="text-xs font-bold text-gray-400">#{i + 1}</span>
                      <span className="text-sm font-medium text-gray-700">{c.country || c.country_code}</span>
                      <span className="text-xs text-gray-500">({c.bookings})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ))}

      <p className="text-xs text-gray-400 text-center">Generated {new Date(data.generated_at).toLocaleString()}</p>
    </div>
  );
}
