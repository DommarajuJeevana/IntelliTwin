import Link from "next/link";

const AGENT_STYLE = {
  echo: {
    label: "Echo",
    role: "Memory",
    href: "/dashboard",
  },
  atlas: {
    label: "Atlas",
    role: "Research",
    href: "/dashboard",
  },
  compass: {
    label: "Compass",
    role: "Planning",
    href: "/dashboard",
  },
  nova: {
    label: "Nova",
    role: "Creation",
    href: "/dashboard",
  },
};

export default function BriefingCard({ briefing }) {
  if (!briefing || briefing.length === 0) {
    return null;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-ink-700 bg-ink-900">
      <div className="divide-y divide-ink-700">
        {briefing.map((note, index) => {
          const meta =
            AGENT_STYLE[note.agent] || {
              label: note.agent,
              role: "Agent",
              href: "/dashboard",
            };

          return (
            <div
              key={`${note.agent}-${index}`}
              className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-ink-600 bg-ink-950 font-display text-sm text-text">
                {meta.label.slice(0, 1)}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium text-text">
                    {meta.label}
                  </p>

                  <span className="text-[10px] uppercase tracking-wide text-text-dim">
                    {meta.role}
                  </span>
                </div>

                <p className="mt-1 text-sm leading-relaxed text-text-dim">
                  {note.message}
                </p>
              </div>

              <Link
                href={meta.href}
                className="inline-flex w-fit shrink-0 items-center rounded-lg border border-ink-600 px-3 py-2 text-xs text-text-dim transition hover:border-ink-500 hover:text-text"
              >
                Open Mission Control
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
}