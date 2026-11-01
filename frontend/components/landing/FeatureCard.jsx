"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export default function FeatureCard({
  title,
  description,
  icon: Icon,
  reverse = false,
  index,
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 60 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.08 }}
      className={`grid items-center gap-12 py-16 ${
        reverse ? "lg:grid-cols-[1fr_1.2fr]" : "lg:grid-cols-[1.2fr_1fr]"
      }`}
    >
      {!reverse && (
        <div
          className="
            flex
            h-[240px]
            w-full
            max-w-[420px]
            items-center
            justify-center
            mx-auto
            rounded-[32px]
            border
            border-accent/20
            bg-white/[0.04]
            backdrop-blur-xl
            
          "
        >
          <Icon className="h-24 w-24 text-accent" />
        </div>
      )}

      <div>
        <div className="mb-5 inline-flex rounded-full border border-accent/20 bg-accent/10 px-4 py-2 text-accent">
          Feature
        </div>

        <h3 className="text-4xl font-black text-text">
          {title}
        </h3>

        <p className="mt-6 text-lg leading-8 text-text-dim">
          {description}
        </p>

        
      </div>

      {reverse && (
        <div
          className="
            flex
            h-[240px]
            w-full
            max-w-[320px]
            items-center
            justify-center
            mx-auto
            rounded-[32px]
            border
            border-accent/20
            bg-white/[0.04]
            backdrop-blur-xl
            
          "
        >
          <Icon className="h-24 w-24 text-accent" />
        </div>
      )}
    </motion.div>
  );
}