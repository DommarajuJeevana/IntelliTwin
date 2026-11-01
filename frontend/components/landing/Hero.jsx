"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Play, CheckCircle2 } from "lucide-react";

import AnimatedBackground from "./AnimatedBackground";
import FloatingWorkspace from "./FloatingWorkspace";
import { hero } from "@/lib/landingData";

export default function Hero() {
  return (
    <section className="relative overflow-hidden bg-ink-950">
      <AnimatedBackground />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-7xl items-center px-6 pt-28 pb-20 lg:px-10">
        <div className="grid w-full items-center gap-20 lg:grid-cols-2">
          {/* LEFT */}

          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
            }}
          >
            {/* Badge */}

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{
                delay: .15,
              }}
              className="
                inline-flex
                items-center
                gap-2

                rounded-full

                border
                border-accent/20

                bg-accent/10

                px-5
                py-2

                text-sm

                text-accent
              "
            >
              <span className="h-2 w-2 rounded-full bg-accent" />

              {hero.badge}
            </motion.div>

            {/* Heading */}

            <motion.h1
              initial={{ opacity: 0, y: 35 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                delay: .2,
              }}
              className="
                mt-8

                text-5xl

                font-black

                leading-tight

                text-text

                md:text-6xl

                xl:text-7xl
              "
            >
              {hero.title1}

              <br />

              <span className="text-accent">
                {hero.title2}
              </span>

              <br />

              {hero.title3}
            </motion.h1>

            {/* Description */}

            <motion.p
              initial={{
                opacity: 0,
                y: 30,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                delay: .35,
              }}
              className="
                mt-8

                max-w-xl

                text-lg

                leading-8

                text-text/80
              "
            >
              {hero.description}
            </motion.p>

            {/* Buttons */}

            <motion.div
              initial={{
                opacity: 0,
                y: 25,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                delay: .5,
              }}
              className="
                mt-10

                flex

                flex-wrap

                gap-5
              "
            >
              <Link
                href="/register"
                className="
                  inline-flex

                  items-center

                  gap-3

                  rounded-2xl

                  bg-accent

                  px-7

                  py-4

                  font-semibold

                  text-ink-950

                  transition-all

                  hover:scale-105

                  hover:bg-accent

                  
                "
              >
                {hero.primary}

                <ArrowRight className="h-5 w-5" />
              </Link>

              <button
                className="
                  inline-flex

                  items-center

                  gap-3

                  rounded-2xl

                  border

                  border-ink-700

                  bg-white/[0.04]

                  px-7

                  py-4

                  text-text

                  backdrop-blur-xl

                  transition-all

                  hover:border-accent/50

                  hover:bg-accent/10
                "
              >
                <Play className="h-5 w-5" />

                {hero.secondary}
              </button>
            </motion.div>

            {/* Highlights */}

            <motion.div
              initial={{
                opacity: 0,
              }}
              animate={{
                opacity: 1,
              }}
              transition={{
                delay: .7,
              }}
              className="
                mt-12

                grid

                gap-4

                sm:grid-cols-2
              "
            >
              {hero.highlights.map((item) => (
                <div
                  key={item}
                  className="
                    flex

                    items-center

                    gap-3

                    text-text/80
                  "
                >
                  <CheckCircle2 className="h-5 w-5 text-accent" />

                  <span>{item}</span>
                </div>
              ))}
            </motion.div>

            {/* Stats */}

            <motion.div
              initial={{
                opacity: 0,
              }}
              animate={{
                opacity: 1,
              }}
              transition={{
                delay: .9,
              }}
              className="
                mt-16

                flex

                flex-wrap

                gap-12
              "
            >
              <div>
                <h2 className="text-4xl font-bold text-accent">
                  4
                </h2>

                <p className="mt-2 text-text-dim">
                  Intelligent Agents
                </p>
              </div>

              <div>
                <h2 className="text-4xl font-bold text-accent">
                  10+
                </h2>

                <p className="mt-2 text-text-dim">
                  Connected Modules
                </p>
              </div>

              <div>
                <h2 className="text-4xl font-bold text-accent">
                  1
                </h2>

                <p className="mt-2 text-text-dim">
                  Intelligent Workspace
                </p>
              </div>
            </motion.div>
          </motion.div>

          {/* RIGHT */}

          <motion.div
            initial={{
              opacity: 0,
              x: 80,
            }}
            animate={{
              opacity: 1,
              x: 0,
            }}
            transition={{
              duration: .8,
            }}
            className="relative"
          >
            <motion.div
              animate={{
                y: [-10, 10, -10],
              }}
              transition={{
                duration: 6,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              <FloatingWorkspace />
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}