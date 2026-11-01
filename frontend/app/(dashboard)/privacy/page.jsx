"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "../../../lib/useApi";
import { useAuth } from "../../../context/AuthContext";
import Card from "../../../components/ui/Card";
import Button from "../../../components/ui/Button";
import Badge from "../../../components/ui/Badge";

const MODULE_LINKS = {
  goals: "/goals",
  tasks: "/tasks",
  calendarEvents: "/calendar",
  notes: "/notes",
  documents: "/documents",
  research: "/research",
  projects: "/projects",
  memory: "/memory-timeline",
  milestones: "/dashboard",
  agentMessages: "/collaboration",
  profile: "/profile",
};

export default function PrivacyPage() {
  const apiClient = useApi();
  const { token, logout } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  const [confirmText, setConfirmText] = useState("");
  const [wiping, setWiping] = useState(false);
  const [wiped, setWiped] = useState(false);

  useEffect(() => {
    apiClient
      .get("/privacy/overview")
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  async function handleExport() {
    setExporting(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api";
      const res = await fetch(`${base}/privacy/export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "intellitwin-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  }

  async function confirmWipe() {
    setWiping(true);
    setError("");
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000/api";
      const res = await fetch(`${base}/privacy/wipe`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ confirm: confirmText }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Failed to delete data.");
      setWiped(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setWiping(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h1 className="font-display text-2xl text-text">What your twin knows</h1>
        <p className="mt-1 text-sm text-text-dim">
          Everything stored about you, in one place — nothing here is inferred or hidden.
        </p>
      </div>

      {error ? <p className="mb-4 text-sm text-rose-400">{error}</p> : null}

      {data?.agentsView ? (
        <Card className="mb-6">
          <p className="text-sm font-medium text-text">What the agents actually read</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-text-dim">
            {data.agentsView.summary || "Your profile is empty — agents currently have no personal context to work from."}
          </p>
          <p className="mt-3 text-xs text-text-dim">
            Used by: {data.agentsView.used_by.join(", ")}. {data.agentsView.note}
          </p>
          <Link href="/profile" className="mt-2 inline-block text-xs text-accent hover:underline">
            Edit your profile →
          </Link>
        </Card>
      ) : null}

      <div className="mb-6 space-y-3">
        {(data?.modules || []).map((m) => (
          <Card key={m.key} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text">{m.label}</p>
              {m.sample?.length ? (
                <p className="mt-1 text-xs text-text-dim">
                  e.g. {m.sample.map((s) => `"${s.label}"`).join(", ")}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-3">
              {m.count !== null ? <Badge tone="dim">{m.count}</Badge> : null}
              <Link href={MODULE_LINKS[m.key] || "/dashboard"} className="text-xs text-accent hover:underline">
                View
              </Link>
            </div>
          </Card>
        ))}
      </div>

      <Card className="mb-6">
        <p className="text-sm font-medium text-text">Export everything</p>
        <p className="mt-1 text-sm text-text-dim">Download a full JSON copy of everything listed above.</p>
        <Button variant="subtle" className="mt-3" onClick={handleExport} disabled={exporting}>
          {exporting ? "Preparing…" : "Download my data"}
        </Button>
      </Card>

      <Card className="border-rose-500/30">
        <p className="text-sm font-medium text-text">Delete everything</p>
        <p className="mt-1 text-sm text-text-dim">
          Permanently deletes every goal, task, note, document, research item, memory, milestone, and
          collaboration log. Your login and profile stay intact. This cannot be undone.
        </p>

        {wiped ? (
          <p className="mt-3 text-sm text-accent">Done — everything has been deleted.</p>
        ) : (
          <div className="mt-3 space-y-2">
            <label className="block text-xs text-text-dim">
              Type <span className="font-mono text-text">DELETE</span> to confirm
            </label>
            <input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="w-full max-w-xs rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text outline-none focus:border-rose-400"
            />
            <div>
              <button
                onClick={confirmWipe}
                disabled={confirmText !== "DELETE" || wiping}
                className="rounded-lg border border-rose-500/50 px-4 py-2 text-sm text-rose-400 transition-colors hover:bg-rose-500/10 disabled:opacity-40"
              >
                {wiping ? "Deleting…" : "Delete everything"}
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
