"use client";

import { motion } from "framer-motion";
import {
  Brain,
  CalendarDays,
  CheckSquare,
  FileText,
  FolderKanban,
  Search,
  Bell,
  Clock3,
  Target,
  Sparkles,
} from "lucide-react";

const modules = [
  { title: "Goals", icon: Target, x: "25%", y: "30%" },
  { title: "Tasks", icon: CheckSquare, x: "68%", y: "30%" },
  { title: "Research", icon: Search, x: "44%", y: "20%" },
  { title: "Memory", icon: Brain, x: "12%", y: "50%" },
  { title: "Timeline", icon: Clock3, x: "75%", y: "50%" },
  { title: "Projects", icon: FolderKanban, x: "18%", y: "70%" },
  { title: "Calendar", icon: CalendarDays, x: "75%", y: "70%" },
  { title: "Documents", icon: FileText, x: "44%", y: "80%" },
];

function WorkspaceCard({ module, index }) {
  const Icon = module.icon;

  return (
    <motion.div
      initial={{
        opacity: 0,
        y: 30,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        delay: index * 0.08,
      }}
      whileHover={{
        scale: 1.06,
        y: -6,
      }}
      className="
        absolute
      "
      style={{
        left: module.x,
        top: module.y,
      }}
    >
      <div
        className="
            flex
            items-center
            gap-2

            rounded-xl

            border
            border-accent/20

            bg-[#111827]/90

            backdrop-blur-xl

            px-3
            py-2

            

            transition-all
            duration-300

            hover:-translate-y-1
            hover:border-accent/60
            
        "
        >
        <Icon className="h-4 w-4 text-accent" />

        <span className="text-xs font-medium text-text">
          {module.title}
        </span>
      </div>
    </motion.div>
  );
}

export default function FloatingWorkspace() {
  return (
    <motion.div
      initial={{
        opacity: 0,
        scale: 0.94,
      }}
      whileInView={{
        opacity: 1,
        scale: 1,
      }}
      viewport={{
        once: true,
      }}
      transition={{
        duration: 0.7,
      }}
      className="
            relative
            mx-auto
            h-[450px]
            max-w-[500px]
            w-full
            overflow-hidden
            rounded-[30px]
            border
            border-accent/20
            bg-white/[0.04]
            backdrop-blur-2xl
            
            "
    >
      {/* Header */}
            <div
            className="
                flex
                items-center
                justify-between
                border-b
                border-ink-700
                px-5
                py-4
            "
            >
            <div>
                <h2 className="text-base font-semibold text-text">
                IntelliTwin Workspace
                </h2>

                <p className="text-xs text-text-dim">
                AI Workspace
                </p>
            </div>

            <div
                className="
                flex
                items-center
                gap-2
                rounded-full
                bg-accent/10
                px-3
                py-1.5
                text-xs
                text-accent
                "
            >
                <Sparkles className="h-3.5 w-3.5" />
                Connected
            </div>
            </div>
      {/* Center Brain */}
            <div
            className="
                absolute
                left-1/2
                top-1/2
                flex
                h-20
                w-20
                -translate-x-1/2
                -translate-y-1/2
                items-center
                justify-center
                rounded-full
                border
                border-accent/40
                bg-accent/10
                backdrop-blur-xl
                
            "
            >
            <Brain className="h-8 w-8 text-accent" />
            </div>

      {/* Connection Lines */}
        <svg
        className="absolute inset-0 h-full w-full"
        preserveAspectRatio="none"
        >
        {modules.map((module, i) => (
            <line
            key={i}
            x1="50%"
            y1="50%"
            x2={`calc(${module.x} + 32px)`}
            y2={`calc(${module.y} + 32px)`}
            stroke="rgba(34,211,238,.18)"
            strokeWidth="1.5"
            />
        ))}
        </svg>

      {/* Cards */}
      {modules.map((module, index) => (
        <WorkspaceCard
          key={module.title}
          module={module}
          index={index}
        />
      ))}
    </motion.div>
  );
}