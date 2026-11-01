"use client";

import { agents } from "@/lib/landingData";

import SectionHeading from "./SectionHeading";
import AgentCard from "./AgentCard";

export default function Agents() {
  return (
    <section
      id="agents"
      className="
        relative
        py-32
        bg-ink-950
      "
    >
      <div className="mx-auto max-w-7xl px-6 lg:px-10">
        <SectionHeading
          badge="AI Agents"
          title="Meet Your Intelligent Team"
          description="Four specialized AI agents work together inside one connected workspace. Every conversation, task, document and goal stays organized."
        />

        <div
          className="
            mt-20
            grid
            gap-8
            md:grid-cols-2
            xl:grid-cols-4
          "
        >
          {agents.map((agent, index) => (
            <AgentCard
              key={agent.name}
              agent={agent}
              index={index}
            />
          ))}
        </div>
      </div>
    </section>
  );
}