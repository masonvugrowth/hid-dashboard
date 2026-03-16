import { Routes, Route, Navigate } from "react-router-dom";
import { BranchProvider } from "./context/BranchContext";
import Sidebar from "./components/Sidebar";
import BranchSelector from "./components/BranchSelector";

// Phase 1 pages
import Dashboard      from "./pages/Dashboard";
import Reservations   from "./pages/Reservations";
import KPITargets     from "./pages/KPITargets";

// Phase 2 pages
import Home              from "./pages/Home";
import KPI               from "./pages/KPI";
import Performance       from "./pages/Performance";
import PerformanceDaily  from "./pages/PerformanceDaily";
import PerformanceWeekly from "./pages/PerformanceWeekly";
import PerformanceMonthly from "./pages/PerformanceMonthly";
import PerformanceOTA    from "./pages/PerformanceOTA";
import Countries         from "./pages/Countries";
import CountryDetail     from "./pages/CountryDetail";

// Phase 3 pages
import CountryIntel from "./pages/CountryIntel";
import Ads      from "./pages/Ads";
import KOL      from "./pages/KOL";
import Marketing from "./pages/Marketing";
import Angles   from "./pages/Angles";
import Insights from "./pages/Insights";
import Report    from "./pages/Report";
import Settings  from "./pages/Settings";

export default function App() {
  return (
    <BranchProvider>
      <div className="flex h-screen bg-gray-50">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Global sticky branch selector */}
          <BranchSelector />
          {/* Page content */}
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/home" replace />} />

              {/* Phase 2 */}
              <Route path="/home"                  element={<Home />} />
              <Route path="/kpi"                   element={<KPI />} />
              <Route path="/performance"           element={<Performance />} />
              <Route path="/performance/daily"     element={<PerformanceDaily />} />
              <Route path="/performance/weekly"    element={<PerformanceWeekly />} />
              <Route path="/performance/monthly"   element={<PerformanceMonthly />} />
              <Route path="/performance/ota"       element={<PerformanceOTA />} />
              <Route path="/countries"             element={<Countries />} />
              <Route path="/countries/:code"       element={<CountryDetail />} />

              {/* Phase 3 — Marketing */}
              <Route path="/country-intel" element={<CountryIntel />} />
              <Route path="/marketing" element={<Marketing />} />
              <Route path="/ads"       element={<Ads />} />
              <Route path="/kol"       element={<KOL />} />
              <Route path="/angles"    element={<Angles />} />
              <Route path="/insights"  element={<Insights />} />
              <Route path="/report"    element={<Report />} />

              {/* Settings */}
              <Route path="/settings" element={<Settings />} />

              {/* Phase 1 legacy */}
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/reservations" element={<Reservations />} />
              <Route path="/kpi-targets"  element={<KPITargets />} />
            </Routes>
          </main>
        </div>
      </div>
    </BranchProvider>
  );
}

function ComingSoon({ title }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
      <div className="text-4xl mb-3">🚧</div>
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm mt-1">Coming in Phase 3</p>
    </div>
  );
}
