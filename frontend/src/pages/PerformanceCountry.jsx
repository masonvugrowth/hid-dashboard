/**
 * Country Reservations Trend — Top 15 countries over 7 weeks / 7 months.
 * Stacked area chart + summary table.
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useBranch } from "../context/BranchContext";

const COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#3b82f6",
  "#a855f7", "#06b6d4", "#ec4899", "#84cc16", "#f97316",
  "#8b5cf6", "#14b8a6", "#e11d48", "#0ea5e9", "#d946ef",
];

function fmtNum(val) {
  if (val == null || val === 0) return "0";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

export default function PerformanceCountry() {
  const { isAll, selected } = useBranch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("monthly");
  const [filterCountry, setFilterCountry] = useState("");

  const load = () => {
    setLoading(true);
    const params = { view, limit: 15 };
    if (!isAll && selected) params.branch_id = selected;

    axios.get("/api/metrics/country-reservations", { params })
      .then((r) => setData(r.data.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(load, [selected, isAll, view]);

  const periods = data?.periods || [];
  const allCountries = data?.countries || [];
  const trend = data?.trend || {};

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
            Top 15 countries — last 7 {view === "monthly" ? "months" : "weeks"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select value={filterCountry} onChange={(e) => setFilterCountry(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm">
            <option value="">All Countries</option>
            {allCountries.map((c) => (
              <option key={c.country_code} value={c.country}>{c.country}</option>
            ))}
          </select>
          <div className="flex rounded-lg border overflow-hidden">
            {["weekly", "monthly"].map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={`px-4 py-1.5 text-sm font-medium ${
                  view === v ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}>
                {v === "weekly" ? "Weekly" : "Monthly"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
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

          {/* Bar Chart — latest period breakdown */}
          <div className="bg-white rounded-lg border p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              {latestPeriod} — Reservations by Country
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={countryNames.map((name, i) => ({
                  country: name,
                  reservations: latestData[name] || 0,
                  prev: prevData[name] || 0,
                  fill: COLORS[i % COLORS.length],
                }))}
                layout="vertical"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="country" width={120} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                  formatter={(val) => [fmtNum(val), "Reservations"]}
                />
                <Bar dataKey="reservations" name={latestPeriod} radius={[0, 4, 4, 0]}>
                  {countryNames.map((_, i) => (
                    <rect key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
                <Bar dataKey="prev" name={prevPeriod} fill="#e5e7eb" radius={[0, 4, 4, 0]} />
              </BarChart>
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
      )}
    </div>
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
