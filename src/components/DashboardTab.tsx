"use client";

import { useMemo, useState } from "react";
import { ROLE_NAMES, type Profile } from "@/lib/readiness/engine";
import { DEPARTMENTS, atRisk, byDepartment, kpis, scoreCohort, toCsv, topGaps } from "@/lib/readiness/cohort";
import { Card, LevelBadge, Metric, downloadText, inputCls } from "./ui";

export default function DashboardTab({ students }: { students: Profile[] }) {
  const [mode, setMode] = useState<"own" | "single">("own");
  const [role, setRole] = useState(ROLE_NAMES[0]);
  const [threshold, setThreshold] = useState(50);
  const [selected, setSelected] = useState<string[]>(DEPARTMENTS);

  const all = useMemo(() => scoreCohort(students, mode === "single" ? role : null), [students, mode, role]);
  const rows = useMemo(() => all.filter((r) => selected.includes(r.major)), [all, selected]);
  const k = useMemo(() => kpis(rows), [rows]);
  const depts = useMemo(() => byDepartment(rows), [rows]);
  const gaps = useMemo(() => topGaps(rows, 8), [rows]);
  const risk = useMemo(() => atRisk(rows, threshold), [rows, threshold]);

  const toggleDept = (d: string) => setSelected((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));
  const maxGap = Math.max(1, ...gaps.map((g) => g.pct));

  return (
    <div className="space-y-5">
      <Card>
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <p className="mb-1 text-xs font-medium text-slate-600">Evaluate students against</p>
            <div className="flex gap-2">
              {(["own", "single"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`rounded-lg border px-3 py-1.5 text-sm ${mode === m ? "border-blue-600 bg-blue-50 font-semibold text-blue-700" : "border-slate-300 text-slate-700"}`}
                >
                  {m === "own" ? "Own target role" : "One role for all"}
                </button>
              ))}
            </div>
            {mode === "single" && (
              <select className={`${inputCls} mt-2`} value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLE_NAMES.map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            )}
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-slate-600">Departments</p>
            <div className="flex flex-wrap gap-1.5">
              {DEPARTMENTS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDept(d)}
                  className={`rounded-full border px-2.5 py-1 text-xs ${selected.includes(d) ? "border-blue-600 bg-blue-50 font-semibold text-blue-700" : "border-slate-300 text-slate-500"}`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">At-risk threshold: score below {threshold}</label>
            <input type="range" min={30} max={75} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="w-full accent-blue-600" />
          </div>
        </div>
      </Card>

      {rows.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-600">No students match the selected departments. Pick at least one.</p>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metric label="Students" value={k.students} />
            <Metric label="Average score" value={k.avg.toFixed(1)} />
            <Metric label="% Ready (75+)" value={`${k.pctReady.toFixed(1)}%`} />
            <Metric label="% Almost ready" value={`${k.pctAlmost.toFixed(1)}%`} />
            <Metric label={`At risk (< ${threshold})`} value={risk.length} hint={`${((100 * risk.length) / k.students).toFixed(0)}% of cohort`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Readiness levels">
              <div className="flex h-8 w-full overflow-hidden rounded-lg text-xs font-semibold text-white">
                <div className="flex items-center justify-center bg-green-600" style={{ width: `${k.pctReady}%` }}>{k.pctReady >= 6 ? `${k.pctReady.toFixed(0)}%` : ""}</div>
                <div className="flex items-center justify-center bg-amber-500" style={{ width: `${k.pctAlmost}%` }}>{k.pctAlmost >= 6 ? `${k.pctAlmost.toFixed(0)}%` : ""}</div>
                <div className="flex items-center justify-center bg-red-600" style={{ width: `${k.pctNeeds}%` }}>{k.pctNeeds >= 6 ? `${k.pctNeeds.toFixed(0)}%` : ""}</div>
              </div>
              <div className="mt-2 flex gap-4 text-xs text-slate-600">
                <span>🟢 Ready</span>
                <span>🟡 Almost ready</span>
                <span>🔴 Needs work</span>
              </div>
            </Card>

            <Card title="Top campus-wide skill gaps" subtitle="% of students missing each required skill">
              <div className="space-y-2">
                {gaps.map((g) => (
                  <div key={g.skill} className="flex items-center gap-3 text-sm">
                    <span className="w-32 shrink-0 text-slate-700">{g.skill}</span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                      <div className="h-full rounded-full bg-red-500" style={{ width: `${(g.pct / maxGap) * 100}%` }} />
                    </div>
                    <span className="w-20 text-right tabular-nums text-slate-600">{g.pct.toFixed(0)}% ({g.count})</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card title="Readiness by department">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="py-1 pr-3">Department</th>
                    <th className="py-1 pr-3">Students</th>
                    <th className="py-1 pr-3">Avg score</th>
                    <th className="py-1 pr-3">% Ready</th>
                    <th className="py-1">% At risk</th>
                  </tr>
                </thead>
                <tbody>
                  {depts.map((d) => (
                    <tr key={d.major} className="border-t border-slate-100">
                      <td className="py-2 pr-3 font-medium text-slate-800">{d.major}</td>
                      <td className="py-2 pr-3 tabular-nums">{d.students}</td>
                      <td className="py-2 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200">
                            <div className={`h-full ${d.avg >= 75 ? "bg-green-500" : d.avg >= 50 ? "bg-amber-500" : "bg-red-500"}`} style={{ width: `${d.avg}%` }} />
                          </div>
                          <span className="tabular-nums">{d.avg.toFixed(1)}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{d.pctReady.toFixed(1)}%</td>
                      <td className="py-2 tabular-nums">{d.pctAtRisk.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="At-risk students" subtitle="Lowest scores first, with the biggest point loss and top missing skills.">
            <div className="mb-3 flex gap-2">
              <button
                type="button"
                disabled={!risk.length}
                onClick={() => downloadText("at_risk_students.csv", toCsv(risk), "text/csv")}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
              >
                ⬇ At-risk CSV
              </button>
              <button
                type="button"
                onClick={() => downloadText("campus_readiness.csv", toCsv(rows), "text/csv")}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                ⬇ All scores CSV
              </button>
            </div>
            {risk.length === 0 ? (
              <p className="text-sm text-green-700">Nobody is below the threshold. 🎉</p>
            ) : (
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="sticky top-0 bg-white text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-1 pr-3">Student</th>
                      <th className="py-1 pr-3">Department</th>
                      <th className="py-1 pr-3">Role</th>
                      <th className="py-1 pr-3">Score</th>
                      <th className="py-1 pr-3">Biggest loss</th>
                      <th className="py-1">Top missing skills</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risk.map((r) => (
                      <tr key={r.id} className="border-t border-slate-100">
                        <td className="py-1.5 pr-3 font-medium text-slate-800">{r.name}</td>
                        <td className="py-1.5 pr-3 text-slate-600">{r.major}</td>
                        <td className="py-1.5 pr-3 text-slate-600">{r.role}</td>
                        <td className="py-1.5 pr-3">
                          <span className="mr-2 tabular-nums">{r.score.toFixed(1)}</span>
                          <LevelBadge level={r.level} />
                        </td>
                        <td className="py-1.5 pr-3 text-slate-600">{r.weakest}</td>
                        <td className="py-1.5 text-slate-600">{r.missing.slice(0, 3).join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
