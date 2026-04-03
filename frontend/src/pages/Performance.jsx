/**
 * Performance Hub — links to sub-pages + KPI Target vs Actual grid (editable)
 */
import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";

const CARDS = [
  { to: "/performance/daily", title: "Daily Brief", desc: "OCC%, Revenue, ADR, RevPAR per branch", color: "bg-indigo-50 border-indigo-200", icon: "\uD83D\uDCC5" },
  { to: "/performance/weekly", title: "Weekly Brief", desc: "Revenue trend, cancellation %, OTA mix", color: "bg-emerald-50 border-emerald-200", icon: "\uD83D\uDCCA" },
  { to: "/performance/monthly", title: "Monthly Brief", desc: "OCC/Revenue/ADR/RevPAR + country breakdown", color: "bg-amber-50 border-amber-200", icon: "\uD83D\uDDD3\uFE0F" },
  { to: "/performance/ota", title: "OTA Channel Mix", desc: "OTA vs Direct split by bookings and revenue", color: "bg-rose-50 border-rose-200", icon: "\uD83D\uDD00" },
];

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function fmtNum(val) {
  if (val == null || val === 0) return "\u2014";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

function hitColor(pct) {
  if (pct == null) return "";
  if (pct >= 100) return "bg-green-100 text-green-800";
  if (pct >= 80) return "bg-yellow-50 text-yellow-700";
  return "bg-red-50 text-red-700";
}

function hitBg(pct) {
  if (pct == null) return "";
  if (pct >= 100) return "bg-green-50";
  if (pct >= 80) return "bg-yellow-50/50";
  if (pct > 0) return "bg-red-50/50";
  return "";
}

export default function Performance() {
  const { isAll, selected } = useBranch();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [grid, setGrid] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params = { year };
    if (!isAll && selected) params.branch_id = selected;
    axios.get("/api/kpi/yearly-grid", { params })
      .then((r) => setGrid(r.data.data))
      .catch(() => setGrid(null))
      .finally(() => setLoading(false));
  }, [year, selected, isAll]);

  useEffect(load, [load]);

  const branches = grid?.branches || [];
  const months = grid?.months || [];
  const totals = grid?.totals || [];

  const handleSaveActual = (branchId, month, value) => {
    axios.put("/api/kpi/actual-override", {
      branch_id: branchId,
      year,
      month,
      actual_revenue: value,
    }).then(() => load());
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Performance Hub</h1>
        <p className="text-sm text-gray-500">Daily, weekly, and monthly briefs</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {CARDS.map(({ to, title, desc, color, icon }) => (
          <Link key={to} to={to}
            className={`rounded-xl border p-6 ${color} hover:shadow-md transition-shadow`}>
            <div className="text-2xl mb-2">{icon}</div>
            <h2 className="text-base font-semibold text-gray-800">{title}</h2>
            <p className="text-sm text-gray-500 mt-1">{desc}</p>
          </Link>
        ))}
      </div>

      {/* KPI Target vs Actual Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-800">Revenue KPI</h2>
            <p className="text-xs text-gray-400">Click on Actual cells to edit (accounting override)</p>
          </div>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}
            className="border rounded px-3 py-1.5 text-sm font-medium">
            {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="text-center text-gray-400 py-12 text-sm animate-pulse">Loading...</div>
        ) : !grid || branches.length === 0 ? (
          <div className="text-center text-gray-400 py-12 text-sm">No KPI data available for {year}.</div>
        ) : (
          <div className="bg-white rounded-lg border overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-900 text-white">
                  <th className="px-4 py-2.5 text-left font-semibold sticky left-0 bg-gray-900 z-10">{year}</th>
                  {branches.map((b) => (
                    <th key={b.id} colSpan={3} className="px-2 py-2.5 text-center font-semibold border-l border-gray-700">
                      {b.name.replace("HiD ", "")}
                    </th>
                  ))}
                </tr>
                <tr className="bg-gray-100">
                  <th className="px-4 py-2 text-left text-xs text-gray-500 font-medium sticky left-0 bg-gray-100 z-10">Month</th>
                  {branches.map((b) => [
                    <th key={b.id + "-t"} className="px-2 py-2 text-right text-xs text-gray-500 font-medium border-l border-gray-200">Target</th>,
                    <th key={b.id + "-a"} className="px-2 py-2 text-right text-xs text-gray-500 font-medium">Actual</th>,
                    <th key={b.id + "-h"} className="px-2 py-2 text-center text-xs text-gray-500 font-medium">Hit %</th>,
                  ])}
                </tr>
              </thead>
              <tbody>
                {months.map((row) => (
                  <tr key={row.month} className="border-t border-gray-100 hover:bg-gray-50/50">
                    <td className="px-4 py-2 font-medium text-gray-700 sticky left-0 bg-white z-10">
                      {MONTHS[row.month]}
                    </td>
                    {row.branches.map((bd, bi) => (
                      <BranchCells
                        key={bd.branch_id}
                        data={bd}
                        currency={branches[bi]?.currency}
                        month={row.month}
                        onSave={handleSaveActual}
                      />
                    ))}
                  </tr>
                ))}
                <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
                  <td className="px-4 py-2.5 font-bold text-gray-900 sticky left-0 bg-gray-50 z-10">Total</td>
                  {totals.map((td, bi) => (
                    <BranchCells key={td.branch_id} data={td} currency={branches[bi]?.currency} isTotal />
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function BranchCells({ data, currency, isTotal, month, onSave }) {
  const sym = CURRENCY_SYMBOLS[currency] || "";
  const hc = hitColor(data.hit_pct);
  const bg = isTotal ? "" : hitBg(data.hit_pct);
  const [editing, setEditing] = useState(false);
  const [editVal, setEditVal] = useState("");

  const startEdit = () => {
    if (isTotal || !onSave) return;
    setEditVal(data.actual > 0 ? String(Math.round(data.actual)) : "");
    setEditing(true);
  };

  const save = () => {
    setEditing(false);
    const num = parseFloat(editVal.replace(/,/g, ""));
    if (isNaN(num) && editVal !== "") return;
    // Empty = clear override (revert to Cloudbeds)
    onSave(data.branch_id, month, editVal === "" ? null : num);
  };

  const handleKey = (e) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") setEditing(false);
  };

  return (
    <>
      <td className={`px-2 py-2 text-right tabular-nums border-l border-gray-100 ${bg}`}>
        {data.target > 0 ? sym + fmtNum(data.target) : <span className="text-gray-300">{"\u2014"}</span>}
      </td>
      <td
        className={`px-2 py-2 text-right tabular-nums ${bg} ${!isTotal ? "cursor-pointer hover:bg-indigo-50" : ""}`}
        onClick={startEdit}
        title={!isTotal ? (data.is_override ? "Manually overridden (click to edit)" : "Click to override Cloudbeds value") : undefined}
      >
        {editing ? (
          <input
            type="text"
            value={editVal}
            onChange={(e) => setEditVal(e.target.value)}
            onBlur={save}
            onKeyDown={handleKey}
            autoFocus
            className="w-24 px-1 py-0.5 text-right text-sm border border-indigo-400 rounded outline-none"
          />
        ) : (
          <span className={data.is_override ? "border-b border-dashed border-indigo-400" : ""}>
            {data.actual > 0 ? sym + fmtNum(data.actual) : <span className="text-gray-300">{"\u2014"}</span>}
          </span>
        )}
      </td>
      <td className={`px-2 py-2 text-center tabular-nums ${bg}`}>
        {data.hit_pct != null ? (
          <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${hc}`}>
            {data.hit_pct.toFixed(1)}%
          </span>
        ) : (
          <span className="text-gray-300">{"\u2014"}</span>
        )}
      </td>
    </>
  );
}
