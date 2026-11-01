
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/useApi";

const DOCUMENT_TYPES = [
  { value: "brief", label: "Brief" },
  { value: "draft", label: "Draft" },
  { value: "summary", label: "Summary" },
  { value: "report", label: "Report" },
  { value: "other", label: "Other" },
];

const DOCUMENT_STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "final", label: "Final" },
];

function formatDate(document) {
  const value =
    document.updatedAt ||
    document.updated_at ||
    document.createdAt ||
    document.created_at;

  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function normalizeType(type) {
  return DOCUMENT_TYPES.some((item) => item.value === type)
    ? type
    : "other";
}

function normalizeStatus(status) {
  return DOCUMENT_STATUSES.some((item) => item.value === status)
    ? status
    : "draft";
}

export default function DocumentsPage() {
  const apiClient = useApi();
  const router = useRouter();

  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [type, setType] = useState("draft");
  const [status, setStatus] = useState("draft");

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("recent");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  // Read the initial collection once for this page mount.
  // Avoid depending on the apiClient object because useApi returns a new object.
  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      setLoading(true);
      setError("");

      try {
        const response = await apiClient.get("/documents");

        if (cancelled) return;

        const items = Array.isArray(response)
          ? response
          : response?.items || response?.documents || [];

        setDocuments(items);
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Unable to load documents.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDocuments();

    return () => {
      cancelled = true;
    };
    // The page loads the collection on mount. apiClient methods are recreated
    // by useApi(), so including apiClient.get here would retrigger this effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleDocuments = documents
    .filter((document) => {
      const query = search.trim().toLowerCase();

      const matchesSearch =
        !query ||
        (document.title || "").toLowerCase().includes(query) ||
        (document.content || "").toLowerCase().includes(query);

      const matchesType =
        typeFilter === "all" ||
        normalizeType(document.type) === typeFilter;

      const matchesStatus =
        statusFilter === "all" ||
        normalizeStatus(document.status) === statusFilter;

      return matchesSearch && matchesType && matchesStatus;
    })
    .sort((a, b) => {
      if (sortBy === "title") {
        return (a.title || "").localeCompare(b.title || "");
      }

      if (sortBy === "oldest") {
        return (
          new Date(
            a.createdAt || a.created_at || 0
          ).getTime() -
          new Date(
            b.createdAt || b.created_at || 0
          ).getTime()
        );
      }

      return (
        new Date(
          b.updatedAt ||
            b.updated_at ||
            b.createdAt ||
            b.created_at ||
            0
        ).getTime() -
        new Date(
          a.updatedAt ||
            a.updated_at ||
            a.createdAt ||
            a.created_at ||
            0
        ).getTime()
      );
    });

  function resetForm() {
    setTitle("");
    setContent("");
    setType("draft");
    setStatus("draft");
    setEditing(false);
    setSelectedDocument(null);
    setError("");
  }

  function openDocument(document) {
    // Documents open in the dedicated full-screen editor.
    if (document?._id || document?.id) {
      router.push(`/editor/documents/${document._id || document.id}`);
      return;
    }
    setSelectedDocument(document);
    setTitle(document.title || "");
    setContent(document.content || "");
    setType(normalizeType(document.type));
    setStatus(normalizeStatus(document.status));
    setEditing(false);
    setError("");
  }

  async function createDocument(event) {
    event.preventDefault();

    const cleanTitle = title.trim();

    if (!cleanTitle) {
      setError("Please enter a title.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/documents", {
        title: cleanTitle,
        content: content.trim(),
        type,
        status,
      });

      const newDocument =
        response?.item || response?.document || response;

      if (newDocument?._id) {
        setDocuments((current) => [
          newDocument,
          ...current.filter((item) => item._id !== newDocument._id),
        ]);
      } else {
        // Refresh only if the API did not return the created document.
        const refreshed = await apiClient.get("/documents");
        const items = Array.isArray(refreshed)
          ? refreshed
          : refreshed?.items || refreshed?.documents || [];
        setDocuments(items);
      }

      setTitle("");
      setContent("");
      setType("draft");
      setStatus("draft");
    } catch (err) {
      setError(err?.message || "Unable to create document.");
    } finally {
      setBusy(false);
    }
  }

  async function saveDocument(event) {
    event.preventDefault();

    if (!selectedDocument?._id) return;

    const cleanTitle = title.trim();

    if (!cleanTitle) {
      setError("Please enter a title.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.put(
        `/documents/${selectedDocument._id}`,
        {
          title: cleanTitle,
          content,
          type,
          status,
        }
      );

      const savedDocument = {
        ...selectedDocument,
        ...(response?.item || response?.document || response || {}),
        title: cleanTitle,
        content,
        type,
        status,
      };

      setDocuments((current) =>
        current.map((item) =>
          item._id === selectedDocument._id ? savedDocument : item
        )
      );

      setSelectedDocument(savedDocument);
      setEditing(false);
    } catch (err) {
      setError(err?.message || "Unable to save document.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteDocument(document) {
    if (!document?._id || deleting) return;

    const confirmed = window.confirm(
      `Delete "${document.title || "Untitled document"}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    setDeleting(true);
    setError("");

    try {
      await apiClient.del(`/documents/${document._id}`);

      setDocuments((current) =>
        current.filter((item) => item._id !== document._id)
      );

      if (selectedDocument?._id === document._id) {
        setSelectedDocument(null);
        setEditing(false);
      }
    } catch (err) {
      setError(err?.message || "Unable to delete document.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent">
            Workspace
          </p>

          <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
            Documents
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
            Create and organize briefs, drafts, summaries, and reports in one
            workspace.
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
              <p className="text-sm font-medium">New document</p>
              <Link
                href="/editor/documents/new"
                className="text-xs text-accent hover:underline"
              >
                Open full-screen editor
              </Link>
            </div>
            <p className="mt-1 text-xs text-text-dim">
              Create a document and keep it in your workspace.
            </p>
          </div>

          <form onSubmit={createDocument} className="space-y-4 p-5">
            <div>
              <label
                htmlFor="new-document-title"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Title
              </label>

              <input
                id="new-document-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Give your document a title"
                maxLength={200}
                required
                className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-accent"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="new-document-type"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Document type
                </label>

                <select
                  id="new-document-type"
                  value={type}
                  onChange={(event) => setType(event.target.value)}
                  className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                >
                  {DOCUMENT_TYPES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="new-document-status"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Status
                </label>

                <select
                  id="new-document-status"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                >
                  {DOCUMENT_STATUSES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label
                htmlFor="new-document-content"
                className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
              >
                Content
              </label>

              <textarea
                id="new-document-content"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="Write your document..."
                rows={8}
                className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none placeholder:text-text-dim/70 focus:border-accent"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={busy}
                className="border rounded-lg border-accent/30 bg-accent/10 px-5 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Saving..." : "Add document"}
              </button>
            </div>
          </form>
        </section>

        <section className="mt-10">
          <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-medium">Your documents</p>
              <p className="mt-1 text-xs text-text-dim">
                Search, filter, and open a document to edit it.
              </p>
            </div>

            {!loading && (
              <span className="text-xs text-text-dim">
                {visibleDocuments.length} of {documents.length} documents
              </span>
            )}
          </div>

          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <input
              type="search"
              aria-label="Search documents"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search title or content..."
              className="min-w-0 border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-accent sm:col-span-2"
            />

            <select
              aria-label="Filter by document type"
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className="border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-3 text-sm text-text/80 outline-none focus:border-accent"
            >
              <option value="all">All types</option>
              {DOCUMENT_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>

            <select
              aria-label="Filter by document status"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-3 text-sm text-text/80 outline-none focus:border-accent"
            >
              <option value="all">All statuses</option>
              {DOCUMENT_STATUSES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-4 flex justify-end">
            <select
              aria-label="Sort documents"
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value)}
              className="border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-2.5 text-sm text-text/80 outline-none focus:border-accent"
            >
              <option value="recent">Most recently updated</option>
              <option value="oldest">Oldest first</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>

          {loading ? (
            <div className="border rounded-xl border-ink-700 bg-ink-900/70 px-5 py-8 text-sm text-text-dim">
              Loading documents...
            </div>
          ) : visibleDocuments.length === 0 ? (
            <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
              <p className="text-sm font-medium text-text/80">
                {documents.length === 0
                  ? "No documents yet"
                  : "No matching documents"}
              </p>

              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-dim">
                {documents.length === 0
                  ? "Create your first document using the form above."
                  : "Try changing your search or filters."}
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {visibleDocuments.map((document) => (
                <button
                  key={document._id}
                  type="button"
                  onClick={() => openDocument(document)}
                  className="flex min-h-48 flex-col border rounded-xl border-ink-700 bg-ink-900/70 p-5 text-left transition hover:border-accent/30 hover:bg-white/[0.02]"
                >
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="border rounded-lg border-accent/20 bg-accent/5 px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-accent">
                      {DOCUMENT_TYPES.find(
                        (item) => item.value === normalizeType(document.type)
                      )?.label || "Other"}
                    </span>

                    <span
                      className={`border rounded-lg px-2 py-1 text-[10px] uppercase tracking-[0.12em] ${
                        normalizeStatus(document.status) === "final"
                          ? "border-emerald-400/20 bg-emerald-400/5 text-emerald-300"
                          : "border-ink-700 text-text-dim"
                      }`}
                    >
                      {normalizeStatus(document.status)}
                    </span>
                  </div>

                  <h2 className="line-clamp-2 text-sm font-medium text-text">
                    {document.title || "Untitled document"}
                  </h2>

                  <p className="mt-3 line-clamp-4 flex-1 whitespace-pre-wrap break-words text-sm leading-6 text-text-dim">
                    {document.content || "No content yet."}
                  </p>

                  <div className="mt-4 border-t border-ink-700 pt-3 text-xs text-text-dim/70">
                    {formatDate(document)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        {selectedDocument && (
          <section className="mt-8 border rounded-xl border-accent/20 bg-ink-900/70">
            <div className="flex items-start justify-between gap-4 border-b border-ink-700 px-5 py-5">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-accent">
                  {editing ? "Edit document" : "Document details"}
                </p>

                {!editing && (
                  <>
                    <h2 className="mt-2 break-words text-xl font-semibold">
                      {selectedDocument.title}
                    </h2>
                    <p className="mt-2 text-xs text-text-dim">
                      {DOCUMENT_TYPES.find(
                        (item) =>
                          item.value === normalizeType(selectedDocument.type)
                      )?.label || "Other"}{" "}
                      · {normalizeStatus(selectedDocument.status)} ·{" "}
                      {formatDate(selectedDocument)}
                    </p>
                  </>
                )}
              </div>

              <button
                type="button"
                onClick={resetForm}
                className="shrink-0 text-xs text-text-dim transition hover:text-text"
              >
                Close
              </button>
            </div>

            {editing ? (
              <form onSubmit={saveDocument} className="space-y-4 p-5">
                <div>
                  <label
                    htmlFor="edit-document-title"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Title
                  </label>

                  <input
                    id="edit-document-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    maxLength={200}
                    required
                    className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor="edit-document-type"
                      className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                    >
                      Type
                    </label>

                    <select
                      id="edit-document-type"
                      value={type}
                      onChange={(event) => setType(event.target.value)}
                      className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                    >
                      {DOCUMENT_TYPES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="edit-document-status"
                      className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                    >
                      Status
                    </label>

                    <select
                      id="edit-document-status"
                      value={status}
                      onChange={(event) => setStatus(event.target.value)}
                      className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                    >
                      {DOCUMENT_STATUSES.map((item) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="edit-document-content"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Content
                  </label>

                  <textarea
                    id="edit-document-content"
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    rows={12}
                    className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none focus:border-accent"
                  />
                </div>

                <div className="flex flex-wrap justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setTitle(selectedDocument.title || "");
                      setContent(selectedDocument.content || "");
                      setType(normalizeType(selectedDocument.type));
                      setStatus(normalizeStatus(selectedDocument.status));
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
                  <p className="whitespace-pre-wrap break-words text-sm leading-7 text-text/80">
                    {selectedDocument.content || "This document has no content."}
                  </p>
                </div>

                <div className="flex flex-wrap justify-between gap-3 border-t border-ink-700 px-5 py-4">
                  <button
                    type="button"
                    onClick={() => deleteDocument(selectedDocument)}
                    disabled={deleting}
                    className="border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-2 text-sm text-rose-300 transition hover:bg-rose-400/10 disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete document"}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setTitle(selectedDocument.title || "");
                      setContent(selectedDocument.content || "");
                      setType(normalizeType(selectedDocument.type));
                      setStatus(normalizeStatus(selectedDocument.status));
                      setEditing(true);
                      setError("");
                    }}
                    className="border rounded-lg border-accent/30 bg-accent/10 px-4 py-2 text-sm text-accent transition hover:bg-accent/15"
                  >
                    Edit document
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
