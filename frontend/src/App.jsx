import { NavLink, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage.jsx";
import CasePage from "./pages/CasePage.jsx";
import CaseHistoryPage from "./pages/CaseHistoryPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

function NavigationLink({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-2 text-sm font-medium ${
          isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-baseline gap-3">
            <span className="text-lg font-semibold tracking-tight">ClaimGuard</span>
            <span className="text-xs text-slate-500">Prior-authorization check for lumbar spine MRI</span>
          </div>
          <nav className="flex gap-1">
            <NavigationLink to="/">New check</NavigationLink>
            <NavigationLink to="/cases">Case history</NavigationLink>
            <NavigationLink to="/dashboard">Dashboard</NavigationLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/cases" element={<CaseHistoryPage />} />
          <Route path="/cases/:caseId" element={<CasePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
    </div>
  );
}
