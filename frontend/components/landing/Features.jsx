"use client";

import {
  Brain,
  Search,
  Sparkles,
  Shield,
  FolderKanban,
  Target,
} from "lucide-react";

import SectionHeading from "./SectionHeading";
import FeatureCard from "./FeatureCard";

const features = [
  {
    title: "Persistent Memory",
    description:
      "IntelliTwin remembers your goals, conversations, preferences and projects so you never lose context again.",
    icon: Brain,
  },

  {
    title: "Universal Search",
    description:
      "Search across notes, documents, research, projects, tasks and memories from one intelligent search bar.",
    icon: Search,
  },

  {
    title: "AI Agents",
    description:
      "Echo, Atlas, Compass and Nova collaborate together instead of working independently.",
    icon: Sparkles,
  },

  {
    title: "Privacy Control",
    description:
      "Own your data with transparent memory management, export tools and complete deletion controls.",
    icon: Shield,
  },

  {
    title: "Project Intelligence",
    description:
      "Every document, task and schedule automatically links to the correct project.",
    icon: FolderKanban,
  },

  {
    title: "Smart Planning",
    description:
      "Break large ambitions into actionable roadmaps with milestones, reminders and AI guidance.",
    icon: Target,
  },
];

export default function Features() {
  return (
    <section
      id="features"
      className="bg-ink-950 py-32"
    >
      <div className="mx-auto max-w-7xl px-6 lg:px-10">
        <SectionHeading
          badge="Features"
          title="Everything Needed To Think Better."
          description="Designed to replace disconnected productivity tools with one intelligent workspace."
        />

        <div className="mt-20">
          {features.map((feature, index) => (
            <FeatureCard
              key={feature.title}
              {...feature}
              reverse={index % 2 === 1}
              index={index}
            />
          ))}
        </div>
      </div>
    </section>
  );
}