/**
 * TypeScript port of the Python scoring + recommendation engine.
 * It reads the SAME catalog.json as the Streamlit app, so roles, skills and
 * learning playbooks have one source of truth.
 */
import catalogJson from "../../../internship-readiness-checker/readiness/data/catalog.json";

export type Level = "Ready" | "Almost ready" | "Needs work";
export type Priority = "High" | "Medium" | "Low";

interface SkillInfo {
  aliases: string[];
  hours: number;
  steps: string[];
  project: string;
}
interface RoleSpec {
  description: string;
  required: string[];
  preferred: string[];
}
interface Catalog {
  roles: Record<string, RoleSpec>;
  skills: Record<string, SkillInfo>;
}

const catalog = catalogJson as unknown as Catalog;

export const ROLE_NAMES: string[] = Object.keys(catalog.roles);
export const ALL_SKILLS: string[] = Object.keys(catalog.skills).sort();

export const W = {
  skills: "Skills match",
  projects: "Projects",
  academics: "Academics",
  soft: "Soft skills",
  experience: "Experience",
  certs: "Certifications",
} as const;

export const WEIGHTS: Record<string, number> = {
  [W.skills]: 35,
  [W.projects]: 20,
  [W.academics]: 15,
  [W.soft]: 15,
  [W.experience]: 10,
  [W.certs]: 5,
};

export const THRESHOLDS = { ready: 75, almost: 50 } as const;
const CAPS = { projects: 4, internships: 2, certs: 3 } as const;
const CGPA = { max: 10, floor: 5, share: 0.6, aptitudeShare: 0.4 } as const;
const REQUIRED_SHARE = 0.85;

export interface Profile {
  id?: number;
  name: string;
  major: string;
  year?: number;
  cgpa: number;
  projects: number;
  internships: number;
  certifications: number;
  communication: number;
  aptitude: number;
  skills: string[];
  targetRole: string;
}

export interface ComponentScore {
  name: string;
  weight: number;
  fraction: number;
  points: number;
  detail: string;
}

export interface ScoreResult {
  role: string;
  total: number;
  level: Level;
  components: ComponentScore[];
  matchedRequired: string[];
  missingRequired: string[];
  matchedPreferred: string[];
  missingPreferred: string[];
  skillsMatchPct: number;
}

export interface Action {
  title: string;
  category: string;
  impact: number;
  hours: number;
  priority: Priority;
  steps: string[];
  projectIdea?: string;
  skill?: string;
}

export interface Assessment {
  profile: Profile;
  role: string;
  result: ScoreResult;
  actions: Action[];
  roleScores: Record<string, number>;
  insights: string[];
  potential: number;
}

const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));
const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);
const round1 = (v: number): number => Math.round(v * 10) / 10;

// --------------------------------------------------------------------------- skills
const aliasMap: Map<string, string> = (() => {
  const m = new Map<string, string>();
  for (const [name, info] of Object.entries(catalog.skills)) {
    m.set(name.toLowerCase(), name);
    for (const a of info.aliases) if (!m.has(a.toLowerCase())) m.set(a.toLowerCase(), name);
  }
  return m;
})();

export function normalizeSkill(raw: string): string | null {
  return aliasMap.get(String(raw).trim().toLowerCase()) ?? null;
}

export function normalizeSkills(raw: string[]): string[] {
  const out = new Set<string>();
  for (const r of raw ?? []) {
    const c = normalizeSkill(r);
    if (c) out.add(c);
  }
  return [...out];
}

const escapeRe = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const skillPatterns: [string, RegExp][] = Object.entries(catalog.skills).map(([name, info]) => {
  const aliases = [...new Set([name.toLowerCase(), ...info.aliases.map((a) => a.toLowerCase())])]
    .sort((a, b) => b.length - a.length)
    .map((a) => escapeRe(a).replace(/\s+/g, "\\s+"));
  return [name, new RegExp(`(?<![A-Za-z0-9+#.])(?:${aliases.join("|")})(?![A-Za-z0-9+#])`, "i")];
});

/** Canonical skills mentioned in free text. */
export function extractSkills(text: string): string[] {
  if (!text?.trim()) return [];
  return skillPatterns.filter(([, re]) => re.test(text)).map(([name]) => name);
}

export function getRole(role: string): RoleSpec {
  const spec = catalog.roles[role];
  if (!spec) throw new Error(`Unknown role "${role}"`);
  return spec;
}

