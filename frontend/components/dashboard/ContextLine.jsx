import Link from "next/link";
import { dueLabel, DUE_TONE_CLASS } from "../../lib/format";
import { AGENTS } from "../../lib/agents";
import { CheckSquare } from "lucide-react";

/** "Next task" row: only rendered when a real task is linked. */
export function NextTaskLine({ task }) {
  if (!task) return null;
  const due = dueLabel(task.dueDate);
  const Planning = AGENTS.compass;
  return (
    <Link
      href="/tasks"
      className="flex items-center gap-2 rounded-md px-2 py-1 text-xs text-text-dim transition-colors hover:bg-white/[0.04] hover:text-text"
    >
      <CheckSquare aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 ${Planning.text}`} strokeWidth={1.75} />
      <span className="shrink-0 text-text-dim/70">Next</span>
      <span className="min-w-0 flex-1 truncate text-text">{task.title}</span>
      {due ? <span className={`shrink-0 ${DUE_TONE_CLASS[due.tone]}`}>{due.text}</span> : null}
    </Link>
  );
}

/** Related research row: only rendered when research is linked to the same goal. */
export function ResearchLine({ item }) {
  if (!item) return null;
  const Research = AGENTS.atlas;
  const Icon = Research.icon;
  return (
    <Link
      href="/research"
      className="flex items-center gap-2 rounded-md px-2 py-1 text-xs text-text-dim transition-colors hover:bg-white/[0.04] hover:text-text"
    >
      <Icon aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 ${Research.text}`} strokeWidth={1.75} />
      <span className="shrink-0 text-text-dim/70">Research</span>
      <span className="min-w-0 flex-1 truncate text-text">{item.query}</span>
    </Link>
  );
}
