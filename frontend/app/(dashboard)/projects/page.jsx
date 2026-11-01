
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useApi } from "@/lib/useApi";

const PROJECT_STATUSES = [
  { value: "active", label: "Active" },
  { value: "in_progress", label: "In Progress" },
  { value: "on_hold", label: "On Hold" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

function getId(project) {
  return project?._id || project?.id;
}

function getProjectName(project) {
  return project?.name || "Untitled project";
}

function getProjectDate(project) {
  const value =
    project?.updatedAt ||
    project?.updated_at ||
    project?.createdAt ||
    project?.created_at;

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

function formatStatus(status) {
  if (!status) return "Active";

  return String(status)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeStatus(status) {
  const normalized = String(status || "active").toLowerCase();

  return PROJECT_STATUSES.some((item) => item.value === normalized)
    ? normalized
    : "active";
}

export default function ProjectsPage() {
  const apiClient = useApi();

  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("recent");

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editStatus, setEditStatus] = useState("active");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await apiClient.get("/projects");

      const items = Array.isArray(response)
        ? response
        : response?.items || response?.projects || [];

      const safeItems = Array.isArray(items) ? items : [];
      setProjects(safeItems);

      // Keep the open details panel synchronized with refreshed data.
      setSelectedProject((current) => {
        if (!current) return null;

        const currentId = getId(current);
        const refreshed = safeItems.find(
          (project) => getId(project) === currentId
        );

        return refreshed || null;
      });
    } catch (err) {
      setError(err?.message || "Unable to load projects.");
    } finally {
      setLoading(false);
    }
  }, [apiClient.get]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const visibleProjects = useMemo(() => {
    const query = search.trim().toLowerCase();

    const filtered = projects.filter((project) => {
      const searchableText = [
        getProjectName(project),
        project?.description || "",
        project?.status || "",
      ]
        .join(" ")
        .toLowerCase();

      return searchableText.includes(query);
    });

    return filtered.sort((a, b) => {
      if (sortBy === "name") {
        return getProjectName(a).localeCompare(getProjectName(b));
      }

      const dateA = getProjectDate(a)?.getTime() || 0;
      const dateB = getProjectDate(b)?.getTime() || 0;

      return sortBy === "oldest" ? dateA - dateB : dateB - dateA;
    });
  }, [projects, search, sortBy]);

  function openProject(project) {
    setSelectedProject(project);
    setEditName(getProjectName(project));
    setEditDescription(project?.description || "");
    setEditStatus(normalizeStatus(project?.status));
    setEditing(false);
    setError("");
    setNotice("");
  }

  function closeProject() {
    setSelectedProject(null);
    setEditing(false);
    setError("");
    setNotice("");
  }

  function startEditing() {
    setEditName(getProjectName(selectedProject));
    setEditDescription(selectedProject?.description || "");
    setEditStatus(normalizeStatus(selectedProject?.status));
    setEditing(true);
    setError("");
    setNotice("");
  }

  function cancelEditing() {
    setEditName(getProjectName(selectedProject));
    setEditDescription(selectedProject?.description || "");
    setEditStatus(normalizeStatus(selectedProject?.status));
    setEditing(false);
    setError("");
  }

  async function createProject(event) {
    event.preventDefault();

    const cleanName = name.trim();
    const cleanDescription = description.trim();

    if (!cleanName) {
      setError("Please enter a project name.");
      return;
    }

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const response = await apiClient.post("/projects", {
        name: cleanName,
        description: cleanDescription,
      });

      const newProject = response?.item || response?.project || response;

      if (newProject && getId(newProject)) {
        setProjects((current) => [
          newProject,
          ...current.filter(
            (project) => getId(project) !== getId(newProject)
          ),
        ]);
      } else {
        await loadProjects();
      }

      setName("");
      setDescription("");
      setNotice("Project created successfully.");
    } catch (err) {
      setError(err?.message || "Unable to create project.");
    } finally {
      setBusy(false);
    }
  }

  async function saveProjectEdit(event) {
    event.preventDefault();

    if (!selectedProject || !getId(selectedProject)) {
      setError("This project cannot be updated because its ID is missing.");
      return;
    }

    const cleanName = editName.trim();
    const cleanDescription = editDescription.trim();

    if (!cleanName) {
      setError("Project name cannot be empty.");
      return;
    }

    setSavingEdit(true);
    setError("");
    setNotice("");

    try {
      const id = getId(selectedProject);

      const response = await apiClient.put(`/projects/${id}`, {
        name: cleanName,
        description: cleanDescription,
        status: editStatus,
      });

      const returnedProject =
        response?.item || response?.project || response;

      const updatedProject =
        returnedProject &&
        typeof returnedProject === "object" &&
        getId(returnedProject)
          ? {
              ...selectedProject,
              ...returnedProject,
              name: cleanName,
              description: cleanDescription,
              status: editStatus,
            }
          : {
              ...selectedProject,
              name: cleanName,
              description: cleanDescription,
              status: editStatus,
            };

      setProjects((current) =>
        current.map((project) =>
          getId(project) === id ? updatedProject : project
        )
      );

      setSelectedProject(updatedProject);
      setEditName(cleanName);
      setEditDescription(cleanDescription);
      setEditStatus(editStatus);
      setEditing(false);
      setNotice("Project updated successfully.");
    } catch (err) {
      setError(err?.message || "Unable to update project.");
    } finally {
      setSavingEdit(false);
    }
  }

  async function deleteProject(project) {
    const id = getId(project);

    if (!id) {
      setError("This project cannot be deleted because its ID is missing.");
      return;
    }

    const confirmed = window.confirm(
      `Delete "${getProjectName(project)}"? This action cannot be undone.`
    );

    if (!confirmed) return;

    setDeleting(true);
    setError("");
    setNotice("");

    try {
      await apiClient.del(`/projects/${id}`);

      setProjects((current) =>
        current.filter((item) => getId(item) !== id)
      );

      setSelectedProject(null);
      setEditing(false);
      setNotice("Project deleted successfully.");
    } catch (err) {
      setError(err?.message || "Unable to delete project.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent">
                Workspace
              </p>

              <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                Projects
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
                Organize larger bodies of work, keep project details together,
                and track the information that matters.
              </p>
            </div>

            <div className="flex gap-3">
              <div className="min-w-24 border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3">
                <p className="text-xs text-text-dim">Total projects</p>
                <p className="mt-1 text-xl font-semibold">
                  {projects.length}
                </p>
              </div>

              <div className="min-w-24 border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3">
                <p className="text-xs text-text-dim">Showing</p>
                <p className="mt-1 text-xl font-semibold">
                  {visibleProjects.length}
                </p>
              </div>
            </div>
          </div>
        </header>

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
            className="mb-5 flex items-center justify-between gap-3 border rounded-lg border-accent/20 bg-accent/5 px-4 py-3 text-sm text-accent"
          >
            <span>{notice}</span>
            <button
              type="button"
              onClick={() => setNotice("")}
              aria-label="Dismiss message"
              className="text-accent/70 hover:text-accent"
            >
              ×
            </button>
          </div>
        )}

        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <section className="border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <p className="text-sm font-medium text-text">New project</p>
              <p className="mt-1 text-xs leading-5 text-text-dim">
                Define a project and record its purpose.
              </p>
            </div>

            <form onSubmit={createProject} className="space-y-5 p-5">
              <div>
                <label
                  htmlFor="project-name"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Project name
                </label>

                <input
                  id="project-name"
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. IntelliTwin development"
                  maxLength={200}
                  required
                  className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none transition placeholder:text-text-dim/70 focus:border-accent"
                />
              </div>

              <div>
                <label
                  htmlFor="project-description"
                  className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                >
                  Description
                </label>

                <textarea
                  id="project-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What are you working on? Record the purpose, scope, and important details."
                  rows={7}
                  className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-6 text-text outline-none transition placeholder:text-text-dim/70 focus:border-accent"
                />

                <p className="mt-2 text-right text-xs text-text-dim/70">
                  {description.length} characters
                </p>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="w-full border rounded-lg border-accent/30 bg-accent/10 px-5 py-3 text-sm font-medium text-accent transition hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Creating project..." : "Create project"}
              </button>
            </form>
          </section>

          <section className="min-w-0">
            <div className="mb-4">
              <h2 className="text-sm font-medium text-text">
                Your projects
              </h2>
              <p className="mt-1 text-xs leading-5 text-text-dim">
                Search, sort, and select a project to view its details.
              </p>
            </div>

            <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_150px]">
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search projects..."
                aria-label="Search projects"
                className="w-full border rounded-xl border-ink-700 bg-ink-900/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-accent"
              />

              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                aria-label="Sort projects"
                className="border rounded-xl border-ink-700 bg-ink-900/70 px-3 py-3 text-sm text-text/80 outline-none focus:border-accent"
              >
                <option value="recent">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="name">Name A–Z</option>
              </select>
            </div>

            {loading ? (
              <div className="border rounded-xl border-ink-700 bg-ink-900/70 px-5 py-10 text-center text-sm text-text-dim">
                Loading projects...
              </div>
            ) : visibleProjects.length === 0 ? (
              <div className="border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
                <div className="mx-auto flex h-11 w-11 items-center justify-center border border-ink-700 text-lg text-text-dim">
                  {search ? "⌕" : "+"}
                </div>

                <p className="mt-4 text-sm font-medium text-text/80">
                  {search ? "No matching projects" : "No projects yet"}
                </p>

                <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-text-dim">
                  {search
                    ? "Try another search term or clear your search."
                    : "Create your first project using the form."}
                </p>

                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    className="mt-4 text-xs text-accent hover:text-accent"
                  >
                    Clear search
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {visibleProjects.map((project) => {
                  const id = getId(project);
                  const selected =
                    id && id === getId(selectedProject);
                  const date = getProjectDate(project);

                  return (
                    <button
                      key={id || getProjectName(project)}
                      type="button"
                      onClick={() => openProject(project)}
                      className={`w-full border rounded-xl p-4 text-left transition ${
                        selected
                          ? "border-accent/30 bg-accent/[0.06]"
                          : "border-ink-700 bg-ink-900/70 hover:border-ink-500 hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="break-words text-sm font-medium text-text transition hover:text-accent">
                            {getProjectName(project)}
                          </p>

                          <p className="mt-2 line-clamp-3 whitespace-pre-wrap break-words text-sm leading-6 text-text-dim">
                            {project.description ||
                              "No description added yet."}
                          </p>
                        </div>

                        <span className="shrink-0 text-text-dim/70">→</span>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 pt-3">
                        <span className="text-xs text-text-dim/70">
                          {formatDate(date)}
                        </span>

                        <span className="border border-ink-700 px-2 py-1 text-xs text-text-dim">
                          {formatStatus(project.status)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {selectedProject && (
          <section className="mt-8 border rounded-xl border-accent/20 bg-ink-900/70">
            <div className="flex flex-col gap-4 border-b border-ink-700 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-accent">
                  Project details
                </p>

                {!editing ? (
                  <h2 className="mt-2 break-words text-xl font-semibold text-text">
                    {getProjectName(selectedProject)}
                  </h2>
                ) : (
                  <p className="mt-2 text-sm text-text-dim">
                    Edit project information
                  </p>
                )}

                <p className="mt-2 text-xs text-text-dim">
                  Recorded date: {formatDate(getProjectDate(selectedProject))}
                </p>
              </div>

              <div className="flex shrink-0 flex-wrap gap-2">
                {!editing && (
                  <button
                    type="button"
                    onClick={startEditing}
                    className="border rounded-lg border-accent/25 bg-accent/[0.06] px-3 py-2 text-xs font-medium text-accent transition hover:bg-accent/10"
                  >
                    Edit project
                  </button>
                )}

                <button
                  type="button"
                  onClick={closeProject}
                  className="border border-ink-700 px-3 py-2 text-xs text-text-dim transition hover:bg-white/[0.04] hover:text-text"
                >
                  Close
                </button>
              </div>
            </div>

            {editing ? (
              <form onSubmit={saveProjectEdit} className="space-y-5 p-5">
                <div>
                  <label
                    htmlFor="edit-project-name"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Project name
                  </label>

                  <input
                    id="edit-project-name"
                    type="text"
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    maxLength={200}
                    required
                    className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label
                    htmlFor="edit-project-description"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Description
                  </label>

                  <textarea
                    id="edit-project-description"
                    value={editDescription}
                    onChange={(event) =>
                      setEditDescription(event.target.value)
                    }
                    rows={7}
                    className="w-full resize-y border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm leading-7 text-text outline-none focus:border-accent"
                  />
                </div>

                <div>
                  <label
                    htmlFor="edit-project-status"
                    className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
                  >
                    Project status
                  </label>

                  <select
                    id="edit-project-status"
                    value={editStatus}
                    onChange={(event) => setEditStatus(event.target.value)}
                    className="w-full border rounded-lg border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none focus:border-accent"
                  >
                    {PROJECT_STATUSES.map((status) => (
                      <option key={status.value} value={status.value}>
                        {status.label}
                      </option>
                    ))}
                  </select>

                  <p className="mt-2 text-xs leading-5 text-text-dim">
                    Choose the current state of this project.
                  </p>
                </div>

                <div className="flex flex-wrap justify-end gap-3">
                  <button
                    type="button"
                    onClick={cancelEditing}
                    disabled={savingEdit}
                    className="border border-ink-700 px-4 py-2.5 text-sm text-text-dim transition hover:text-text disabled:opacity-50"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={savingEdit}
                    className="border rounded-lg border-accent/30 bg-accent/10 px-5 py-2.5 text-sm font-medium text-accent transition hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingEdit ? "Saving changes..." : "Save changes"}
                  </button>
                </div>
              </form>
            ) : (
              <>
                <div className="space-y-6 px-5 py-6">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-text-dim">
                      Status
                    </p>
                    <p className="mt-2 text-sm text-accent">
                      {formatStatus(selectedProject.status)}
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-text-dim">
                      Description
                    </p>
                    <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-7 text-text/80">
                      {selectedProject.description ||
                        "This project has no description."}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-3 border-t border-ink-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-text-dim/70">
                    Project information is saved in your workspace.
                  </p>

                  <button
                    type="button"
                    onClick={() => deleteProject(selectedProject)}
                    disabled={deleting}
                    className="border rounded-lg border-rose-400/20 bg-rose-400/5 px-4 py-2.5 text-sm text-rose-300 transition hover:bg-rose-400/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Delete project"}
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
