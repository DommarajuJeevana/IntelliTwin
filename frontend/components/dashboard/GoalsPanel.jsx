import Link from "next/link";
import { Target } from "lucide-react";
import Panel from "./Panel";
import { NextTaskLine, ResearchLine } from "./ContextLine";
import { dueLabel, DUE_TONE_CLASS } from "../../lib/format";
import { idOf, nextTaskFor, researchFor } from "../../lib/workspaceContext";

function dueMs(goal) {
  const t = goal.dueDate ? new Date(goal.dueDate).getTime() : NaN;
  return Number.isNaN(t) ? Infinity : t;
}

export default function GoalsPanel({ goals, index, onRetry, className = "" }) {
  const active = (goals.data || [])
    .filter((g) => g.status !== "done")
    .sort((a, b) => dueMs(a) - dueMs(b) || (b.progress || 0) - (a.progress || 0))
    .slice(0, 4);

  return (
    <Panel
      title="Goals"
      icon={Target}
      href="/goals"
      state={goals}
      onRetry={onRetry}
      isEmpty={active.length === 0}
      emptyTitle="No active goals"
      emptyHint="Goals track progress from the tasks you link to them."
      emptyHref="/goals"
      emptyLabel="Set a goal"
      className={className}
    >
      <ul className="space-y-4">
        {active.map((goal) => {
          const gid = idOf(goal._id);
          const pct = Math.max(0, Math.min(100, Math.round(goal.progress || 0)));
          const due = dueLabel(goal.dueDate);
          const next = nextTaskFor([gid], index);
          const research = researchFor([gid], index);
          return (
            <li key={gid}>
              <div className="flex items-baseline justify-between gap-3">
                <Link href="/goals" className="min-w-0 truncate text-sm text-text transition-colors hover:text-accent">
                  {goal.title}
                </Link>
                <span className="shrink-0 text-xs tabular-nums text-text-dim">{pct}%</span>
              </div>
              <div
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${goal.title} progress`}
                className="mt-2 h-1 overflow-hidden rounded-full bg-ink-700"
              >
                <div className="h-full rounded-full bg-accent/80" style={{ width: `${pct}%` }} />
              </div>
              <p className="mt-1.5 text-[11px] text-text-dim">
                {goal.totalTasks > 0
                  ? `${goal.completedTasks} of ${goal.totalTasks} tasks done`
                  : "No tasks linked yet"}
                {due ? (
                  <>
                    {" · "}
                    <span className={DUE_TONE_CLASS[due.tone]}>{due.text}</span>
                  </>
                ) : null}
              </p>
              {next || research ? (
                <div className="mt-1.5 space-y-0.5">
                  <NextTaskLine task={next} />
                  <ResearchLine item={research} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
