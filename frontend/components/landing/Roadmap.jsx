"use client";

import { motion } from "framer-motion";
import { roadmap } from "@/lib/landingData";
import SectionHeading from "./SectionHeading";

export default function Roadmap() {
  return (
    <section
      id="roadmap"
      className="relative bg-ink-950 py-32 overflow-hidden"
    >
      <div className="absolute left-1/2 top-0 h-full w-px bg-white/[0.07] -translate-x-1/2" />

      <div className="mx-auto max-w-6xl px-6">
        <SectionHeading
          badge="Roadmap"
          title="Building The Future Of AI Workspaces"
          description="Our vision for IntelliTwin."
        />

        <div className="relative mt-24 space-y-20">
          {roadmap.map((phase, index) => (
            <motion.div
              key={phase}
              initial={{ opacity: 0, y: 50 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * .08 }}
              className={`flex ${
                index % 2 === 0
                  ? "justify-start"
                  : "justify-end"
              }`}
            >
              <div className="relative w-full max-w-md">
                <span className="absolute top-8 left-1/2 -translate-x-1/2 h-5 w-5 rounded-full bg-accent " />

                <div className="rounded-3xl border border-ink-700 bg-white/[0.04] p-8 backdrop-blur-xl">
                  <p className="text-sm uppercase tracking-[.3em] text-accent">
                    Phase {index + 1}
                  </p>

                  <h3 className="mt-3 text-3xl font-bold text-text">
                    {phase}
                  </h3>

                  <p className="mt-4 leading-8 text-text-dim">
                    Expand IntelliTwin with intelligent,
                    connected capabilities that continue
                    to improve the workspace experience.
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}