import { useState, useEffect, useMemo } from "react";
import { getSeasonMatrix, getCountryHolidays, getMonthOpportunities, getUpcomingWindows, getCrossReference } from "../api/holidayIntel";

/* ── Country metadata ──────────────────────────────────────────────────── */
const COUNTRIES_TOP15 = [
  "VN","TW","JP","KR","CN","US","AU","TH","SG","MY","HK","IN","ID","PH","CA",
];
const COUNTRIES_EU = ["GB","FR","DE","NL","ES","IT","CH","SE","DK","NO"];
const ALL_COUNTRIES = [...COUNTRIES_TOP15, ...COUNTRIES_EU];

const COUNTRY_NAME = {
  VN:"Vietnam",TW:"Taiwan",JP:"Japan",KR:"South Korea",CN:"China",
  US:"USA",AU:"Australia",TH:"Thailand",SG:"Singapore",MY:"Malaysia",
  HK:"Hong Kong",IN:"India",ID:"Indonesia",PH:"Philippines",CA:"Canada",
  GB:"United Kingdom",FR:"France",DE:"Germany",NL:"Netherlands",ES:"Spain",
  IT:"Italy",CH:"Switzerland",SE:"Sweden",DK:"Denmark",NO:"Norway",
};

const FLAG = {
  VN:"\u{1F1FB}\u{1F1F3}",TW:"\u{1F1F9}\u{1F1FC}",JP:"\u{1F1EF}\u{1F1F5}",
  KR:"\u{1F1F0}\u{1F1F7}",CN:"\u{1F1E8}\u{1F1F3}",US:"\u{1F1FA}\u{1F1F8}",
  AU:"\u{1F1E6}\u{1F1FA}",TH:"\u{1F1F9}\u{1F1ED}",SG:"\u{1F1F8}\u{1F1EC}",
  MY:"\u{1F1F2}\u{1F1FE}",HK:"\u{1F1ED}\u{1F1F0}",IN:"\u{1F1EE}\u{1F1F3}",
  ID:"\u{1F1EE}\u{1F1E9}",PH:"\u{1F1F5}\u{1F1ED}",CA:"\u{1F1E8}\u{1F1E6}",
  GB:"\u{1F1EC}\u{1F1E7}",FR:"\u{1F1EB}\u{1F1F7}",DE:"\u{1F1E9}\u{1F1EA}",
  NL:"\u{1F1F3}\u{1F1F1}",ES:"\u{1F1EA}\u{1F1F8}",IT:"\u{1F1EE}\u{1F1F9}",
  CH:"\u{1F1E8}\u{1F1ED}",SE:"\u{1F1F8}\u{1F1EA}",DK:"\u{1F1E9}\u{1F1F0}",
  NO:"\u{1F1F3}\u{1F1F4}",
};

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const PEAK_COLOR = { PEAK: "bg-green-600 text-white", SHOULDER: "bg-yellow-400 text-gray-900", OFF: "bg-gray-100 text-gray-400" };
const PEAK_DOT = { PEAK: "bg-green-500", SHOULDER: "bg-yellow-400", OFF: "bg-gray-300" };

