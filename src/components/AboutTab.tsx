"use client";

import { ROLE_NAMES, WEIGHTS, getRole } from "@/lib/readiness/engine";
import { Card } from "./ui";

const ARCHITECTURE = `Streamlit UI  (app.py + readiness/ui/*)
   |  student | resume analyzer | placement dashboard | AI mentor
   v
service.assess() -> scoring -> recommendations -> reports
   |                                 |
   |                                 +--> llm.py (Ollama llama3.2 --fallback--> rule-based mentor)
   v
cache.py (st.cache_data) -> analytics.py -> database.py -> SQLite (data/readiness.db)
                                                 ^
                         seed_db.py / seed.py ---+     catalog.json (roles, skills, playbooks, JDs)
resume.py (PDF/text -> skills) -> semantic.py (TF-IDF | ChromaDB + Ollama embeddings)`;

const RULES: Record<string, string> = {
  "Skills match": "85% required-skill coverage + 15% preferred-skill coverage for the chosen role",
  Projects: "projects / 4, capped at 1",
  Academics: "60% CGPA (5.0 → 0, 10 → 1) + 40% aptitude score",
  "Soft skills": "communication score / 100",
  Experience: "internships / 2, capped at 1",
  Certifications: "certifications / 3, capped at 1",
};

const DEMO = [
  ["0:00", "Open the app; explain the problem: a number without a plan."],
  ["0:20", "Student tab: gauge, breakdown, switch role, tweak skills for a live what-if."],
  ["1:05", "Skill gaps and action plan: learning steps, mini-project, hours, points impact, weekly timeline."],
  ["1:40", "Resume analyzer (Streamlit): paste or upload PDF, extracted skills, semantic job matches."],
  ["2:10", "Placement dashboard: KPIs, department view, top gaps, at-risk list, CSV export."],
  ["2:40", "AI mentor: grounded in score and gaps, Ollama first, rule-based fallback. Download the report."],
];

export default function AboutTab() {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card title="About this prototype">
        <div className="space-y-3 text-sm text-slate-700">
          <p>
            The deliverable is a <b>Python / Streamlit / Pandas / SQLite</b> app in <code className="rounded bg-slate-100 px-1">internship-readiness-checker/</code>. This web page is a live
            companion: a TypeScript port of the same scoring engine, reading the same <code className="rounded bg-slate-100 px-1">catalog.json</code>, so you can try the logic in the browser.
          </p>
          <p className="font-semibold text-slate-900">Run the Streamlit app locally</p>
          <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{`cd internship-readiness-checker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed_db.py        # 80 synthetic students -> SQLite
streamlit run app.py
pytest                   # scoring + pipeline tests

# optional local LLM
ollama pull llama3.2`}</pre>
          <p className="text-xs text-slate-500">
            Streamlit-only features: PDF resume upload, semantic job matching (TF-IDF / ChromaDB), PDF report export and st.cache_data caching. All student data is synthetic.
          </p>
        </div>
      </Card>

      <Card title="Scoring model" subtitle="Weights sum to 100. Ready ≥ 75 · Almost ready 50-74 · Needs work < 50">
        <table className="w-full text-left text-sm">
          <tbody>
            {Object.entries(WEIGHTS).map(([name, weight]) => (
              <tr key={name} className="border-t border-slate-100 first:border-0">
                <td className="py-1.5 pr-3 font-medium text-slate-800">{name}</td>
                <td className="py-1.5 pr-3 tabular-nums text-slate-900">{weight}</td>
                <td className="py-1.5 text-slate-600">{RULES[name]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Target roles" className="lg:col-span-2">
        <div className="grid gap-3 md:grid-cols-2">
          {ROLE_NAMES.map((name) => {
            const spec = getRole(name);
            return (
              <div key={name} className="rounded-xl border border-slate-200 p-3 text-sm">
                <p className="font-semibold text-slate-900">{name}</p>
                <p className="mb-2 text-xs text-slate-500">{spec.description}</p>
                <p>
                  <b className="text-slate-700">Required:</b> <span className="text-slate-600">{spec.required.join(", ")}</span>
                </p>
                <p>
                  <b className="text-slate-700">Preferred:</b> <span className="text-slate-600">{spec.preferred.join(", ")}</span>
                </p>
              </div>
            );
          })}
        </div>
      </Card>

      <Card title="Architecture">
        <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-snug text-slate-100">{ARCHITECTURE}</pre>
      </Card>

      <Card title="3-minute demo flow">
        <ol className="space-y-2 text-sm text-slate-700">
          {DEMO.map(([t, text]) => (
            <li key={t} className="flex gap-3">
              <span className="w-10 shrink-0 font-mono text-xs text-blue-700">{t}</span>
              <span>{text}</span>
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs text-slate-500">Full script with talking points lives in the project README.</p>
      </Card>
    </div>
  );
}
