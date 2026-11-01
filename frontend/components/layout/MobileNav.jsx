"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X, LogOut } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import NavSections from "./NavSections";
import Brand from "./Brand";

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const closeRef = useRef(null);
  const openRef = useRef(null);

  // Close after any navigation.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Escape closes; focus moves into the drawer and returns to the trigger.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const trigger = openRef.current;
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      trigger?.focus();
    };
  }, [open]);

  function handleLogout() {
    setOpen(false);
    logout();
    router.replace("/login");
  }

  return (
    <div className="lg:hidden">
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-ink-700 bg-ink-900/95 px-4 py-3 backdrop-blur">
        <Brand compact />
        <button
          ref={openRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-ink-600 text-text-dim transition-colors hover:text-text"
        >
          <Menu aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      {open ? (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            tabIndex={-1}
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/70"
            onClick={() => setOpen(false)}
          />

          <aside className="absolute inset-y-0 right-0 flex w-[300px] max-w-[88vw] flex-col border-l border-ink-700 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm text-text">{user?.name || "Guest"}</p>
                <p className="truncate text-[11px] text-text-dim">{user?.role || "Member"}</p>
              </div>
              <button
                ref={closeRef}
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation"
                className="rounded-lg p-2 text-text-dim transition-colors hover:text-text"
              >
                <X aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-3 py-4">
              <NavSections onNavigate={() => setOpen(false)} />
            </div>

            <div className="border-t border-ink-700 p-3">
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-text-dim transition-colors hover:bg-white/[0.04] hover:text-text"
              >
                <LogOut aria-hidden="true" className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
