import { useState } from "react";
import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import { getRole, setRole } from "./api.js";
import Queue from "./pages/Queue.jsx";
import CaseDetail from "./pages/CaseDetail.jsx";
import Review from "./pages/Review.jsx";

const ROLES = ["clinician", "reviewer", "admin"];

function RoleSwitch() {
  const [role, setLocal] = useState(getRole());
  return (
    <label className="flex items-center gap-2 text-sm text-slate-600">
      Role
      <select
        value={role}
        onChange={(e) => { setRole(e.target.value); setLocal(e.target.value); window.location.reload(); }}
        className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
      >
        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
    </label>
  );
}

function TopNav() {
  const link = ({ isActive }) =>
    `px-3 py-2 text-sm font-medium rounded ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <div className="flex items-center gap-6">
        <span className="font-semibold text-slate-900">PA Console</span>
        <nav className="flex gap-1">
          <NavLink to="/queue" className={link}>Queue</NavLink>
          <NavLink to="/review" className={link}>Review</NavLink>
        </nav>
      </div>
      <RoleSwitch />
    </header>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <TopNav />
      <main className="mx-auto max-w-6xl px-6 py-6">
        <Routes>
          <Route path="/" element={<Navigate to="/queue" replace />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/cases/:id" element={<CaseDetail />} />
          <Route path="/review" element={<Review />} />
        </Routes>
      </main>
    </div>
  );
}
