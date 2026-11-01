import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { greetingFor, daysFromToday } from "../../lib/format";

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/**
 * One honest line built only from data that actually loaded. Parts whose
 * source failed or is still loading are left out rather than guessed.
 */
function overview({ tasks, calendar, goals }) {
  const parts = [];

  if (tasks.status === "ready") {
    const open = tasks.data.filter((t) => t.status !== "done");
    const overdue = open.filter((t) => daysFromToday(t.dueDate) !== null && daysFromToday(t.dueDate) < 0).length;
    const today = open.filter((t) => daysFromToday(t.dueDate) === 0).length;
    if (overdue) parts.push(`${plural(overdue, "task")} overdue`);
    if (today) parts.push(`${plural(today, "task")} due today`);
    if (!overdue && !today && open.length) parts.push(`${plural(open.length, "open task")}, none due today`);
  }

  if (calendar.status === "ready") {
    const now = Date.now();
    const todays = calendar.data.filter((e) => {
      if (daysFromToday(e.startsAt) !== 0) return false;
      const end = new Date(e.endsAt || e.startsAt).getTime();
      return end >= now;
    }).length;
    if (todays) parts.push(`${plural(todays, "event")} left today`);
  }

  if (goals.status === "ready") {
    const active = goals.data.filter((g) => g.status !== "done").length;
    if (active) parts.push(`${plural(active, "active goal")}`);
  }

  if (!parts.length) {
    const anyReady = [tasks, calendar, goals].some((s) => s.status === "ready");
    return anyReady ? "Nothing urgent on your plate right now." : null;
  }
  return parts.join(" · ");
}

export default function Greeting({ user, tasks, calendar, goals }) {
  const now = new Date();
  const firstName = (user?.name || "").trim().split(/\s+/)[0];
  const loading = [tasks, calendar, goals].some((s) => s.status === "loading");
  const line = overview({ tasks, calendar, goals });

  return (
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-xs text-text-dim">
          {now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </p>
        <h1 className="mt-1.5 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
          {greetingFor(now.getHours())}
          {firstName ? `, ${firstName}` : ""}
        </h1>
        <div className="mt-2 min-h-[1.25rem] text-sm text-text-dim" aria-live="polite">
          {loading && !line ? <div className="skeleton h-4 w-64" aria-hidden="true" /> : line}
        </div>
      </div>

      <Link
        href="/privacy"
        className="inline-flex w-fit items-center gap-1.5 rounded-full border border-ink-600 px-3.5 py-1.5 text-xs text-text-dim transition-colors hover:border-ink-500 hover:text-text"
      >
        What your twin knows
        <ArrowRight aria-hidden="true" className="h-3 w-3" />
      </Link>
    </header>
  );
}
