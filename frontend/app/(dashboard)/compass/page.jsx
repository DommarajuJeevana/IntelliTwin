"use client";

import { useState } from "react";
import { useApi } from "../../../lib/useApi";
import AgentPageHeader from "../../../components/ui/AgentPageHeader";

function TaskItem({ task, index }) {
  return (
    <div className="flex gap-4 border-b border-ink-700 py-4 last:border-b-0">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center border border-amber-400/25 text-[10px] text-amber-300">
        {index + 1}
      </div>

      <div className="min-w-0">
        <p className="text-sm text-text">
          {task?.title || "Untitled task"}
        </p>

        {task?.description && (
          <p className="mt-1 text-xs leading-5 text-text-dim">
            {task.description}
          </p>
        )}

        {task?.dueDate && (
          <p className="mt-2 text-[10px] uppercase tracking-wider text-text-dim">
            Due {task.dueDate}
          </p>
        )}
      </div>
    </div>
  );
}

function PlanCard({ plan }) {
  const goal = plan?.goal;
  const tasks = plan?.tasks || [];

  return (
    <article className="border rounded-xl border-ink-700 bg-ink-900/60">
      <div className="border-b border-ink-700 px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-amber-300">
              Goal
            </p>

            <h3 className="mt-2 text-base font-medium text-text">
              {goal?.title || "Untitled goal"}
            </h3>
          </div>

          <span className="shrink-0 border border-amber-400/20 px-2 py-1 text-[10px] uppercase tracking-wider text-amber-300">
            Active
          </span>
        </div>

        {goal?.description && (
          <p className="mt-3 text-sm leading-6 text-text-dim">
            {goal.description}
          </p>
        )}
      </div>

      <div className="px-5 py-5">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
            Starter tasks
          </p>

          <span className="text-xs text-text-dim">
            {tasks.length} {tasks.length === 1 ? "task" : "tasks"}
          </span>
        </div>

        {tasks.length > 0 ? (
          <div className="mt-2">
            {tasks.map((task, index) => (
              <TaskItem
                key={
                  task?._id ||
                  task?.id ||
                  `${task?.title}-${index}`
                }
                task={task}
                index={index}
              />
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-text-dim">
            No starter tasks were returned for this plan.
          </p>
        )}
      </div>
    </article>
  );
}

export default function CompassPage() {
  const apiClient = useApi();

  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState("");

  async function createPlan(e) {
    e.preventDefault();

    const value = title.trim();

    if (!value || busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/agents/compass", {
        title: value,
      });

      if (response?.goal || response?.tasks) {
        setPlans((previous) => [
          {
            goal: response.goal,
            tasks: response.tasks || [],
          },
          ...previous,
        ]);
      }

      setTitle("");
    } catch (err) {
      setError(
        err?.message ||
          "Something went wrong while creating the plan."
      );
    } finally {
      setBusy(false);
    }
  }

  function useSuggestion(text) {
    setTitle(text);
  }

  return (
    <div className="mx-auto w-full max-w-5xl">
      <AgentPageHeader
          agent="compass"
          title="Turn intentions into plans."
          description="Compass takes an objective and turns it into a structured goal with concrete starter tasks."
        />

      {/* CREATE PLAN */}
      <section className="mt-8">
        <div className="mb-4">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-text-dim">
            Create a plan
          </p>

          <h2 className="mt-2 text-lg font-medium text-text">
            What are you trying to accomplish?
          </h2>
        </div>

        <form onSubmit={createPlan}>
          <div className="border rounded-xl border-ink-700 bg-ink-900/70">
            <textarea
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="For example: Prepare my final-year project presentation."
              rows={5}
              disabled={busy}
              className="w-full resize-none bg-transparent px-5 py-5 text-sm leading-6 text-text outline-none placeholder:text-text-dim/60 disabled:opacity-60"
            />

            <div className="flex flex-col gap-3 border-t border-ink-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-text-dim">
                Compass will create the goal and starter tasks.
              </p>

              <button
                type="submit"
                disabled={!title.trim() || busy}
                className="border rounded-lg border-amber-400/30 bg-amber-400/10 px-5 py-2.5 text-xs font-medium text-amber-300 transition hover:border-amber-400/50 hover:bg-amber-400/15 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Planning..." : "Create plan"}
              </button>
            </div>
          </div>
        </form>

        {error && (
          <div className="mt-4 border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}
      </section>

      {/* SUGGESTIONS */}
      <section className="mt-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
          Start with an example
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {[
            "Prepare for my upcoming presentation.",
            "Finish my current project.",
            "Create a study plan for my next exam.",
          ].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => useSuggestion(suggestion)}
              className="border border-ink-700 px-3 py-2 text-xs text-text-dim transition hover:border-amber-400/30 hover:text-text"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      {/* PLANS */}
      <section className="mt-12">
        <div className="flex items-end justify-between gap-4 border-b border-ink-700 pb-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
              Planning activity
            </p>

            <h2 className="mt-2 text-lg font-medium text-text">
              Plans created in this session
            </h2>
          </div>

          {plans.length > 0 && (
            <span className="text-xs text-text-dim">
              {plans.length}{" "}
              {plans.length === 1 ? "plan" : "plans"}
            </span>
          )}
        </div>

        {plans.length === 0 ? (
          <div className="mt-6 border border-dashed border-ink-700 px-6 py-10">
            <p className="text-sm text-text-dim">
              No plans created from this session yet.
            </p>

            <p className="mt-2 max-w-xl text-xs leading-5 text-text-dim/70">
              Give Compass an objective and it will turn it into a goal
              with concrete starter tasks.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {plans.map((plan, index) => (
              <PlanCard
                key={
                  plan?.goal?._id ||
                  plan?.goal?.id ||
                  `plan-${index}`
                }
                plan={plan}
              />
            ))}
          </div>
        )}
      </section>

      {/* WORKFLOW */}
      <section className="mt-12 border-t border-ink-700 pt-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
          How Compass works
        </p>

        <div className="mt-5 grid gap-px border rounded-lg overflow-hidden border-ink-700 bg-ink-700 sm:grid-cols-3">
          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-amber-300">
              01 / Objective
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Describe what you want to accomplish.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-amber-300">
              02 / Goal
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Compass creates a structured goal in the workspace.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-amber-300">
              03 / Tasks
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              The goal receives concrete starter tasks to begin execution.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}