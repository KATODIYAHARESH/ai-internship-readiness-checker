/** Mentor logic shared by the API route (server) and UI: Ollama prompt + rule-based fallback + report. */
import { ROLE_CERTS, buildTimeline, extractSkills, getSkill, normalizeSkills, type Assessment } from "./engine";

export function buildSystemPrompt(a: Assessment): string {
  const r = a.result;
  const p = a.profile;
  const breakdown = r.components.map((c) => `${c.name} ${c.points.toFixed(1)}/${c.weight}`).join("; ");
  const actions = a.actions.slice(0, 5).map((x) => `${x.title} (+${x.impact.toFixed(1)} pts, ~${x.hours}h)`).join("; ") || "none";
  const others = Object.entries(a.roleScores).map(([k, v]) => `${k}: ${v.toFixed(0)}`).join(", ");
  return [
    "You are a friendly, concise internship-readiness mentor for a university student.",
    "Answer ONLY using the facts below; if something is not covered, say so and give general advice.",
    "Be specific, use short bullet points, keep answers under 170 words. Never invent scores.",
    "",
    `STUDENT: ${p.name} | major: ${p.major} | CGPA ${p.cgpa.toFixed(2)}/10 | projects ${p.projects} | internships ${p.internships} | certifications ${p.certifications} | communication ${Math.round(p.communication)}/100 | aptitude ${Math.round(p.aptitude)}/100`,
    `TARGET ROLE: ${a.role}`,
    `READINESS SCORE: ${r.total.toFixed(1)}/100 (${r.level})`,
    `BREAKDOWN: ${breakdown}`,
    `SKILLS MATCHED (required): ${r.matchedRequired.join(", ") || "none"}`,
    `SKILLS MISSING (required): ${r.missingRequired.join(", ") || "none"}`,
    `SKILLS MISSING (preferred): ${r.missingPreferred.join(", ") || "none"}`,
    `TOP ACTIONS: ${actions}`,
    `SCORE FOR OTHER ROLES: ${others}`,
  ].join("\n");
}

const has = (q: string, ...words: string[]): boolean => words.some((w) => q.includes(w));

function skillHelp(skill: string, a: Assessment): string {
  const info = getSkill(skill);
  const r = a.result;
  const owned = new Set(normalizeSkills(a.profile.skills));
  let status: string;
  if (r.missingRequired.includes(skill)) status = "is a **required** skill you are still missing";
  else if (r.missingPreferred.includes(skill)) status = "is a nice-to-have you are still missing";
  else if (owned.has(skill) && [...r.matchedRequired, ...r.matchedPreferred].includes(skill)) status = "is already on your profile and counts towards your score";
  else if (owned.has(skill)) status = "is on your profile but is not scored for this role";
  else status = "is not part of this role's requirements, but is still a useful extra";
  if (!info) return `**${skill}** ${status}.`;
  const steps = info.steps.map((s, i) => `${i + 1}. ${s}`).join("\n");
  return `**${skill}** ${status} for ${a.role}. Plan (~${info.hours} h):\n${steps}\n\n**Mini-project:** ${info.project}`;
}