/* ── PropensityBadge ─────────────────────────────────────────────────── */
function PropBadge({ level }) {
  const cls = level === "HIGH" ? "bg-green-100 text-green-700" : level === "MEDIUM" ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-500";
  return <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${cls}`}>{level}</span>;
}

/* ═══════════════════════════════════════════════════════════════════════ */
export default function HolidayIntel() {
  const [matrix, setMatrix] = useState([]);
  const [upcoming, setUpcoming] = useState([]);
  const [countryHolidays, setCountryHolidays] = useState([]);
  const [monthData, setMonthData] = useState([]);
  const [crossRef, setCrossRef] = useState([]);       // 12-month cross-reference for selected country
  const [loading, setLoading] = useState(true);

  // Filters
  const [filter, setFilter] = useState("all");       // "top15" | "europe" | "all"
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [selectedCountry, setSelectedCountry] = useState("JP");

  // ── Load initial data ─────────────────────────────────────────────
  useEffect(() => {
    Promise.all([getSeasonMatrix(), getUpcomingWindows()])
      .then(([m, u]) => { setMatrix(m); setUpcoming(u); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Load month data when selectedMonth changes ────────────────────
  useEffect(() => {
    getMonthOpportunities(selectedMonth).then(setMonthData).catch(() => {});
  }, [selectedMonth]);

  // ── Load country detail + cross-reference when selectedCountry changes
  useEffect(() => {
    getCountryHolidays(selectedCountry).then(setCountryHolidays).catch(() => {});
    // Load cross-reference for all 12 months
    Promise.all(
      Array.from({ length: 12 }, (_, i) => getCrossReference(selectedCountry, i + 1).catch(() => null))
    ).then(results => setCrossRef(results.filter(Boolean)));
  }, [selectedCountry]);

  // ── Build heatmap grid ────────────────────────────────────────────
  const heatmapCountries = useMemo(() => {
    if (filter === "top15") return COUNTRIES_TOP15;
    if (filter === "europe") return COUNTRIES_EU;
    return ALL_COUNTRIES;
  }, [filter]);

  const matrixMap = useMemo(() => {
    const m = {};
    matrix.forEach(r => { m[`${r.country_code}_${r.month}`] = r; });
    return m;
  }, [matrix]);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-gray-400 text-sm animate-pulse">Loading Holiday Intelligence...</div>;
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Holiday Intelligence</h1>
        <p className="text-sm text-gray-500 mt-1">Country travel season planner — campaign timing guide across 25 source markets</p>
      </div>

      {/* ═══ Section 1: Season Heatmap ═════════════════════════════════ */}
      <section className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Season Heatmap</h2>
          <div className="flex gap-1">
            {[["all","All 25"],["top15","Top 15"],["europe","Europe"]].map(([k,l]) => (
              <button key={k} onClick={() => setFilter(k)}
                className={`px-3 py-1 text-xs rounded font-medium transition-colors ${filter === k ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                {l}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="text-left py-2 px-2 font-semibold text-gray-600 sticky left-0 bg-white z-10 w-32">Country</th>
                {MONTHS.map((m,i) => (
                  <th key={i} className={`text-center py-2 px-1 font-medium w-16 ${i+1 === new Date().getMonth()+1 ? "text-indigo-600 font-bold" : "text-gray-500"}`}>{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmapCountries.map(code => (
                <tr key={code} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="py-1.5 px-2 sticky left-0 bg-white z-10">
                    <button onClick={() => setSelectedCountry(code)} className="flex items-center gap-1.5 hover:text-indigo-600 transition-colors">
                      <span className="text-sm">{FLAG[code]}</span>
                      <span className="font-medium text-gray-700">{COUNTRY_NAME[code]}</span>
                    </button>
                  </td>
                  {Array.from({length:12},(_,i)=>i+1).map(m => {
                    const cell = matrixMap[`${code}_${m}`];
                    const label = cell?.peak_label || "OFF";
                    return (
                      <td key={m} className="text-center py-1.5 px-0.5" title={cell ? `Score: ${cell.season_score} | ${(cell.holiday_names||[]).join(", ")}` : "No data"}>
                        <div className={`mx-auto w-12 py-1 rounded text-xs font-semibold ${PEAK_COLOR[label]}`}>
                          {cell ? cell.season_score.toFixed(1) : "—"}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-green-600" /> PEAK (7+)</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-yellow-400" /> SHOULDER (4–6.9)</span>
          <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded bg-gray-100 border" /> OFF (&lt;4)</span>
        </div>
      </section>

      {/* ═══ Section 2: Month Spotlight ════════════════════════════════ */}
      <section className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Month Spotlight</h2>
          <select value={selectedMonth} onChange={e => setSelectedMonth(+e.target.value)}
            className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
            {MONTHS.map((m,i) => <option key={i} value={i+1}>{m}</option>)}
          </select>
        </div>
        {monthData.length > 0 && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-indigo-800">
              Consider launching campaigns for these markets <strong>4–6 weeks before {MONTHS[selectedMonth-1]}</strong> to capture peak travel intent.
            </p>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {monthData.map(r => (
            <div key={r.country_code} className="border border-gray-200 rounded-lg p-3 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-2">
                <span className="flex items-center gap-1.5">
                  <span className="text-lg">{FLAG[r.country_code]}</span>
                  <span className="font-semibold text-gray-800">{COUNTRY_NAME[r.country_code]}</span>
                </span>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${r.peak_label === "PEAK" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${PEAK_DOT[r.peak_label]}`} />
                  {r.peak_label}
                </span>
              </div>
              <p className="text-xs text-gray-500">Score: {r.season_score.toFixed(1)} | {r.holiday_count} holidays | {r.long_holiday_days}d long</p>
              {r.holiday_names?.length > 0 && (
                <p className="text-xs text-gray-600 mt-1">{r.holiday_names.join(", ")}</p>
              )}
            </div>
          ))}
          {monthData.length === 0 && (
            <p className="text-sm text-gray-400 col-span-full text-center py-8">No PEAK or SHOULDER markets for {MONTHS[selectedMonth-1]}.</p>
          )}
        </div>
      </section>

      {/* ═══ Section 3: Country Deep Dive ═════════════════════════════ */}
      <section className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Country Deep Dive</h2>
          <select value={selectedCountry} onChange={e => setSelectedCountry(e.target.value)}
            className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500">
            {ALL_COUNTRIES.map(c => <option key={c} value={c}>{FLAG[c]} {COUNTRY_NAME[c]}</option>)}
          </select>
        </div>

        {/* 12-month timeline */}
        <div className="flex gap-0.5 mb-4">
          {Array.from({length:12},(_,i)=>i+1).map(m => {
            const cell = matrixMap[`${selectedCountry}_${m}`];
            const label = cell?.peak_label || "OFF";
            return (
              <div key={m} className="flex-1 text-center">
                <div className={`h-6 rounded-sm flex items-center justify-center text-xs font-semibold ${PEAK_COLOR[label]}`}>
                  {MONTHS[m-1]}
                </div>
              </div>
            );
          })}
        </div>

        {/* Holiday cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {countryHolidays.map(h => (
            <div key={h.id} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-start justify-between mb-1">
                <h3 className="font-semibold text-gray-800 text-sm">{h.holiday_name}</h3>
                <PropBadge level={h.travel_propensity} />
              </div>
              <p className="text-xs text-gray-500">
                {MONTHS[h.month_start-1]}{h.day_start ? ` ${h.day_start}` : ""} – {MONTHS[h.month_end-1]}{h.day_end ? ` ${h.day_end}` : ""} ({h.duration_days}d)
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs text-gray-400">{h.holiday_type}</span>
                {h.is_long_holiday && <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded font-medium">Long Holiday</span>}
              </div>
              {h.days_until_next != null && h.days_until_next >= 0 && (
                <p className={`text-xs mt-1.5 font-medium ${h.days_until_next <= 30 ? "text-red-600" : h.days_until_next <= 60 ? "text-orange-600" : "text-gray-500"}`}>
                  {h.days_until_next === 0 ? "Today!" : `${h.days_until_next}d away`}
                </p>
              )}
              {h.notes && <p className="text-xs text-gray-400 mt-1">{h.notes}</p>}
            </div>
          ))}
        </div>

        {/* Cross-reference panel: Actual bookings vs expected pattern */}
        {crossRef.length > 0 && (
          <div className="mt-5 border border-gray-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-3">Actual Bookings vs Expected Pattern</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="py-2 px-2 text-left font-medium text-gray-500 w-20">Month</th>
                    <th className="py-2 px-2 text-center font-medium text-gray-500">Expected</th>
                    <th className="py-2 px-2 text-center font-medium text-gray-500">Actual</th>
                    <th className="py-2 px-2 text-right font-medium text-gray-500">Bookings</th>
                    <th className="py-2 px-2 text-right font-medium text-gray-500">Avg</th>
                    <th className="py-2 px-2 text-center font-medium text-gray-500">Status</th>
                    <th className="py-2 px-2 text-left font-medium text-gray-500">Holidays</th>
                  </tr>
                </thead>
                <tbody>
                  {crossRef.map(cr => (
                    <tr key={cr.month} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-1.5 px-2 font-medium text-gray-700">{MONTHS[cr.month - 1]}</td>
                      <td className="py-1.5 px-2 text-center">
                        {cr.expected_peak
                          ? <span className="bg-green-100 text-green-700 px-1.5 py-0.5 rounded text-xs font-semibold">PEAK</span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="py-1.5 px-2 text-center">
                        {cr.actual_peak
                          ? <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs font-semibold">PEAK</span>
                          : <span className="text-gray-400">—</span>}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono text-gray-700">{cr.booking_count}</td>
                      <td className="py-1.5 px-2 text-right font-mono text-gray-400">{cr.avg_monthly_bookings}</td>
                      <td className="py-1.5 px-2 text-center">
                        {cr.match
                          ? <span className="text-green-600 font-semibold" title="Holiday peak matches booking peak">&#10003;</span>
                          : cr.expected_peak && !cr.actual_peak
                            ? <span className="text-orange-500 font-semibold" title="Holiday peak but low bookings — untapped opportunity">&#9888;</span>
                            : <span className="text-blue-500 font-semibold" title="High bookings without holiday — may be event-driven">&#9679;</span>}
                      </td>
                      <td className="py-1.5 px-2 text-gray-500 truncate max-w-[180px]">{(cr.holiday_names || []).join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
              <span><span className="text-green-600 font-bold">&#10003;</span> Validated — peak matches bookings</span>
              <span><span className="text-orange-500 font-bold">&#9888;</span> Untapped — holiday peak, low bookings</span>
              <span><span className="text-blue-500 font-bold">&#9679;</span> Event-driven — high bookings, no holiday</span>
            </div>
          </div>
        )}
      </section>

      {/* ═══ Section 4: Upcoming Windows (Alert Panel) ════════════════ */}
      <section className="bg-white rounded-lg shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800">Upcoming Windows <span className="text-sm font-normal text-gray-400">(next 60 days)</span></h2>
          {upcoming.length > 0 && (
            <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-1 rounded-full">{upcoming.length} alerts</span>
          )}
        </div>
        {upcoming.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No holiday windows in the next 60 days.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {upcoming.map((w,i) => (
              <div key={i} className="border border-gray-200 rounded-lg p-3 hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-lg">{FLAG[w.country_code]}</span>
                  <span className="font-semibold text-gray-800 text-sm">{COUNTRY_NAME[w.country_code]}</span>
                </div>
                <p className="font-medium text-gray-700 text-sm">{w.holiday_name}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {MONTHS[w.month_start-1]}{w.day_start ? ` ${w.day_start}` : ""} – {MONTHS[w.month_end-1]}{w.day_end ? ` ${w.day_end}` : ""} ({w.duration_days}d)
                </p>
                <div className="flex items-center justify-between mt-2">
                  <PropBadge level={w.travel_propensity} />
                  <span className={`text-xs font-bold ${w.days_until <= 14 ? "text-red-600" : w.days_until <= 30 ? "text-orange-600" : "text-gray-600"}`}>
                    {w.days_until === 0 ? "Today!" : `in ${w.days_until}d`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
