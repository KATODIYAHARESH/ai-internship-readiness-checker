"use client";

import { useCallback, useMemo, useState } from "react";
import { assess, type Profile } from "@/lib/readiness/engine";
import { generateStudents } from "@/lib/readiness/cohort";
import AboutTab from "./AboutTab";
import DashboardTab from "./DashboardTab";
import MentorTab from "./MentorTab";
import StudentTab from "./StudentTab";

const TABS = [
  { id: "student", label: "🎓 Student" },
  { id: "dashboard", label: "🏫 Placement dashboard" },
  { id: "mentor", label: "🤖 AI mentor" },
  { id: "about", label: "ℹ️ About & run guide" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function ReadinessApp() {
  const students = useMemo(() => generateStudents(80, 42), []);
  const [tab, setTab] = useState<TabId>("student");
  const [profile, setProfile] = useState<Profile>(students[0]);
  const [role, setRole] = useState<string>(students[0].targetRole);

  const assessment = useMemo(() => assess(profile, role), [profile, role]);

  const selectStudent = useCallback(
    (id: number) => {
      const next = students.find((s) => s.id === id);
      if (next) {
        setProfile(next);
        setRole(next.targetRole);
      }
    },
    [students],
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">Use case 44 · Live web preview</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">🎯 AI Internship Readiness Checker</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Explainable, role-specific readiness scores · skill-gap action plans · placement analytics · AI mentor with rule-based fallback. Backed by 80 synthetic students.
        </p>
      </header>

      <nav className="mb-6 flex flex-wrap gap-1 border-b border-slate-200" role="tablist" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`-mb-px rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-medium transition ${
              tab === t.id ? "border-blue-600 bg-white text-blue-700" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "student" && (
          <StudentTab
            students={students}
            profile={profile}
            role={role}
            assessment={assessment}
            onSelectStudent={selectStudent}
            onProfileChange={setProfile}
            onRoleChange={setRole}
          />
        )}
        {tab === "dashboard" && <DashboardTab students={students} />}
        {tab === "mentor" && <MentorTab assessment={assessment} />}
        {tab === "about" && <AboutTab />}
      </main>

      <footer className="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-500">
        All data is synthetic. Scores are guidance for students, not hiring decisions. Full Python/Streamlit project: <code>internship-readiness-checker/</code>.
      </footer>
    </div>
  );
}
