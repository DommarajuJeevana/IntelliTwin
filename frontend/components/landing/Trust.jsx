"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Lock, Database } from "lucide-react";
import SectionHeading from "./SectionHeading";

const items = [
  {
    title: "Own Your Data",
    icon: Database,
    text: "Everything belongs to you. Export anytime.",
  },
  {
    title: "Transparent AI",
    icon: ShieldCheck,
    text: "View exactly what IntelliTwin remembers.",
  },
  {
    title: "Delete Anytime",
    icon: Lock,
    text: "Remove memories, documents and history whenever you want.",
  },
];

export default function Trust() {
  return (
    <section className="bg-ink-950 py-32">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeading
          badge="Privacy"
          title="AI You Can Trust"
          description="Privacy is built into IntelliTwin from day one."
        />

        <div className="mt-20 grid gap-8 md:grid-cols-3">
          {items.map((item, i) => {
            const Icon = item.icon;

            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * .1 }}
                className="rounded-3xl border border-ink-700 bg-white/[0.04] p-8 backdrop-blur-xl"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10">
                  <Icon className="h-8 w-8 text-accent" />
                </div>

                <h3 className="mt-8 text-2xl font-bold text-text">
                  {item.title}
                </h3>

                <p className="mt-4 leading-8 text-text-dim">
                  {item.text}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}