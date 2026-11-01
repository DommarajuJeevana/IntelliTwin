// Calm, static backdrop for the landing hero: a faint grid and two soft
// glows. No particles or looping motion, so the page stays quiet and cheap.
export default function AnimatedBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse at 50% 30%, black 20%, transparent 75%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 30%, black 20%, transparent 75%)",
        }}
      />
      <div className="absolute -top-56 left-1/2 h-[560px] w-[560px] -translate-x-1/2 rounded-full bg-accent/[0.07] blur-[160px]" />
      <div className="absolute -right-40 bottom-0 h-[420px] w-[420px] rounded-full bg-accent-violet/[0.06] blur-[160px]" />
    </div>
  );
}
