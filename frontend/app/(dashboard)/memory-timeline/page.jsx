
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

function formatDate(value) {
  if (!value) return "Unknown date";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Unknown date";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value) {
  if (!value) return "Unknown date";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Unknown date";

  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getMemoryDate(memory) {
  return memory?.occurredAt || memory?.createdAt || null;
}

function getMemoryTitle(memory) {
  return (
    memory?.title?.trim() ||
    memory?.content?.trim()?.split(/\s+/).slice(0, 8).join(" ") ||
    "Untitled memory"
  );
}

export default function MemoryTimelinePage() {
  const apiClient = useApi();

  const [memories, setMemories] = useState([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("active");
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState({ title: "", content: "", importance: 3 });
  const [savingId, setSavingId] = useState(null);
  const [restoringId, setRestoringId] = useState(null);

  const loadMemories = useCallback(
    async (isRefresh = false) => {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      try {
        const response = await apiClient.get(`/memory/timeline?view=${view}`);

        const items = Array.isArray(response)
          ? response
          : response?.items || response?.memories || [];

        const sorted = [...items].sort((a, b) => {
          const dateA = new Date(getMemoryDate(a) || 0).getTime();
          const dateB = new Date(getMemoryDate(b) || 0).getTime();
          return dateB - dateA;
        });

        setMemories(sorted);
      } catch (err) {
        setError(err?.message || "Unable to load memories.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [apiClient, view]
  );

  useEffect(() => {
    loadMemories();
  }, [loadMemories]);

  const filteredMemories = useMemo(() => {
    const query = search.trim().toLowerCase();

    return memories.filter((memory) => {
      const title = getMemoryTitle(memory);
      const content = memory?.content || "";

      const matchesSearch =
        !query ||
        title.toLowerCase().includes(query) ||
        content.toLowerCase().includes(query);

      const hasDetails = Boolean(content.trim());

      const matchesFilter =
        filter === "all" ||
        (filter === "detailed" && hasDetails) ||
        (filter === "titles" && !hasDetails);

      return matchesSearch && matchesFilter;
    });
  }, [memories, search, filter]);

  const detailedCount = useMemo(
    () =>
      memories.filter((memory) => Boolean(memory?.content?.trim())).length,
    [memories]
  );

  const latestDate = memories.length
    ? formatDate(getMemoryDate(memories[0]))
    : "No memories yet";

  function startEdit(memory) {
    setEditingId(memory._id);
    setDraft({
      title: memory.title || "",
      content: memory.content || "",
      importance: memory.importance || 3,
    });
    setError("");
  }

  async function saveEdit(memory) {
    if (savingId) return;
    if (!draft.title.trim()) {
      setError("A memory needs a title.");
      return;
    }
    setSavingId(memory._id);
    setError("");
    try {
      await apiClient.put(`/memory/${memory._id}`, {
        title: draft.title.trim(),
        content: draft.content,
        importance: Number(draft.importance) || 3,
        // Refuse to overwrite a newer version saved elsewhere (e.g. by Echo).
        expectedUpdatedAt: memory.updatedAt,
      });
      setEditingId(null);
      await loadMemories(true);
    } catch (err) {
      setError(
        err?.status === 409
          ? "This memory changed elsewhere. It has been reloaded - review it and try again."
          : err?.message || "Unable to save memory."
      );
      if (err?.status === 409) {
        setEditingId(null);
        await loadMemories(true);
      }
    } finally {
      setSavingId(null);
    }
  }

  async function restoreMemory(memory) {
    if (restoringId) return;
    setRestoringId(memory._id);
    setError("");
    try {
      await apiClient.post(`/memory/${memory._id}/restore`, {});
      await loadMemories(true);
    } catch (err) {
      setError(err?.message || "Unable to restore memory.");
    } finally {
      setRestoringId(null);
    }
  }

  async function deleteMemory(memory) {
    if (!memory?._id || deletingId) return;

    const confirmed = window.confirm(
      `Permanently delete "${getMemoryTitle(memory)}"? This cannot be undone.`
    );

    if (!confirmed) return;

    setDeletingId(memory._id);
    setError("");

    try {
      await apiClient.del(`/memory/${memory._id}`);

      setMemories((current) =>
        current.filter((item) => item._id !== memory._id)
      );
    } catch (err) {
      setError(err?.message || "Unable to delete memory.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-agent-echo">
              Echo / Personal knowledge
            </p>

            <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
              Memory Timeline
            </h1>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
              Review what Echo has stored, correct it, restore archived items,
              and see which memories were replaced by newer ones.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadMemories(true)}
            disabled={loading || refreshing}
            className="inline-flex items-center justify-center gap-2 self-start border rounded-lg border-ink-700 bg-white/[0.03] px-4 py-2.5 text-sm text-text/80 transition hover:border-agent-echo/30 hover:text-text disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto"
          >
            <span className={refreshing ? "animate-spin" : ""}>↻</span>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-6 flex flex-col justify-between gap-3 border rounded-lg border-rose-400/20 bg-rose-400/[0.05] px-4 py-3 sm:flex-row sm:items-center"
          >
            <p className="text-sm text-rose-300">{error}</p>
            <button
              type="button"
              onClick={() => loadMemories()}
              className="self-start text-sm text-rose-200 underline underline-offset-4 hover:text-text sm:self-auto"
            >
              Try again
            </button>
          </div>
        )}

        <section className="mb-8 grid gap-3 sm:grid-cols-3">
          <div className="border rounded-xl border-ink-700 bg-ink-900/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-dim">
              Total memories
            </p>
            <p className="mt-3 text-3xl font-semibold tabular-nums text-text">
              {memories.length}
            </p>
            <p className="mt-1 text-xs text-text-dim">Stored by Echo</p>
          </div>

          <div className="border rounded-xl border-ink-700 bg-ink-900/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-dim">
              With details
            </p>
            <p className="mt-3 text-3xl font-semibold tabular-nums text-text">
              {detailedCount}
            </p>
            <p className="mt-1 text-xs text-text-dim">
              Memories with additional content
            </p>
          </div>

          <div className="border rounded-xl border-ink-700 bg-ink-900/70 p-5">
            <p className="text-xs uppercase tracking-[0.15em] text-text-dim">
              Most recent
            </p>
            <p className="mt-3 text-lg font-semibold text-text">
              {latestDate}
            </p>
            <p className="mt-1 text-xs text-text-dim">
              Based on the timeline date
            </p>
          </div>
        </section>

        <section className="mb-8 border rounded-xl border-ink-700 bg-ink-900/70 p-4 sm:p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0 flex-1">
              <label
                htmlFor="memory-search"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Search memories
              </label>
              <input
                id="memory-search"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search memory titles and content..."
                className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-agent-echo"
              />
            </div>

            <div className="min-w-0 lg:w-56">
              <label
                htmlFor="memory-view"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Status
              </label>
              <select
                id="memory-view"
                value={view}
                onChange={(event) => setView(event.target.value)}
                className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-agent-echo"
              >
                <option value="active">Current</option>
                <option value="superseded">Replaced by newer memory</option>
                <option value="archived">Archived</option>
                <option value="all">Everything</option>
              </select>
            </div>

            <div className="min-w-0 lg:w-72">
              <label
                htmlFor="memory-filter"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Show
              </label>
              <select
                id="memory-filter"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-agent-echo"
              >
                <option value="all">All memories</option>
                <option value="detailed">Memories with details</option>
                <option value="titles">Memories without details</option>
              </select>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-ink-700 pt-4">
            <p className="text-xs text-text-dim">
              Showing {filteredMemories.length} of {memories.length} memories
            </p>

            {(search || filter !== "all") && (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setFilter("all");
                }}
                className="text-xs text-agent-echo transition hover:text-text"
              >
                Clear filters
              </button>
            )}
          </div>
        </section>

        {loading ? (
          <div className="border rounded-xl border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
            <div className="mx-auto mb-4 h-5 w-5 animate-spin border-2 border-agent-echo/30 border-t-agent-echo" />
            <p className="text-sm text-text-dim">
              Loading memory timeline...
            </p>
          </div>
        ) : memories.length === 0 ? (
          <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-16 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center border rounded-lg border-ink-700 bg-white/[0.03] text-xl text-text-dim">
              ◷
            </div>
            <h2 className="mt-5 text-base font-medium text-text">
              No memories yet
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-dim">
              Memories stored by Echo will appear here.
            </p>
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-14 text-center">
            <h2 className="text-base font-medium text-text">
              No matching memories
            </h2>
            <p className="mt-2 text-sm text-text-dim">
              Try another search term or clear the filters.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
              className="mt-5 border border-ink-700 px-4 py-2 text-sm text-text/80 transition hover:border-agent-echo/30 hover:text-text"
            >
              Clear search
            </button>
          </div>
        ) : (
          <section aria-label="Memory timeline" className="min-w-0">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-sm font-medium text-text">
                Chronological record
              </h2>
              <span className="text-xs text-text-dim">Newest first</span>
            </div>

            <div className="relative">
              <div className="absolute bottom-2 left-[7px] top-2 w-px bg-white/[0.09]" />

              <div className="space-y-5">
                {filteredMemories.map((memory) => {
                  const date = getMemoryDate(memory);
                  const isDeleting = deletingId === memory._id;

                  return (
                    <div key={memory._id} className="relative pl-8">
                      <div className="absolute left-0 top-4 h-[15px] w-[15px] border-2 border-ink-950 bg-ink-500" />

                      <p className="mb-2 text-xs font-medium uppercase tracking-[0.12em] text-text-dim">
                        {formatDate(date)}
                      </p>

                      <div className="border rounded-xl border-ink-700 bg-ink-900/70 p-4 sm:p-5">
                        {editingId === memory._id ? (
                          <div className="space-y-3">
                            <input
                              aria-label="Memory title"
                              value={draft.title}
                              maxLength={200}
                              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                              className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-3 py-2 text-sm text-text outline-none focus:border-agent-echo"
                            />
                            <textarea
                              aria-label="Memory details"
                              value={draft.content}
                              rows={4}
                              maxLength={5000}
                              onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                              className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-3 py-2 text-sm text-text outline-none focus:border-agent-echo"
                            />
                            <label className="flex items-center gap-2 text-xs text-text-dim">
                              Importance (1-5)
                              <input
                                type="number"
                                min={1}
                                max={5}
                                value={draft.importance}
                                onChange={(e) => setDraft({ ...draft, importance: e.target.value })}
                                className="w-16 border rounded-lg border-ink-700 bg-ink-950/70 px-2 py-1 text-sm text-text outline-none"
                              />
                            </label>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => saveEdit(memory)}
                                disabled={Boolean(savingId)}
                                className="border rounded-lg border-agent-echo/30 bg-agent-echo/[0.08] px-3 py-2 text-xs text-agent-echo transition hover:bg-agent-echo/15 disabled:opacity-50"
                              >
                                {savingId === memory._id ? "Saving..." : "Save"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingId(null)}
                                disabled={Boolean(savingId)}
                                className="border border-ink-700 px-3 py-2 text-xs text-text/80 transition hover:text-text disabled:opacity-50"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center justify-between gap-4">
                              <div className="min-w-0">
                                <h3 className="break-words text-sm font-medium text-text">
                                  {getMemoryTitle(memory)}
                                </h3>
                                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.1em]">
                                  <span
                                    className={
                                      memory.lifecycle === "superseded"
                                        ? "text-amber-300"
                                        : memory.lifecycle === "archived"
                                        ? "text-text-dim"
                                        : "text-emerald-300"
                                    }
                                  >
                                    {memory.lifecycle === "superseded"
                                      ? "Replaced"
                                      : memory.lifecycle === "archived"
                                      ? "Archived"
                                      : "Current"}
                                  </span>
                                  {memory.importance ? (
                                    <span className="text-text-dim">Importance {memory.importance}/5</span>
                                  ) : null}
                                </div>
                              </div>

                              <div className="flex shrink-0 gap-2">
                                {memory.lifecycle === "archived" ? (
                                  <button
                                    type="button"
                                    onClick={() => restoreMemory(memory)}
                                    disabled={Boolean(restoringId)}
                                    className="border border-agent-echo/20 px-3 py-2 text-xs text-agent-echo transition hover:bg-agent-echo/10 disabled:opacity-50"
                                  >
                                    {restoringId === memory._id ? "Restoring..." : "Restore"}
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => startEdit(memory)}
                                    className="border border-ink-700 px-3 py-2 text-xs text-text/80 transition hover:text-text"
                                  >
                                    Edit
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => deleteMemory(memory)}
                                  disabled={Boolean(deletingId)}
                                  className="border rounded-lg border-rose-400/20 bg-rose-400/[0.05] px-3 py-2 text-xs text-rose-300 transition hover:bg-rose-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  {isDeleting ? "Deleting..." : "Delete"}
                                </button>
                              </div>
                            </div>

                            {memory.content ? (
                              <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-text-dim">
                                {memory.content}
                              </p>
                            ) : null}

                            {memory.lifecycle === "superseded" ? (
                              <p className="mt-3 text-xs text-amber-200/80">
                                Replaced
                                {memory.supersededAt ? ` on ${formatDate(memory.supersededAt)}` : ""}
                                {memory.supersededByTitle ? ` by "${memory.supersededByTitle}"` : " by a newer memory"}.
                                Echo no longer uses this one; it is kept as history.
                              </p>
                            ) : null}
                          </>
                        )}

                        <p className="mt-3 border-t border-ink-700 pt-3 text-xs text-text-dim">
                          {formatDateTime(date)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
