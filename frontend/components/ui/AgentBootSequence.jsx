"use client";
import { useEffect, useState } from "react";

const DEFAULT_STEPS = [
  { id: "auth", label: "Verifying identity" },
  { id: "compass", label: "Compass loading your plan" },
  { id: "atlas", label: "Atlas indexing recent research" },
  { id: "echo", label: "Echo restoring memory" },
  { id: "nova", label: "Nova preparing your workspace" },
];

/**
 * Renders a step-by-step "booting your twin" sequence, ticking one step at a
 * time. Purely presentational - the parent decides how long it runs and
 * what happens on completion (`onDone`).
 */
export default function AgentBootSequence({ steps = DEFAULT_STEPS, stepDurationMs = 480, onDone }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [doneIds, setDoneIds] = useState([]);

  useEffect(() => {
    if (activeIndex >= steps.length) {
      const t = setTimeout(() => onDone && onDone(), 250);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => {
      setDoneIds((d) => [...d, steps[activeIndex].id]);
      setActiveIndex((i) => i + 1);
    }, stepDurationMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIndex]);

  const progressPct = Math.min(100, Math.round((doneIds.length / steps.length) * 100));

  return (
    <div className="w-full">
      <div className="h-1.5 w-full rounded-full bg-ink-700 overflow-hidden mb-4">
        <div
          className="h-full bg-cyan-400 transition-all duration-300 ease-out"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <ul className="space-y-2.5">
        {steps.map((step, i) => {
          const isDone = doneIds.includes(step.id);
          const isActive = i === activeIndex;
          return (
            <li
              key={step.id}
              className={`flex items-center gap-3 text-sm transition-opacity duration-300 ${
                i > activeIndex ? "opacity-30" : "opacity-100"
              }`}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] ${
                  isDone
                    ? "border-cyan-400 bg-cyan-400/10 text-cyan-400"
                    : isActive
                    ? "border-cyan-400 text-cyan-400 animate-pulse"
                    : "border-ink-600 text-ink-600"
                }`}
              >
                {isDone ? "✓" : i + 1}
              </span>
              <span className={isDone ? "text-text" : isActive ? "text-cyan-300" : "text-text-dim"}>
                {step.label}
                {isActive && !isDone ? <span className="animate-pulse">…</span> : null}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
