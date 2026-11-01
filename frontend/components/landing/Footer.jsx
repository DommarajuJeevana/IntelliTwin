import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-ink-700 bg-ink-950">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-8 px-6 py-12 text-center lg:flex-row">
        <div>
          <h2 className="text-2xl font-bold text-text">
            IntelliTwin
          </h2>

          <p className="mt-2 text-text-dim/70">
            AI-Powered Intelligent Workspace
          </p>
        </div>

        <div className="flex flex-wrap justify-center gap-8 text-text-dim">
          <Link href="#">GitHub</Link>
          <Link href="#">Documentation</Link>
          <Link href="#">Privacy</Link>
          <Link href="#">Terms</Link>
          <Link href="#">Contact</Link>
        </div>

        <p className="text-sm text-text-dim/70">
          © 2026 IntelliTwin. All rights reserved.
        </p>
      </div>
    </footer>
  );
}