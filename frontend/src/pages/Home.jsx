/**
 * Home — v1.5
 * All Branches selected → Group Summary Table with persistent deduction %
 * Single branch selected → KPI card + OCC heatmap
 */
import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import axios from "axios";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";
import KPICard from "../components/KPICard";
import CountryBadge from "../components/CountryBadge";
import OCCHeatmap from "../components/OCCHeatmap";

const now        = new Date();
const YEAR       = now.getFullYear();
const MONTH      = now.getMonth() + 1;
const MONTH_NAME = now.toLocaleString("en-US", { month: "long", year: "numeric" });

function toISO(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getPeriodRange(key) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const to = new Date(today);
  let from;
  switch (key) {
    case "7d":
      from = new Date(today); from.setDate(from.getDate() - 6); break;
    case "30d":
      from = new Date(today); from.setDate(from.getDate() - 29); break;
    case "90d":
      from = new Date(today); from.setDate(from.getDate() - 89); break;
    case "this_month":
      from = new Date(today.getFullYear(), today.getMonth(), 1); break;
    case "last_month": {
      const lm = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      from = lm;
      to.setTime(new Date(today.getFullYear(), today.getMonth(), 0).getTime());
      break;
    }
    case "ytd":
      from = new Date(today.getFullYear(), 0, 1); break;
    default:
      from = new Date(today); from.setDate(from.getDate() - 29);
  }
  return { from: toISO(from), to: toISO(to) };
}

const PERIOD_OPTIONS = [
  { key: "7d", label: "7 Days" },
  { key: "30d", label: "30 Days" },
  { key: "90d", label: "90 Days" },
  { key: "this_month", label: "This Month" },
  { key: "last_month", label: "Last Month" },
  { key: "ytd", label: "Year to Date" },
];

function fmt(value, currency) {
  if (value == null) return "\u2014";
  const sym = CURRENCY_SYMBOLS[currency] || currency || "";
  return sym + new Intl.NumberFormat("en").format(Math.round(value));
}

function AchievementBadge({ value }) {
  if (value == null) return <span className="text-gray-400">{"\u2014"}</span>;
  const cls =
    value >= 100 ? "text-green-700 bg-green-50" :
    value >= 80  ? "text-yellow-700 bg-yellow-50" :
    value >= 60  ? "text-orange-600 bg-orange-50" :
                   "text-red-600 bg-red-50";
  return <span className={"px-2 py-0.5 rounded text-xs font-semibold " + cls}>{Math.round(value)}%</span>;
}

