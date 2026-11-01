
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/useApi";

export default function NotesPage() {
  const apiClient = useApi();
  const router = useRouter();

  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("updated");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);


  useEffect(() => {
    let cancelled = false;

    async function loadNotes() {
      setLoading(true);
      setError("");

      try {
        const response = await apiClient.get("/notes");

        if (cancelled) return;

        const items = Array.isArray(response)
          ? response
          : response?.items || response?.notes || [];

        setNotes(items);
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Unable to load notes.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadNotes();

    return () => {
      cancelled = true;
    };
  }, [apiClient.get]);


  const visibleNotes = useMemo(() => {
    const query = search.trim().toLowerCase();

    return [...notes]
      .filter((note) => {
        if (!query) return true;

        return (
          (note.title || "").toLowerCase().includes(query) ||
          (note.body || "").toLowerCase().includes(query)
        );
      })
      .sort((a, b) => {
        if (Boolean(a.pinned) !== Boolean(b.pinned)) {
          return a.pinned ? -1 : 1;
        }

        if (sortBy === "title") {
          return (a.title || "").localeCompare(b.title || "");
        }

        const dateA = new Date(
          a.updatedAt || a.updated_at || a.createdAt || a.created_at || 0
        ).getTime();

        const dateB = new Date(
          b.updatedAt || b.updated_at || b.createdAt || b.created_at || 0
        ).getTime();

        return dateB - dateA;
      });
  }, [notes, search, sortBy]);

  function openNote(note) {
    // Notes open in the dedicated full-screen editor.
    if (note?._id || note?.id) {
      router.push(`/editor/notes/${note._id || note.id}`);
      return;
    }
    setSelectedNote(note);
    setTitle(note.title || "");
    setBody(note.body || "");
    setEditing(false);
    setError("");
  }

  function closeNote() {
    setSelectedNote(null);
    setEditing(false);
    setError("");
  }

  async function createNote(event) {
    event.preventDefault();

    const cleanTitle = title.trim();
    const cleanBody = body.trim();

    if (!cleanTitle) {
      setError("Please enter a title.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/notes", {
        title: cleanTitle,
        body: cleanBody,
        pinned: false,
      });

      const newNote = response?.item || response?.note || response;

      if (newNote?._id) {
        setNotes((current) => [
          newNote,
          ...current.filter((note) => note._id !== newNote._id),
        ]);
      } else {
        await loadNotes();
      }

      setTitle("");
      setBody("");
    } catch (err) {
      setError(err?.message || "Unable to create note.");
    } finally {
      setBusy(false);
    }
  }

  async function saveNote(event) {
    event.preventDefault();

    if (!selectedNote?._id) return;

    const cleanTitle = title.trim();
    const cleanBody = body.trim();

    if (!cleanTitle) {
      setError("Please enter a title.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.put(
        `/notes/${selectedNote._id}`,
        {
          title: cleanTitle,
          body: cleanBody,
          pinned: Boolean(selectedNote.pinned),
        }
      );

      const updatedNote = response?.item || response?.note || response;

      const finalNote = {
        ...selectedNote,
        ...(updatedNote && typeof updatedNote === "object"
          ? updatedNote
          : {}),
        title: cleanTitle,
        body: cleanBody,
        pinned: Boolean(selectedNote.pinned),
      };

      setNotes((current) =>
        current.map((note) =>
          note._id === selectedNote._id ? finalNote : note
        )
      );

      setSelectedNote(finalNote);
      setEditing(false);
    } catch (err) {
      setError(err?.message || "Unable to save changes.");
    } finally {
      setBusy(false);
    }
  }

  async function togglePin(note) {
    if (!note?._id || busy) return;

    setBusy(true);
    setError("");

    try {
      const pinned = !note.pinned;

      const response = await apiClient.put(`/notes/${note._id}`, {
        title: note.title,
        body: note.body || "",
        pinned,
      });

      const updatedNote = response?.item || response?.note || response;

      const finalNote = {
        ...note,
        ...(updatedNote && typeof updatedNote === "object"
          ? updatedNote
          : {}),
        pinned,
      };

      setNotes((current) =>
        current.map((item) =>
          item._id === note._id ? finalNote : item
        )
      );

      if (selectedNote?._id === note._id) {
        setSelectedNote(finalNote);
      }
    } catch (err) {
      setError(err?.message || "Unable to update pin.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteNote(note) {
    if (!note?._id || deleting) return;

    const confirmed = window.confirm(
      `Delete "${note.title || "Untitled note"}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    setDeleting(true);
    setError("");

    try {
      await apiClient.del(`/notes/${note._id}`);

      setNotes((current) =>
        current.filter((item) => item._id !== note._id)
      );

      if (selectedNote?._id === note._id) {
        closeNote();
      }
    } catch (err) {
      setError(err?.message || "Unable to delete note.");
    } finally {
      setDeleting(false);
    }
  }

  function formatDate(note) {
    const value =
      note.updatedAt ||
      note.updated_at ||
      note.createdAt ||
      note.created_at;

    if (!value) return "Date unavailable";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "Date unavailable";

    return date.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent">
            Knowledge
          </p>

          <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
            Notes
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
            Capture thoughts, information, and ideas you want IntelliTwin to
            keep in view.
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-5 border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-300"
          >
            {error}
          </div>
        )}

        <section className="border rounded-xl border-ink-700 bg-ink-900/70">
          <div className="border-b border-ink-700 px-5 py-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">New note</p>
              <Link
                href="/editor/notes/new"
                className="text-xs text-accent hover:underline"
              >
                Open full-screen editor
              </Link>
            </div>
            <p className="mt-1 text-xs text-text-dim">
              Save something you want to remember.
            </p>
          </div>

          <form onSubmit={createNote} className="space-y-4 p-5">
            <div>
              <label
                htmlFor="new-note-title"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Title
              </label>

              <input
                id="new-note-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Give your note a title"
                maxLength={200}
                required
                className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none transition placeholder:text-text-dim/70 focus:border-accent"
              />
            </div>

            <div>
              <label
                htmlFor="new-note-body"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Note
              </label>

              <textarea
                id="new-note-body"
                value={body}
                onChange={(event) => setBody(event.target.value)}
                placeholder="Write your note..."
                rows={5}
                className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-text-dim/70 focus:border-accent"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy}
                className="border rounded-lg border-accent/30 bg-accent/10 px-5 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Saving..." : "Add note"}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-10">
          <div className="mb-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-medium">Your notes</p>
              <p className="mt-1 text-xs text-text-dim">
                Search, pin, and organize your saved notes.
              </p>
            </div>

            {!loading && (
              <p className="text-xs text-text-dim">
                {visibleNotes.length} of {notes.length}{" "}
                {notes.length === 1 ? "note" : "notes"}
              </p>
            )}
          </div>

          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <input
                type="search"
                aria-label="Search notes"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search titles and note content..."
                className="w-full border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-accent"
              />
            </div>

            <select
              aria-label="Sort notes"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3 text-sm text-text/80 outline-none focus:border-accent"
            >
              <option value="updated">Most recent</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>

          {loading ? (
            <div className="border rounded-xl border-ink-700 bg-ink-900/70 px-5 py-8 text-sm text-text-dim">
              Loading notes...
            </div>
          ) : visibleNotes.length === 0 ? (
            <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
              <p className="text-sm font-medium text-text/80">
                {search.trim() ? "No matching notes" : "No notes yet"}
              </p>

              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-dim">
                {search.trim()
                  ? "Try a different search term."
                  : "Your saved notes will appear here. Add your first note using the form above."}
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {visibleNotes.map((note) => (
                <article
                  key={note._id}
                  className="flex min-h-44 flex-col border rounded-xl border-ink-700 bg-ink-900/70 transition hover:border-accent/25"
                >
                  <button
                    type="button"
                    onClick={() => openNote(note)}
                    className="flex-1 p-5 text-left"
                  >
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <h2 className="line-clamp-2 text-sm font-medium text-text">
                        {note.title || "Untitled note"}
                      </h2>

                      {note.pinned && (
                        <span
                          title="Pinned note"
                          className="shrink-0 text-xs text-accent"
                        >
                          PINNED
                        </span>
                      )}
                    </div>

                    <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm leading-6 text-text-dim">
                      {note.body || "No content"}
                    </p>
                  </button>

                  <div className="flex items-center justify-between border-t border-ink-700 px-5 py-3">
                    <span className="text-xs text-text-dim/70">
                      {formatDate(note)}
                    </span>

                    <button
                      type="button"
                      onClick={() => togglePin(note)}
                      disabled={busy}
                      aria-label={
                        note.pinned ? "Unpin note" : "Pin note"
                      }
                      className="text-xs text-text-dim transition hover:text-accent disabled:opacity-50"
                    >
                      {note.pinned ? "Unpin" : "Pin"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        {selectedNote && (
          <section className="mt-8 border rounded-xl border-accent/20 bg-ink-900/70">
            <div className="flex items-start justify-between gap-4 border-b border-ink-700 px-5 py-5">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-accent">
                  {editing ? "Edit note" : "Note details"}
                </p>

                {!editing && (
                  <h2 className="mt-2 break-words text-xl font-semibold">
                    {selectedNote.title}
                  </h2>
                )}
              </div>

              <button
                type="button"
                onClick={closeNote}
                className="shrink-0 text-xs text-text-dim transition hover:text-text"
              >
                Close
              </button>
            </div>

            {editing ? (
              <form onSubmit={saveNote} className="space-y-4 p-5">
                <div>
                  <label
                    htmlFor="edit-note-title"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Title
                  </label>

                  <input
                    id="edit-note-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    maxLength={200}
                    required
                    className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label
                    htmlFor="edit-note-body"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Note
                  </label>

                  <textarea
                    id="edit-note-body"
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    rows={8}
                    className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none focus:border-accent"
                  />
                </div>

                <div className="flex flex-wrap justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setTitle(selectedNote.title || "");
                      setBody(selectedNote.body || "");
                      setEditing(false);
                      setError("");
                    }}
                    className="border border-ink-700 px-4 py-2 text-sm text-text/80 hover:bg-white/[0.04]"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={busy}
                    className="border rounded-lg border-accent/30 bg-accent/10 px-4 py-2 text-sm text-accent hover:bg-accent/15 disabled:opacity-50"
                  >
                    {busy ? "Saving..." : "Save changes"}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="px-5 py-6">
                  <div className="mb-5 flex flex-wrap items-center gap-3 text-xs text-text-dim">
                    <span>{formatDate(selectedNote)}</span>
                    <span>·</span>
                    <span>
                      {selectedNote.pinned ? "Pinned" : "Not pinned"}
                    </span>
                  </div>

                  <p className="whitespace-pre-wrap break-words text-sm leading-7 text-text/80">
                    {selectedNote.body || "This note has no content."}
                  </p>
                </div>

                <div className="flex flex-wrap justify-between gap-3 border-t border-ink-700 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => deleteNote(selectedNote)}
                    disabled={deleting}
                    className="border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-2 text-sm text-rose-300 transition hover:bg-rose-400/10 disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete note"}
                  </button>

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => togglePin(selectedNote)}
                      disabled={busy}
                      className="border border-ink-700 px-4 py-2 text-sm text-text/80 transition hover:bg-white/[0.04] disabled:opacity-50"
                    >
                      {selectedNote.pinned ? "Unpin note" : "Pin note"}
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setTitle(selectedNote.title || "");
                        setBody(selectedNote.body || "");
                        setEditing(true);
                        setError("");
                      }}
                      className="border rounded-lg border-accent/30 bg-accent/10 px-4 py-2 text-sm text-accent transition hover:bg-accent/15"
                    >
                      Edit note
                    </button>
                  </div>
                </div>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
