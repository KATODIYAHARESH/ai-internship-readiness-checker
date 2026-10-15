/** Deterministic synthetic cohort (80 students) + campus analytics, mirroring analytics.py. */
import { ROLE_NAMES, ALL_SKILLS, getRole, scoreStudent, type Level, type Profile, W } from "./engine";

const FIRST = [
  "Aarav", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Rohan", "Meera", "Vihaan", "Saanvi", "Aditya", "Priya", "Karan",
  "Neha", "Rahul", "Sneha", "Siddharth", "Tanvi", "Yash", "Pooja", "Liam", "Emma", "Noah", "Olivia", "Ethan", "Sophia",
  "Lucas", "Amelia", "Mateo", "Isabella", "Omar", "Fatima", "Wei", "Mei", "Hiro", "Yuki", "Chinedu", "Amara", "Kwame",
  "Zainab", "Daniel", "Sofia", "Mohammed", "Aisha", "Ravi", "Lakshmi", "Nikhil", "Riya", "Farhan", "Zoya",
];
const LAST = [
  "Sharma", "Patel", "Iyer", "Reddy", "Gupta", "Nair", "Singh", "Mehta", "Kapoor", "Joshi", "Khan", "Verma", "Das", "Bose",
  "Menon", "Rao", "Chopra", "Malhotra", "Bhat", "Pillai", "Smith", "Johnson", "Garcia", "Martinez", "Brown", "Nguyen", "Kim",
  "Tanaka", "Chen", "Wang", "Okafor", "Adeyemi", "Hassan", "Ali", "Silva", "Costa", "Novak", "Ivanov", "Rossi", "Muller",
];

interface MajorCfg {
  weight: number;
  roles: Record<string, number>;
  boost: string[];
  bonus: number;
}
const MAJORS: Record<string, MajorCfg> = {
  "Computer Science": { weight: 0.27, roles: { "Backend Developer": 0.3, "Web Developer": 0.28, "ML Engineer": 0.2, "Data Analyst": 0.22 }, boost: ["Python", "Git", "Data Structures", "SQL", "Linux", "JavaScript", "HTML", "CSS"], bonus: 0.08 },
  "Information Technology": { weight: 0.18, roles: { "Web Developer": 0.35, "Backend Developer": 0.3, "Data Analyst": 0.25, "ML Engineer": 0.1 }, boost: ["HTML", "CSS", "JavaScript", "SQL", "Git", "REST APIs", "Linux"], bonus: 0.06 },
  "Data Science": { weight: 0.15, roles: { "Data Analyst": 0.4, "ML Engineer": 0.5, "Backend Developer": 0.05, "Web Developer": 0.05 }, boost: ["Python", "Pandas", "NumPy", "Statistics", "Machine Learning", "Scikit-learn", "Data Visualization"], bonus: 0.1 },
  "Business Analytics": { weight: 0.12, roles: { "Data Analyst": 0.85, "ML Engineer": 0.05, "Backend Developer": 0.03, "Web Developer": 0.07 }, boost: ["Excel", "SQL", "BI Tools", "Statistics", "Data Visualization", "Data Cleaning"], bonus: 0.1 },
  "Electronics & Communication": { weight: 0.12, roles: { "Backend Developer": 0.3, "ML Engineer": 0.25, "Data Analyst": 0.25, "Web Developer": 0.2 }, boost: ["Python", "Linux", "NumPy", "Statistics"], bonus: 0 },
  "Electrical Engineering": { weight: 0.08, roles: { "Data Analyst": 0.4, "ML Engineer": 0.25, "Backend Developer": 0.2, "Web Developer": 0.15 }, boost: ["Excel", "Python", "Statistics"], bonus: -0.02 },
  "Mechanical Engineering": { weight: 0.08, roles: { "Data Analyst": 0.6, "ML Engineer": 0.15, "Backend Developer": 0.1, "Web Developer": 0.15 }, boost: ["Excel", "Statistics", "Data Visualization"], bonus: -0.05 },
};
export const DEPARTMENTS = Object.keys(MAJORS);

/** mulberry32: tiny seeded PRNG so server and client render the same cohort. */
function makeRng(seed: number) {
  let a = seed >>> 0;
  const next = (): number => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const gauss = (mu: number, sd: number): number => {
    const u = Math.max(next(), 1e-9);
    return mu + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * next());
  };
  const choice = <T,>(items: T[], weights?: number[]): T => {
    if (!weights) return items[Math.floor(next() * items.length)];
    const total = weights.reduce((s, w) => s + w, 0);
    let r = next() * total;
    for (let i = 0; i < items.length; i++) {
      r -= weights[i];
      if (r <= 0) return items[i];
    }
    return items[items.length - 1];
  };
  return { next, gauss, choice };
}

const clip = (x: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, x));

