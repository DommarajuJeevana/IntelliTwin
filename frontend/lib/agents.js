import { Brain, Search, Compass, Sparkles } from "lucide-react";

/**
 * Single source of truth for the four agents' identities.
 * Class strings are written out in full so Tailwind's JIT can see them.
 */
export const AGENTS = {
  echo: {
    id: "echo",
    name: "Echo",
    role: "Memory",
    href: "/echo",
    icon: Brain,
    text: "text-agent-echo",
    dot: "bg-agent-echo",
    soft: "bg-agent-echo/10 border-agent-echo/25",
  },
  atlas: {
    id: "atlas",
    name: "Atlas",
    role: "Research",
    href: "/atlas",
    icon: Search,
    text: "text-agent-atlas",
    dot: "bg-agent-atlas",
    soft: "bg-agent-atlas/10 border-agent-atlas/25",
  },
  compass: {
    id: "compass",
    name: "Compass",
    role: "Planning",
    href: "/compass",
    icon: Compass,
    text: "text-agent-compass",
    dot: "bg-agent-compass",
    soft: "bg-agent-compass/10 border-agent-compass/25",
  },
  nova: {
    id: "nova",
    name: "Nova",
    role: "Creation",
    href: "/nova",
    icon: Sparkles,
    text: "text-agent-nova",
    dot: "bg-agent-nova",
    soft: "bg-agent-nova/10 border-agent-nova/25",
  },
};

export const AGENT_LIST = Object.values(AGENTS);
