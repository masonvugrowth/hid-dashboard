/**
 * Home — v1.4
 * All Branches selected → Group Summary Table with deduction % and next-month actual revenue
 * Single branch selected → KPI card + Hot country badges + OCC heatmap
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";
import KPICard from "../components/KPICard";
import CountryBadge from "../components/CountryBadge";
import OCCHeatmap from "../components/OCCHeatmap";

const now        = new Date();
const YEAR       = now.getFullYear();
const MONTH      = now.getMonth() + 1;
const MONTH_NAME = now.toLocaleString("en-US", { month: "long", year: "numeric" });

function fmt(value, currency) {
  if (value == null) return "—";
  const sym = CURRENCY_SYMBOLS[currency] || currency || "";
  if (Math.abs(value) >= 1_000_000_000) return sym + (value / 1_000_000_000).toFixed(1) + "B";
  if (Math.abs(value) >= 1_000_000)     return sym + (value / 1_000_000).toFixed(1) + "M";
  return sym + Math.round(value).toLocaleString();
}

function pct(v) { return v == null ? "—" : Math.round(v) + "%"; }

function AchievementBadge({ value }) {
  if (value == null) return <span className="text-gray-400">—</span>;
  const cls =
    value >= 100 ? "text-green-700 bg-green-50" :
    value >= 80  ? "text-yellow-700 bg-yellow-50" :
    value >= 60  ? "text-orange-600 bg-orange-50" :
                   "text-red-600 bg-red-50";
  return <span className={"px-2 py-0.5 rounded text-xs font-semibold " + cls}>{Math.round(value)}%</span>;
}

function AllBranchesTable({ data, loading }) {
  // Per-branch deduction % state
  const [deductions, setDeductions] = useState({});

  const setDeduction = (branchId, val) => {
    // Clamp 0-100
    const num = Math.max(0, Math.min(100, parseFloat(val) || 0));
    setDeductions(prev => ({ ...prev, [branchId]: num }));
  };

  // Compute adjusted forecasts
  const rows = useMemo(() => {
    return data.map(row => {
      const dedPct = deductions[row.branch_id] || 0;
      const multiplier = 1 - dedPct / 100;
      return {
        ...row,
        deduction_pct: dedPct,
        adjusted_forecast: row.occ_forecast_native != null
          ? row.occ_forecast_native * multiplier
          : null,
        adjusted_next_forecast: row.next_month_forecast_native != null
          ? row.next_month_forecast_native * multiplier
          : null,
      };
    });
  }, [data, deductions]);

  if (loading) return <div className="bg-white rounded-xl border p-8 text-center text-gray-400 animate-pulse">Loading…</div>;
  if (!data.length) return <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No data — add branches and set KPI targets.</div>;
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-800">Group Summary — {MONTH_NAME}</h2>
        <p className="text-xs text-gray-400 mt-0.5">Native currency per branch · No cross-branch aggregation</p>
        <p className="text-xs text-gray-400 mt-0.5">
          Revenue from Cloudbeds Insights API · Excludes cancelled/no-show automatically
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide text-left">
              <th className="px-5 py-3">Branch</th>
              <th className="px-3 py-3">Currency</th>
              <th className="px-3 py-3 text-right">Revenue</th>
              <th className="px-3 py-3 text-right">Target</th>
              <th className="px-3 py-3 text-center">KPI %</th>
              <th className="px-3 py-3 text-center">Forecast (this month)</th>
              <th className="px-3 py-3 text-center whitespace-nowrap">Deduct %</th>
              <th className="px-3 py-3 text-center">Adjusted Forecast</th>
              <th className="px-3 py-3 text-center">Revenue (next month)</th>
              <th className="px-3 py-3 text-center">Forecast (next month)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => {
              const cur = row.currency || "VND";
              return (
                <tr key={row.branch_id} className="hover:bg-gray-50">
                  <td className="px-5 py-3.5 font-medium text-gray-800">{row.branch_name}</td>
                  <td className="px-3 py-3.5 text-gray-500">{cur}</td>
                  <td className="px-3 py-3.5 text-right font-mono">{fmt(row.actual_revenue_native, cur)}</td>
                  <td className="px-3 py-3.5 text-right font-mono text-gray-500">{fmt(row.target_revenue_native, cur)}</td>
                  <td className="px-3 py-3.5 text-center"><AchievementBadge value={row.achievement_pct != null ? row.achievement_pct * 100 : null} /></td>
                  {/* Forecast this month */}
                  <td className="px-3 py-3.5 text-center">
                    {row.occ_forecast_native != null
                      ? <span className="text-indigo-700 font-medium">
                          {fmt(row.occ_forecast_native, cur)}
                          {row.target_revenue_native
                            ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                ({Math.round(row.occ_forecast_native / row.target_revenue_native * 100)}%)
                              </span>
                            : null}
                        </span>
                      : <span className="text-gray-300 text-xs">Enter OCC%</span>}
                  </td>
                  {/* Deduction % input */}
                  <td className="px-3 py-3.5 text-center">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="1"
                      value={row.deduction_pct || ""}
                      onChange={e => setDeduction(row.branch_id, e.target.value)}
                      placeholder="0"
                      className="w-14 px-1.5 py-1 text-center text-xs border border-gray-300 rounded focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none"
                    />
                  </td>
                  {/* Adjusted forecast */}
                  <td className="px-3 py-3.5 text-center">
                    {row.adjusted_forecast != null
                      ? <span className={row.deduction_pct > 0 ? "text-orange-600 font-medium" : "text-indigo-700 font-medium"}>
                          {fmt(row.adjusted_forecast, cur)}
                          {row.target_revenue_native
                            ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                ({Math.round(row.adjusted_forecast / row.target_revenue_native * 100)}%)
                              </span>
                            : null}
                        </span>
                      : <span className="text-gray-300">—</span>}
                  </td>
                  {/* Next month actual revenue (booked) */}
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
                      : <span className="text-gray-300">—</span>}
                  </td>
                  {/* Next month forecast */}
                  <td className="px-3 py-3.5 text-center">
                    {row.next_month_forecast_native != null
                      ? <span className="text-purple-700 font-medium">
                          {fmt(row.adjusted_next_forecast != null && row.deduction_pct > 0
                            ? row.adjusted_next_forecast
                            : row.next_month_forecast_native, cur)}
                          {row.next_month_target_native
                            ? <span className="ml-1 text-xs text-gray-400 font-normal">
                                ({Math.round((row.deduction_pct > 0 && row.adjusted_next_forecast != null
                                  ? row.adjusted_next_forecast
                                  : row.next_month_forecast_native) / row.next_month_target_native * 100)}%)
                              </span>
                            : null}
                        </span>
                      : <span className="text-gray-300">—</span>}
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

  if (loading) return <div className="p-8 text-gray-400 animate-pulse">Loading…</div>;
  if (error)   return <div className="p-8 text-red-500">Error: {error}</div>;

  return (
    <div className="space-y-6">
      {kpi && (
        <KPICard
          label={branch.name + " — Revenue"}
          actual={kpi.actual_revenue_native}
          target={kpi.target_revenue_native}
          currency={branch.currency || branch.native_currency}
          forecast={{ occ: kpi.occ_forecast_native }}
        />
      )}
      <OCCHeatmap data={occData} title={branch.name + " — Daily OCC% (30 days)"} />
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
      {isAll
        ? <AllBranchesTable data={allData} loading={allLoading} />
        : currentBranch
          ? <SingleBranchView branch={currentBranch} />
          : <div className="bg-white rounded-xl border p-8 text-center text-gray-400">Select a branch above.</div>
      }
    </div>
  );
}
