/**
 * Country Reservations Trend — Top 15 countries over 7 weeks / 7 months.
 * + Compare to Last Year (via Cloudbeds Insights API).
 * Stacked area chart + summary table.
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import {
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useBranch } from "../context/BranchContext";

const COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#3b82f6",
  "#a855f7", "#06b6d4", "#ec4899", "#84cc16", "#f97316",
  "#8b5cf6", "#14b8a6", "#e11d48", "#0ea5e9", "#d946ef",
];

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtNum(val) {
  if (val == null || val === 0) return "0";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

export default function PerformanceCountry() {
  const { isAll, selected, branches } = useBranch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("monthly"); // weekly | monthly | compare
  const [filterCountry, setFilterCountry] = useState("");

  // Compare view state
  const now = new Date();
  const [cmpYear, setCmpYear] = useState(now.getFullYear());
  const [cmpMonth, setCmpMonth] = useState(now.getMonth() + 1);
  const [cmpData, setCmpData] = useState(null);
  const [cmpLoading, setCmpLoading] = useState(false);

  // Branch compare state
  const [compareBranch, setCompareBranch] = useState("");
  const [compareBranchData, setCompareBranchData] = useState(null);

  // Reset compareBranch when switching away from compare view or to "all"
  useEffect(() => {
    if (view !== "compare" || isAll) {
      setCompareBranch("");
      setCompareBranchData(null);
    }
  }, [view, isAll]);

  // Load trend data (weekly/monthly)
  const loadTrend = () => {
    setLoading(true);
    const params = { view, limit: 15 };
    if (!isAll && selected) params.branch_id = selected;

    axios.get("/api/metrics/country-reservations", { params })
      .then((r) => setData(r.data.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  // Load compare data (Cloudbeds Insights API)
  const loadCompare = () => {
    setCmpLoading(true);
    const params = { year: cmpYear, month: cmpMonth };
    if (!isAll && selected) params.branch_id = selected;

    const requests = [axios.get("/api/metrics/country-yoy-insights", { params })];

    // If comparing with another branch, fetch that too
    if (compareBranch) {
      requests.push(
        axios.get("/api/metrics/country-yoy-insights", {
          params: { year: cmpYear, month: cmpMonth, branch_id: compareBranch },
        })
      );
    }

    Promise.all(requests)
      .then(([mainRes, cmpBranchRes]) => {
        setCmpData(mainRes.data.data);
        setCompareBranchData(cmpBranchRes ? cmpBranchRes.data.data : null);
      })
      .catch(() => {
        setCmpData(null);
        setCompareBranchData(null);
      })
      .finally(() => setCmpLoading(false));
  };

  useEffect(() => {
    if (view === "compare") {
      loadCompare();
    } else {
      loadTrend();
    }
  }, [selected, isAll, view, cmpYear, cmpMonth, compareBranch]);

  const periods = data?.periods || [];
  const allCountries = data?.countries || [];
  const trend = data?.trend || {};

  // Other branches for compare dropdown (exclude current)
  const otherBranches = useMemo(() => {
    if (isAll || !selected) return [];
    return branches.filter((b) => b.id !== selected);
  }, [branches, selected, isAll]);

  const compareBranchName = useMemo(() => {
    if (!compareBranch) return "";
    const b = branches.find((br) => br.id === compareBranch);
    return b?.name || "";
  }, [branches, compareBranch]);

  const currentBranchName = useMemo(() => {
    if (isAll || !selected) return "Current";
    const b = branches.find((br) => br.id === selected);
    return b?.name || "Current";
  }, [branches, selected, isAll]);

  // Union of countries for filter dropdown when branch compare is active
  const compareCountryList = useMemo(() => {
    if (!compareBranchData || !cmpData) return [];
    const names = new Set([
      ...(cmpData.countries || []).map((c) => c.country),
      ...(compareBranchData.countries || []).map((c) => c.country),
    ]);
    return [...names].sort();
  }, [cmpData, compareBranchData]);

  // Filter countries
  const countries = useMemo(() => {
    if (!filterCountry) return allCountries;
    return allCountries.filter((c) => c.country === filterCountry);
  }, [allCountries, filterCountry]);

  const countryNames = countries.map((c) => c.country);

  // Build chart data: [{period, Country1: N, Country2: N, ...}, ...]
  const chartData = useMemo(() => {
    return periods.map((p) => {
      const row = { period: p };
      const periodData = trend[p] || {};
      for (const name of countryNames) {
        row[name] = periodData[name] || 0;
      }
      return row;
    });
  }, [periods, trend, countryNames]);

  // Total for the most recent period (last element)
  const latestPeriod = periods[periods.length - 1];
  const prevPeriod = periods[periods.length - 2];
  const latestData = trend[latestPeriod] || {};
  const prevData = trend[prevPeriod] || {};
  const latestTotal = Object.values(latestData).reduce((a, b) => a + b, 0);
  const prevTotal = Object.values(prevData).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Country Reservations</h1>
          <p className="text-sm text-gray-500">
            {view === "compare"
              ? `${MONTHS[cmpMonth - 1]} ${cmpYear} vs ${MONTHS[cmpMonth - 1]} ${cmpYear - 1}`
              : `Top 15 countries \u2014 last 7 ${view === "monthly" ? "months" : "weeks"}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select value={filterCountry} onChange={(e) => setFilterCountry(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm">
            <option value="">All Countries</option>
            {view === "compare" && compareBranch
              ? compareCountryList.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))
              : view === "compare"
              ? (cmpData?.countries || []).map((c) => (
                  <option key={c.country} value={c.country}>{c.country}</option>
                ))
              : allCountries.map((c) => (
                  <option key={c.country_code} value={c.country}>{c.country}</option>
                ))
            }
          </select>
          {view === "compare" && (
            <div className="flex items-center gap-2">
              <select value={cmpMonth} onChange={(e) => setCmpMonth(Number(e.target.value))}
                className="border rounded px-2 py-1.5 text-sm">
                {MONTHS.map((m, i) => (
                  <option key={i + 1} value={i + 1}>{m}</option>
                ))}
              </select>
              <select value={cmpYear} onChange={(e) => setCmpYear(Number(e.target.value))}
                className="border rounded px-2 py-1.5 text-sm">
                {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          )}
          {view === "compare" && !isAll && selected && (
            <select value={compareBranch} onChange={(e) => setCompareBranch(e.target.value)}
              className="border rounded px-2 py-1.5 text-sm bg-indigo-50 border-indigo-300 text-indigo-700">
              <option value="">Compare Branch...</option>
              {otherBranches.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
          <div className="flex rounded-lg border overflow-hidden">
            {["weekly", "monthly", "compare"].map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={`px-4 py-1.5 text-sm font-medium ${
                  view === v ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}>
                {v === "weekly" ? "Weekly" : v === "monthly" ? "Monthly" : "Compare"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Compare View ── */}
      {view === "compare" ? (
        cmpLoading ? (
          <div className="text-center text-gray-400 py-16 text-sm animate-pulse">Loading...</div>
        ) : !cmpData || cmpData.countries?.length === 0 ? (
          <div className="text-center text-gray-400 py-16 text-sm">No data available.</div>
        ) : compareBranch && compareBranchData ? (
          <BranchCompareView
            dataA={cmpData}
            dataB={compareBranchData}
            nameA={currentBranchName}
            nameB={compareBranchName}
            filterCountry={filterCountry}
          />
        ) : (
          <CompareView data={cmpData} filterCountry={filterCountry} />
        )
      ) : (
        /* ── Trend View (Weekly / Monthly) ── */
        loading ? (
          <div className="text-center text-gray-400 py-16 text-sm animate-pulse">Loading...</div>
        ) : !data || countries.length === 0 ? (
          <div className="text-center text-gray-400 py-16 text-sm">No data available.</div>
        ) : (
          <>
            {/* KPI Summary */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-lg border p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  {latestPeriod} Reservations
                </p>
                <p className="text-2xl font-bold text-gray-900">{fmtNum(latestTotal)}</p>
                {prevTotal > 0 && (
                  <PctChange current={latestTotal} previous={prevTotal} label={prevPeriod} />
                )}
              </div>
              <div className="bg-white rounded-lg border p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Top Country</p>
                <p className="text-2xl font-bold text-gray-900">{countries[0]?.country || "-"}</p>
                <p className="text-xs text-gray-400 mt-1">{fmtNum(countries[0]?.total_reservations)} total reservations</p>
              </div>
              <div className="bg-white rounded-lg border p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Countries Tracked</p>
                <p className="text-2xl font-bold text-gray-900">{countries.length}</p>
                <p className="text-xs text-gray-400 mt-1">{fmtNum(countries.reduce((a, c) => a + c.total_nights, 0))} total room nights</p>
              </div>
            </div>

            {/* Stacked Area Chart */}
            <div className="bg-white rounded-lg border p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">
                Reservation Trend by Country
              </h2>
              <ResponsiveContainer width="100%" height={360}>
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(val, name) => [fmtNum(val), name]}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {countryNames.map((name, i) => (
                    <Area
                      key={name}
                      type="monotone"
                      dataKey={name}
                      stackId="1"
                      fill={COLORS[i % COLORS.length]}
                      stroke={COLORS[i % COLORS.length]}
                      fillOpacity={0.7}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Summary Table */}
            <div className="bg-white rounded-lg border overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-center px-3 py-3 font-semibold text-gray-600 w-10">#</th>
                    <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-600">Total Reservations</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-600">Room Nights</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-600">Revenue (VND)</th>
                    {/* Per-period columns */}
                    {periods.map((p) => (
                      <th key={p} className="text-right px-3 py-3 font-semibold text-gray-500 text-xs">{p}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {countries.map((c, i) => (
                    <tr key={c.country_code} className="hover:bg-gray-50">
                      <td className="px-3 py-2.5 text-center">
                        <span className="inline-block w-5 h-5 rounded-full text-xs font-bold text-white leading-5 text-center"
                          style={{ backgroundColor: COLORS[i % COLORS.length] }}>
                          {i + 1}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium text-gray-900">{c.country}</td>
                      <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(c.total_reservations)}</td>
                      <td className="px-4 py-2.5 text-right">{fmtNum(c.total_nights)}</td>
                      <td className="px-4 py-2.5 text-right">{fmtNum(c.total_revenue)}</td>
                      {periods.map((p) => {
                        const val = (trend[p] || {})[c.country] || 0;
                        return (
                          <td key={p} className="px-3 py-2.5 text-right text-xs">
                            {val > 0 ? (
                              <span className="font-medium">{val}</span>
                            ) : (
                              <span className="text-gray-300">-</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )
      )}
    </div>
  );
}


/* ── Compare View Component ─────────────────────────────────────────────────── */

function CompareView({ data, filterCountry }) {
  const { year, month } = data;
  const countries = filterCountry
    ? data.countries.filter((c) => c.country === filterCountry)
    : data.countries;
  const monthName = MONTHS[month - 1];

  // Summary KPIs
  const totalCurrentNights = countries.reduce((a, c) => a + c.current_nights, 0);
  const totalPrevNights = countries.reduce((a, c) => a + c.prev_nights, 0);
  const totalCurrentRevenue = countries.reduce((a, c) => a + c.current_revenue, 0);
  const totalPrevRevenue = countries.reduce((a, c) => a + c.prev_revenue, 0);
  const growingCount = countries.filter((c) => c.nights_change_pct != null && c.nights_change_pct > 0).length;
  const decliningCount = countries.filter((c) => c.nights_change_pct != null && c.nights_change_pct < 0).length;

  return (
    <>
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
            {monthName} {year} Nights
          </p>
          <p className="text-2xl font-bold text-gray-900">{fmtNum(totalCurrentNights)}</p>
          {totalPrevNights > 0 && (
            <PctChange current={totalCurrentNights} previous={totalPrevNights}
              label={`${monthName} ${year - 1}`} />
          )}
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
            {monthName} {year} Revenue
          </p>
          <p className="text-2xl font-bold text-gray-900">{fmtNum(totalCurrentRevenue)}</p>
          {totalPrevRevenue > 0 && (
            <PctChange current={totalCurrentRevenue} previous={totalPrevRevenue}
              label={`${monthName} ${year - 1}`} />
          )}
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Growing</p>
          <p className="text-2xl font-bold text-emerald-600">{growingCount}</p>
          <p className="text-xs text-gray-400 mt-1">countries with more room nights</p>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Declining</p>
          <p className="text-2xl font-bold text-red-500">{decliningCount}</p>
          <p className="text-xs text-gray-400 mt-1">countries with fewer room nights</p>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="bg-white rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-center px-3 py-3 font-semibold text-gray-600 w-10">#</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Nights {year}
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Nights {year - 1}
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Change</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Revenue {year}
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Revenue {year - 1}
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Change</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Guests {year}
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                Guests {year - 1}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {countries.map((c, i) => (
              <tr key={c.country} className="hover:bg-gray-50">
                <td className="px-3 py-2.5 text-center text-gray-400 font-mono text-xs">{i + 1}</td>
                <td className="px-4 py-2.5 font-medium text-gray-900">{c.country}</td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(c.current_nights)}</td>
                <td className="px-4 py-2.5 text-right text-gray-500">{fmtNum(c.prev_nights)}</td>
                <td className="px-4 py-2.5 text-right">
                  <ChangeBadge value={c.nights_change_pct} />
                </td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(c.current_revenue)}</td>
                <td className="px-4 py-2.5 text-right text-gray-500">{fmtNum(c.prev_revenue)}</td>
                <td className="px-4 py-2.5 text-right">
                  <ChangeBadge value={c.revenue_change_pct} />
                </td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(c.current_guests)}</td>
                <td className="px-4 py-2.5 text-right text-gray-500">{fmtNum(c.prev_guests)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}


/* ── Branch Compare View Component ─────────────────────────────────────────── */

function BranchCompareView({ dataA, dataB, nameA, nameB, filterCountry }) {
  const { year, month } = dataA;
  const monthName = MONTHS[month - 1];

  // Build lookup maps
  const mapA = {};
  for (const c of dataA.countries) mapA[c.country] = c;
  const mapB = {};
  for (const c of dataB.countries) mapB[c.country] = c;

  // Union of countries, filtered
  let allCountryNames = [...new Set([
    ...dataA.countries.map((c) => c.country),
    ...dataB.countries.map((c) => c.country),
  ])];
  if (filterCountry) {
    allCountryNames = allCountryNames.filter((c) => c === filterCountry);
  }

  // Build merged rows sorted by branch A nights desc
  const rows = allCountryNames.map((country) => {
    const a = mapA[country] || { current_nights: 0, current_revenue: 0, current_guests: 0 };
    const b = mapB[country] || { current_nights: 0, current_revenue: 0, current_guests: 0 };
    return { country, a, b };
  }).sort((x, y) => y.a.current_nights - x.a.current_nights);

  // Totals
  const totA = { nights: 0, revenue: 0, guests: 0 };
  const totB = { nights: 0, revenue: 0, guests: 0 };
  for (const r of rows) {
    totA.nights += r.a.current_nights;
    totA.revenue += r.a.current_revenue;
    totA.guests += r.a.current_guests;
    totB.nights += r.b.current_nights;
    totB.revenue += r.b.current_revenue;
    totB.guests += r.b.current_guests;
  }

  function diffPct(valA, valB) {
    if (valB === 0) return valA === 0 ? null : 100.0;
    return ((valA - valB) / valB) * 100;
  }

  return (
    <>
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
            {nameA} Nights
          </p>
          <p className="text-2xl font-bold text-gray-900">{fmtNum(totA.nights)}</p>
          <p className="text-xs text-gray-400 mt-1">{monthName} {year}</p>
        </div>
        <div className="bg-white rounded-lg border p-4 border-indigo-200 bg-indigo-50/30">
          <p className="text-xs text-indigo-500 uppercase tracking-wider mb-1">
            {nameB} Nights
          </p>
          <p className="text-2xl font-bold text-indigo-700">{fmtNum(totB.nights)}</p>
          <p className="text-xs text-gray-400 mt-1">{monthName} {year}</p>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">
            {nameA} Revenue
          </p>
          <p className="text-2xl font-bold text-gray-900">{fmtNum(totA.revenue)}</p>
          <p className="text-xs text-gray-400 mt-1">{monthName} {year}</p>
        </div>
        <div className="bg-white rounded-lg border p-4 border-indigo-200 bg-indigo-50/30">
          <p className="text-xs text-indigo-500 uppercase tracking-wider mb-1">
            {nameB} Revenue
          </p>
          <p className="text-2xl font-bold text-indigo-700">{fmtNum(totB.revenue)}</p>
          <p className="text-xs text-gray-400 mt-1">{monthName} {year}</p>
        </div>
      </div>

      {/* Branch Comparison Table */}
      <div className="bg-white rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-center px-3 py-3 font-semibold text-gray-600 w-10">#</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                {nameA}<br /><span className="text-xs font-normal text-gray-400">Nights</span>
              </th>
              <th className="text-right px-4 py-3 font-semibold text-indigo-600">
                {nameB}<br /><span className="text-xs font-normal text-indigo-400">Nights</span>
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Diff</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                {nameA}<br /><span className="text-xs font-normal text-gray-400">Revenue</span>
              </th>
              <th className="text-right px-4 py-3 font-semibold text-indigo-600">
                {nameB}<br /><span className="text-xs font-normal text-indigo-400">Revenue</span>
              </th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Diff</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">
                {nameA}<br /><span className="text-xs font-normal text-gray-400">Guests</span>
              </th>
              <th className="text-right px-4 py-3 font-semibold text-indigo-600">
                {nameB}<br /><span className="text-xs font-normal text-indigo-400">Guests</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((r, i) => (
              <tr key={r.country} className="hover:bg-gray-50">
                <td className="px-3 py-2.5 text-center text-gray-400 font-mono text-xs">{i + 1}</td>
                <td className="px-4 py-2.5 font-medium text-gray-900">{r.country}</td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(r.a.current_nights)}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-indigo-700">{fmtNum(r.b.current_nights)}</td>
                <td className="px-4 py-2.5 text-right">
                  <ChangeBadge value={diffPct(r.a.current_nights, r.b.current_nights)} />
                </td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(r.a.current_revenue)}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-indigo-700">{fmtNum(r.b.current_revenue)}</td>
                <td className="px-4 py-2.5 text-right">
                  <ChangeBadge value={diffPct(r.a.current_revenue, r.b.current_revenue)} />
                </td>
                <td className="px-4 py-2.5 text-right font-semibold">{fmtNum(r.a.current_guests)}</td>
                <td className="px-4 py-2.5 text-right font-semibold text-indigo-700">{fmtNum(r.b.current_guests)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}


/* ── Helpers ─────────────────────────────────────────────────────────────────── */

function ChangeBadge({ value }) {
  if (value == null) return <span className="text-gray-300">-</span>;
  const isUp = value > 0;
  const isZero = value === 0;
  const cls = isUp
    ? "bg-emerald-50 text-emerald-700"
    : isZero
    ? "bg-gray-50 text-gray-500"
    : "bg-red-50 text-red-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {isUp ? "+" : ""}{value.toFixed(1)}%
    </span>
  );
}

function PctChange({ current, previous, label }) {
  const pct = ((current - previous) / previous) * 100;
  const isUp = pct > 0;
  const cls = isUp ? "text-green-600" : pct < 0 ? "text-red-600" : "text-gray-500";
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <span className={"text-xs font-medium " + cls}>
        {isUp ? "\u25B2" : pct < 0 ? "\u25BC" : ""}{Math.abs(pct).toFixed(1)}%
      </span>
      <span className="text-xs text-gray-400">vs {label}</span>
    </div>
  );
}
