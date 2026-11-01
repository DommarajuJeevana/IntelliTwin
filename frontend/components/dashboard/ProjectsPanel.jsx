import Link from "next/link";
import { FolderKanban } from "lucide-react";
import Panel from "./Panel";
import { NextTaskLine, ResearchLine } from "./ContextLine";
import { idOf, nextTaskFor, researchFor } from "../../lib/workspaceContext";

const INACTIVE = new Set(["complete", "completed", "cancelled"]);
const STATUS_ORDER = { in_progress: 0, active: 1, planning: 2, on_hold: 3, paused: 3 };
const STATUS_LABEL = {
  planning: "Planning",
  active: "Active",
  in_progress: "In progress",
  on_hold: "On hold",
  paused: "Paused",
};

export default function ProjectsPanel({ projects, index, onRetry, className = "" }) {
  const active = (projects.data || [])
    .filter((p) => !INACTIVE.has(String(p.status || "").toLowerCase()))
    .sort((a, b) => (STATUS_ORDER[a.status] ?? 4) - (STATUS_ORDER[b.status] ?? 4))
    .slice(0, 4);

  return (
    <Panel
      title="Active projects"
      icon={FolderKanban}
      href="/projects"
      state={projects}
      onRetry={onRetry}
      isEmpty={active.length === 0}
      emptyTitle="No active projects"
      emptyHint="Projects group the goals, tasks and research for one body of work."
      emptyHref="/projects"
      emptyLabel="Start a project"
      className={className}
    >
      <ul className="space-y-3">
        {active.map((project) => {
          const goalIds = (Array.isArray(project.goals) ? project.goals : [])
            .map(idOf)
            .filter((id) => id && index.goalById.has(id));
          const next = nextTaskFor(goalIds, index);
          const research = researchFor(goalIds, index);
          const linkedGoals = goalIds.map((id) => index.goalById.get(id));

          return (
            <li key={idOf(project._id)} className="rounded-xl border border-ink-700 bg-ink-800/40 p-3.5">
              <div className="flex items-start justify-between gap-3">
                <Link href="/projects" className="min-w-0 truncate text-sm font-medium text-text transition-colors hover:text-accent">
                  {project.name}
                </Link>
                <span className="shrink-0 rounded-full border border-ink-600 px-2 py-0.5 text-[10px] text-text-dim">
                  {STATUS_LABEL[project.status] || "Active"}
                </span>
              </div>

              {project.description ? (
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-text-dim">{project.description}</p>
              ) : null}

              {linkedGoals.length ? (
                <p className="mt-2 truncate text-[11px] text-text-dim">
                  {linkedGoals.length === 1 ? "Goal: " : `${linkedGoals.length} goals: `}
                  <span className="text-text">{linkedGoals.map((g) => g.title).join(", ")}</span>
                </p>
              ) : null}

              {next || research ? (
                <div className="mt-1.5 space-y-0.5">
                  <NextTaskLine task={next} />
                  <ResearchLine item={research} />
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
