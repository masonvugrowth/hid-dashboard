/**
 * KPI Page — editable predicted OCC% + current & next month forecasts
 */
import { useEffect, useState } from "react";
import axios from "axios";
import KPICard from "../components/KPICard";
import { useBranch } from "../context/BranchContext";

const MONTHS = [
  "Jan","Feb","Mar","Apr","May","Jun",
  "Jul","Aug","Sep","Oct","Nov","Dec",
];

export default function KPI() {
  const { selected, isAll } = useBranch();
  const now = new Date();
  const [year,  setYear]  = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data,  setData]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState({}); // { branchId: { cur: val, next: val } }

  const fetchData = () => {
    setLoading(true);
    const bParam = !isAll && selected ? `&branch_id=${selected}` : "";
    axios.get(`/api/kpi/summary?year=${year}&month=${month}${bParam}`)
      .then((r) => setData(r.data.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, [year, month, selected, isAll]);

  const handleOccChange = (branchId, field, val) => {
    setEditing((prev) => ({ ...prev, [branchId]: { ...prev[branchId], [field]: val } }));
  };

  const saveOcc = async (branchId, targetYear, targetMonth, field) => {
    const val = editing[branchId]?.[field];
    if (val === undefined) return;
    const pct = parseFloat(val) / 100;
    const res = await axios.get(`/api/kpi/targets?branch_id=${branchId}&year=${targetYear}`);
    const targets = res.data.data || [];
    const target = targets.find((t) => t.month === targetMonth);
    if (!target) return;
    await axios.patch(`/api/kpi/targets/${target.id}`, { predicted_occ_pct: pct });
    setEditing((prev) => {
      const n = { ...prev };
      if (n[branchId]) { delete n[branchId][field]; }
      return n;
    });
    fetchData();
  };

  return (
    <div className="space-y-6">
      {/* Header + selectors */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">KPI Dashboard</h1>
          <p className="text-sm text-gray-500">Revenue achievement + forecasts</p>
        </div>
        <div className="flex gap-2">
          <select
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            value={month}
            onChange={(e) => setMonth(+e.target.value)}
          >
            {MONTHS.map((m, i) => (
              <option key={i} value={i + 1}>{m}</option>
            ))}
          </select>
          <select
            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
            value={year}
            onChange={(e) => setYear(+e.target.value)}
          >
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-400 animate-pulse">Loading…</div>
      ) : data.length === 0 ? (
        <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
          No data. Add branches and set KPI targets first.
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((b) => (
            <div key={b.branch_id} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-base font-semibold text-gray-800">{b.branch_name}</h2>
                  <p className="text-xs text-gray-400">{b.branch_city} · {b.currency}</p>
                </div>
                {b.achievement_pct !== null && (
                  <span className={`text-sm font-bold px-3 py-1 rounded-full ${
                    b.achievement_pct >= 1   ? "bg-green-100 text-green-700"
                    : b.achievement_pct >= 0.8 ? "bg-yellow-100 text-yellow-700"
                    : "bg-red-100 text-red-700"
                  }`}>
                    {(b.achievement_pct * 100).toFixed(1)}% of target
                  </span>
                )}
              </div>

              {/* Revenue row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Actual Revenue</p>
                  <p className="font-semibold text-gray-800 mt-0.5">
                    {new Intl.NumberFormat("vi-VN").format(Math.round(b.actual_revenue_native))}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Target</p>
                  <p className="font-semibold text-gray-800 mt-0.5">
                    {b.target_revenue_native
                      ? new Intl.NumberFormat("vi-VN").format(Math.round(b.target_revenue_native))
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">This Month Forecast</p>
                  <p className="font-semibold text-indigo-600 mt-0.5">
                    {b.occ_forecast_native
                      ? new Intl.NumberFormat("vi-VN").format(Math.round(b.occ_forecast_native))
                      : "—"}
                  </p>
                  {b.avg_adr_native && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      ADR {new Intl.NumberFormat("vi-VN").format(Math.round(b.avg_adr_native))} · {b.nights_booked} nights booked
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide">Next Month Forecast</p>
                  <p className="font-semibold text-emerald-600 mt-0.5">
                    {b.next_month_forecast_native
                      ? new Intl.NumberFormat("vi-VN").format(Math.round(b.next_month_forecast_native))
                      : "—"}
                  </p>
                  {b.next_month_adr && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      ADR {new Intl.NumberFormat("vi-VN").format(Math.round(b.next_month_adr))} · {b.next_month_booked_nights} nights booked
                    </p>
                  )}
                </div>
              </div>

              {/* OCC editors */}
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Current month OCC */}
                <div className="flex items-center gap-3">
                  <p className="text-xs text-gray-500 whitespace-nowrap">This month OCC%:</p>
                  <input
                    type="number" min="0" max="100" step="0.1"
                    className="border border-gray-200 rounded-lg px-2 py-1 text-sm w-20 text-center"
                    defaultValue={b.predicted_occ_pct != null ? (b.predicted_occ_pct * 100).toFixed(1) : ""}
                    placeholder="—"
                    onChange={(e) => handleOccChange(b.branch_id, "cur", e.target.value)}
                  />
                  {editing[b.branch_id]?.cur !== undefined && (
                    <button
                      className="text-xs bg-indigo-600 text-white px-3 py-1 rounded-lg hover:bg-indigo-700"
                      onClick={() => saveOcc(b.branch_id, year, month, "cur")}
                    >Save</button>
                  )}
                  <p className="text-xs text-gray-400">({b.days_elapsed}/{b.total_days}d)</p>
                </div>

                {/* Next month OCC */}
                <div className="flex items-center gap-3">
                  <p className="text-xs text-gray-500 whitespace-nowrap">Next month OCC%:</p>
                  <input
                    type="number" min="0" max="100" step="0.1"
                    className="border border-gray-200 rounded-lg px-2 py-1 text-sm w-20 text-center"
                    defaultValue={b.predicted_occ_next != null ? (b.predicted_occ_next * 100).toFixed(1) : ""}
                    placeholder="—"
                    onChange={(e) => handleOccChange(b.branch_id, "next", e.target.value)}
                  />
                  {editing[b.branch_id]?.next !== undefined && (
                    <button
                      className="text-xs bg-emerald-600 text-white px-3 py-1 rounded-lg hover:bg-emerald-700"
                      onClick={() => saveOcc(b.branch_id, b.next_year, b.next_month, "next")}
                    >Save</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
