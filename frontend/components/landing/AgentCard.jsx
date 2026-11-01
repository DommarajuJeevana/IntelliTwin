"use client";

import { motion } from "framer-motion";

export default function AgentCard({ agent, index }) {
  const Icon = agent.icon;

  return (
    <motion.div
      initial={{
        opacity: 0,
        y: 50,
      }}
      whileInView={{
        opacity: 1,
        y: 0,
      }}
      viewport={{
        once: true,
      }}
      transition={{
        delay: index * .12,
      }}
      whileHover={{
        y: -10,
        scale: 1.03,
      }}
      className="
        group
        relative
        overflow-hidden
        rounded-3xl
        border
        border-ink-700
        bg-white/[0.04]
        p-8
        backdrop-blur-2xl
        transition-all
        hover:border-accent/40
        
      "
    >
      <div
        className="
          absolute
          inset-0
          opacity-0
          transition-opacity
          duration-500
          group-hover:opacity-100
          bg-gradient-to-br
          from-accent/10
          via-transparent
          to-transparent
        "
      />

      <div
        className="
          relative
          z-10
        "
      >
        <div
          className="
            mb-8
            flex
            h-16
            w-16
            items-center
            justify-center
            rounded-2xl
            bg-accent/10
            border
            border-accent/20
          "
        >
          <Icon className="h-8 w-8 text-accent" />
        </div>

        <span
          className="
            text-sm
            font-semibold
            uppercase
            tracking-[0.25em]
            text-accent
          "
        >
          {agent.name}
        </span>

        <h3
          className="
            mt-3
            text-2xl
            font-bold
            text-text
          "
        >
          {agent.title}
        </h3>

        <p
          className="
            mt-5
            leading-8
            text-text-dim
          "
        >
          {agent.description}
        </p>
      </div>
    </motion.div>
  );
}