export function generateStudents(count = 80, seed = 42): Profile[] {
  const rng = makeRng(seed);
  const names = new Set<string>();
  while (names.size < count) names.add(`${rng.choice(FIRST)} ${rng.choice(LAST)}`);
  const majorNames = Object.keys(MAJORS);
  const out: Profile[] = [];
  let id = 1;
  for (const name of [...names]) {
    const major = rng.choice(majorNames, majorNames.map((m) => MAJORS[m].weight));
    const cfg = MAJORS[major];
    const roleKeys = Object.keys(cfg.roles).filter((r) => ROLE_NAMES.includes(r));
    const role = rng.choice(roleKeys, roleKeys.map((r) => cfg.roles[r]));
    const ability = clip(rng.gauss(0.56, 0.22), 0.02, 0.98);
    const drive = clip(0.45 * ability + 0.55 * rng.gauss(0.56, 0.24), 0, 1);
    const year = rng.choice([2, 3, 4], [0.2, 0.4, 0.4]);
    const boost = new Set(cfg.boost);

    const spec = getRole(role);
    const chosen = new Set<string>();
    for (const s of spec.required) {
      const p = 0.1 + 0.78 * ability + (boost.has(s) ? cfg.bonus : cfg.bonus / 3);
      if (rng.next() < clip(p, 0.02, 0.97)) chosen.add(s);
    }
    for (const s of spec.preferred) {
      const p = 0.04 + 0.5 * ability + (boost.has(s) ? cfg.bonus / 2 : 0);
      if (rng.next() < clip(p, 0.01, 0.85)) chosen.add(s);
    }
    for (const s of ALL_SKILLS) {
      if (chosen.has(s)) continue;
      const p = 0.03 + 0.14 * ability + (boost.has(s) ? 0.06 : 0);
      if (rng.next() < clip(p, 0, 0.4)) chosen.add(s);
    }
    const pIntern = clip(0.05 + 0.85 * drive * (0.6 + (0.2 * year) / 2), 0, 0.95);
    out.push({
      id: id++,
      name,
      major,
      year,
      cgpa: Math.round(clip(6.1 + 2.5 * ability + rng.gauss(0, 0.4), 5.2, 9.9) * 100) / 100,
      projects: Math.round(clip(rng.gauss(0.5 + 3.8 * drive, 0.9), 0, 6)),
      internships: (rng.next() < pIntern ? 1 : 0) + (rng.next() < pIntern * 0.35 ? 1 : 0),
      certifications: Math.round(clip(rng.gauss(0.3 + 3 * drive, 1), 0, 6)),
      communication: Math.round(clip(rng.gauss(30 + 40 * drive + 18 * ability, 10), 20, 98) * 10) / 10,
      aptitude: Math.round(clip(rng.gauss(32 + 55 * ability, 9), 15, 98) * 10) / 10,
      skills: [...chosen].sort(),
      targetRole: role,
    });
  }
  return out;
}

// --------------------------------------------------------------------------- analytics
export interface ScoredRow {
  id: number;
  name: string;
  major: string;
  role: string;
  score: number;
  level: Level;
  weakest: string;
  missing: string[];
  cgpa: number;
}

export function scoreCohort(students: Profile[], roleOverride?: string | null): ScoredRow[] {
  return students.map((s) => {
    const role = roleOverride || s.targetRole;
    const r = scoreStudent(s, role);
    const weakest = [...r.components].sort((a, b) => b.weight - b.points - (a.weight - a.points))[0];
    return { id: s.id ?? 0, name: s.name, major: s.major, role, score: r.total, level: r.level, weakest: weakest?.name ?? W.skills, missing: r.missingRequired, cgpa: s.cgpa };
  });
}

export interface Kpis {
  students: number;
  avg: number;
  pctReady: number;
  pctAlmost: number;
  pctNeeds: number;
}

export function kpis(rows: ScoredRow[]): Kpis {
  const n = rows.length;
  if (!n) return { students: 0, avg: 0, pctReady: 0, pctAlmost: 0, pctNeeds: 0 };
  const pct = (lv: Level) => Math.round((1000 * rows.filter((r) => r.level === lv).length) / n) / 10;
  return { students: n, avg: Math.round((10 * rows.reduce((s, r) => s + r.score, 0)) / n) / 10, pctReady: pct("Ready"), pctAlmost: pct("Almost ready"), pctNeeds: pct("Needs work") };
}

export interface DeptRow {
  major: string;
  students: number;
  avg: number;
  pctReady: number;
  pctAtRisk: number;
}

export function byDepartment(rows: ScoredRow[]): DeptRow[] {
  const groups = new Map<string, ScoredRow[]>();
  for (const r of rows) groups.set(r.major, [...(groups.get(r.major) ?? []), r]);
  return [...groups.entries()]
    .map(([major, g]) => ({
      major,
      students: g.length,
      avg: Math.round((10 * g.reduce((s, r) => s + r.score, 0)) / g.length) / 10,
      pctReady: Math.round((1000 * g.filter((r) => r.level === "Ready").length) / g.length) / 10,
      pctAtRisk: Math.round((1000 * g.filter((r) => r.level === "Needs work").length) / g.length) / 10,
    }))
    .sort((a, b) => b.avg - a.avg);
}

export function topGaps(rows: ScoredRow[], topN = 8): { skill: string; count: number; pct: number }[] {
  const counts = new Map<string, number>();
  for (const r of rows) for (const s of r.missing) counts.set(s, (counts.get(s) ?? 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, topN)
    .map(([skill, count]) => ({ skill, count, pct: rows.length ? Math.round((1000 * count) / rows.length) / 10 : 0 }));
}

export function atRisk(rows: ScoredRow[], threshold = 50): ScoredRow[] {
  return rows.filter((r) => r.score < threshold).sort((a, b) => a.score - b.score);
}

export function toCsv(rows: ScoredRow[]): string {
  const esc = (v: string | number): string => `"${String(v).replace(/"/g, '""')}"`;
  const head = ["id", "name", "department", "role", "score", "level", "biggest_loss", "missing_required_skills"];
  const body = rows.map((r) => [r.id, r.name, r.major, r.role, r.score, r.level, r.weakest, r.missing.join("; ")].map(esc).join(","));
  return [head.join(","), ...body].join("\n");
}
