/**
 * Monthly Brief — OCC/Revenue/ADR/RevPAR + country breakdown multi-year
 * - Single branch: trend charts
 * - All branches: per-branch monthly table (separate currencies, no cross-mixing)
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import TrendChart from "../components/TrendChart";
import { useBranch } from "../context/BranchContext";

const MONTH_LABELS = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmt(val, currency) {
  if (val == null || val === 0) return "—";
  const sym = { VND: "₫", TWD: "NT$", JPY: "¥" }[currency] || (currency + " ");
  if (Math.abs(val) >= 1_000_000_000) return `${sym}${(val / 1e9).toFixed(1)}B`;
  if (Math.abs(val) >= 1_000_000)     return `${sym}${(val / 1e6).toFixed(1)}M`;
  if (Math.abs(val) >= 1_000)         return `${sym}${(val / 1e3).toFixed(0)}K`;
  return `${sym}${Math.round(val).toLocaleString()}`;
}

function pct(val) {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

export default function PerformanceMonthly() {
  const { branches, selected, isAll } = useBranch();
  const now = new Date();
  const [yearFrom, setYearFrom] = useState(now.getFullYear() - 1);
  const [yearTo,   setYearTo]   = useState(now.getFullYear());
  const [monthly,  setMonthly]  = useState([]);
  const [loading,  setLoading]  = useState(true);

  const branchMap = useMemo(() => {
    const m = {};
    for (const b of branches) m[b.id] = b;
    return m;
  }, [branches]);

  useEffect(() => {
    setLoading(true);
    const bParam = !isAll && selected ? `&branch_id=${selected}` : "";
    axios.get(`/api/metrics/monthly?year_from=${yearFrom}&year_to=${yearTo}${bParam}`)
      .then((r) => setMonthly(r.data.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [yearFrom, yearTo, selected, isAll]);

  // ── Single branch: monthly trend ───────────────────────────────────────────
  const chartData = useMemo(() => {
    if (isAll) return [];
    return [...monthly]
      .sort((a, b) => a.year !== b.year ? a.year - b.year : a.month - b.month)
      .map((m) => ({
        label:   `${MONTH_LABELS[m.month]} ${m.year}`,
        revenue: Math.round(m.revenue_native),
        occ_pct: +((m.avg_occ_pct || 0) * 100).toFixed(1),
        adr:     +(m.avg_adr_native || 0).toFixed(0),
        revpar:  +(m.avg_revpar_native || 0).toFixed(0),
      }));
  }, [monthly, isAll]);

  // ── All branches: group by branch → list of months ─────────────────────────
  const byBranch = useMemo(() => {
    if (!isAll) return {};
    const map = {};
    for (const m of monthly) {
      if (!map[m.branch_id]) map[m.branch_id] = [];
      map[m.branch_id].push(m);
    }
    // Sort months within each branch
    for (const rows of Object.values(map)) {
      rows.sort((a, b) => a.year !== b.year ? a.year - b.year : a.month - b.month);
    }
    return map;
  }, [monthly, isAll]);

  // Country data — last 3 months (single branch only)
  const recentMonths = useMemo(() => {
    if (isAll) return [];
    return [...monthly]
      .sort((a, b) => b.year - a.year || b.month - a.month)
      .slice(0, 3);
  }, [monthly, isAll]);

  const yearPicker = (
    <div className="flex gap-2 text-sm">
      <select className="border border-gray-200 rounded-lg px-3 py-1.5" value={yearFrom}
        onChange={(e) => setYearFrom(+e.target.value)}>
        {[2022,2023,2024,2025,2026].map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
      <span className="text-gray-400 self-center">–</span>
      <select className="border border-gray-200 rounded-lg px-3 py-1.5" value={yearTo}
        onChange={(e) => setYearTo(+e.target.value)}>
        {[2022,2023,2024,2025,2026].map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">Monthly Brief</h1>
          <p className="text-sm text-gray-500">Multi-year performance + country breakdown</p>
        </div>
        {yearPicker}
      </div>

      {loading ? <div className="text-gray-400 animate-pulse">Loading…</div> : (
        <>
          {/* ── Single branch: charts ── */}
          {!isAll && (
            <>
              <TrendChart
                title="Monthly Revenue"
                data={chartData}
                xKey="label"
                bars={[{ key: "revenue", name: "Revenue", color: "#6366f1" }]}
                height={240}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <TrendChart
                  title="Avg OCC%"
                  data={chartData}
                  xKey="label"
                  lines={[{ key: "occ_pct", name: "OCC%", color: "#10b981" }]}
                  formatY={(v) => `${v}%`}
                  formatTooltip={(v) => [`${v}%`, "OCC%"]}
                  height={200}
                />
                <TrendChart
                  title="ADR & RevPAR"
                  data={chartData}
                  xKey="label"
                  lines={[
                    { key: "adr",    name: "ADR",    color: "#f59e0b" },
                    { key: "revpar", name: "RevPAR", color: "#ef4444" },
                  ]}
                  height={200}
                />
              </div>

              {/* Country breakdown */}
              {recentMonths.map((m) => (
                <div key={`${m.year}-${m.month}`} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                  <p className="text-sm font-semibold text-gray-700 mb-3">
                    Top Countries — {MONTH_LABELS[m.month]} {m.year}
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {(m.country_breakdown || []).slice(0, 8).map((c) => (
                      <div key={c.country_code} className="bg-gray-50 rounded-lg px-3 py-2">
                        <p className="text-xs font-semibold text-gray-700">{c.country || c.country_code}</p>
                        <p className="text-xs text-gray-400">{c.count} bookings</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}

          {/* ── All branches: per-branch tables ── */}
          {isAll && Object.entries(byBranch).map(([branchId, rows]) => {
            const branch = branchMap[branchId];
            const cur = branch?.native_currency || branch?.currency || "VND";
            return (
              <div key={branchId} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
                <div className="px-4 pt-4 pb-2">
                  <p className="text-sm font-semibold text-gray-800">{branch?.name || branchId}</p>
                  <p className="text-xs text-gray-400">{branch?.city} · {cur} · Excludes: Cancelled · No-show · KOL · Blogger · Maintenance · House Use · Day Use</p>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-100 bg-gray-50">
                      <th className="px-4 py-2 text-left">Month</th>
                      <th className="px-4 py-2 text-right">Revenue</th>
                      <th className="px-4 py-2 text-right">OCC%</th>
                      <th className="px-4 py-2 text-right">ADR</th>
                      <th className="px-4 py-2 text-right">RevPAR</th>
                      <th className="px-4 py-2 text-right">Rooms Sold</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {rows.map((m) => (
                      <tr key={`${m.year}-${m.month}`} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-600 font-medium">
                          {MONTH_LABELS[m.month]} {m.year}
                        </td>
                        <td className="px-4 py-2 text-right font-semibold text-gray-800 tabular-nums">
                          {fmt(m.revenue_native, cur)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600 tabular-nums">
                          {pct(m.avg_occ_pct)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600 tabular-nums">
                          {fmt(m.avg_adr_native, cur)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-600 tabular-nums">
                          {fmt(m.avg_revpar_native, cur)}
                        </td>
                        <td className="px-4 py-2 text-right text-gray-500 tabular-nums">
                          {m.total_sold?.toLocaleString() ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
