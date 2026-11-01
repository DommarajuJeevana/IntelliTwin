import Link from "next/link";
import { Brain } from "lucide-react";
import Panel from "./Panel";
import { relativeTime } from "../../lib/format";

export default function MemoryPanel({ summary, onRetry, className = "" }) {
  const memories = (summary.status === "ready" ? summary.data?.recentMemories : null) || [];
  const items = memories.slice(0, 3);

  return (
    <Panel
      title="What Echo remembers"
      icon={Brain}
      agent="echo"
      href="/memory-timeline"
      linkLabel="Timeline"
      state={summary}
      onRetry={onRetry}
      isEmpty={items.length === 0}
      emptyTitle="No memories yet"
      emptyHint="Echo saves what matters as you work and talk. It will show up here."
      emptyHref="/echo"
      emptyLabel="Open Echo"
      skeletonRows={2}
      className={className}
    >
      <ul className="grid gap-3 md:grid-cols-3">
        {items.map((memory) => (
          <li key={memory._id}>
            <Link
              href="/memory-timeline"
              className="block h-full rounded-xl border border-ink-700 bg-ink-800/40 p-3.5 transition-colors hover:border-ink-600"
            >
              <p className="truncate text-sm text-text">{memory.title || "Untitled memory"}</p>
              {memory.content ? (
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-text-dim">{memory.content}</p>
              ) : null}
              <p className="mt-2 text-[11px] text-text-dim/70">
                {relativeTime(memory.occurredAt || memory.createdAt)}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
