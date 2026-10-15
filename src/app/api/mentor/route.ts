import { ROLE_NAMES, assess, type Profile } from "@/lib/readiness/engine";
import { buildSystemPrompt, ruleBasedReply } from "@/lib/readiness/mentor";

export const dynamic = "force-dynamic";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const num = (v: unknown, lo: number, hi: number): number => {
  const n = typeof v === "number" && Number.isFinite(v) ? v : 0;
  return Math.max(lo, Math.min(hi, n));
};

function sanitizeProfile(raw: Record<string, unknown>, role: string): Profile {
  const skills = Array.isArray(raw.skills) ? raw.skills.filter((s): s is string => typeof s === "string").slice(0, 60) : [];
  return {
    name: typeof raw.name === "string" && raw.name.trim() ? raw.name.trim().slice(0, 80) : "Student",
    major: typeof raw.major === "string" ? raw.major.slice(0, 80) : "Unknown",
    cgpa: num(raw.cgpa, 0, 10),
    projects: Math.floor(num(raw.projects, 0, 50)),
    internships: Math.floor(num(raw.internships, 0, 20)),
    certifications: Math.floor(num(raw.certifications, 0, 50)),
    communication: num(raw.communication, 0, 100),
    aptitude: num(raw.aptitude, 0, 100),
    skills,
    targetRole: role,
  };
}

/** POST { question, role, profile, history? } -> { reply, source: "ollama" | "rule-based", note? } */
export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const question = typeof body.question === "string" ? body.question.trim().slice(0, 500) : "";
  const role = typeof body.role === "string" ? body.role : "";
  if (!question) return Response.json({ error: "Please type a question." }, { status: 400 });
  if (!ROLE_NAMES.includes(role)) return Response.json({ error: "Unknown role." }, { status: 400 });
  if (typeof body.profile !== "object" || body.profile === null) {
    return Response.json({ error: "Missing student profile." }, { status: 400 });
  }

  const assessment = assess(sanitizeProfile(body.profile as Record<string, unknown>, role), role);
  const history: ChatMessage[] = Array.isArray(body.history)
    ? (body.history as ChatMessage[])
        .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content.slice(0, 1500) }))
    : [];

  const host = (process.env.OLLAMA_HOST ?? "http://localhost:11434").replace(/\/$/, "");
  const model = process.env.OLLAMA_MODEL ?? "llama3.2";
  const timeoutMs = Number(process.env.OLLAMA_TIMEOUT_MS ?? 20000);

  try {
    const res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        stream: false,
        options: { temperature: 0.4 },
        messages: [{ role: "system", content: buildSystemPrompt(assessment) }, ...history, { role: "user", content: question }],
      }),
      signal: AbortSignal.timeout(Number.isFinite(timeoutMs) ? timeoutMs : 20000),
    });
    if (!res.ok) throw new Error(`Ollama responded ${res.status}`);
    const data = (await res.json()) as { message?: { content?: string } };
    const content = data.message?.content?.trim();
    if (!content) throw new Error("Empty response");
    return Response.json({ reply: content, source: "ollama", model });
  } catch {
    return Response.json({
      reply: ruleBasedReply(question, assessment),
      source: "rule-based",
      note: "Ollama is not reachable, so this answer comes from the built-in rule-based mentor.",
    });
  }
}