export function getSkill(skill: string): SkillInfo | undefined {
  return catalog.skills[skill];
}

// --------------------------------------------------------------------------- scoring
export function levelFor(score: number): Level {
  if (score >= THRESHOLDS.ready) return "Ready";
  if (score >= THRESHOLDS.almost) return "Almost ready";
  return "Needs work";
}

export function scoreStudent(p: Profile, role: string): ScoreResult {
  const spec = getRole(role);
  const owned = new Set(normalizeSkills(p.skills));
  const matchedRequired = spec.required.filter((s) => owned.has(s));
  const missingRequired = spec.required.filter((s) => !owned.has(s));
  const matchedPreferred = spec.preferred.filter((s) => owned.has(s));
  const missingPreferred = spec.preferred.filter((s) => !owned.has(s));

  const reqCov = spec.required.length ? matchedRequired.length / spec.required.length : 0;
  const prefCov = spec.preferred.length ? matchedPreferred.length / spec.preferred.length : reqCov;
  const skillsFrac = REQUIRED_SHARE * reqCov + (1 - REQUIRED_SHARE) * prefCov;

  const cgpa = num(p.cgpa);
  const aptitude = clamp(num(p.aptitude) / 100);
  const academicsFrac =
    CGPA.share * clamp((cgpa - CGPA.floor) / (CGPA.max - CGPA.floor)) + CGPA.aptitudeShare * aptitude;
  const comm = clamp(num(p.communication) / 100);
  const projects = Math.max(0, Math.floor(num(p.projects)));
  const internships = Math.max(0, Math.floor(num(p.internships)));
  const certs = Math.max(0, Math.floor(num(p.certifications)));

  const rows: [string, number, string][] = [
    [
      W.skills,
      skillsFrac,
      `${matchedRequired.length}/${spec.required.length} required and ${matchedPreferred.length}/${spec.preferred.length} preferred skills for ${role}`,
    ],
    [W.projects, clamp(projects / CAPS.projects), `${projects} project(s); full marks at ${CAPS.projects}+`],
    [W.academics, academicsFrac, `CGPA ${cgpa.toFixed(2)}/10 (60%) and aptitude ${Math.round(aptitude * 100)}/100 (40%)`],
    [W.soft, comm, `Communication score ${Math.round(comm * 100)}/100`],
    [W.experience, clamp(internships / CAPS.internships), `${internships} internship(s); full marks at ${CAPS.internships}+`],
    [W.certs, clamp(certs / CAPS.certs), `${certs} certification(s); full marks at ${CAPS.certs}+`],
  ];

  const components: ComponentScore[] = rows.map(([name, fraction, detail]) => ({
    name,
    weight: WEIGHTS[name],
    fraction,
    points: WEIGHTS[name] * fraction,
    detail,
  }));
  const total = round1(components.reduce((s, c) => s + c.points, 0));
  const reqTotal = matchedRequired.length + missingRequired.length;
  return {
    role,
    total,
    level: levelFor(total),
    components,
    matchedRequired,
    missingRequired,
    matchedPreferred,
    missingPreferred,
    skillsMatchPct: reqTotal ? (100 * matchedRequired.length) / reqTotal : 0,
  };
}

// --------------------------------------------------------------------------- recommendations
export const ROLE_CERTS: Record<string, string[]> = {
  "Data Analyst": ["Google Data Analytics Certificate", "Microsoft PL-300 (Power BI)", "Tableau Desktop Specialist"],
  "ML Engineer": ["DeepLearning.AI Machine Learning Specialization", "TensorFlow or PyTorch badge", "AWS Cloud Practitioner"],
  "Web Developer": ["freeCodeCamp Responsive Web Design + JavaScript", "Meta Front-End Developer Certificate", "Google UX Design Certificate"],
  "Backend Developer": ["AWS Certified Cloud Practitioner", "HackerRank SQL (Advanced)", "Linux Foundation LFS101"],
};

const priorityFor = (impact: number): Priority => (impact >= 3.5 ? "High" : impact >= 1.5 ? "Medium" : "Low");
const RANK: Record<Priority, number> = { High: 0, Medium: 1, Low: 2 };

