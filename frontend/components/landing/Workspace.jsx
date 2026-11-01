"use client";

import { motion } from "framer-motion";
import {
  Target,
  CheckSquare,
  FolderKanban,
  CalendarDays,
  Search,
  FileText,
  NotebookPen,
  Brain,
  Clock3,
  Bell,
  ArrowRight,
} from "lucide-react";

import SectionHeading from "./SectionHeading";

const modules = [
  { title: "Goals", icon: Target },
  { title: "Tasks", icon: CheckSquare },
  { title: "Projects", icon: FolderKanban },
  { title: "Calendar", icon: CalendarDays },
  { title: "Research", icon: Search },
  { title: "Documents", icon: FileText },
  { title: "Notes", icon: NotebookPen },
  { title: "Memory Timeline", icon: Brain },
  { title: "Notifications", icon: Bell },
  { title: "Universal Search", icon: Search },
  { title: "Schedule", icon: Clock3 },
];

export default function Workspace() {
  return (
    <section
      id="workspace"
      className="relative overflow-hidden bg-ink-950 py-32"
    >
      {/* Background Glow */}

      <div className="absolute left-1/2 top-20 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-accent/[0.05] blur-[160px]" />

      <div className="relative z-10 mx-auto max-w-7xl px-6 lg:px-10">
        <SectionHeading
          badge="Universal Workspace"
          title="Everything Works Together."
          description="Goals, research, tasks, notes, schedules and documents are connected inside one intelligent workspace instead of being scattered across different apps."
        />

        <div className="mt-20 grid items-center gap-16 lg:grid-cols-2">
          {/* LEFT */}

          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: .7 }}
            className="space-y-8"
          >
            <h3 className="text-4xl font-black text-text">
              Build your workspace.
            </h3>

            <p className="text-lg leading-8 text-text-dim">
              Every goal connects to projects.
              <br />
              Every project connects to research.
              <br />
              Every research connects to documents.
              <br />
              Every document connects to tasks.
              <br />
              Every task connects to schedules.
              <br />
              Every schedule becomes memory.
            </p>

            <div className="space-y-5">
              {[
                "Everything connected",
                "Persistent Memory",
                "Universal Search",
                "Cross-module Intelligence",
                "AI-powered organization",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-4"
                >
                  <div className="h-2 w-2 rounded-full bg-accent" />

                  <span className="text-text/80">
                    {item}
                  </span>
                </div>
              ))}
            </div>

            <button
              className="
                mt-8
                inline-flex
                items-center
                gap-3
                rounded-2xl
                bg-accent
                px-6
                py-4
                font-semibold
                text-ink-950
                transition
                hover:scale-105
              "
            >
              Explore Workspace

              <ArrowRight size={18} />
            </button>
          </motion.div>

          {/* RIGHT */}

          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: .7 }}
            className="
              relative
              overflow-hidden
              rounded-[34px]
              border
              border-ink-700
              bg-white/[0.04]
              p-8
              backdrop-blur-2xl
            "
          >
            {/* Brain */}

            <div className="absolute left-1/2 top-1/2 z-20 flex h-28 w-28 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-accent/30 bg-accent/10 backdrop-blur-xl ">
              <Brain className="h-12 w-12 text-accent" />
            </div>

            <div className="grid grid-cols-2 gap-5">
              {modules.map((module, index) => {
                const Icon = module.icon;

                return (
                  <motion.div
                    key={module.title}
                    initial={{
                      opacity: 0,
                      y: 30,
                    }}
                    whileInView={{
                      opacity: 1,
                      y: 0,
                    }}
                    viewport={{
                      once: true,
                    }}
                    transition={{
                      delay: index * .05,
                    }}
                    whileHover={{
                      y: -6,
                      scale: 1.03,
                    }}
                    className="
                      rounded-2xl
                      border
                      border-ink-700
                      bg-ink-900
                      p-5
                      transition-all
                      hover:border-accent/40
                      hover:bg-accent/5
                    "
                  >
                    <Icon className="mb-5 h-7 w-7 text-accent" />

                    <h4 className="font-semibold text-text">
                      {module.title}
                    </h4>

                    <p className="mt-2 text-sm text-text-dim">
                      Connected to every other module.
                    </p>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}