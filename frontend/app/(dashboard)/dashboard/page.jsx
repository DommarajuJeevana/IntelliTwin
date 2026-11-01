"use client";

import { useAuth } from "../../../context/AuthContext";
import AgentWorkspace from "../../../components/ui/AgentWorkspace";
import Greeting from "../../../components/dashboard/Greeting";
import NextUp from "../../../components/dashboard/NextUp";
import GoalsPanel from "../../../components/dashboard/GoalsPanel";
import ProjectsPanel from "../../../components/dashboard/ProjectsPanel";
import SchedulePanel from "../../../components/dashboard/SchedulePanel";
import RecentPanel from "../../../components/dashboard/RecentPanel";
import ResearchPanel from "../../../components/dashboard/ResearchPanel";
import MemoryPanel from "../../../components/dashboard/MemoryPanel";
import { useDashboardData } from "../../../components/dashboard/useDashboardData";

/**
 * Home. Reading order follows "what should I do next?":
 *   1. Next up (Compass) is the largest, accented module.
 *   2. The assistant sits beside it on wide screens, right after it on small ones.
 *   3. Goals and projects show the connected context (next task, research).
 *   4. Schedule, recent writing, research and memory are secondary.
 * "Next up" mixes Compass's AI-written suggestions (labelled "AI") with the
 * rule-based reminders, which remain the fallback when the model is unavailable.
 * Every module loads from an existing endpoint and shows its own
 * loading / empty / error state; nothing here is mock data.
 */
export default function DashboardPage() {
  const { user } = useAuth();
  const { state, reload, dismissSuggestion, index, aiRefreshing, refreshAi } = useDashboardData();

  return (
    <div className="mx-auto w-full max-w-[1400px]">
      <Greeting user={user} tasks={state.tasks} calendar={state.calendar} goals={state.goals} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-12 xl:gap-5">
        <NextUp
          suggestions={state.suggestions}
          ai={state.ai}
          aiRefreshing={aiRefreshing}
          onRefreshAi={refreshAi}
          summary={state.summary}
          onRetry={() => reload("suggestions")}
          onDismiss={dismissSuggestion}
          className="md:col-span-2 xl:col-span-8"
        />

        <AgentWorkspace
          briefing={state.summary.status === "ready" ? state.summary.data?.briefing || [] : []}
          className="md:col-span-2 xl:col-span-4 xl:row-span-2"
        />

        <GoalsPanel goals={state.goals} index={index} onRetry={() => reload("goals")} className="xl:col-span-4" />
        <ProjectsPanel projects={state.projects} index={index} onRetry={() => reload("projects")} className="xl:col-span-4" />

        <SchedulePanel calendar={state.calendar} onRetry={() => reload("calendar")} className="xl:col-span-4" />
        <RecentPanel notes={state.notes} documents={state.documents} onRetry={reload} className="xl:col-span-4" />
        <ResearchPanel research={state.research} onRetry={() => reload("research")} className="xl:col-span-4" />

        <MemoryPanel summary={state.summary} onRetry={() => reload("summary")} className="md:col-span-2 xl:col-span-12" />
      </div>
    </div>
  );
}
