/**
 * Marketing Activity — Consolidated view of Paid Ads, KOL, and CRM performance.
 * Currency: VND when "All Branches", native currency per branch.
 */
import { useEffect, useState, useMemo } from "react";
import { useBranch, CURRENCY_SYMBOLS } from "../context/BranchContext";
import { getMarketingActivitySummary } from "../api/marketingActivity";

function fmtNum(val) {
  if (val == null || val === 0) return "0";
  return new Intl.NumberFormat("en").format(Math.round(val));
}

function fmtMoney(val, cur) {
  if (val == null) return "\u2014";
  const sym = CURRENCY_SYMBOLS[cur] || "";
  return sym + new Intl.NumberFormat("en").format(Math.round(val));
}

function RoasBadge({ value }) {
  if (value == null || value === 0) return <span className="text-gray-400">{"\u2014"}</span>;
  const cls =
    value >= 3
      ? "text-green-700 bg-green-50"
      : value >= 1.5
      ? "text-yellow-700 bg-yellow-50"
      : "text-red-600 bg-red-50";
  return (
    <span className={"px-2 py-0.5 rounded text-xs font-semibold " + cls}>
      {value.toFixed(2)}x
    </span>
  );
}

function ActivityBadges({ activities }) {
  const colors = {
    "Paid Ads": "bg-blue-100 text-blue-700",
    KOL: "bg-purple-100 text-purple-700",
    CRM: "bg-emerald-100 text-emerald-700",
  };
  return (
    <div className="flex gap-1 flex-wrap">
      {activities.map((a) => (
        <span
          key={a}
          className={
            "px-2 py-0.5 rounded text-xs font-medium " +
            (colors[a] || "bg-gray-100 text-gray-600")
          }
        >
          {a}
        </span>
      ))}
    </div>
  );
}

function KPICard({ label, value, sub }) {
  return (
    <div className="bg-white rounded-lg border p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function MarketingActivity() {
  const { isAll, selected, currency: branchCurrency } = useBranch();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");

  const today = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const fmtDate = (d) =>
    d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());

  const [dateFrom, setDateFrom] = useState(
    fmtDate(new Date(today.getFullYear(), 0, 1))
  );
  const [dateTo, setDateTo] = useState(fmtDate(today));
  const [filterCountry, setFilterCountry] = useState("");

  const load = () => {
    setLoading(true);
    const params = {};
    if (!isAll && selected) params.branch_id = selected;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    getMarketingActivitySummary(params)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(load, [selected, isAll, dateFrom, dateTo]);

  // Currency: VND for all branches, native for single branch
  const cur = isAll ? "VND" : (data?.currency || branchCurrency || "VND");

  const overview = data?.overview;
  const monthly = data?.monthly_by_country || [];
  const suggestions = data?.kol_suggestions || [];

  const countries = useMemo(() => {
    const set = new Set(monthly.map((r) => r.country));
    return [...set].sort();
  }, [monthly]);

  const filteredMonthly = useMemo(() => {
    if (!filterCountry) return monthly;
    return monthly.filter((r) => r.country === filterCountry);
  }, [monthly, filterCountry]);

  const TABS = [
    { key: "overview", label: "Overview" },
    { key: "monthly", label: "Monthly by Country" },
    { key: "kol-suggest", label: "KOL Suggestions" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-bold text-gray-900">Marketing Activity</h1>
        <div className="flex items-center gap-2">
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
            className="border rounded px-2 py-1 text-sm" />
          <span className="text-gray-400">to</span>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
            className="border rounded px-2 py-1 text-sm" />
        </div>
      </div>

      <div className="flex gap-1 border-b">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-16 text-sm animate-pulse">Loading...</div>
      ) : !data ? (
        <div className="text-center text-gray-400 py-16 text-sm">No data available</div>
      ) : (
        <>
          {tab === "overview" && <OverviewTab overview={overview} cur={cur} />}
          {tab === "monthly" && (
            <MonthlyTab rows={filteredMonthly} countries={countries}
              filterCountry={filterCountry} setFilterCountry={setFilterCountry} cur={cur} />
          )}
          {tab === "kol-suggest" && <KOLSuggestTab rows={suggestions} />}
        </>
      )}
    </div>
  );
}