export function buildActions(p: Profile, r: ScoreResult): Action[] {
  const items: Action[] = [];
  const nReq = r.matchedRequired.length + r.missingRequired.length;
  const nPref = r.matchedPreferred.length + r.missingPreferred.length;

  const groups: [string[], number, string][] = [
    [r.missingRequired, (WEIGHTS[W.skills] * REQUIRED_SHARE) / Math.max(nReq, 1), "required"],
    [r.missingPreferred, (WEIGHTS[W.skills] * (1 - REQUIRED_SHARE)) / Math.max(nPref, 1), "nice-to-have"],
  ];
  for (const [skills, impact, kind] of groups) {
    for (const skill of skills) {
      const info = getSkill(skill);
      items.push({
        title: `Learn ${skill} (${kind})`,
        category: "skill",
        impact: Math.round(impact * 100) / 100,
        hours: info?.hours ?? 20,
        priority: priorityFor(impact),
        steps: info?.steps ?? [`Find a free beginner course for ${skill} and build one small project.`],
        projectIdea: info?.project,
        skill,
      });
    }
  }

  const comp = (name: string) => r.components.find((c) => c.name === name) as ComponentScore;
  const lost = (c: ComponentScore) => c.weight - c.points;

  const pj = comp(W.projects);
  if (pj.fraction < 1) {
    const need = CAPS.projects - Math.round(pj.fraction * CAPS.projects);
    const ideas = [...r.missingRequired, ...r.missingPreferred]
      .slice(0, 3)
      .map((s) => getSkill(s)?.project)
      .filter((x): x is string => Boolean(x));
    items.push({
      title: `Build ${need} more role-aligned project${need === 1 ? "" : "s"}`,
      category: "projects",
      impact: Math.round(lost(pj) * 100) / 100,
      hours: 25 * need,
      priority: priorityFor(lost(pj)),
      steps: [
        ideas.length ? `Project ideas that also close your skill gaps: ${ideas.join(" | ")}` : `Ship working demos of problems a ${r.role} solves.`,
        "Give every project a README: problem, approach, results, screenshot and a live demo link.",
        "Pin the projects on GitHub and add one quantified bullet per project to your resume.",
      ],
    });
  }
  const ex = comp(W.experience);
  if (ex.fraction < 1) {
    items.push({
      title: "Land an internship or real-world experience",
      category: "experience",
      impact: Math.round(lost(ex) * 100) / 100,
      hours: 30,
      priority: priorityFor(lost(ex)),
      steps: [
        "Apply to 10 internships a week (LinkedIn, Internshala, career pages) with a role-tailored resume.",
        "No offer yet? Do a free virtual internship, contribute to open source or join a hackathon.",
        "Ask the placement cell and alumni for referrals; book 3 short informational chats.",
      ],
    });
  }
  const ce = comp(W.certs);
  if (ce.fraction < 1) {
    items.push({
      title: "Earn a role-relevant certification",
      category: "certifications",
      impact: Math.round(lost(ce) * 100) / 100,
      hours: 30,
      priority: priorityFor(lost(ce)),
      steps: [
        `Pick one credential: ${(ROLE_CERTS[r.role] ?? []).join("; ")}.`,
        "Study 4-5 hours a week with the free learning path; pay only for the exam if needed.",
        "Add the verification link to LinkedIn and your resume.",
      ],
    });
  }
  if (p.communication < 80) {
    const impact = Math.max(0, ((80 - p.communication) / 100) * WEIGHTS[W.soft]);
    items.push({
      title: "Strengthen communication and interview skills",
      category: "communication",
      impact: Math.round(impact * 100) / 100,
      hours: 15,
      priority: priorityFor(impact),
      steps: [
        "Record a 2-minute self-introduction, review it and iterate until it is clear and structured.",
        "Practise 5 behavioural questions with the STAR method and do 2 mock interviews.",
        "Present one project demo to a club or class; join Toastmasters or the debate society.",
      ],
    });
  }
  if (p.aptitude < 80) {
    const impact = Math.max(0, ((80 - p.aptitude) / 100) * CGPA.aptitudeShare * WEIGHTS[W.academics]);
    items.push({
      title: "Raise your aptitude test score",
      category: "academics",
      impact: Math.round(impact * 100) / 100,
      hours: 25,
      priority: priorityFor(impact),
      steps: [
        "Take a free diagnostic aptitude test and log the topics you miss (quant, logic, verbal).",
        "Practise 20 questions a day in timed 25-minute sets; review every wrong answer.",
        "Re-test after 3 weeks and aim for 75+.",
      ],
    });
  }
  if (p.cgpa && p.cgpa < 8) {
    const impact = Math.max(0, ((8 - p.cgpa) / (CGPA.max - CGPA.floor)) * CGPA.share * WEIGHTS[W.academics]);
    items.push({
      title: "Protect and lift your CGPA",
      category: "academics",
      impact: Math.round(impact * 100) / 100,
      hours: 40,
      priority: priorityFor(impact),
      steps: [
        "Identify the two courses dragging your CGPA down and book faculty office hours.",
        "Block a weekly 3-hour revision slot and work through past papers.",
        "Many recruiters use a 6.5-7.5 cut-off, so keep your CGPA above it this semester.",
      ],
    });
  }
  items.sort((a, b) => RANK[a.priority] - RANK[b.priority] || a.hours - b.hours || b.impact - a.impact);
  return items;
}

