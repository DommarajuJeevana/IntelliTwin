import Link from "next/link";
import { Compass, ArrowRight, X, Sparkles, RotateCw } from "lucide-react";
import Panel from "./Panel";
import DriftBanner from "../ui/DriftBanner";
import { AGENTS } from "../../lib/agents";
import { relativeTime } from "../../lib/format";

const MODULE_HREF = { tasks: "/tasks", goals: "/goals", calendar: "/calendar" };
const SEVERITY_DOT = { high: "bg-rose-400", medium: "bg-amber-400", low: "bg-ink-500" };
const SEVERITY_LABEL = { high: "Needs attention", medium: "Coming up", low: "Housekeeping" };
const VISIBLE = 5;

function DismissButton({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title="Hide for a week"
      className="shrink-0 rounded-md p-1.5 text-text-dim/60 transition-colors hover:bg-white/[0.06] hover:text-text"
    >
      <X aria-hidden="true" className="h-3.5 w-3.5" />
    </button>
  );
}

function AiTag() {
  const Compass_ = AGENTS.compass;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${Compass_.soft} ${Compass_.text}`}
      title="Written by Compass from your tasks, goals and calendar"
    >
      <Sparkles aria-hidden="true" className="h-2.5 w-2.5" />
      AI
      <span className="sr-only"> suggestion from Compass</span>
    </span>
  );
}

function Primary({ item, onDismiss }) {
  const href = MODULE_HREF[item.module] || "/dashboard";
  return (
    <div className="rounded-xl border border-ink-600 bg-ink-800/60 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-text-dim">
          <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${SEVERITY_DOT[item.severity] || "bg-ink-500"}`} />
          {SEVERITY_LABEL[item.severity] || "Suggested"}
          {item.source === "ai" ? <AiTag /> : null}
        </p>
        <DismissButton onClick={() => onDismiss(item.key)} label="Dismiss this suggestion" />
      </div>
      <p className="mt-2 text-base leading-7 text-text sm:text-lg">{item.message}</p>
      {item.reason ? <p className="mt-1 text-sm leading-6 text-text-dim">{item.reason}</p> : null}
      <Link
        href={href}
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-text px-3.5 py-2 text-xs font-medium text-ink-950 transition-opacity hover:opacity-90"
      >
        Open {item.module || "workspace"}
        <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

function Row({ item, onDismiss }) {
  const href = MODULE_HREF[item.module] || "/dashboard";
  return (
    <li className="flex items-start gap-3 rounded-lg px-1 py-2">
      <span aria-hidden="true" className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${SEVERITY_DOT[item.severity] || "bg-ink-500"}`} />
      <Link href={href} className="group min-w-0 flex-1">
        <span className="block text-sm text-text-dim transition-colors group-hover:text-text">
          {item.source === "ai" ? (
            <span className="mr-1.5 align-middle">
              <AiTag />
            </span>
          ) : null}
          {item.message}
        </span>
        {item.reason ? <span className="mt-0.5 block text-xs leading-5 text-text-dim/70">{item.reason}</span> : null}
      </Link>
      <DismissButton onClick={() => onDismiss(item.key)} label="Dismiss this suggestion" />
    </li>
  );
}

function AgentNotes({ briefing }) {
  const notes = (briefing || []).filter((n) => n?.message).slice(0, 3);
  if (!notes.length) return null;
  return (
    <div className="mt-5 border-t border-ink-700 pt-4">
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-text-dim/70">From your agents</p>
      <ul className="space-y-2.5">
        {notes.map((note, i) => {
          const agent = AGENTS[note.agent];
          const Icon = agent?.icon;
          return (
            <li key={`${note.agent}-${i}`} className="flex items-start gap-2.5">
              {Icon ? (
                <Icon aria-hidden="true" className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${agent.text}`} strokeWidth={1.75} />
              ) : null}
              <p className="text-sm leading-6 text-text-dim">
                {agent ? <span className="sr-only">{agent.name}: </span> : null}
                {note.message}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** One quiet line saying where the AI items stand. Never claims more than is true. */
function AiStatus({ ai, refreshing, onRefresh }) {
  const data = ai.status === "ready" ? ai.data : null;
  if (!data || data.status === "disabled") return null;

  let content = null;
  if (refreshing) {
    content = (
      <span className="flex items-center gap-2">
        <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-agent-compass" />
        Compass is reviewing your workspace…
      </span>
    );
  } else if (data.status === "unavailable") {
    content = (
      <span>
        AI suggestions are unavailable{data.message ? `: ${data.message}` : "."} Showing reminders from your schedule.
      </span>
    );
  } else if (data.status === "ready" && data.generatedAt) {
    content = <span>AI suggestions by Compass · updated {relativeTime(data.generatedAt)}</span>;
  }
  if (!content) return null;

  return (
    <div
      className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 pt-3 text-[11px] text-text-dim"
      role="status"
      aria-live="polite"
    >
      {content}
      {!refreshing && (data.status === "unavailable" || data.status === "ready") ? (
        <button
          type="button"
          onClick={() => onRefresh({ force: true })}
          className="inline-flex items-center gap-1.5 rounded-md border border-ink-600 px-2 py-1 text-text-dim transition-colors hover:text-text"
        >
          <RotateCw aria-hidden="true" className="h-3 w-3" />
          {data.status === "unavailable" ? "Try again" : "Refresh"}
        </button>
      ) : null}
    </div>
  );
}

export default function NextUp({
  suggestions,
  ai,
  aiRefreshing,
  onRefreshAi,
  summary,
  onRetry,
  onDismiss,
  className = "",
}) {
  const aiItems = ai.status === "ready" ? ai.data?.suggestions || [] : [];
  // A rule reminder is redundant once the AI has written about the same record.
  const covered = new Set(aiItems.map((s) => s.recordId).filter(Boolean));
  const ruleItems = (suggestions.data || []).filter((s) => !(s.recordId && covered.has(s.recordId)));
  const items = [...aiItems, ...ruleItems];

  const [first, ...rest] = items;
  const shown = rest.slice(0, VISIBLE - 1);
  const hidden = Math.max(0, rest.length - shown.length);
  const summaryData = summary.status === "ready" ? summary.data : null;
  const thinking = aiRefreshing && !first;

  return (
    <Panel
      title="Next up"
      icon={Compass}
      agent="compass"
      state={suggestions}
      onRetry={onRetry}
      isEmpty={!first && !thinking}
      emptyTitle="You're clear for now"
      emptyHint="Nothing is overdue or coming due. Add a task or goal and it will show up here."
      emptyHref="/tasks"
      emptyLabel="Open tasks"
      skeletonRows={3}
      className={`border-t-2 border-t-agent-compass/40 ${className}`}
    >
      {first ? <Primary item={first} onDismiss={onDismiss} /> : null}
      {thinking ? (
        <p className="rounded-xl border border-dashed border-ink-600 px-4 py-6 text-center text-sm text-text-dim">
          Compass is reviewing your tasks, goals and calendar…
        </p>
      ) : null}

      {shown.length ? (
        <ul className="mt-3 divide-y divide-ink-700/60">
          {shown.map((item) => (
            <Row key={item.key} item={item} onDismiss={onDismiss} />
          ))}
        </ul>
      ) : null}
      {hidden ? <p className="mt-2 px-1 text-xs text-text-dim/70">+{hidden} more in your workspace</p> : null}

      <AiStatus ai={ai} refreshing={aiRefreshing} onRefresh={onRefreshAi} />
      <AgentNotes briefing={summaryData?.briefing} />
      {summaryData?.drift ? <DriftBanner drift={summaryData.drift} /> : null}
    </Panel>
  );
}
