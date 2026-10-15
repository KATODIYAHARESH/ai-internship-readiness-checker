"use client";

import type { ReactNode } from "react";
import type { Level } from "@/lib/readiness/engine";

export const LEVEL_COLOR: Record<Level, string> = {
  Ready: "#16a34a",
  "Almost ready": "#d97706",
  "Needs work": "#dc2626",
};

export const LEVEL_BG: Record<Level, string> = {
  Ready: "bg-green-100 text-green-800",
  "Almost ready": "bg-amber-100 text-amber-800",
  "Needs work": "bg-red-100 text-red-800",
};

export function barColor(fraction: number): string {
  return fraction >= 0.75 ? "bg-green-500" : fraction >= 0.5 ? "bg-amber-500" : "bg-red-500";
}

export function Card({ title, subtitle, children, className = "" }: { title?: string; subtitle?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {title && (
        <header className="mb-3">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </header>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function LevelBadge({ level }: { level: Level }) {
  return <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${LEVEL_BG[level]}`}>{level}</span>;
}

type ChipKind = "good" | "bad" | "warn" | "neutral";
const CHIP: Record<ChipKind, string> = {
  good: "bg-green-100 text-green-800 hover:bg-green-200",
  bad: "bg-red-100 text-red-800 hover:bg-red-200",
  warn: "bg-amber-100 text-amber-800 hover:bg-amber-200",
  neutral: "bg-slate-100 text-slate-700 hover:bg-slate-200",
};

export function Chip({ children, kind = "neutral", onClick, title }: { children: ReactNode; kind?: ChipKind; onClick?: () => void; title?: string }) {
  const cls = `inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${CHIP[kind]}`;
  return onClick ? (
    <button type="button" onClick={onClick} title={title} className={`${cls} cursor-pointer transition`}>
      {children}
    </button>
  ) : (
    <span className={cls}>{children}</span>
  );
}

export function Gauge({ value, level }: { value: number; level: Level }) {
  const radius = 80;
  const half = Math.PI * radius;
  const pct = Math.min(100, Math.max(0, value)) / 100;
  const arc = "M 20 100 A 80 80 0 0 1 180 100";
  return (
    <svg viewBox="0 0 200 125" role="img" aria-label={`Readiness score ${value.toFixed(1)} out of 100, ${level}`} className="mx-auto w-full max-w-[260px]">
      <path d={arc} fill="none" stroke="#e2e8f0" strokeWidth="16" strokeLinecap="round" />
      <path d={arc} fill="none" stroke={LEVEL_COLOR[level]} strokeWidth="16" strokeLinecap="round" strokeDasharray={`${half * pct} ${half}`} style={{ transition: "stroke-dasharray .5s" }} />
      <text x="100" y="90" textAnchor="middle" fontSize="36" fontWeight="700" fill="#0f172a">
        {value.toFixed(1)}
      </text>
      <text x="100" y="110" textAnchor="middle" fontSize="12" fill={LEVEL_COLOR[level]} fontWeight="600">
        {level}
      </text>
      <text x="14" y="120" fontSize="9" fill="#94a3b8">0</text>
      <text x="176" y="120" fontSize="9" fill="#94a3b8">100</text>
    </svg>
  );
}

export function downloadText(filename: string, text: string, mime = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";