export function ruleBasedReply(question: string, a: Assessment): string {
  const q = (question ?? "").toLowerCase().trim();
  const r = a.result;
  const p = a.profile;
  const top = a.actions[0];
  if (!q) return "Ask me anything about your score, skill gaps, projects or interview prep.";

  const mentioned = extractSkills(question);
  if (mentioned.length && has(q, "learn", "how", "start", "study", "resource", "course", "practice", "improve", "need", "should")) {
    return mentioned.slice(0, 2).map((s) => skillHelp(s, a)).join("\n\n");
  }
  if (has(q, "which role", "best role", "fit", "switch", "other role", "better role", "suit")) {
    const ranked = Object.entries(a.roleScores).sort((x, y) => y[1] - x[1]);
    const lines = ranked.map(([k, v]) => `- **${k}**: ${v.toFixed(1)}`).join("\n");
    const best = ranked[0][0];
    return `Your role-specific readiness scores:\n${lines}\n\n${best === a.role ? "You are already targeting your best-fit role." : `**${best}** is currently your strongest fit; applying to it alongside ${a.role} widens your chances.`}`;
  }
  if (has(q, "plan", "week", "schedule", "roadmap", "timeline", "first", "priorit", "next", "where do i start", "what should i")) {
    if (!a.actions.length) return "Nothing urgent: your profile is in great shape. Keep polishing projects and mock interviews.";
    const lines = a.actions.slice(0, 3).map((x, i) => `${i + 1}. **${x.title}**: +${x.impact.toFixed(1)} pts, ~${x.hours} h`).join("\n");
    const tl = buildTimeline(a.actions, 10, 5);
    return `Start with the highest-impact, lowest-effort items:\n${lines}\n\nAt ~10 h/week the first ${tl.length} actions take roughly **${tl[tl.length - 1]?.weeks ?? "1"} weeks** and could lift you to about **${a.potential.toFixed(0)}/100**. First step: ${top.steps[0]}`;
  }
  if (has(q, "gap", "missing", "lack", "skills do i", "what skills", "weak skill")) {
    return `For **${a.role}** you have: ${r.matchedRequired.join(", ") || "none yet"}.\n\n**Missing required:** ${r.missingRequired.join(", ") || "none"}\n\n**Nice-to-have gaps:** ${r.missingPreferred.slice(0, 4).join(", ") || "none"}\n\nAsk "how do I learn <skill>?" for a step-by-step plan.`;
  }
  if (has(q, "why", "score", "low", "explain", "breakdown", "weak", "points", "how am i", "result")) {
    const worst = [...r.components].sort((x, y) => y.weight - y.points - (x.weight - x.points)).slice(0, 3);
    const lines = worst.map((c) => `- **${c.name}**: ${c.points.toFixed(1)}/${c.weight} (${c.detail})`).join("\n");
    return `Your score is **${r.total.toFixed(1)}/100 (${r.level})** for ${a.role}. The three biggest point losses:\n${lines}${top ? `\n\nFixing the top action (${top.title}) adds about +${top.impact.toFixed(1)} pts.` : ""}`;
  }
  if (has(q, "project", "portfolio", "github")) {
    const ideas = [...r.missingRequired, ...r.missingPreferred].slice(0, 3).map((s) => getSkill(s)?.project).filter(Boolean).map((i) => `- ${i}`).join("\n");
    return `You have **${p.projects}** project(s); 4+ earns full marks.\nProjects that also close your gaps:\n${ideas || `- Build something a ${a.role} would ship at work.`}\n\nAdd a README, a live demo and one quantified result per project.`;
  }
  if (has(q, "internship", "experience", "apply", "job", "placement", "offer")) {
    return `You have **${p.internships}** internship(s).\n- Apply to 10 roles a week with a role-tailored resume.\n- Do a free virtual internship or open-source contribution if you have no offers yet.\n- Ask alumni and the placement cell for referrals.\n${r.level === "Needs work" ? "Close the top 2-3 skill gaps first, then apply." : "You can start applying now."}`;
  }
  if (has(q, "cert", "course", "badge")) {
    return `You hold **${p.certifications}** certification(s). Good options for ${a.role}:\n${(ROLE_CERTS[a.role] ?? []).map((c) => `- ${c}`).join("\n")}`;
  }
  if (has(q, "communicat", "interview", "soft", "speak", "present")) {
    return `Your communication score is **${Math.round(p.communication)}/100**.\n- Record a 2-minute self-introduction and refine it.\n- Prepare 5 STAR stories (challenge, action, result, learning).\n- Do 2 mock interviews and present a project demo to a club.`;
  }
  if (has(q, "cgpa", "gpa", "grade", "academic", "aptitude", "marks")) {
    return `Academics: CGPA ${p.cgpa.toFixed(2)} and aptitude ${Math.round(p.aptitude)}/100. Aptitude is the faster lever: 20 timed questions a day for 3 weeks usually adds 10-15 points.`;
  }
  if (has(q, "resume", "cv")) {
    return "Resume checklist: a Projects section with quantified results, a skills line that mirrors the job description, GitHub + LinkedIn links and one page.";
  }
  if (has(q, "ready", "level", "chance", "good enough", "am i")) {
    const next = r.level === "Ready" ? "You are already Ready: start applying." : `You need **${((r.level === "Almost ready" ? 75 : 50) - r.total).toFixed(1)} more points** to reach the next level.`;
    return `You are **${r.level}** (${r.total.toFixed(1)}/100) for ${a.role}. ${next}`;
  }
  if (/\b(hi|hello|hey|help|who are you)\b/.test(q)) {
    return `Hi ${p.name.split(" ")[0]}! I'm your internship mentor. You scored **${r.total.toFixed(1)} (${r.level})** for ${a.role}. Try: *Why is my score low?*, *What should I learn first?*, *How do I learn SQL?* or *Which role fits me best?*`;
  }
  return `You're **${r.level}** (${r.total.toFixed(1)}/100) for ${a.role}. Your top priority is **${top?.title ?? "polishing your portfolio"}**. Ask about your score, skill gaps, a learning plan, projects, internships or which role fits you best.`;
}

export function buildMarkdownReport(a: Assessment): string {
  const r = a.result;
  const p = a.profile;
  const lines: string[] = [
    `# Internship Readiness Report: ${p.name}`,
    "",
    `*Target role: **${a.role}***`,
    "",
    `## Overall score: ${r.total.toFixed(1)} / 100 (${r.level})`,
    `Estimated score after completing the top actions: **${a.potential.toFixed(1)}**`,
    "",
    "## Score breakdown",
    "",
    "| Component | Weight | Points | Why |",
    "|---|---:|---:|---|",
    ...r.components.map((c) => `| ${c.name} | ${c.weight} | ${c.points.toFixed(1)} | ${c.detail} |`),
    "",
    "## Skill gaps",
    `- Matched required: ${r.matchedRequired.join(", ") || "none"}`,
    `- Missing required: ${r.missingRequired.join(", ") || "none"}`,
    `- Missing preferred: ${r.missingPreferred.join(", ") || "none"}`,
    "",
    "## Action plan",
  ];
  a.actions.forEach((x, i) => {
    lines.push("", `### ${i + 1}. ${x.title} [${x.priority}]`, `*Impact: +${x.impact.toFixed(1)} pts | Effort: ~${x.hours} h*`, "");
    x.steps.forEach((s, j) => lines.push(`${j + 1}. ${s}`));
    if (x.projectIdea) lines.push("", `**Mini-project:** ${x.projectIdea}`);
  });
  lines.push("", "---", "*Scores are guidance, not a guarantee.*", "");
  return lines.join("\n");
}
