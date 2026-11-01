import Link from "next/link";
import { Search } from "lucide-react";
import Panel from "./Panel";
import { relativeTime } from "../../lib/format";

const STATUS = {
  complete: { label: "Complete", cls: "text-agent-atlas border-agent-atlas/30 bg-agent-atlas/10" },
  researching: { label: "Researching", cls: "text-text-dim border-ink-600" },
  queued: { label: "Queued", cls: "text-text-dim border-ink-600" },
};

export default function ResearchPanel({ research, onRetry, className = "" }) {
  const items = (research.data || []).slice(0, 3);

  return (
    <Panel
      title="Research findings"
      icon={Search}
      agent="atlas"
      href="/research"
      state={research}
      onRetry={onRetry}
      isEmpty={items.length === 0}
      emptyTitle="No research yet"
      emptyHint="Ask Atlas to look into a question and the findings are saved here."
      emptyHref="/atlas"
      emptyLabel="Open Atlas"
      className={className}
    >
      <ul className="space-y-3">
        {items.map((item) => {
          const status = STATUS[item.status] || STATUS.queued;
          const sources = Array.isArray(item.sources) ? item.sources.length : 0;
          return (
            <li key={item._id}>
              <Link
                href="/research"
                className="block rounded-lg px-2 py-1.5 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="min-w-0 text-sm text-text">{item.query}</span>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] ${status.cls}`}>
                    {status.label}
                  </span>
                </div>
                {item.summary ? (
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-text-dim">{item.summary}</p>
                ) : null}
                <p className="mt-1 text-[11px] text-text-dim/70">
                  {sources ? `${sources} source${sources === 1 ? "" : "s"} · ` : ""}
                  {relativeTime(item.createdAt)}
                </p>
              </Link>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
