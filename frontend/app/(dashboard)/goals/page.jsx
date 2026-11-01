"use client";

import { useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

function getStatusLabel(status) {
  if (!status) return "active";

  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getProgress(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return 0;
  }

  return Math.max(0, Math.min(100, number));
}

function GoalCard({ goal }) {
  const progress = getProgress(goal.progress);
  const completed = goal.status === "done";

  return (
    <article className="border rounded-xl border-ink-700 bg-ink-900/70">
      {/* Header */}
      <div className="border-b border-ink-700 px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-accent">
              Objective
            </p>

            <h2 className="mt-1 truncate text-base font-medium text-text">
              {goal.title}
            </h2>
          </div>

          <span
            className={`
              shrink-0
              border rounded-lg
              px-2.5
              py-1
              text-[10px]
              font-semibold
              uppercase
              tracking-[0.16em]
              ${
                completed
                  ? "border-accent/20 bg-accent/[0.06] text-accent"
                  : "border-ink-700 bg-white/[0.025] text-text-dim"
              }
            `}
          >
            {getStatusLabel(goal.status)}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-5">
        {goal.description ? (
          <p className="text-sm leading-6 text-text-dim">
            {goal.description}
          </p>
        ) : (
          <p className="text-sm italic leading-6 text-text-dim/70">
            No description added.
          </p>
        )}

        {/* Progress */}
        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
              Progress
            </span>

            <span className="text-xs font-medium text-text-dim">
              {progress}%
            </span>
          </div>

          <div className="h-1 w-full bg-white/[0.06]">
            <div
              className="h-full bg-accent transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </article>
  );
}

function EmptyGoals() {
  return (
    <div className="flex min-h-[360px] flex-col items-center justify-center border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center border rounded-lg border-accent/20 bg-accent/[0.04] text-sm font-semibold text-accent">
        G
      </div>

      <p className="mt-5 text-sm font-medium text-text/80">
        No goals yet
      </p>

      <p className="mt-2 max-w-sm text-xs leading-6 text-text-dim/70">
        Create your first objective and use Compass to break it into
        actionable tasks.
      </p>
    </div>
  );
}

export default function GoalsPage() {
  const apiClient = useApi();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [goals, setGoals] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  /*
   * The existing ModulePage handled fetching internally.
   * This page now owns the request so the workspace can have
   * the same visual/interaction model as Atlas, Echo and Nova.
   */
  async function loadGoals() {
    try {
      const response = await apiClient.get("/goals");

      const items = Array.isArray(response)
        ? response
        : response?.items ||
          response?.goals ||
          response?.data ||
          [];

      setGoals(items);
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not load goals."
      );
    }
  }

  async function createGoal(event) {
    event.preventDefault();

    const cleanTitle = title.trim();
    const cleanDescription = description.trim();

    if (!cleanTitle || busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      await apiClient.post("/goals", {
        title: cleanTitle,
        description: cleanDescription,
      });

      setTitle("");
      setDescription("");

      await loadGoals();
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Could not create the goal."
      );
    } finally {
      setBusy(false);
    }
  }

  /*
   * Load existing goals once.
   */
  useMemo(() => {
    loadGoals();
  }, []);

  const activeGoals = goals.filter(
    (goal) => goal.status !== "done"
  );

  const completedGoals = goals.filter(
    (goal) => goal.status === "done"
  );

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">

        {/* Header */}
        <header className="border-b border-ink-700 pb-6">
          <div className="flex items-start justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center border rounded-lg border-accent/25 bg-accent/[0.05] text-sm font-semibold text-accent">
                G
              </div>

              <div>
                <div className="flex items-center gap-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-accent">
                    Goals
                  </p>

                  <span className="h-1 w-1 rounded-full bg-ink-600" />

                  <span className="text-[10px] uppercase tracking-[0.18em] text-text-dim/70">
                    Objective control
                  </span>
                </div>

                <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                  Goals workspace
                </h1>

                <p className="mt-2 max-w-xl text-sm leading-6 text-text-dim">
                  Define what you are working toward and keep your
                  objectives visible as your workspace evolves.
                </p>
              </div>
            </div>

            <div className="hidden border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-2 sm:block">
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
                Objectives
              </p>

              <p className="mt-1.5 text-sm text-text/80">
                {goals.length}
              </p>
            </div>
          </div>
        </header>

        {/* Workspace */}
        <section className="mt-7 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">

          {/* Create goal */}
          <aside className="h-fit border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim">
                  New objective
                </p>

                <span className="text-[10px] uppercase tracking-[0.16em] text-ink-500">
                  GOALS / 01
                </span>
              </div>

              <p className="mt-2 text-xs leading-5 text-text-dim">
                Define an outcome you want IntelliTwin to help you
                work toward.
              </p>
            </div>

            <form
              onSubmit={createGoal}
              className="p-5"
            >
              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
                  Goal
                </span>

                <input
                  value={title}
                  onChange={(event) =>
                    setTitle(event.target.value)
                  }
                  disabled={busy}
                  placeholder="What do you want to achieve?"
                  className="
                    mt-2
                    h-10
                    w-full
                    border rounded-lg
                    border-ink-700
                    bg-ink-950/70
                    px-3.5
                    text-sm
                    text-text
                    outline-none
                    transition
                    placeholder:text-text-dim/70
                    focus:border-accent
                    disabled:opacity-50
                  "
                />
              </label>

              <label className="mt-4 block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
                  Description
                </span>

                <textarea
                  value={description}
                  onChange={(event) =>
                    setDescription(event.target.value)
                  }
                  disabled={busy}
                  rows={5}
                  placeholder="Add context or define what success looks like."
                  className="
                    mt-2
                    w-full
                    resize-none
                    border rounded-lg
                    border-ink-700
                    bg-ink-950/70
                    px-3.5
                    py-3
                    text-sm
                    leading-6
                    text-text
                    outline-none
                    transition
                    placeholder:text-text-dim/70
                    focus:border-accent
                    disabled:opacity-50
                  "
                />
              </label>

              <button
                type="submit"
                disabled={!title.trim() || busy}
                className="
                  mt-4
                  flex
                  h-10
                  w-full
                  items-center
                  justify-center
                  gap-2
                  border rounded-lg
                  border-accent/20
                  bg-accent/[0.08]
                  px-4
                  text-xs
                  font-medium
                  text-accent
                  transition
                  hover:border-accent/40
                  hover:bg-accent/[0.12]
                  disabled:cursor-not-allowed
                  disabled:border-ink-700
                  disabled:bg-white/[0.03]
                  disabled:text-text-dim/70
                "
              >
                {busy ? "Creating..." : "Create goal"}
                {!busy && <span>→</span>}
              </button>

              {error && (
                <div className="mt-4 border rounded-lg border-rose-400/20 bg-rose-400/[0.05] px-3 py-3 text-xs leading-5 text-rose-300">
                  {error}
                </div>
              )}
            </form>

            {/* Compass relationship */}
            <div className="border-t border-ink-700 px-5 py-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim/70">
                Compass
              </p>

              <p className="mt-2 text-xs leading-5 text-text-dim">
                Goals define the destination. Compass can turn them
                into actionable tasks.
              </p>
            </div>
          </aside>

          {/* Goals */}
          <section className="min-w-0">
            <div className="mb-4 flex items-end justify-between">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim/70">
                  Workspace
                </p>

                <h2 className="mt-1 text-lg font-medium text-text">
                  Active objectives
                </h2>
              </div>

              {activeGoals.length > 0 && (
                <span className="text-[10px] text-text-dim/70">
                  {activeGoals.length} active
                </span>
              )}
            </div>

            {activeGoals.length === 0 ? (
              <EmptyGoals />
            ) : (
              <div className="space-y-4">
                {activeGoals.map((goal) => (
                  <GoalCard
                    key={goal._id}
                    goal={goal}
                  />
                ))}
              </div>
            )}

            {/* Completed */}
            {completedGoals.length > 0 && (
              <section className="mt-8">
                <div className="mb-4 flex items-center gap-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim/70">
                    Completed
                  </p>

                  <span className="h-px flex-1 bg-white/[0.06]" />

                  <span className="text-[10px] text-ink-500">
                    {completedGoals.length}
                  </span>
                </div>

                <div className="space-y-4 opacity-75">
                  {completedGoals.map((goal) => (
                    <GoalCard
                      key={goal._id}
                      goal={goal}
                    />
                  ))}
                </div>
              </section>
            )}
          </section>
        </section>
      </div>
    </div>
  );
}