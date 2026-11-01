
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

function getId(item) {
  return item?._id || item?.id;
}

function getTitle(item) {
  return item?.title || item?.query || "Untitled research";
}

function getSummary(item) {
  return item?.summary || item?.content || "";
}

function getDate(item) {
  const value =
    item?.updatedAt ||
    item?.updated_at ||
    item?.createdAt ||
    item?.created_at;

  if (!value) return null;

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(date) {
  if (!date) return "Date unavailable";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function getErrorMessage(err, fallback) {
  return err?.message || fallback;
}

export default function ResearchPage() {
  const apiClient = useApi();

  const [research, setResearch] = useState([]);
  const [selectedResearch, setSelectedResearch] = useState(null);

  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("recent");

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editSummary, setEditSummary] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadResearch = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await apiClient.get("/research");

      const items = Array.isArray(response)
        ? response
        : response?.items || response?.research || [];

      setResearch(Array.isArray(items) ? items : []);
    } catch (err) {
      setError(getErrorMessage(err, "Unable to load research."));
    } finally {
      setLoading(false);
    }
  }, [apiClient.get]);

  useEffect(() => {
    loadResearch();
  }, [loadResearch]);

  const visibleResearch = useMemo(() => {
    const query = search.trim().toLowerCase();

    const filtered = research.filter((item) => {
      const searchableText = [
        getTitle(item),
        getSummary(item),
        item?.query || "",
      ]
        .join(" ")
        .toLowerCase();

      return searchableText.includes(query);
    });

    return filtered.sort((a, b) => {
      if (sortBy === "title") {
        return getTitle(a).localeCompare(getTitle(b));
      }

      const dateA = getDate(a)?.getTime() || 0;
      const dateB = getDate(b)?.getTime() || 0;

      return sortBy === "oldest" ? dateA - dateB : dateB - dateA;
    });
  }, [research, search, sortBy]);

  function openResearch(item) {
    setSelectedResearch(item);
    setEditTitle(getTitle(item));
    setEditSummary(getSummary(item));
    setEditing(false);
    setError("");
    setNotice("");
  }

  function closeResearch() {
    setSelectedResearch(null);
    setEditing(false);
    setError("");
    setNotice("");
  }

  async function createResearch(event) {
    event.preventDefault();

    const cleanTitle = title.trim();
    const cleanSummary = summary.trim();

    if (!cleanTitle) {
      setError("Please enter a research title.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const response = await apiClient.post("/research", {
        title: cleanTitle,
        summary: cleanSummary,
      });

      const newItem = response?.item || response?.research || response;

      if (newItem && getId(newItem)) {
        setResearch((current) => [
          newItem,
          ...current.filter((item) => getId(item) !== getId(newItem)),
        ]);
      } else {
        await loadResearch();
      }

      setTitle("");
      setSummary("");
      setNotice("Research saved successfully.");
    } catch (err) {
      setError(getErrorMessage(err, "Unable to save research."));
    } finally {
      setBusy(false);
    }
  }

  async function saveResearchEdit(event) {
    event.preventDefault();

    if (!selectedResearch || !getId(selectedResearch)) {
      setError("This research entry cannot be updated because its ID is missing.");
      return;
    }

    const cleanTitle = editTitle.trim();
    const cleanSummary = editSummary.trim();

    if (!cleanTitle) {
      setError("Research title cannot be empty.");
      return;
    }

    setSavingEdit(true);
    setError("");
    setNotice("");

    try {
      const id = getId(selectedResearch);

      const response = await apiClient.put(`/research/${id}`, {
        title: cleanTitle,
        summary: cleanSummary,
      });

      const updatedItem =
        response?.item || response?.research || response;

      const savedItem =
        updatedItem && typeof updatedItem === "object" && getId(updatedItem)
          ? { ...selectedResearch, ...updatedItem }
          : { ...selectedResearch, title: cleanTitle, summary: cleanSummary };

      setResearch((current) =>
        current.map((item) =>
          getId(item) === id ? savedItem : item
        )
      );

      setSelectedResearch(savedItem);
      setEditTitle(getTitle(savedItem));
      setEditSummary(getSummary(savedItem));
      setEditing(false);
      setNotice("Research updated successfully.");
    } catch (err) {
      setError(getErrorMessage(err, "Unable to update research."));
    } finally {
      setSavingEdit(false);
    }
  }

  async function deleteResearch(item) {
    const id = getId(item);

    if (!id) {
      setError("This research entry cannot be deleted because its ID is missing.");
      return;
    }

    const confirmed = window.confirm(
      `Delete "${getTitle(item)}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    setDeleting(true);
    setError("");
    setNotice("");

    try {
      await apiClient.del(`/research/${id}`);

      setResearch((current) =>
        current.filter((entry) => getId(entry) !== id)
      );

      setSelectedResearch(null);
      setEditing(false);
      setNotice("Research deleted successfully.");
    } catch (err) {
      setError(getErrorMessage(err, "Unable to delete research."));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <header className="mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-agent-atlas">
                Knowledge workspace
              </p>

              <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                Research
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
                Collect findings, preserve useful information, and build
                your own searchable research library.
              </p>
            </div>

            <div className="flex gap-3">
              <div className="min-w-24 border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3">
                <p className="text-xs text-text-dim">Total entries</p>
                <p className="mt-1 text-xl font-semibold">
                  {research.length}
                </p>
              </div>

              <div className="min-w-24 border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3">
                <p className="text-xs text-text-dim">Showing</p>
                <p className="mt-1 text-xl font-semibold">
                  {visibleResearch.length}
                </p>
              </div>
            </div>
          </div>
        </header>

        {/* Feedback */}
        {error && (
          <div
            role="alert"
            className="mb-5 flex items-start justify-between gap-3 border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-300"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              aria-label="Dismiss error"
              className="text-rose-300/70 hover:text-rose-200"
            >
              ×
            </button>
          </div>
        )}

        {notice && !error && (
          <div
            role="status"
            className="mb-5 flex items-center justify-between gap-3 border rounded-lg border-agent-atlas/20 bg-agent-atlas/5 px-4 py-3 text-sm text-agent-atlas"
          >
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice("")}
              aria-label="Dismiss message"
              className="text-agent-atlas/70 hover:text-agent-atlas"
            >
              ×
            </button>
          </div>
        )}

        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          {/* Create research */}
          <section className="border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <p className="text-sm font-medium text-text">
                Create an entry
              </p>
              <p className="mt-1 text-xs leading-5 text-text-dim">
                Save an idea, a finding, a topic, or a research summary.
              </p>
            </div>

            <form onSubmit={createResearch} className="space-y-5 p-5">
              <div>
                <label
                  htmlFor="research-title"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Title
                </label>

                <input
                  id="research-title"
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="e.g. Federated learning approaches"
                  maxLength={200}
                  required
                  className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none transition placeholder:text-text-dim/70 focus:border-agent-atlas"
                />
              </div>

              <div>
                <label
                  htmlFor="research-summary"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Findings and notes
                </label>

                <textarea
                  id="research-summary"
                  value={summary}
                  onChange={(event) => setSummary(event.target.value)}
                  placeholder="Record your findings, important details, conclusions, and useful references..."
                  rows={9}
                  className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-text-dim/70 focus:border-agent-atlas"
                />

                <p className="mt-2 text-right text-xs text-text-dim/70">
                  {summary.length} characters
                </p>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="w-full border rounded-lg border-agent-atlas/30 bg-agent-atlas/10 px-5 py-3 text-sm font-medium text-agent-atlas transition hover:bg-agent-atlas/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Saving research..." : "Save research"}
              </button>
            </form>
          </section>

          {/* Research library */}
          <section className="min-w-0">
            <div className="mb-4">
              <h2 className="text-sm font-medium text-text">
                Research library
              </h2>
              <p className="mt-1 text-xs leading-5 text-text-dim">
                Search your entries or select one to view and edit it.
              </p>
            </div>

            {/* Search and sorting */}
            <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_150px]">
              <div className="relative">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-dim"
                >
                  ⌕
                </span>

                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search titles and findings..."
                  aria-label="Search research"
                  className="w-full border rounded-xl border-ink-700 bg-ink-900/70 py-3 pl-9 pr-4 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-agent-atlas"
                />
              </div>

              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                aria-label="Sort research"
                className="border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-3 text-sm text-text/80 outline-none focus:border-agent-atlas"
              >
                <option value="recent">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="title">Title A–Z</option>
              </select>
            </div>

            {loading ? (
              <div className="border rounded-xl border-ink-700 bg-ink-900/70 px-5 py-10 text-center">
                <p className="text-sm text-text-dim">
                  Loading your research library...
                </p>
              </div>
            ) : visibleResearch.length === 0 ? (
              <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
                <div className="mx-auto flex h-11 w-11 items-center justify-center border border-ink-700 text-lg text-text-dim">
                  {search ? "⌕" : "+"}
                </div>

                <p className="mt-4 text-sm font-medium text-text/80">
                  {search
                    ? "No matching research"
                    : "Your research library is empty"}
                </p>

                <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-text-dim">
                  {search
                    ? "Try a different search term or clear your search."
                    : "Create your first entry using the form. It will appear here once saved."}
                </p>

                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="mt-4 text-xs text-agent-atlas hover:text-agent-atlas"
                  >
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {visibleResearch.map((item) => {
                  const id = getId(item);
                  const isSelected =
                    id && id === getId(selectedResearch);
                  const itemSummary = getSummary(item);
                  const itemDate = getDate(item);

                  return (
                    <button
                      key={id || `${getTitle(item)}-${itemSummary}`}
                      type="button"
                      onClick={() => openResearch(item)}
                      className={`group w-full border rounded-xl p-4 text-left transition ${
                        isSelected
                          ? "border-agent-atlas/30 bg-agent-atlas/[0.06]"
                          : "border-ink-700 bg-ink-900/70 hover:border-ink-500 hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="break-words text-sm font-medium text-text transition group-hover:text-agent-atlas">
                            {getTitle(item)}
                          </p>

                          <p className="mt-2 line-clamp-3 whitespace-pre-wrap break-words text-sm leading-6 text-text-dim">
                            {itemSummary || "No findings or summary added yet."}
                          </p>
                        </div>

                        <span className="shrink-0 text-text-dim/70 transition group-hover:text-agent-atlas">
                          →
                        </span>
                      </div>

                      <div className="mt-4 flex items-center justify-between gap-3 border-t border-ink-700 pt-3">
                        <span className="text-xs text-text-dim/70">
                          {formatDate(itemDate)}
                        </span>

                        <span className="text-xs text-text-dim">
                          {itemSummary.length} characters
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {/* Research detail */}
        {selectedResearch && (
          <section className="mt-8 border rounded-xl border-agent-atlas/20 bg-ink-900/70">
            <div className="flex flex-col gap-4 border-b border-ink-700 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-agent-atlas">
                  Research entry
                </p>

                {!editing ? (
                  <h2 className="mt-2 break-words text-xl font-semibold text-text">
                    {getTitle(selectedResearch)}
                  </h2>
                ) : (
                  <p className="mt-2 text-sm text-text-dim">
                    Edit your research details
                  </p>
                )}

                <p className="mt-2 text-xs text-text-dim">
                  Last recorded date: {formatDate(getDate(selectedResearch))}
                </p>
              </div>

              <div className="flex shrink-0 flex-wrap gap-2">
                {!editing && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditTitle(getTitle(selectedResearch));
                      setEditSummary(getSummary(selectedResearch));
                      setEditing(true);
                      setError("");
                      setNotice("");
                    }}
                    className="border rounded-lg border-agent-atlas/25 bg-agent-atlas/[0.06] px-3 py-2 text-xs font-medium text-agent-atlas transition hover:bg-agent-atlas/10"
                  >
                    Edit entry
                  </button>
                )}

                <button
                  type="button"
                  onClick={closeResearch}
                  className="border border-ink-700 px-3 py-2 text-xs text-text-dim transition hover:bg-white/[0.04] hover:text-text"
                >
                  Close
                </button>
              </div>
            </div>

            {editing ? (
              <form onSubmit={saveResearchEdit} className="space-y-5 p-5">
                <div>
                  <label
                    htmlFor="edit-research-title"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Title
                  </label>

                  <input
                    id="edit-research-title"
                    type="text"
                    value={editTitle}
                    onChange={(event) => setEditTitle(event.target.value)}
                    maxLength={200}
                    required
                    className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-agent-atlas"
                  />
                </div>

                <div>
                  <label
                    htmlFor="edit-research-summary"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Findings and notes
                  </label>

                  <textarea
                    id="edit-research-summary"
                    value={editSummary}
                    onChange={(event) => setEditSummary(event.target.value)}
                    rows={10}
                    className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-7 text-text outline-none focus:border-agent-atlas"
                  />
                </div>

                <div className="flex flex-wrap justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setEditTitle(getTitle(selectedResearch));
                      setEditSummary(getSummary(selectedResearch));
                      setError("");
                    }}
                    disabled={savingEdit}
                    className="border border-ink-700 px-4 py-2.5 text-sm text-text-dim transition hover:text-text disabled:opacity-50"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={savingEdit}
                    className="border rounded-lg border-agent-atlas/30 bg-agent-atlas/10 px-5 py-2.5 text-sm font-medium text-agent-atlas transition hover:bg-agent-atlas/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingEdit ? "Saving changes..." : "Save changes"}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="min-h-40 px-5 py-6">
                  {getSummary(selectedResearch) ? (
                    <p className="whitespace-pre-wrap break-words text-sm leading-7 text-text/80">
                      {getSummary(selectedResearch)}
                    </p>
                  ) : (
                    <p className="text-sm italic text-text-dim">
                      No findings or summary have been added to this entry.
                    </p>
                  )}
                </div>

                <div className="flex flex-col gap-3 border-t border-ink-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-text-dim/70">
                    Changes are saved to your research library.
                  </p>

                  <button
                    type="button"
                    onClick={() => deleteResearch(selectedResearch)}
                    disabled={deleting}
                    className="border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-2.5 text-sm text-rose-300 transition hover:bg-rose-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete research"}
                  </button>
                </div>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
