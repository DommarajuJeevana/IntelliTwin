export default function ProgressBar({ value = 0, className = "" }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={`h-1.5 w-full rounded-full bg-ink-700 overflow-hidden ${className}`}>
      <div className="h-full bg-cyan-400" style={{ width: `${pct}%` }} />
    </div>
  );
}
