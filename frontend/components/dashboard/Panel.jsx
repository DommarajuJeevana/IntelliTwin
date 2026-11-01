import Link from "next/link";
import { ArrowRight, AlertCircle, RotateCw } from "lucide-react";
import { AGENTS } from "../../lib/agents";

function Skeleton({ rows = 3 }) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-10 w-full" />
      ))}
    </div>
  );
}

/**
 * Shared dashboard surface. Handles loading / error / unavailable / empty so
 * every module behaves the same way.
 *
 *   state    – { status: "loading" | "ready" | "error" | "unavailable", error }
 *   agent    – optional agent id; tints the header icon with that agent's colour
 *   isEmpty  – true when state is ready but there is nothing to show
 */
export default function Panel({
  title,
  icon: Icon,
  agent,
  href,
  linkLabel = "View all",
  state,
  onRetry,
  isEmpty = false,
  emptyTitle,
  emptyHint,
  emptyHref,
  emptyLabel,
  skeletonRows = 3,
  className = "",
  children,
}) {
  const identity = agent ? AGENTS[agent] : null;
  const headingId = `panel-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  const status = state?.status || "ready";

  let body;
  if (status === "loading") {
    body = <Skeleton rows={skeletonRows} />;
  } else if (status === "error") {
    body = (
      <div role="alert" className="flex items-start gap-3 rounded-lg border border-rose-400/20 bg-rose-400/5 p-3">
        <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" />
        <div className="min-w-0 flex-1">
          <p className="text-sm text-rose-200">Couldn&apos;t load {title.toLowerCase()}.</p>
          {state?.error ? <p className="mt-0.5 text-xs text-text-dim">{state.error}</p> : null}
        </div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-md border border-ink-600 px-2.5 py-1 text-xs text-text-dim transition-colors hover:text-text"
          >
            <RotateCw aria-hidden="true" className="h-3 w-3" />
            Retry
          </button>
        ) : null}
      </div>
    );
  } else if (status === "unavailable") {
    body = (
      <p className="rounded-lg border border-dashed border-ink-600 px-4 py-6 text-center text-sm text-text-dim">
        {title} isn&apos;t available right now.
      </p>
    );
  } else if (isEmpty) {
    body = (
      <div className="rounded-lg border border-dashed border-ink-600 px-4 py-6 text-center">
        <p className="text-sm text-text">{emptyTitle}</p>
        {emptyHint ? <p className="mt-1 text-xs text-text-dim">{emptyHint}</p> : null}
        {emptyHref ? (
          <Link
            href={emptyHref}
            className="mt-3 inline-flex items-center gap-1 text-xs text-accent transition-colors hover:underline"
          >
            {emptyLabel} <ArrowRight aria-hidden="true" className="h-3 w-3" />
          </Link>
        ) : null}
      </div>
    );
  } else {
    body = children;
  }

  return (
    <section aria-labelledby={headingId} aria-busy={status === "loading"} className={`panel flex flex-col p-5 ${className}`}>
      <header className="mb-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon ? (
            <span
              aria-hidden="true"
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${
                identity ? identity.soft : "border-ink-600 bg-ink-800"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${identity ? identity.text : "text-text-dim"}`} strokeWidth={1.75} />
            </span>
          ) : null}
          <h2 id={headingId} className="truncate font-display text-sm font-semibold text-text">
            {title}
          </h2>
        </div>
        {href ? (
          <Link
            href={href}
            className="inline-flex shrink-0 items-center gap-1 rounded-md text-xs text-text-dim transition-colors hover:text-text"
          >
            {linkLabel}
            <ArrowRight aria-hidden="true" className="h-3 w-3" />
          </Link>
        ) : null}
      </header>
      <div className="min-h-0 flex-1">{body}</div>
    </section>
  );
}
