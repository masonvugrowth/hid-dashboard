import { NavLink, useLocation } from "react-router-dom";

const NAV = [
  {
    label: "Overview",
    items: [
      { to: "/home", label: "Home", icon: "⊞" },
    ],
  },
  {
    label: "Performance",
    items: [
      { to: "/performance",         label: "Summary",  icon: "▦" },
      { to: "/performance/daily",   label: "Daily",    icon: "▤" },
      { to: "/performance/weekly",  label: "Weekly",   icon: "▥" },
      { to: "/performance/monthly", label: "Monthly",  icon: "▧" },
      { to: "/performance/ota",     label: "OTA Mix",  icon: "◈" },
    ],
  },
  {
    label: "Strategy",
    items: [
      { to: "/kpi",           label: "KPI Dashboard",    icon: "◎" },
      { to: "/kpi-targets",   label: "Set Targets",      icon: "◌" },
      { to: "/countries",     label: "Countries",        icon: "◉" },
      { to: "/country-intel", label: "Country Intel",    icon: "◍" },
    ],
  },
  {
    label: "Marketing",
    items: [
      { to: "/marketing", label: "Activity Log", icon: "◆" },
      { to: "/ads",       label: "Paid Ads",     icon: "◇" },
      { to: "/kol",       label: "KOL",          icon: "◈" },
      { to: "/angles",    label: "Ad Angles",    icon: "◐" },
      { to: "/insights",  label: "Insights",     icon: "◑" },
    ],
  },
  {
    label: "Reports",
    items: [
      { to: "/report", label: "Weekly Report", icon: "◻" },
    ],
  },
  {
    label: "Admin",
    items: [
      { to: "/settings", label: "Settings", icon: "⚙" },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="w-52 bg-gray-900 text-white flex flex-col shrink-0">
      {/* Brand */}
      <div className="px-5 py-4 border-b border-gray-700">
        <span className="text-base font-bold tracking-wide">HiD</span>
        <p className="text-xs text-gray-400 mt-0.5">Hotel Intelligence</p>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 px-2 py-3 space-y-3 overflow-y-auto">
        {NAV.map(({ label, items }) => (
          <div key={label}>
            <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
              {label}
            </p>
            <div className="space-y-0.5">
              {items.map(({ to, label: itemLabel, icon }) => {
                const isPerformanceParent =
                  to === "/performance" && location.pathname.startsWith("/performance");
                return (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/performance"}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
                        isActive || isPerformanceParent
                          ? "bg-indigo-600 text-white"
                          : "text-gray-400 hover:bg-gray-700 hover:text-white"
                      }`
                    }
                  >
                    <span className="text-xs w-3 text-center">{icon}</span>
                    {itemLabel}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-2.5 border-t border-gray-700 text-xs text-gray-500">
        v1.3
      </div>
    </aside>
  );
}
