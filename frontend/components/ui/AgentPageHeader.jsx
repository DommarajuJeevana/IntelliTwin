import { AGENTS } from "../../lib/agents";

/**
 * Shared header for the four agent pages so Echo, Atlas, Compass and Nova
 * read as one family: same layout, each with its own icon and colour.
 */
export default function AgentPageHeader({ agent, title, description, aside = null }) {
  const identity = AGENTS[agent];
  const Icon = identity.icon;

  return (
    <header className="border-b border-ink-700 pb-6">
      <div className="flex items-start justify-between gap-6">
        <div className="flex items-start gap-4">
          <span
            aria-hidden="true"
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${identity.soft}`}
          >
            <Icon className={`h-5 w-5 ${identity.text}`} strokeWidth={1.75} />
          </span>

          <div>
            <p className={`text-[11px] font-medium uppercase tracking-[0.2em] ${identity.text}`}>
              {identity.name}
              <span className="px-2 text-text-dim/50" aria-hidden="true">
                /
              </span>
              <span className="text-text-dim">{identity.role}</span>
            </p>
            <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
              {title}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">{description}</p>
          </div>
        </div>
        {aside}
      </div>
    </header>
  );
}
