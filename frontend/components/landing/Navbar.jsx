"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ArrowRight } from "lucide-react";

import { navLinks } from "@/lib/landingData";

export default function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 25);
    };

    handleScroll();

    window.addEventListener("scroll", handleScroll);

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <>
      <header
        className={`fixed left-0 right-0 top-0 z-50 transition-all duration-300 ${
          scrolled
            ? "border-b border-ink-700 bg-ink-950/70 backdrop-blur-2xl"
            : "bg-transparent"
        }`}
      >
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-10">
          {/* Logo */}

          <Link href="/" className="group flex items-center gap-3">
            <div
              className="
                flex
                h-11
                w-11
                items-center
                justify-center
                rounded-2xl
                border
                border-accent/30
                bg-accent/10
                text-accent
                
                transition-all
                group-hover:scale-110
                group-hover:border-accent
              "
            >
              ✦
            </div>

            <div>
              <h1 className="text-lg font-bold tracking-wide text-text">
                IntelliTwin
              </h1>

              <p className="text-xs text-text-dim">
                AI-Powered Intelligent Workspace
              </p>
            </div>
          </Link>

          {/* Desktop Navigation */}

          <nav className="hidden items-center gap-8 lg:flex">
            {navLinks.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="
                  text-sm
                  font-medium
                  text-text/80
                  transition-all
                  hover:text-accent
                "
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* Desktop Buttons */}

          <div className="hidden items-center gap-3 lg:flex">
            <Link
              href="/login"
              className="
                rounded-xl
                border
                border-ink-700
                px-5
                py-2.5
                text-sm
                font-medium
                text-text
                transition-all
                hover:border-accent/50
                hover:bg-accent/10
              "
            >
              Login
            </Link>

            <Link
              href="/register"
              className="
                flex
                items-center
                gap-2
                rounded-xl
                bg-accent
                px-5
                py-2.5
                text-sm
                font-semibold
                text-ink-950
                transition-all
                hover:scale-105
                hover:bg-accent
              "
            >
              Get Started

              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          {/* Mobile Button */}

          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="
              rounded-xl
              border
              border-ink-700
              p-3
              text-text
              lg:hidden
            "
          >
            {mobileOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </button>
        </div>
      </header>

      {/* Mobile Menu */}

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{
              opacity: 0,
              y: -20,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            exit={{
              opacity: 0,
              y: -20,
            }}
            transition={{
              duration: 0.25,
            }}
            className="
              fixed
              top-20
              left-4
              right-4
              z-40

              rounded-3xl

              border
              border-ink-700

              bg-ink-950/95

              p-6

              backdrop-blur-2xl

              lg:hidden
            "
          >
            <div className="space-y-5">
              {navLinks.map((item) => (
                <Link
                  key={item.label}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className="
                    block
                    text-text/80
                    transition
                    hover:text-accent
                  "
                >
                  {item.label}
                </Link>
              ))}

              <div className="pt-6 space-y-3">
                <Link
                  href="/login"
                  className="
                    block
                    rounded-xl
                    border
                    border-ink-700
                    px-5
                    py-3
                    text-center
                    text-text
                  "
                >
                  Login
                </Link>

                <Link
                  href="/register"
                  className="
                    block
                    rounded-xl
                    bg-accent
                    px-5
                    py-3
                    text-center
                    font-semibold
                    text-ink-950
                  "
                >
                  Get Started
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}