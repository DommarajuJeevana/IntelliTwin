"use client";

import { motion } from "framer-motion";
import { useCases } from "@/lib/landingData";
import SectionHeading from "./SectionHeading";

export default function UseCases() {
  return (
    <section className="bg-ink-950 py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-10">
        <SectionHeading
          badge="Use Cases"
          title="Built For Every Profession"
          description="IntelliTwin adapts to the way you work, regardless of your profession."
        />

        <div className="mt-20 grid gap-8 sm:grid-cols-2 xl:grid-cols-3">
          {useCases.map((item, index) => {
            const Icon = item.icon;

            return (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{
                  delay: index * .06,
                }}
                whileHover={{
                  y: -8,
                }}
                className="
                  group
                  rounded-3xl
                  border
                  border-ink-700
                  bg-white/[0.04]
                  p-8
                  backdrop-blur-xl
                  transition-all
                  hover:border-accent/40
                  
                "
              >
                <div
                  className="
                    mb-6
                    flex
                    h-16
                    w-16
                    items-center
                    justify-center
                    rounded-2xl
                    bg-accent/10
                  "
                >
                  <Icon className="h-8 w-8 text-accent" />
                </div>

                <h3 className="text-2xl font-bold text-text">
                  {item.title}
                </h3>

                <p className="mt-5 leading-8 text-text-dim">
                  IntelliTwin helps {item.title.toLowerCase()}s organize research,
                  tasks, documents, schedules, AI workflows and long-term memory
                  in one connected workspace.
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}