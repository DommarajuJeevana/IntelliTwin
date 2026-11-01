export default function Badge({ children, tone = "cyan" }) {
  const tones = {
    cyan: "bg-cyan-400/10 text-cyan-300 border-cyan-400/30",
    dim: "bg-ink-700 text-text-dim border-ink-600",
    violet: "bg-accent-violet/10 text-accent-violet border-accent-violet/30",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs ${tones[tone]}`}>
      {children}
    </span>
  );
}
