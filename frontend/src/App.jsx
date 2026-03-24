import { Routes, Route, Navigate } from "react-router-dom";
import { BranchProvider } from "./context/BranchContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Sidebar from "./components/Sidebar";
import BranchSelector from "./components/BranchSelector";
import Login from "./pages/Login";

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
import Users     from "./pages/Users";

// Phase 4 — Creative Intelligence Library
import AdCombos          from "./pages/AdCombos";
import AdAnalyzer        from "./pages/AdAnalyzer";
import CreativeCopies    from "./pages/CreativeCopies";
import CreativeMaterials from "./pages/CreativeMaterials";

// CRM Dashboard
import CRMDashboard from "./pages/CRMDashboard";

export default function App() {
  return (
    <AuthProvider>
      <BranchProvider>
        <AppRoutes />
      </BranchProvider>
    </AuthProvider>
  );
}

function AppRoutes() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500 text-sm animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*"      element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <BranchSelector />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/home" replace />} />
            <Route path="/login" element={<Navigate to="/home" replace />} />

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

            {/* Phase 4 — Creative Intelligence Library */}
            <Route path="/combos"       element={<AdCombos />} />
            <Route path="/ad-analyzer" element={<AdAnalyzer />} />
            <Route path="/copies"      element={<CreativeCopies />} />
            <Route path="/materials" element={<CreativeMaterials />} />

            {/* CRM Dashboard */}
            <Route path="/crm" element={<CRMDashboard />} />

            {/* Settings & Admin */}
            <Route path="/settings" element={<Settings />} />
            <Route path="/users"    element={<Users />} />

            {/* Phase 1 legacy */}
            <Route path="/dashboard"    element={<Dashboard />} />
            <Route path="/reservations" element={<Reservations />} />
            <Route path="/kpi-targets"  element={<KPITargets />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
