"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function CTA() {
  return (
    <section className="relative overflow-hidden py-36">
      <div className="absolute inset-0 bg-accent/[0.05] blur-[160px]" />

      <div className="relative mx-auto max-w-5xl rounded-3xl border border-accent/20 bg-white/[0.04] px-10 py-20 text-center backdrop-blur-2xl">
        <h2 className="text-5xl font-black text-text">
          Ready to build your intelligent workspace?
        </h2>

        <p className="mx-auto mt-8 max-w-2xl text-lg leading-8 text-text-dim">
          Replace scattered tools with one connected AI-powered workspace.
        </p>

        <Link
          href="/register"
          className="mt-12 inline-flex items-center gap-3 rounded-2xl bg-accent px-8 py-5 font-semibold text-ink-950 transition hover:scale-105"
        >
          Start Free

          <ArrowRight />
        </Link>
      </div>
    </section>
  );
}