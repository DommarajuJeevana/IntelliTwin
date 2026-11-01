import Link from "next/link";

export default function Brand({ compact = false }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-3" aria-label="IntelliTwin home">
      <span
        aria-hidden="true"
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-agent-echo/30 bg-agent-echo/10 font-display text-xs font-semibold text-agent-echo"
      >
        IT
      </span>
      <span>
        <span className="block font-display text-sm font-semibold text-text">IntelliTwin</span>
        {compact ? null : (
          <span className="block text-[10px] text-text-dim">Intelligent workspace</span>
        )}
      </span>
    </Link>
  );
}
