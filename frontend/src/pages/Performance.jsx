/**
 * Performance Hub — links to Daily / Weekly / Monthly / OTA sub-pages
 */
import { Link } from "react-router-dom";

const CARDS = [
  {
    to: "/performance/daily",
    title: "Daily Brief",
    desc: "OCC%, Revenue, ADR, RevPAR per branch with color bands and event pins",
    color: "bg-indigo-50 border-indigo-200",
    icon: "📅",
  },
  {
    to: "/performance/weekly",
    title: "Weekly Brief",
    desc: "Revenue trend, cancellation %, OTA mix, conversion %",
    color: "bg-emerald-50 border-emerald-200",
    icon: "📊",
  },
  {
    to: "/performance/monthly",
    title: "Monthly Brief",
    desc: "OCC/Revenue/ADR/RevPAR + country breakdown multi-year",
    color: "bg-amber-50 border-amber-200",
    icon: "🗓️",
  },
  {
    to: "/performance/ota",
    title: "OTA Channel Mix",
    desc: "OTA vs Direct split by bookings and revenue",
    color: "bg-rose-50 border-rose-200",
    icon: "🔀",
  },
];

export default function Performance() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Performance Hub</h1>
        <p className="text-sm text-gray-500">Daily, weekly, and monthly briefs</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {CARDS.map(({ to, title, desc, color, icon }) => (
          <Link
            key={to}
            to={to}
            className={`rounded-xl border p-6 ${color} hover:shadow-md transition-shadow`}
          >
            <div className="text-2xl mb-2">{icon}</div>
            <h2 className="text-base font-semibold text-gray-800">{title}</h2>
            <p className="text-sm text-gray-500 mt-1">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
