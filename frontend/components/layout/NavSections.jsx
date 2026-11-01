"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import {
  HOME_NAV,
  AGENT_NAV,
  WORKSPACE_NAV,
  ACCOUNT_NAV,
  PRODUCT_NAV,
  isActive,
} from "./navConfig";

function NavLink({ item, pathname, onNavigate }) {
  const active = isActive(pathname, item.href);
  const Icon = item.icon;
  const tint = item.agent?.text;

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-white/[0.07] text-text"
          : "text-text-dim hover:bg-white/[0.04] hover:text-text"
      }`}
    >
      {Icon ? (
        <Icon
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 ${tint || (active ? "text-accent" : "text-text-dim group-hover:text-text")}`}
          strokeWidth={1.75}
        />
      ) : null}
      <span className="truncate">{item.label}</span>
      {item.hint ? (
        <span className="ml-auto text-[10px] uppercase tracking-wider text-text-dim/60">
          {item.hint}
        </span>
      ) : null}
    </Link>
  );
}

function Group({ label, items, pathname, onNavigate }) {
  return (
    <div>
      {label ? (
        <p className="mb-1.5 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim/60">
          {label}
        </p>
      ) : null}
      <div className="space-y-0.5">
        {items.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  );
}

/** Shared by the desktop sidebar and the mobile drawer. */
export default function NavSections({ onNavigate }) {
  const pathname = usePathname();
  const moreActive = ACCOUNT_NAV.some((i) => isActive(pathname, i.href));

  return (
    <nav aria-label="Primary" className="space-y-6">
      <Group items={HOME_NAV} pathname={pathname} onNavigate={onNavigate} />
      <Group label="Agents" items={AGENT_NAV} pathname={pathname} onNavigate={onNavigate} />
      <Group label="Workspace" items={WORKSPACE_NAV} pathname={pathname} onNavigate={onNavigate} />

      <details className="group/more" open={moreActive || undefined}>
        <summary className="flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim/60 transition-colors hover:text-text-dim [&::-webkit-details-marker]:hidden">
          More
          <ChevronDown
            aria-hidden="true"
            className="h-3.5 w-3.5 transition-transform group-open/more:rotate-180"
          />
        </summary>
        <div className="mt-1 space-y-4">
          <Group items={ACCOUNT_NAV} pathname={pathname} onNavigate={onNavigate} />
          <div>
            <p className="mb-1.5 px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim/60">
              About IntelliTwin
            </p>
            <div className="space-y-0.5">
              {PRODUCT_NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className="block rounded-lg px-3 py-1.5 text-sm text-text-dim transition-colors hover:bg-white/[0.04] hover:text-text"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </details>
    </nav>
  );
}