/* ── Overview Tab ──────────────────────────────────────────────────────────── */
function OverviewTab({ overview, cur }) {
  if (!overview) return null;
  const { paid_ads, kol, crm, total } = overview;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard label="Total Bookings" value={fmtNum(total.bookings)} />
        <KPICard label="Total Revenue" value={fmtMoney(total.revenue, cur)} />
        <KPICard label="Total Cost" value={fmtMoney(total.cost, cur)} />
        <KPICard label="Blended ROAS" value={total.roas ? total.roas.toFixed(2) + "x" : "\u2014"} />
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Source</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Bookings</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Revenue ({cur})</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Cost ({cur})</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">ROAS</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">
                <span className="inline-block w-2 h-2 rounded-full bg-blue-500 mr-2" />Paid Ads
              </td>
              <td className="px-4 py-3 text-right">{fmtNum(paid_ads.bookings)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(paid_ads.revenue)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(paid_ads.cost)}</td>
              <td className="px-4 py-3 text-right"><RoasBadge value={paid_ads.roas} /></td>
            </tr>
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">
                <span className="inline-block w-2 h-2 rounded-full bg-purple-500 mr-2" />KOL
              </td>
              <td className="px-4 py-3 text-right">{fmtNum(kol.bookings)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(kol.revenue)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(kol.cost)}</td>
              <td className="px-4 py-3 text-right">
                <RoasBadge value={kol.cost > 0 ? kol.revenue / kol.cost : null} />
              </td>
            </tr>
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-2" />CRM
              </td>
              <td className="px-4 py-3 text-right">{fmtNum(crm.bookings)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(crm.revenue)}</td>
              <td className="px-4 py-3 text-right text-gray-400">{"\u2014"}</td>
              <td className="px-4 py-3 text-right text-gray-400">{"\u2014"}</td>
            </tr>
            <tr className="bg-gray-50 font-semibold">
              <td className="px-4 py-3">Total</td>
              <td className="px-4 py-3 text-right">{fmtNum(total.bookings)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(total.revenue)}</td>
              <td className="px-4 py-3 text-right">{fmtNum(total.cost)}</td>
              <td className="px-4 py-3 text-right"><RoasBadge value={total.roas} /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Monthly by Country Tab ────────────────────────────────────────────────── */
function MonthlyTab({ rows, countries, filterCountry, setFilterCountry, cur }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-600">Country:</label>
        <select value={filterCountry} onChange={(e) => setFilterCountry(e.target.value)}
          className="border rounded px-2 py-1 text-sm">
          <option value="">All</option>
          {countries.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {rows.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-8">No marketing activity found for this period.</p>
      ) : (
        <div className="bg-white rounded-lg border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Month</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Activities</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Bookings</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Revenue ({cur})</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Cost ({cur})</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">ROAS</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((r, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-700">{r.month}</td>
                  <td className="px-4 py-3">{r.country}</td>
                  <td className="px-4 py-3"><ActivityBadges activities={r.activities} /></td>
                  <td className="px-4 py-3 text-right">{fmtNum(r.total_bookings)}</td>
                  <td className="px-4 py-3 text-right">{fmtNum(r.total_revenue)}</td>
                  <td className="px-4 py-3 text-right">
                    {r.total_cost > 0 ? fmtNum(r.total_cost) : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-right"><RoasBadge value={r.roas} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ── KOL Suggestions Tab ───────────────────────────────────────────────────── */
function KOLSuggestTab({ rows }) {
  if (rows.length === 0) {
    return (
      <p className="text-gray-400 text-sm text-center py-8">
        No KOL suggestions available. KOLs already used in paid ads are excluded.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        KOLs with organic bookings not yet used in Paid Ads — sorted by revenue.
      </p>
      <div className="bg-white rounded-lg border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">KOL</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Country</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Branch</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Organic Bookings</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Organic Revenue (VND)</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Nationality</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Usage Rights Until</th>
              <th className="text-center px-4 py-3 font-semibold text-gray-600">Ads Eligible</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((r, i) => (
              <tr key={i} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">
                  {r.kol_name.replace("KOL_", "")}
                </td>
                <td className="px-4 py-3">{r.country}</td>
                <td className="px-4 py-3 text-gray-600">{r.branch}</td>
                <td className="px-4 py-3 text-right font-medium">{fmtNum(r.organic_bookings)}</td>
                <td className="px-4 py-3 text-right">{fmtNum(r.organic_revenue_vnd)}</td>
                <td className="px-4 py-3 text-gray-600">{r.kol_nationality || "\u2014"}</td>
                <td className="px-4 py-3">
                  {r.usage_rights_until ? (
                    <span className={new Date(r.usage_rights_until) < new Date() ? "text-red-600" : "text-gray-700"}>
                      {r.usage_rights_until}
                    </span>
                  ) : <span className="text-gray-400">{"\u2014"}</span>}
                </td>
                <td className="px-4 py-3 text-center">
                  {r.paid_ads_eligible
                    ? <span className="text-green-600 font-medium">Yes</span>
                    : <span className="text-gray-400">No</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
