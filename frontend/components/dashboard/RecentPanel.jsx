import Link from "next/link";
import { FileText, NotebookPen, Pin } from "lucide-react";
import Panel from "./Panel";
import { relativeTime } from "../../lib/format";
import { AGENTS } from "../../lib/agents";

const MAX_ITEMS = 6;

function stamp(item) {
  return new Date(item.updatedAt || item.createdAt || 0).getTime();
}

function plainTitle(item, fallback) {
  return (item.title || "").trim() || fallback;
}

export default function RecentPanel({ notes, documents, onRetry, className = "" }) {
  // Show whichever source loaded; only report an error if neither did.
  const sources = [notes, documents];
  const ready = sources.filter((s) => s.status === "ready");
  const state = ready.length
    ? { status: "ready" }
    : sources.some((s) => s.status === "loading")
    ? { status: "loading" }
    : sources.find((s) => s.status === "error") || sources[0];

  const items = [
    ...(notes.data || []).map((n) => ({ kind: "note", item: n })),
    ...(documents.data || []).map((d) => ({ kind: "document", item: d })),
  ]
    .sort((a, b) => stamp(b.item) - stamp(a.item))
    .slice(0, MAX_ITEMS);

  const Nova = AGENTS.nova;

  return (
    <Panel
      title="Recent notes & documents"
      icon={FileText}
      href="/notes"
      linkLabel="Notes"
      state={state}
      onRetry={() => {
        onRetry("notes");
        onRetry("documents");
      }}
      isEmpty={items.length === 0}
      emptyTitle="No notes or documents yet"
      emptyHint="Capture a note, or ask Nova to draft a document."
      emptyHref="/notes"
      emptyLabel="Write a note"
      className={className}
    >
      <ul className="space-y-0.5">
        {items.map(({ kind, item }) => {
          const isNote = kind === "note";
          const Icon = isNote ? NotebookPen : FileText;
          return (
            <li key={`${kind}-${item._id}`}>
              <Link
                href={`/editor/${isNote ? "notes" : "documents"}/${item._id}`}
                className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-white/[0.04]"
              >
                <Icon
                  aria-hidden="true"
                  className={`h-4 w-4 shrink-0 ${isNote ? "text-text-dim" : Nova.text}`}
                  strokeWidth={1.75}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-text">
                    {plainTitle(item, isNote ? "Untitled note" : "Untitled document")}
                  </span>
                  <span className="block text-[11px] text-text-dim">
                    {isNote ? "Note" : item.status === "final" ? "Document · final" : "Document · draft"}
                  </span>
                </span>
                {isNote && item.pinned ? (
                  <Pin aria-label="Pinned" className="h-3 w-3 shrink-0 text-text-dim" />
                ) : null}
                <span className="shrink-0 text-[11px] text-text-dim">{relativeTime(item.updatedAt || item.createdAt)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
