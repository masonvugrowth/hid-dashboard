/**
 * Country Reservations — Top 15 countries by reservation count.
 * Weekly + Monthly views with period-over-period comparison.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";

function fmtNum(val) {
  if (val == null || val === 0) return "0";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

function ChangeBadge({ current, previous }) {
  if (!previous || previous === 0) return null;
  const pct = ((current - previous) / previous) * 100;
  const isUp = pct > 0;
  const cls = isUp ? "text-green-600" : pct < 0 ? "text-red-600" : "text-gray-500";
  return (
    <span className={"text-xs font-medium " + cls}>
      {isUp ? "\u25B2" : pct < 0 ? "\u25BC" : ""}{Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function PctBar({ pct }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct.toFixed(1)}%</span>
    </div>
  );
}

export default function PerformanceCountry() {
  const { isAll, selected, currency: branchCurrency } = useBranch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("monthly");

  const today = new Date();
  const currentMonth = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0");
  const [month, setMonth] = useState(currentMonth);

  const cur = isAll ? "VND" : (branchCurrency || "VND");
  const sym = CURRENCY_SYMBOLS[cur] || "";

  const load = () => {
    setLoading(true);
    const params = { view, limit: 15 };
    if (!isAll && selected) params.branch_id = selected;
    if (view === "monthly") params.month = month;

    axios.get("/api/metrics/country-reservations", { params })
      .then((r) => setData(r.data.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(load, [selected, isAll, view, month]);

  const rows = data?.rows || [];
  const totalRes = data?.total_reservations || 0;
  const period = data?.period || "";
  const prevPeriod = data?.prev_period || "";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-bold text-gray-900">Country Reservations</h1>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex rounded-lg border overflow-hidden">
            {["weekly", "monthly"].map((v) => (
              <button key={v} onClick={() => setView(v)}
                className={`px-3 py-1.5 text-sm font-medium ${
                  view === v ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}>
                {v === "weekly" ? "Weekly" : "Monthly"}
              </button>
            ))}
          </div>
          {/* Month picker (only for monthly view) */}
          {view === "monthly" && (
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
              className="border rounded px-3 py-1.5 text-sm" />
          )}
        </div>
      </div>

      {/* Period label */}
      <div className="flex items-center gap-3 text-sm text-gray-500">
        <span>Period: <span className="font-medium text-gray-700">{period}</span></span>
        <span className="text-gray-300">|</span>
        <span>vs <span className="text-gray-600">{prevPeriod}</span></span>
        <span className="text-gray-300">|</span>
        <span>Total: <span className="font-semibold text-gray-700">{fmtNum(totalRes)}</span> reservations</span>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-16 text-sm animate-pulse">Loading...</div>
      ) : !data || rows.length === 0 ? (
        <div className="text-center text-gray-400 py-16 text-sm">No reservation data available for this period.</div>
      ) : (
        <div className="bg-white rounded-lg border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-center px-3 py-3 font-semibold text-gray-600 w-10">#</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Reservations</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Share</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Room Nights</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Revenue ({cur})</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">
                  vs {view === "monthly" ? "Prev Month" : "Prev Week"}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((r, i) => (
                <tr key={r.country_code} className="hover:bg-gray-50">
                  <td className="px-3 py-3 text-center text-gray-400 font-medium">{i + 1}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">{r.country}</td>
                  <td className="px-4 py-3 text-right font-semibold">{fmtNum(r.reservations)}</td>
                  <td className="px-4 py-3"><PctBar pct={r.pct_of_total || 0} /></td>
                  <td className="px-4 py-3 text-right">{fmtNum(r.room_nights)}</td>
                  <td className="px-4 py-3 text-right">{sym}{fmtNum(isAll ? r.revenue : r.revenue_native)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <span className="text-xs text-gray-400">{fmtNum(r.prev_reservations)}</span>
                      <ChangeBadge current={r.reservations} previous={r.prev_reservations} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