export interface TimelineRow {
  order: number;
  action: string;
  hours: number;
  weeks: string;
  impact: number;
  priority: Priority;
}

export function buildTimeline(actions: Action[], hoursPerWeek = 10, maxItems = 8): TimelineRow[] {
  const hpw = Math.max(1, Math.floor(hoursPerWeek));
  let cursor = 0;
  return actions.slice(0, maxItems).map((a, i) => {
    const start = Math.floor(cursor / hpw) + 1;
    cursor += a.hours;
    const end = Math.max(start, Math.ceil(cursor / hpw));
    return { order: i + 1, action: a.title, hours: a.hours, weeks: start === end ? `${start}` : `${start}-${end}`, impact: a.impact, priority: a.priority };
  });
}

export function roleScores(p: Profile): Record<string, number> {
  return Object.fromEntries(ROLE_NAMES.map((r) => [r, scoreStudent(p, r).total]));
}

function buildInsights(p: Profile, r: ScoreResult, actions: Action[], scores: Record<string, number>): string[] {
  const out: string[] = [];
  const strongest = [...r.components].sort((a, b) => b.fraction - a.fraction)[0];
  const weakest = [...r.components].sort((a, b) => b.weight - b.points - (a.weight - a.points))[0];
  out.push(
    `${r.level} for ${r.role} with ${r.total.toFixed(1)}/100. Strongest: ${strongest.name} (${strongest.points.toFixed(1)}/${strongest.weight}); biggest loss: ${weakest.name} (-${(weakest.weight - weakest.points).toFixed(1)} pts).`,
  );
  if (r.level !== "Ready") {
    const target = r.total < THRESHOLDS.almost ? THRESHOLDS.almost : THRESHOLDS.ready;
    out.push(`You are ${(target - r.total).toFixed(1)} points away from ${r.total < THRESHOLDS.almost ? "Almost ready" : "Ready"}.`);
  }
  if (r.missingRequired.length) {
    const top = r.missingRequired.slice(0, 3);
    const gain = actions.filter((a) => a.skill && top.includes(a.skill)).reduce((s, a) => s + a.impact, 0);
    out.push(`Closing ${top.join(", ")} adds about +${gain.toFixed(1)} pts.`);
  } else {
    out.push("You cover all required skills for this role. Add preferred skills to stand out.");
  }
  const quick = actions.filter((a) => a.priority !== "Low");
  if (quick.length) {
    const best = quick.reduce((m, a) => (a.hours / Math.max(a.impact, 0.1) < m.hours / Math.max(m.impact, 0.1) ? a : m));
    out.push(`Best quick win: ${best.title} (about ${best.hours} h for +${best.impact.toFixed(1)} pts).`);
  }
  const bestRole = Object.entries(scores).sort((a, b) => b[1] - a[1])[0];
  if (bestRole && bestRole[0] !== r.role && bestRole[1] - r.total >= 5) {
    out.push(`Your profile fits ${bestRole[0]} better (${bestRole[1].toFixed(1)}) than ${r.role} (${r.total.toFixed(1)}).`);
  }
  if (p.internships === 0) out.push("No internship yet: even one short project-based internship earns half of the experience points.");
  return out;
}

export function assess(profile: Profile, role: string): Assessment {
  const result = scoreStudent(profile, role);
  const actions = buildActions(profile, result);
  const scores = roleScores(profile);
  const potential = round1(Math.min(100, result.total + actions.slice(0, 5).reduce((s, a) => s + a.impact, 0)));
  return { profile, role, result, actions, roleScores: scores, insights: buildInsights(profile, result, actions, scores), potential };
}
