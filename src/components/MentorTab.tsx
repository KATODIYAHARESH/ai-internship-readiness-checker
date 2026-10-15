"use client";

import { useEffect, useRef, useState } from "react";
import type { Assessment } from "@/lib/readiness/engine";
import { Card, Chip, inputCls } from "./ui";

interface Message {
  role: "user" | "assistant";
  content: string;
  source?: "ollama" | "rule-based";
  note?: string;
}

const SUGGESTIONS = ["Why is my score low?", "What should I learn first?", "Which role fits me best?", "How do I learn SQL?", "Give me a 4-week plan"];

/** Renders **bold**, *italic* and line breaks without pulling in a markdown library. */
function Rich({ text }: { text: string }) {
  return (
    <div className="space-y-1 text-sm leading-relaxed text-slate-800">
      {text.split("\n").map((line, i) => (
        <p key={i} className={line.startsWith("- ") ? "pl-3" : ""}>
          {line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, j) =>
            part.startsWith("**") ? <strong key={j}>{part.slice(2, -2)}</strong> : part.startsWith("*") && part.length > 2 ? <em key={j}>{part.slice(1, -1)}</em> : <span key={j}>{part}</span>,
          )}
        </p>
      ))}
    </div>
  );
}

export default function MentorTab({ assessment }: { assessment: Assessment }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const contextKey = `${assessment.profile.name}|${assessment.role}|${assessment.result.total}`;
  const lastContext = useRef(contextKey);

  useEffect(() => {
    if (lastContext.current !== contextKey) {
      lastContext.current = contextKey;
      setMessages([]);
    }
  }, [contextKey]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy]);

  async function ask(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/mentor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, role: assessment.role, profile: assessment.profile, history }),
      });
      const data = (await res.json()) as { reply?: string; source?: "ollama" | "rule-based"; note?: string; error?: string };
      if (!res.ok || !data.reply) throw new Error(data.error ?? "Mentor unavailable");
      setMessages((m) => [...m, { role: "assistant", content: data.reply as string, source: data.source, note: data.note }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `Sorry, something went wrong: ${(err as Error).message}`, source: "rule-based" }]);
    } finally {
      setBusy(false);
    }
  }

  const r = assessment.result;
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card>
        <p className="text-sm text-slate-700">
          Context sent to the mentor: <b>{assessment.profile.name}</b> → <b>{assessment.role}</b>, score <b>{r.total.toFixed(1)}</b> ({r.level}); missing: {r.missingRequired.slice(0, 5).join(", ") || "nothing"}.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          The route tries a local Ollama (llama3.2) first and falls back to the rule-based mentor automatically, exactly like the Streamlit app.
        </p>
      </Card>

      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <Chip key={s} kind="neutral" onClick={() => void ask(s)}>
            {s}
          </Chip>
        ))}
        {messages.length > 0 && (
          <Chip kind="warn" onClick={() => setMessages([])}>
            Clear
          </Chip>
        )}
      </div>

      <Card className="min-h-[320px]">
        <div className="max-h-[480px] space-y-3 overflow-y-auto pr-1" aria-live="polite">
          {messages.length === 0 && <p className="text-sm text-slate-500">Try a suggestion above or ask e.g. “How do I learn Docker?” or “Am I ready to apply?”.</p>}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[88%] rounded-2xl px-4 py-2.5 ${m.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100"}`}>
                {m.role === "user" ? <p className="text-sm">{m.content}</p> : <Rich text={m.content} />}
                {m.role === "assistant" && (
                  <p className="mt-1.5 text-[11px] text-slate-500">{m.source === "ollama" ? "🧠 Ollama" : "📋 Rule-based mentor"}</p>
                )}
              </div>
            </div>
          ))}
          {busy && <p className="text-sm text-slate-500">Mentor is thinking…</p>}
          <div ref={bottom} />
        </div>
      </Card>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
        className="flex gap-2"
      >
        <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={500} placeholder="Ask your mentor about your score, gaps or next steps…" className={inputCls} aria-label="Question for the mentor" />
        <button type="submit" disabled={busy || !input.trim()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40">
          Send
        </button>
      </form>
    </div>
  );
}
