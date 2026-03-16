/**
 * Weekly Brief — Revenue trend by branch, cancellation %, OTA mix
 */
import { useEffect, useState, useMemo } from "react";
import axios from "axios";
import {
  BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useBranch } from "../context/BranchContext";

const BRANCH_COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#3b82f6"];
const OTA_COLORS    = ["#6366f1","#10b981","#f59e0b","#ef4444","#a855f7","#06b6d4"];

function fmtCompact(val, currency) {
  if (!val) return "0";
  if (currency === "VND") {
    if (val >= 1e9) return `${(val/1e9).toFixed(1)}B`;
    if (val >= 1e6) return `${(val/1e6).toFixed(0)}M`;
    return new Intl.NumberFormat("vi-VN").format(Math.round(val));
  }
  if (val >= 1e6) return `${(val/1e6).toFixed(1)}M`;
  if (val >= 1e3) return `${(val/1e3).toFixed(0)}K`;
  return val.toFixed(0);
}

// Merge OTA categories case-insensitively
function mergeOtaMix(rows) {
  const map = {};
  for (const r of rows) {
    const key = r.category?.toLowerCase() || "other";
    if (!map[key]) map[key] = { category: key, count: 0, revenue_native: 0 };
    map[key].count += r.count;
    map[key].revenue_native += r.revenue_native;
  }
  const total = Object.values(map).reduce((s, r) => s + r.count, 0);
  return Object.values(map)
    .sort((a, b) => b.count - a.count)
    .map((r) => ({ ...r, pct: total > 0 ? (r.count / total) * 100 : 0 }));
}

export default function PerformanceWeekly() {
  const { branches, selected, isAll } = useBranch();

  // Build branchMap locally
  const branchMap = useMemo(() => {
    const m = {};
    for (const b of branches) {
      m[b.id] = { name: b.name, currency: b.native_currency || b.currency || "VND" };
    }
    return m;
  }, [branches]);

  const [weeklyByBranch, setWeeklyByBranch] = useState({}); // { branchId: [...] }
  const [otaMixByBranch, setOtaMixByBranch] = useState({}); // { branchId: [...] }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!branches.length) return;
    setLoading(true);

    // When a branch is selected, only fetch that branch; otherwise fetch all
    const targetBranches = !isAll && selected
      ? branches.filter((b) => b.id === selected)
      : branches;

    const weeklyFetches = targetBranches.map((b) =>
      axios.get(`/api/metrics/weekly?branch_id=${b.id}`).then((r) => [b.id, r.data.data || []])
    );
    const otaFetches = targetBranches.map((b) =>
      axios.get(`/api/metrics/ota-mix?branch_id=${b.id}`).then((r) => [b.id, r.data.data || []])
    );

    Promise.all([Promise.all(weeklyFetches), Promise.all(otaFetches)])
      .then(([weeklyResults, otaResults]) => {
        const wMap = {};
        for (const [id, rows] of weeklyResults) wMap[id] = rows;
        setWeeklyByBranch(wMap);

        const oMap = {};
        for (const [id, rows] of otaResults) oMap[id] = mergeOtaMix(rows);
        setOtaMixByBranch(oMap);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [branches, selected, isAll]);

  // Build combined chart data: all branches, keyed by week_start (VND for comparison)
  const revenueChartData = useMemo(() => {
    const dateSet = new Set();
    for (const rows of Object.values(weeklyByBranch)) {
      rows.forEach((r) => dateSet.add(r.week_start));
    }
    return [...dateSet].sort().map((week) => {
      const row = { week };
      for (const [bid, rows] of Object.entries(weeklyByBranch)) {
        const found = rows.find((r) => r.week_start === week);
        row[bid] = found ? found.revenue_native : 0;
      }
      return row;
    });
  }, [weeklyByBranch]);

  const cancelChartData = useMemo(() => {
    const dateSet = new Set();
    for (const rows of Object.values(weeklyByBranch)) {
      rows.forEach((r) => dateSet.add(r.week_start));
    }
    return [...dateSet].sort().map((week) => {
      const row = { week };
      for (const [bid, rows] of Object.entries(weeklyByBranch)) {
        const found = rows.find((r) => r.week_start === week);
        row[bid] = found ? +((found.cancellation_pct || 0) * 100).toFixed(1) : 0;
      }
      return row;
    });
  }, [weeklyByBranch]);

  const branchIds = useMemo(() => Object.keys(weeklyByBranch), [weeklyByBranch]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-xl font-bold text-gray-800">Weekly Brief</h1></div>
        <div className="text-gray-400 animate-pulse">Loading…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-800">Weekly Brief</h1>
        <p className="text-sm text-gray-500">Last 13 weeks — revenue, cancellations, OTA mix by branch</p>
      </div>

      {/* Revenue trend */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <p className="text-sm font-semibold text-gray-700 mb-3">Weekly Revenue by Branch</p>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={revenueChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} tickFormatter={(v) => v?.slice(5)} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => fmtCompact(v, "VND")} width={48} />
            <Tooltip
              formatter={(v, name) => {
                const branch = branchMap[name];
                return [fmtCompact(v, branch?.currency || "VND"), branch?.name || name];
              }}
              labelFormatter={(l) => `Week of ${l}`}
            />
            <Legend formatter={(id) => branchMap[id]?.name || id} />
            {branchIds.map((id, i) => (
              <Bar key={id} dataKey={id} fill={BRANCH_COLORS[i % BRANCH_COLORS.length]} radius={[2,2,0,0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cancellation % */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <p className="text-sm font-semibold text-gray-700 mb-3">Weekly Cancellation % by Branch</p>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={cancelChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} tickFormatter={(v) => v?.slice(5)} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} width={40} />
            <Tooltip
              formatter={(v, name) => [`${v}%`, branchMap[name]?.name || name]}
              labelFormatter={(l) => `Week of ${l}`}
            />
            <Legend formatter={(id) => branchMap[id]?.name || id} />
            {branchIds.map((id, i) => (
              <Line
                key={id}
                dataKey={id}
                stroke={BRANCH_COLORS[i % BRANCH_COLORS.length]}
                dot={false}
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* OTA Mix per branch */}
      <div>
        <p className="text-sm font-semibold text-gray-700 mb-3">OTA vs Direct Mix (Last 30 days)</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {branchIds.map((bid) => {
            const mix = otaMixByBranch[bid] || [];
            const branch = branchMap[bid];
            if (!mix.length) return null;
            return (
              <div key={bid} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <p className="text-xs font-semibold text-gray-600 mb-2">{branch?.name}</p>
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie
                      data={mix}
                      dataKey="count"
                      nameKey="category"
                      cx="50%"
                      cy="50%"
                      outerRadius={60}
                      label={({ category, pct }) => `${pct.toFixed(0)}%`}
                      labelLine={false}
                    >
                      {mix.map((_, i) => (
                        <Cell key={i} fill={OTA_COLORS[i % OTA_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, name) => [`${v} bookings`, name]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-2 mt-1">
                  {mix.map((o, i) => (
                    <span key={o.category} className="flex items-center gap-1 text-xs text-gray-500">
                      <span className="w-2 h-2 rounded-full inline-block" style={{ background: OTA_COLORS[i % OTA_COLORS.length] }} />
                      {o.category} {o.pct.toFixed(0)}%
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
