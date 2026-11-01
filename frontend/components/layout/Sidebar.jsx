"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import NavSections from "./NavSections";
import Brand from "./Brand";

export default function Sidebar() {
  const router = useRouter();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="hidden h-screen w-[248px] shrink-0 flex-col border-r border-ink-700 bg-ink-900/80 lg:sticky lg:top-0 lg:flex">
      <div className="px-5 pb-4 pt-6">
        <Brand />
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4">
        <NavSections />
      </div>

      <div className="border-t border-ink-700 p-3">
        <div className="flex items-center gap-2">
          <Link
            href="/profile"
            className="flex min-w-0 flex-1 items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-white/[0.04]"
          >
            <span
              aria-hidden="true"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-ink-600 bg-ink-800 text-xs text-text"
            >
              {(user?.name || "?").slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm text-text">{user?.name || "Guest"}</span>
              <span className="block truncate text-[11px] text-text-dim">{user?.role || "Member"}</span>
            </span>
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
            className="rounded-lg p-2 text-text-dim transition-colors hover:bg-white/[0.04] hover:text-text"
          >
            <LogOut aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
