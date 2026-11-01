import Link from "next/link";
import { AGENTS } from "../../lib/agents";

/**
 * Renders the drift insight from the dashboard summary. Deliberately quiet
 * when things are fine and only takes visual weight when Echo has something
 * worth the user's attention (drifting / no profile).
 */
export default function DriftBanner({ drift }) {
  if (!drift) return null;
  const Echo = AGENTS.echo;
  const Icon = Echo.icon;

  if (drift.status === "drifting") {
    return (
      <div className={`mt-4 flex items-start gap-3 rounded-xl border p-3.5 ${Echo.soft}`}>
        <Icon aria-hidden="true" className={`mt-0.5 h-4 w-4 shrink-0 ${Echo.text}`} strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-sm font-medium text-text">Echo noticed something</p>
          <p className="mt-1 text-sm leading-6 text-text-dim">{drift.message}</p>
          <Link href="/profile" className={`mt-2 inline-block text-xs hover:underline ${Echo.text}`}>
            Update your focus →
          </Link>
        </div>
      </div>
    );
  }

  if (drift.status === "no_profile") {
    return (
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed border-ink-600 p-3.5">
        <p className="text-sm text-text-dim">{drift.message}</p>
        <Link href="/profile" className={`text-xs hover:underline ${Echo.text}`}>
          Fill in profile →
        </Link>
      </div>
    );
  }

  if (drift.status === "aligned") {
    return (
      <p className="mt-4 flex items-center gap-2 text-xs text-text-dim">
        <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${Echo.dot}`} />
        {drift.message}
      </p>
    );
  }

  return null; // not_enough_activity: stay quiet rather than nag
}
