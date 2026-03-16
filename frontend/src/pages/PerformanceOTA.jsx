/**
 * OTA Channel Mix — detailed OTA vs Direct + source breakdown
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { useBranch } from "../context/BranchContext";

const COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#3b82f6","#8b5cf6","#ec4899"];

export default function PerformanceOTA() {
  const { selected, isAll } = useBranch();
  const today = new Date().toISOString().slice(0, 10);
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 29);
    return d.toISOString().slice(0, 10);
  });
  const [dateTo,   setDateTo]   = useState(today);
  const [mix,      setMix]      = useState([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    setLoading(true);
    const bParam = !isAll && selected ? `&branch_id=${selected}` : "";
    axios.get(`/api/metrics/ota-mix?date_from=${dateFrom}&date_to=${dateTo}${bParam}`)
      .then((r) => setMix(r.data.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo, selected, isAll]);

  const totalCount   = mix.reduce((s, m) => s + m.count, 0);
  const totalRevenue = mix.reduce((s, m) => s + m.revenue_native, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">OTA Channel Mix</h1>
          <p className="text-sm text-gray-500">Booking source breakdown</p>
        </div>
        <div className="flex gap-2 items-center text-sm">
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5" />
          <span className="text-gray-400">→</span>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-1.5" />
        </div>
      </div>

      {loading ? (
        <div className="text-gray-400 animate-pulse">Loading…</div>
      ) : mix.length === 0 ? (
        <div className="bg-white rounded-xl border p-8 text-center text-gray-400">No data for this period.</div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <p className="text-xs text-gray-400 uppercase">Total Bookings</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">{totalCount.toLocaleString()}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
              <p className="text-xs text-gray-400 uppercase">Total Revenue</p>
              <p className="text-2xl font-bold text-gray-800 mt-1">
                {new Intl.NumberFormat("vi-VN").format(Math.round(totalRevenue))}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Pie by count */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <p className="text-sm font-semibold text-gray-700 mb-3">By Booking Count</p>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={mix} dataKey="count" nameKey="category"
                    cx="50%" cy="50%" outerRadius={80}
                    label={({ category, count_pct }) => `${category} ${(count_pct*100).toFixed(0)}%`}
                    labelLine={false}>
                    {mix.map((_, i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Bar by revenue */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <p className="text-sm font-semibold text-gray-700 mb-3">By Revenue</p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={mix} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }}
                    tickFormatter={(v) => new Intl.NumberFormat("vi-VN", { notation: "compact" }).format(v)} />
                  <YAxis type="category" dataKey="category" tick={{ fontSize: 12 }} width={60} />
                  <Tooltip formatter={(v) => new Intl.NumberFormat("vi-VN").format(Math.round(v))} />
                  <Bar dataKey="revenue_native" name="Revenue" radius={[0,4,4,0]}>
                    {mix.map((_, i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Table */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-4 py-3 text-left">Category</th>
                  <th className="px-4 py-3 text-right">Bookings</th>
                  <th className="px-4 py-3 text-right">Count %</th>
                  <th className="px-4 py-3 text-right">Revenue</th>
                  <th className="px-4 py-3 text-right">Revenue %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {mix.map((m, i) => (
                  <tr key={m.category} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-gray-700">
                      <span className="inline-block w-2 h-2 rounded-full mr-2"
                        style={{ background: COLORS[i%COLORS.length] }} />
                      {m.category}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-600">{m.count}</td>
                    <td className="px-4 py-2.5 text-right text-gray-500">{(m.count_pct*100).toFixed(1)}%</td>
                    <td className="px-4 py-2.5 text-right text-gray-700">
                      {new Intl.NumberFormat("vi-VN").format(Math.round(m.revenue_native))}
                    </td>
                    <td className="px-4 py-2.5 text-right text-gray-500">{(m.revenue_pct*100).toFixed(1)}%</td>
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
