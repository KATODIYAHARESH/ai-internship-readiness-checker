"use client";

import { useMemo, useState } from "react";
import {
  ALL_SKILLS,
  ROLE_NAMES,
  THRESHOLDS,
  buildTimeline,
  getRole,
  normalizeSkills,
  type Assessment,
  type Profile,
} from "@/lib/readiness/engine";
import { buildMarkdownReport } from "@/lib/readiness/mentor";
import { Card, Chip, Gauge, LevelBadge, Metric, barColor, downloadText, inputCls } from "./ui";

interface Props {
  students: Profile[];
  profile: Profile;
  role: string;
  assessment: Assessment;
  onSelectStudent: (id: number) => void;
  onProfileChange: (p: Profile) => void;
  onRoleChange: (role: string) => void;
}

const PRIORITY_DOT: Record<string, string> = { High: "bg-red-500", Medium: "bg-amber-500", Low: "bg-green-500" };

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

export default function StudentTab({ students, profile, role, assessment, onSelectStudent, onProfileChange, onRoleChange }: Props) {
  const [hours, setHours] = useState(10);
  const [showAll, setShowAll] = useState(false);
  const r = assessment.result;
  const spec = getRole(role);
  const owned = useMemo(() => new Set(normalizeSkills(profile.skills)), [profile.skills]);
  const timeline = useMemo(() => buildTimeline(assessment.actions, hours), [assessment.actions, hours]);

  const set = <K extends keyof Profile>(key: K, value: Profile[K]) => onProfileChange({ ...profile, [key]: value });
  const toggleSkill = (skill: string) =>
    set("skills", owned.has(skill) ? normalizeSkills(profile.skills).filter((s) => s !== skill) : [...normalizeSkills(profile.skills), skill]);
  const numberInput = (key: "projects" | "internships" | "certifications", max: number) => (
    <input
      type="number"
      min={0}
      max={max}
      value={profile[key]}
      onChange={(e) => set(key, Math.max(0, Math.min(max, Math.floor(Number(e.target.value) || 0))))}
      className={inputCls}
    />
  );
  const roleSkillSet = new Set([...spec.required, ...spec.preferred]);
  const otherSkills = ALL_SKILLS.filter((s) => !roleSkillSet.has(s));

  return (
    <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
      {/* ---------------- left: editable profile ---------------- */}
      <div className="space-y-5">
        <Card title="Student & role" subtitle="Pick a synthetic student, then tweak anything: the score updates live (what-if mode).">
          <div className="space-y-3">
            <Field label="Student">
              <select className={inputCls} value={profile.id ?? ""} onChange={(e) => onSelectStudent(Number(e.target.value))}>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.major}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Target role">
              <select className={inputCls} value={role} onChange={(e) => onRoleChange(e.target.value)}>
                {ROLE_NAMES.map((n) => (
                  <option key={n}>{n}</option>
                ))}
              </select>
            </Field>
            <p className="text-xs text-slate-500">{spec.description}</p>
          </div>
        </Card>

        <Card title="Profile">
          <div className="space-y-3">
            <Field label={`CGPA: ${profile.cgpa.toFixed(2)} / 10`}>
              <input type="range" min={5} max={10} step={0.1} value={profile.cgpa} onChange={(e) => set("cgpa", Number(e.target.value))} className="w-full accent-blue-600" />
            </Field>
            <Field label={`Communication: ${Math.round(profile.communication)} / 100`}>
              <input type="range" min={0} max={100} value={profile.communication} onChange={(e) => set("communication", Number(e.target.value))} className="w-full accent-blue-600" />
            </Field>
            <Field label={`Aptitude: ${Math.round(profile.aptitude)} / 100`}>
              <input type="range" min={0} max={100} value={profile.aptitude} onChange={(e) => set("aptitude", Number(e.target.value))} className="w-full accent-blue-600" />
            </Field>
            <div className="grid grid-cols-3 gap-2">
              <Field label="Projects">{numberInput("projects", 20)}</Field>
              <Field label="Internships">{numberInput("internships", 10)}</Field>
              <Field label="Certs">{numberInput("certifications", 20)}</Field>
            </div>
          </div>
        </Card>

        <Card title="Skills" subtitle="Click a skill to add or remove it.">
          <p className="mb-1 text-xs font-semibold text-slate-600">Required for {role}</p>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {spec.required.map((s) => (
              <Chip key={s} kind={owned.has(s) ? "good" : "bad"} onClick={() => toggleSkill(s)}>
                {owned.has(s) ? "✓ " : "+ "}
                {s}
              </Chip>
            ))}
          </div>
          <p className="mb-1 text-xs font-semibold text-slate-600">Nice to have</p>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {spec.preferred.map((s) => (
              <Chip key={s} kind={owned.has(s) ? "good" : "warn"} onClick={() => toggleSkill(s)}>
                {owned.has(s) ? "✓ " : "+ "}
                {s}
              </Chip>
            ))}
          </div>
          <button type="button" onClick={() => setShowAll((v) => !v)} className="text-xs font-medium text-blue-600 hover:underline">
            {showAll ? "Hide" : "Show"} other skills ({otherSkills.length})
          </button>
          {showAll && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {otherSkills.map((s) => (
                <Chip key={s} kind={owned.has(s) ? "good" : "neutral"} onClick={() => toggleSkill(s)}>
                  {s}
                </Chip>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ---------------- right: results ---------------- */}
      <div className="space-y-5">
        <Card>
          <div className="grid items-center gap-4 md:grid-cols-[260px_1fr]">
            <Gauge value={r.total} level={r.level} />
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <h2 className="text-xl font-semibold text-slate-900">{profile.name}</h2>
                <LevelBadge level={r.level} />
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Metric label="Score" value={`${r.total.toFixed(1)}`} hint="out of 100" />
                <Metric label="Required skills" value={`${r.matchedRequired.length}/${r.matchedRequired.length + r.missingRequired.length}`} hint={`${r.skillsMatchPct.toFixed(0)}% match`} />
                <Metric label="Potential" value={assessment.potential.toFixed(0)} hint="after top 5 actions" />
              </div>
              <p className="mt-3 text-xs text-slate-500">
                Levels: Ready ≥ {THRESHOLDS.ready} · Almost ready ≥ {THRESHOLDS.almost} · otherwise Needs work.
              </p>
            </div>
          </div>
        </Card>

        <Card title="Explainable breakdown" subtitle="Weights: Skills 35 · Projects 20 · Academics 15 · Soft skills 15 · Experience 10 · Certifications 5">
          <div className="space-y-3">
            {r.components.map((c) => (
              <div key={c.name}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="font-medium text-slate-800">{c.name}</span>
                  <span className="tabular-nums text-slate-600">
                    {c.points.toFixed(1)} / {c.weight}
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div className={`h-full rounded-full ${barColor(c.fraction)}`} style={{ width: `${Math.max(1, c.fraction * 100)}%`, transition: "width .4s" }} />
                </div>
                <p className="mt-1 text-xs text-slate-500">{c.detail}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card title="AI insights">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-700">
            {assessment.insights.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Card>

        <Card title="Personalised action plan" subtitle="Sorted by impact, then quickest win first.">
          {assessment.actions.length === 0 ? (
            <p className="text-sm text-green-700">No gaps found. Keep polishing your portfolio. 🎉</p>
          ) : (
            <>
              <div className="mb-3 flex items-center gap-3 text-sm">
                <label htmlFor="hpw" className="text-slate-600">
                  Hours per week: <b>{hours}</b>
                </label>
                <input id="hpw" type="range" min={3} max={30} value={hours} onChange={(e) => setHours(Number(e.target.value))} className="accent-blue-600" />
              </div>
              <div className="mb-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-1 pr-3">#</th>
                      <th className="py-1 pr-3">Action</th>
                      <th className="py-1 pr-3">Hours</th>
                      <th className="py-1 pr-3">Weeks</th>
                      <th className="py-1">Impact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timeline.map((t) => (
                      <tr key={t.order} className="border-t border-slate-100">
                        <td className="py-1.5 pr-3 text-slate-500">{t.order}</td>
                        <td className="py-1.5 pr-3 font-medium text-slate-800">{t.action}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{t.hours}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{t.weeks}</td>
                        <td className="py-1.5 tabular-nums text-green-700">+{t.impact.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="space-y-2">
                {assessment.actions.slice(0, 10).map((a, i) => (
                  <details key={a.title} open={i < 1} className="rounded-lg border border-slate-200 px-3 py-2">
                    <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-800">
                      <span className={`h-2.5 w-2.5 rounded-full ${PRIORITY_DOT[a.priority]}`} />
                      {i + 1}. {a.title}
                      <span className="ml-auto text-xs font-normal text-slate-500">
                        +{a.impact.toFixed(1)} pts · ~{a.hours} h
                      </span>
                    </summary>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-700">
                      {a.steps.map((s) => (
                        <li key={s}>{s}</li>
                      ))}
                    </ol>
                    {a.projectIdea && <p className="mt-2 rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-900">Mini-project: {a.projectIdea}</p>}
                  </details>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card title="Role fit" subtitle="The same profile scored against every role.">
          <div className="space-y-2">
            {Object.entries(assessment.roleScores)
              .sort((a, b) => b[1] - a[1])
              .map(([name, score]) => (
                <div key={name} className="flex items-center gap-3 text-sm">
                  <span className={`w-36 shrink-0 ${name === role ? "font-semibold text-blue-700" : "text-slate-700"}`}>{name}</span>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <div className={`h-full rounded-full ${name === role ? "bg-blue-600" : "bg-slate-400"}`} style={{ width: `${score}%` }} />
                  </div>
                  <span className="w-10 text-right tabular-nums text-slate-600">{score.toFixed(1)}</span>
                </div>
              ))}
          </div>
        </Card>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => downloadText(`readiness_${profile.name.replace(/[^A-Za-z0-9_-]+/g, "_")}.md`, buildMarkdownReport(assessment), "text/markdown")}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          >
            ⬇ Download Markdown report
          </button>
        </div>
      </div>
    </div>
  );
}
