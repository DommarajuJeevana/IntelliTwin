"use client";

import { useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

const priorityStyles = {
  high: {
    dot: "bg-rose-400",
    text: "text-rose-300",
    label: "High",
  },
  medium: {
    dot: "bg-amber-400",
    text: "text-amber-300",
    label: "Medium",
  },
  low: {
    dot: "bg-accent",
    text: "text-accent",
    label: "Low",
  },
};

const statusStyles = {
  todo: {
    label: "To Do",
    text: "text-text-dim",
  },
  in_progress: {
    label: "In Progress",
    text: "text-amber-300",
  },
  done: {
    label: "Done",
    text: "text-emerald-300",
  },
};

function TaskRow({
  task,
  goals,
  onStatusChange,
  onGoalChange,
  updating,
}) {
  const priority = String(
    task.priority || "medium"
  ).toLowerCase();

  const style =
    priorityStyles[priority] ||
    priorityStyles.medium;

  const currentStatus = String(
    task.status || "todo"
  ).toLowerCase();

  const completed = currentStatus === "done";

  const currentGoalId = task.goal
    ? String(task.goal)
    : "";

  return (
    <div
      className={`border-b border-ink-700 px-5 py-4 transition-colors hover:bg-white/[0.02] ${
        completed ? "opacity-60" : ""
      }`}
    >
      <div className="flex items-center gap-4">
        {/* Priority */}
        <div
          className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`}
          title={`${style.label} priority`}
        />

        {/* Task */}
        <div className="min-w-0 flex-1">
          <p
            className={`truncate text-sm font-medium ${
              completed
                ? "text-text-dim line-through"
                : "text-text"
            }`}
          >
            {task.title}
          </p>

          {task.dueDate ? (
            <p className="mt-1 text-xs text-text-dim">
              Due{" "}
              {new Date(
                task.dueDate
              ).toLocaleDateString()}
            </p>
          ) : null}
        </div>

        {/* Priority */}
        <div className="hidden items-center gap-3 sm:flex">
          <span
            className={`text-xs ${style.text}`}
          >
            {style.label}
          </span>
        </div>

        {/* Status */}
        <div className="flex items-center">
          <select
            value={currentStatus}
            disabled={updating}
            onChange={(event) =>
              onStatusChange(
                task,
                event.target.value
              )
            }
            className={`h-9 min-w-[120px] border rounded-lg border-ink-700 bg-ink-950/70 px-3 text-xs outline-none transition-colors focus:border-accent disabled:cursor-not-allowed disabled:opacity-50 ${
              statusStyles[currentStatus]?.text ||
              "text-text-dim"
            }`}
            aria-label={`Change status for ${task.title}`}
          >
            <option value="todo">
              To Do
            </option>

            <option value="in_progress">
              In Progress
            </option>

            <option value="done">
              Done
            </option>
          </select>
        </div>
      </div>

      {/* Goal relationship */}
      <div className="mt-3 ml-6 flex items-center gap-3">
        <span className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
          Goal
        </span>

        <select
          value={currentGoalId}
          disabled={updating}
          onChange={(event) =>
            onGoalChange(
              task,
              event.target.value
            )
          }
          className="h-8 min-w-0 max-w-[320px] border rounded-lg border-ink-700 bg-ink-950/70 px-3 text-xs text-text-dim outline-none transition-colors focus:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={`Change goal for ${task.title}`}
        >
          <option value="">
            No goal
          </option>

          {goals.map((goal) => (
            <option
              key={goal._id}
              value={goal._id}
            >
              {goal.title}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default function TasksPage() {
  const { get, post, put } = useApi();

  const [tasks, setTasks] = useState([]);
  const [goals, setGoals] = useState([]);

  const [title, setTitle] = useState("");
  const [priority, setPriority] =
    useState("medium");
  const [selectedGoal, setSelectedGoal] =
    useState("");

  const [busy, setBusy] = useState(false);
  const [updatingTaskId, setUpdatingTaskId] =
    useState(null);

  const [loading, setLoading] = useState(true);
  const [loadingGoals, setLoadingGoals] =
    useState(true);

  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadTasks() {
      try {
        setLoading(true);
        setError("");

        const response = await get("/tasks");

        const items = Array.isArray(response)
          ? response
          : response?.items ||
            response?.tasks ||
            response?.data ||
            [];

        if (active) {
          setTasks(items);
        }
      } catch (err) {
        if (active) {
          setError(
            err?.message ||
              "Unable to load tasks."
          );
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    async function loadGoals() {
      try {
        setLoadingGoals(true);

        const response = await get("/goals");

        const items = Array.isArray(response)
          ? response
          : response?.items ||
            response?.goals ||
            response?.data ||
            [];

        if (active) {
          setGoals(items);
        }
      } catch (err) {
        if (active) {
          setError(
            err?.message ||
              "Unable to load goals."
          );
        }
      } finally {
        if (active) {
          setLoadingGoals(false);
        }
      }
    }

    loadTasks();
    loadGoals();

    return () => {
      active = false;
    };
  }, [get]);

  /*
   * useMemo is correct here.
   * These are derived values calculated from tasks.
   */
  const openTasks = useMemo(
    () =>
      tasks.filter(
        (task) => task.status !== "done"
      ),
    [tasks]
  );

  const completedTasks = useMemo(
    () =>
      tasks.filter(
        (task) => task.status === "done"
      ),
    [tasks]
  );

  async function createTask(event) {
    event.preventDefault();

    const cleanTitle = title.trim();

    if (!cleanTitle || busy) {
      return;
    }

    try {
      setBusy(true);
      setError("");

      const response = await post("/tasks", {
        title: cleanTitle,
        priority,
        status: "todo",
        goal: selectedGoal || null,
      });

      const created =
        response?.item ||
        response?.task ||
        response?.data ||
        response;

      if (
        created &&
        typeof created === "object"
      ) {
        setTasks((current) => [
          created,
          ...current,
        ]);
      }

      setTitle("");
      setPriority("medium");
      setSelectedGoal("");
    } catch (err) {
      setError(
        err?.message ||
          "Unable to create task."
      );
    } finally {
      setBusy(false);
    }
  }

  async function updateTask(
    task,
    updates
  ) {
    if (
      !task?._id ||
      updatingTaskId === task._id
    ) {
      return;
    }

    try {
      setUpdatingTaskId(task._id);
      setError("");

      const response = await put(
        `/tasks/${task._id}`,
        updates
      );

      const updated =
        response?.item ||
        response?.task ||
        response?.data ||
        response;

      if (
        updated &&
        typeof updated === "object"
      ) {
        setTasks((current) =>
          current.map((currentTask) =>
            currentTask._id === task._id
              ? {
                  ...currentTask,
                  ...updated,
                }
              : currentTask
          )
        );
      } else {
        setTasks((current) =>
          current.map((currentTask) =>
            currentTask._id === task._id
              ? {
                  ...currentTask,
                  ...updates,
                }
              : currentTask
          )
        );
      }
    } catch (err) {
      setError(
        err?.message ||
          "Unable to update task."
      );
    } finally {
      setUpdatingTaskId(null);
    }
  }

  async function changeTaskStatus(
    task,
    newStatus
  ) {
    const previousStatus =
      task.status || "todo";

    if (previousStatus === newStatus) {
      return;
    }

    await updateTask(task, {
      status: newStatus,
    });
  }

  async function changeTaskGoal(
    task,
    newGoalId
  ) {
    const previousGoal = task.goal
      ? String(task.goal)
      : "";

    if (previousGoal === newGoalId) {
      return;
    }

    await updateTask(task, {
      goal: newGoalId || null,
    });
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-accent" />

            <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent/80">
              Action queue
            </span>
          </div>

          <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
            Tasks
          </h1>

          <p className="mt-2 max-w-xl text-sm leading-6 text-text-dim">
            The work that needs your attention,
            whether you added it yourself or
            Compass created it from a plan.
          </p>
        </header>

        {/* Create task */}
        <section className="mb-8 border rounded-xl border-ink-700 bg-ink-900/70">
          <div className="border-b border-ink-700 px-5 py-4">
            <p className="text-sm font-medium text-text">
              Add a task
            </p>

            <p className="mt-1 text-xs text-text-dim">
              Capture the next action and connect
              it to an objective.
            </p>
          </div>

          <form
            onSubmit={createTask}
            className="grid gap-3 p-5 lg:grid-cols-4"
          >
            {/* Title */}
            <input
              value={title}
              onChange={(event) =>
                setTitle(event.target.value)
              }
              placeholder="What needs to be done?"
              className="h-11 min-w-0 border rounded-lg border-ink-700 bg-ink-950/70 px-4 text-sm text-text outline-none transition-colors placeholder:text-text-dim/70 focus:border-accent"
            />

            {/* Priority */}
            <select
              value={priority}
              onChange={(event) =>
                setPriority(event.target.value)
              }
              className="h-11 min-w-0 border rounded-lg border-ink-700 bg-ink-950/70 px-4 text-sm text-text/80 outline-none focus:border-accent"
            >
              <option value="high">
                High priority
              </option>

              <option value="medium">
                Medium priority
              </option>

              <option value="low">
                Low priority
              </option>
            </select>

            {/* Goal */}
            <select
              value={selectedGoal}
              onChange={(event) =>
                setSelectedGoal(
                  event.target.value
                )
              }
              disabled={loadingGoals}
              className="h-11 min-w-0 border rounded-lg border-ink-700 bg-ink-950/70 px-4 text-sm text-text/80 outline-none focus:border-accent disabled:opacity-50"
            >
              <option value="">
                {loadingGoals
                  ? "Loading goals..."
                  : "No goal"}
              </option>

              {goals.map((goal) => (
                <option
                  key={goal._id}
                  value={goal._id}
                >
                  {goal.title}
                </option>
              ))}
            </select>

            {/* Add */}
            <button
              type="submit"
              disabled={
                busy || !title.trim()
              }
              className="h-11 border rounded-lg border-accent/30 bg-accent/10 px-6 text-sm font-medium text-accent transition-colors hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy
                ? "Adding..."
                : "Add task"}
            </button>
          </form>
        </section>

        {/* Error */}
        {error ? (
          <div className="mb-6 border rounded-lg border-rose-400/20 bg-rose-400/[0.04] px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        ) : null}

        {/* Summary */}
        <div className="mb-5 grid grid-cols-2 gap-px border rounded-lg overflow-hidden border-ink-700 bg-white/[0.07] sm:max-w-md">
          <div className="bg-ink-900/70 px-5 py-4">
            <p className="text-xs uppercase tracking-wider text-text-dim/70">
              Open
            </p>

            <p className="mt-1 text-xl font-semibold text-text">
              {openTasks.length}
            </p>
          </div>

          <div className="bg-ink-900/70 px-5 py-4">
            <p className="text-xs uppercase tracking-wider text-text-dim/70">
              Completed
            </p>

            <p className="mt-1 text-xl font-semibold text-text">
              {completedTasks.length}
            </p>
          </div>
        </div>

        {/* Open tasks */}
        <section className="border rounded-xl border-ink-700 bg-ink-900/70">
          <div className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
            <div>
              <p className="text-sm font-medium text-text">
                Open tasks
              </p>

              <p className="mt-1 text-xs text-text-dim">
                Work still requiring action.
              </p>
            </div>

            <span className="text-xs text-text-dim/70">
              {openTasks.length} active
            </span>
          </div>

          {loading ? (
            <div className="px-5 py-10 text-center text-sm text-text-dim/70">
              Loading tasks...
            </div>
          ) : openTasks.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm text-text-dim">
                No open tasks.
              </p>

              <p className="mt-1 text-xs text-text-dim/70">
                Add one above or let Compass
                create tasks from a plan.
              </p>
            </div>
          ) : (
            <div>
              {openTasks.map((task) => (
                <TaskRow
                  key={task._id}
                  task={task}
                  goals={goals}
                  onStatusChange={
                    changeTaskStatus
                  }
                  onGoalChange={
                    changeTaskGoal
                  }
                  updating={
                    updatingTaskId ===
                    task._id
                  }
                />
              ))}
            </div>
          )}
        </section>

        {/* Completed */}
        {completedTasks.length > 0 ? (
          <section className="mt-6 border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <p className="text-sm font-medium text-text/80">
                Completed
              </p>

              <p className="mt-1 text-xs text-text-dim/70">
                Finished work stays here as a
                record.
              </p>
            </div>

            <div>
              {completedTasks.map((task) => (
                <TaskRow
                  key={task._id}
                  task={task}
                  goals={goals}
                  onStatusChange={
                    changeTaskStatus
                  }
                  onGoalChange={
                    changeTaskGoal
                  }
                  updating={
                    updatingTaskId ===
                    task._id
                  }
                />
              ))}
            </div>
          </section>
        ) : null}

        {/* Relationship */}
        <section className="mt-8 border-l border-accent/30 pl-4">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent/70">
            Goal connection
          </p>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
            Every task can belong to an objective.
            Completing linked tasks automatically
            contributes to that goal's progress.
          </p>
        </section>
      </div>
    </div>
  );
}