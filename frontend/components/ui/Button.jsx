"use client";

export default function Button({ children, variant = "primary", className = "", ...props }) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-accent";
  const variants = {
    primary: "bg-cyan-400 text-ink-950 hover:bg-cyan-500",
    ghost: "bg-transparent border border-ink-600 text-text hover:border-ink-500",
    subtle: "bg-ink-700 text-text hover:bg-ink-600",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