function KPIAchievement({ branchId }) {
  const [period, setPeriod] = useState("90d");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const { from, to } = getPeriodRange(period);
    setLoading(true);
    const params = `date_from=${from}&date_to=${to}` + (branchId ? `&branch_id=${branchId}` : "");
    axios.get("/api/kpi/period-achievement?" + params)
      .then(r => {
        const rows = r.data.data || [];
        if (branchId) {
          setData(rows[0] || null);
        } else {
          // Aggregate all branches — pick first currency for display, sum values
          if (!rows.length) { setData(null); return; }
          const agg = {
            actual_revenue: 0, target_revenue: 0, daily_goal: 0, daily_actual: 0,
            total_days: rows[0].total_days, date_from: rows[0].date_from, date_to: rows[0].date_to,
            branches: rows,
          };
          for (const r of rows) {
            agg.actual_revenue += r.actual_revenue;
            agg.target_revenue += r.target_revenue;
            agg.daily_goal += r.daily_goal;
            agg.daily_actual += r.daily_actual;
          }
          agg.achievement_pct = agg.target_revenue > 0 ? agg.actual_revenue / agg.target_revenue : null;
          setData(agg);
        }
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [period, branchId]);

  const fmtDate = (s) => {
    const d = new Date(s + "T00:00:00");
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
  };

  const pct = data?.achievement_pct;
  const pctDisplay = pct != null ? (pct * 100).toFixed(1) + "%" : "\u2014";
  const pctColor =
    pct == null ? "text-gray-400" :
    pct >= 1.0  ? "text-green-600" :
    pct >= 0.8  ? "text-yellow-600" :
    pct >= 0.6  ? "text-orange-600" :
                  "text-red-600";
  const barColor =
    pct == null ? "bg-gray-300" :
    pct >= 1.0  ? "bg-green-500" :
    pct >= 0.8  ? "bg-yellow-400" :
    pct >= 0.6  ? "bg-orange-400" :
                  "bg-red-500";
  const barWidth = pct != null ? Math.min(pct * 100, 100).toFixed(1) + "%" : "0%";

  // For single branch, use its currency; for all, show VND or skip symbol
  const cur = data?.currency || (data?.branches?.[0]?.currency) || "";
  const fmtVal = (v) => {
    if (v == null) return "\u2014";
    const sym = CURRENCY_SYMBOLS[cur] || cur || "";
    return sym + new Intl.NumberFormat("en").format(Math.round(v));
  };

  // For all-branches mode, format per-branch using their own currency
  const fmtBranch = (v, c) => {
    if (v == null) return "\u2014";
    const sym = CURRENCY_SYMBOLS[c] || c || "";
    return sym + new Intl.NumberFormat("en").format(Math.round(v));
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      {/* Header with period selector */}
      <div className="px-5 py-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
          <h2 className="font-semibold text-gray-800">Goal Achievement</h2>
          {data && (
            <span className="text-xs text-gray-400 ml-1">
              {fmtDate(data.date_from)} – {fmtDate(data.date_to)}
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {PERIOD_OPTIONS.map(opt => (
            <button
              key={opt.key}
              onClick={() => setPeriod(opt.key)}
              className={
                "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors " +
                (period === opt.key
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200")
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="px-5 py-5">
        {loading ? (
          <div className="text-center py-4 text-gray-400 animate-pulse">Loading...</div>
        ) : !data ? (
          <div className="text-center py-4 text-gray-400">No data available</div>
        ) : data.branches ? (
          /* All branches mode — show per-branch breakdown */
          <div className="space-y-4">
            {data.branches.map(row => {
              const rPct = row.achievement_pct;
              const rPctDisplay = rPct != null ? (rPct * 100).toFixed(1) + "%" : "\u2014";
              const rPctColor =
                rPct == null ? "text-gray-400" :
                rPct >= 1.0  ? "text-green-600" :
                rPct >= 0.8  ? "text-yellow-600" :
                rPct >= 0.6  ? "text-orange-600" :
                               "text-red-600";
              const rBarColor =
                rPct == null ? "bg-gray-300" :
                rPct >= 1.0  ? "bg-green-500" :
                rPct >= 0.8  ? "bg-yellow-400" :
                rPct >= 0.6  ? "bg-orange-400" :
                               "bg-red-500";
              const rBarW = rPct != null ? Math.min(rPct * 100, 100).toFixed(1) + "%" : "0%";
              const dailyDiff = row.daily_goal > 0
                ? ((row.daily_actual - row.daily_goal) / row.daily_goal * 100).toFixed(1)
                : null;

              return (
                <div key={row.branch_id}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700">{row.branch_name}</span>
                    <span className={"text-lg font-bold " + rPctColor}>{rPctDisplay}</span>
                  </div>
                  <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-xl font-bold text-gray-800">
                      {fmtBranch(row.actual_revenue, row.currency)}
                    </span>
                    <span className="text-sm text-gray-400">
                      / {fmtBranch(row.target_revenue, row.currency)}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-1.5">
                    <div className={"h-full rounded-full transition-all duration-500 " + rBarColor} style={{ width: rBarW }} />
                  </div>
                  <p className="text-xs text-gray-400">
                    Daily Goal {fmtBranch(row.daily_goal, row.currency)}
                    {" \u00b7 "}
                    Daily Actual {fmtBranch(row.daily_actual, row.currency)}
                    {dailyDiff != null && (
                      <span className={Number(dailyDiff) >= 0 ? "text-green-600 ml-1" : "text-red-500 ml-1"}>
                        ({Number(dailyDiff) >= 0 ? "+" : ""}{dailyDiff}%)
                      </span>
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          /* Single branch mode */
          <>
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="text-2xl font-bold text-gray-800">
                  {fmtVal(data.actual_revenue)}
                </span>
                <span className="text-sm text-gray-400 ml-2">
                  / {fmtVal(data.target_revenue)}
                </span>
              </div>
              <span className={"text-2xl font-bold " + pctColor}>{pctDisplay}</span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden mb-3">
              <div className={"h-full rounded-full transition-all duration-500 " + barColor} style={{ width: barWidth }} />
            </div>
            <p className="text-xs text-gray-400">
              Daily Goal {fmtVal(data.daily_goal)}
              {" \u00b7 "}
              Daily Actual {fmtVal(data.daily_actual)}
              {data.daily_goal > 0 && (() => {
                const diff = ((data.daily_actual - data.daily_goal) / data.daily_goal * 100).toFixed(1);
                return (
                  <span className={Number(diff) >= 0 ? "text-green-600 ml-1" : "text-red-500 ml-1"}>
                    ({Number(diff) >= 0 ? "+" : ""}{diff}%)
                  </span>
                );
              })()}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function AllBranchesTable({ data, loading }) {
  // Per-branch deduction % state — initialized from API data
  const [deductions, setDeductions] = useState({});
  const [saving, setSaving] = useState({});
  const saveTimers = useRef({});

  // Initialize deductions from API data
  useEffect(() => {
    if (!data.length) return;
    const init = {};
    for (const row of data) {
      init[row.branch_id] = row.deduction_pct || 0;
    }
    setDeductions(init);
  }, [data]);

  // Save deduction to backend (debounced)
  const saveDeduction = useCallback((branchId, val) => {
    const num = Math.max(0, Math.min(100, parseFloat(val) || 0));

    // Clear previous timer
    if (saveTimers.current[branchId]) {
      clearTimeout(saveTimers.current[branchId]);
    }

    // Debounce 800ms
    saveTimers.current[branchId] = setTimeout(() => {
      setSaving(prev => ({ ...prev, [branchId]: true }));
      axios.put("/api/kpi/deduction", {
        branch_id: branchId,
        year: YEAR,
        month: MONTH,
        deduction_pct: num,
      })
        .then(() => {
          setSaving(prev => ({ ...prev, [branchId]: false }));
        })
        .catch(() => {
          setSaving(prev => ({ ...prev, [branchId]: false }));
        });
    }, 800);
  }, []);

  const setDeduction = (branchId, val) => {
    const num = Math.max(0, Math.min(100, parseFloat(val) || 0));
    setDeductions(prev => ({ ...prev, [branchId]: num }));
    saveDeduction(branchId, num);
  };

  // Compute adjusted forecasts
  const rows = useMemo(() => {
    return data.map(row => {
      const dedPct = deductions[row.branch_id] ?? row.deduction_pct ?? 0;
      const multiplier = 1 - dedPct / 100;
      return {
        ...row,
        deduction_pct_local: dedPct,
        adjusted_forecast: row.occ_forecast_native != null
          ? row.occ_forecast_native * multiplier
          : null,
        adjusted_next_forecast: row.next_month_forecast_native != null
          ? row.next_month_forecast_native * multiplier
          : null,
      };
    });
  }, [data, deductions]);

  if (loading) return (
    <div className="bg-white rounded-xl border p-8 text-center">
      <div className="text-gray-400 animate-pulse text-lg">Loading\u2026</div>
      <p className="text-xs text-gray-300 mt-2">Loading data…</p>
    </div>
  );
  if (!data.length) return <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No data \u2014 add branches and set KPI targets.</div>;
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-800">Group Summary \u2014 {MONTH_NAME}</h2>
        <p className="text-xs text-gray-400 mt-0.5">
          Native currency per branch
          {data[0]?.data_synced_at && (
            <span> \u00b7 Last synced: {new Date(data[0].data_synced_at).toLocaleString("en-GB", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
          )}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide text-left">
              <th className="px-5 py-3">Branch</th>
              <th className="px-3 py-3">Cur</th>
              <th className="px-3 py-3 text-right">Revenue</th>
              <th className="px-3 py-3 text-right">Target</th>
              <th className="px-3 py-3 text-center">KPI %</th>
              <th className="px-3 py-3 text-center">Forecast</th>
              <th className="px-3 py-3 text-center whitespace-nowrap">Deduct %</th>
              <th className="px-3 py-3 text-center">Adjusted</th>
              <th className="px-3 py-3 text-center whitespace-nowrap">Next Rev</th>
              <th className="px-3 py-3 text-center whitespace-nowrap">Next Forecast</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => {
              const cur = row.currency || "VND";
              const dedPct = row.deduction_pct_local;
              const isSaving = saving[row.branch_id];
              return (
                <tr key={row.branch_id} className="hover:bg-gray-50">
                  <td className="px-5 py-3.5 font-medium text-gray-800">{row.branch_name}</td>
                  <td className="px-3 py-3.5 text-gray-500 text-xs">{cur}</td>
                  <td className="px-3 py-3.5 text-right font-mono">{fmt(row.actual_revenue_native, cur)}</td>
                  <td className="px-3 py-3.5 text-right font-mono text-gray-500">{fmt(row.target_revenue_native, cur)}</td>
                  <td className="px-3 py-3.5 text-center"><AchievementBadge value={row.achievement_pct != null ? row.achievement_pct * 100 : null} /></td>
                  {/* Forecast this month */}
                  <td className="px-3 py-3.5 text-center">
                    {row.occ_forecast_native != null
                      ? <div>
                          <span className="text-indigo-700 font-medium">
                            {fmt(row.occ_forecast_native, cur)}
                            {row.target_revenue_native
                              ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                  ({Math.round(row.occ_forecast_native / row.target_revenue_native * 100)}%)
                                </span>
                              : null}
                          </span>
                          {(() => {
                            const rOcc = row.predicted_room_occ_pct;
                            const dOcc = row.predicted_dorm_occ_pct;
                            const fallback = row.predicted_occ_pct;
                            const hasDorm = row.total_dorm_count > 0;
                            if (rOcc != null || dOcc != null) {
                              return (
                                <div className="text-[10px] text-gray-400 mt-0.5">
                                  {rOcc != null && <span>R:{Math.round(rOcc * 100)}%</span>}
                                  {rOcc != null && dOcc != null && hasDorm && <span> · </span>}
                                  {dOcc != null && hasDorm && <span>D:{Math.round(dOcc * 100)}%</span>}
                                </div>
                              );
                            }
                            if (fallback != null) {
                              return (
                                <div className="text-[10px] text-gray-400 mt-0.5">
                                  {hasDorm ? `R:${Math.round(fallback * 100)}% · D:${Math.round(fallback * 100)}%` : `R:${Math.round(fallback * 100)}%`}
                                </div>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      : <span className="text-gray-300 text-xs">Enter OCC%</span>}
                  </td>
                  {/* Deduction % input — auto-saves */}
                  <td className="px-3 py-3.5 text-center">
                    <div className="relative inline-block">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        value={dedPct || ""}
                        onChange={e => setDeduction(row.branch_id, e.target.value)}
                        placeholder="0"
                        className={
                          "w-14 px-1.5 py-1 text-center text-xs border rounded outline-none " +
                          (isSaving
                            ? "border-yellow-400 bg-yellow-50"
                            : "border-gray-300 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400")
                        }
                      />
                      {isSaving && (
                        <span className="absolute -top-1 -right-1 w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
                      )}
                    </div>
                  </td>
                  {/* Adjusted forecast */}
                  <td className="px-3 py-3.5 text-center">
                    {row.adjusted_forecast != null
                      ? <span className={dedPct > 0 ? "text-orange-600 font-medium" : "text-indigo-700 font-medium"}>
                          {fmt(row.adjusted_forecast, cur)}
                          {row.target_revenue_native
                            ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                ({Math.round(row.adjusted_forecast / row.target_revenue_native * 100)}%)
                              </span>
                            : null}
                        </span>
                      : <span className="text-gray-300">{"\u2014"}</span>}
                  </td>
                  {/* Next month actual booked revenue */}
                  <td className="px-3 py-3.5 text-center">
                    {row.next_month_booked_revenue != null && row.next_month_booked_revenue > 0
                      ? <span className="text-gray-700 font-mono">
                          {fmt(row.next_month_booked_revenue, cur)}
                          {row.next_month_target_native
                            ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                ({Math.round(row.next_month_booked_revenue / row.next_month_target_native * 100)}%)
                              </span>
                            : null}
                        </span>
                      : <span className="text-gray-300">{"\u2014"}</span>}
                  </td>
                  {/* Next month forecast — always shows adjusted */}
                  <td className="px-3 py-3.5 text-center">
                    {row.adjusted_next_forecast != null
                      ? <div>
                          <span className={dedPct > 0 ? "text-orange-600 font-medium" : "text-purple-700 font-medium"}>
                            {fmt(row.adjusted_next_forecast, cur)}
                            {row.next_month_target_native
                              ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                  ({Math.round(row.adjusted_next_forecast / row.next_month_target_native * 100)}%)
                                </span>
                              : null}
                          </span>
                          {(() => {
                            const rOcc = row.predicted_room_occ_next;
                            const dOcc = row.predicted_dorm_occ_next;
                            const fallback = row.predicted_occ_next;
                            const hasDorm = row.total_dorm_count > 0;
                            if (rOcc != null || dOcc != null) {
                              return (
                                <div className="text-[10px] text-gray-400 mt-0.5">
                                  {rOcc != null && <span>R:{Math.round(rOcc * 100)}%</span>}
                                  {rOcc != null && dOcc != null && hasDorm && <span> · </span>}
                                  {dOcc != null && hasDorm && <span>D:{Math.round(dOcc * 100)}%</span>}
                                </div>
                              );
                            }
                            if (fallback != null) {
                              return (
                                <div className="text-[10px] text-gray-400 mt-0.5">
                                  {hasDorm ? `R:${Math.round(fallback * 100)}% · D:${Math.round(fallback * 100)}%` : `R:${Math.round(fallback * 100)}%`}
                                </div>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      : <span className="text-gray-300">{"\u2014"}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SingleBranchView({ branch }) {
  const [kpi, setKpi]         = useState(null);
  const [countries, setCountries] = useState([]);
  const [occData, setOccData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    if (!branch) return;
    setLoading(true);
    Promise.all([
      axios.get("/api/kpi/summary/" + branch.id + "?year=" + YEAR + "&month=" + MONTH),
      axios.get("/api/countries/ranking?top_n=5&branch_id=" + branch.id),
      axios.get("/api/metrics/daily?branch_id=" + branch.id + "&days=30"),
    ])
      .then(([kpiRes, cRes, occRes]) => {
        setKpi(kpiRes.data.data || kpiRes.data);
        setCountries(cRes.data.data || []);
        setOccData(occRes.data.data || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [branch && branch.id]);

  if (loading) return (
    <div className="p-8 text-center">
      <div className="text-gray-400 animate-pulse text-lg">Loading\u2026</div>
      <p className="text-xs text-gray-300 mt-2">Loading data…</p>
    </div>
  );
  if (error)   return <div className="p-8 text-red-500">Error: {error}</div>;

  return (
    <div className="space-y-6">
      {kpi && (
        <KPICard
          label={branch.name + " \u2014 Revenue"}
          actual={kpi.actual_revenue_native}
          target={kpi.target_revenue_native}
          currency={branch.currency || branch.native_currency}
          forecast={{ occ: kpi.occ_forecast_native }}
        />
      )}
      <OCCHeatmap data={occData} title={branch.name + " \u2014 Daily OCC% (30 days)"} />
    </div>
  );
}

export default function Home() {
  const { isAll, currentBranch } = useBranch();
  const [allData, setAllData]       = useState([]);
  const [allLoading, setAllLoading] = useState(false);

  useEffect(() => {
    if (!isAll) return;
    setAllLoading(true);
    axios.get("/api/kpi/summary?year=" + YEAR + "&month=" + MONTH + "&months=current,next")
      .then(r => setAllData(r.data.data || []))
      .catch(() => setAllData([]))
      .finally(() => setAllLoading(false));
  }, [isAll]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-gray-800">
          {isAll ? "All Branches" : (currentBranch ? currentBranch.name : "Dashboard")}
        </h1>
        <p className="text-xs text-gray-400 mt-0.5">{MONTH_NAME}</p>
      </div>
      <KPIAchievement branchId={isAll ? null : (currentBranch ? currentBranch.id : null)} />
      {isAll
        ? <AllBranchesTable data={allData} loading={allLoading} />
        : currentBranch
          ? <SingleBranchView branch={currentBranch} />
          : <div className="bg-white rounded-xl border p-8 text-center text-gray-400">Select a branch above.</div>
      }
    </div>
  );
}
