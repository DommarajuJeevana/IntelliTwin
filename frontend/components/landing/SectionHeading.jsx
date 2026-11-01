"use client";

import { motion } from "framer-motion";

export default function SectionHeading({
  badge,
  title,
  description,
  center = true,
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 35 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: .6 }}
      className={`${center ? "text-center" : ""} mx-auto max-w-3xl`}
    >
      {badge && (
        <span
          className="
            inline-flex
            rounded-full
            border
            border-accent/20
            bg-accent/10
            px-4
            py-2
            text-sm
            font-medium
            text-accent
          "
        >
          {badge}
        </span>
      )}

      <h2
        className="
          mt-6
          text-4xl
          font-black
          text-text
          md:text-5xl
        "
      >
        {title}
      </h2>

      {description && (
        <p
          className="
            mt-6
            text-lg
            leading-8
            text-text-dim
          "
        >
          {description}
        </p>
      )}
    </motion.div>
  );
}