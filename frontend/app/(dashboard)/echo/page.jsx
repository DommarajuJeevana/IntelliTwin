"use client";

import { useState } from "react";
import { useApi } from "../../../lib/useApi";
import AgentPageHeader from "../../../components/ui/AgentPageHeader";

function MemoryCard({ entry }) {
  if (!entry) {
    return null;
  }

  return (
    <article className="border rounded-xl border-ink-700 bg-ink-900/60 px-5 py-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-agent-echo">
            Memory saved
          </p>

          <h3 className="mt-2 text-base font-medium text-text">
            {entry.title || "Untitled memory"}
          </h3>
        </div>

        <span className="shrink-0 border border-agent-echo/20 px-2 py-1 text-[10px] uppercase tracking-wider text-agent-echo">
          Active
        </span>
      </div>

      {entry.content && (
        <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-text-dim">
          {entry.content}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-ink-700 pt-4 text-[11px] text-text-dim">
        {entry.confidence !== undefined && (
          <span>
            Confidence{" "}
            <strong className="font-medium text-text">
              {Math.round(Number(entry.confidence) * 100)}%
            </strong>
          </span>
        )}

        {entry.source && (
          <span>
            Source{" "}
            <strong className="font-medium text-text">
              {entry.source}
            </strong>
          </span>
        )}

        {entry.status && (
          <span>
            Status{" "}
            <strong className="font-medium text-text">
              {entry.status}
            </strong>
          </span>
        )}
      </div>
    </article>
  );
}

export default function EchoPage() {
  const apiClient = useApi();

  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [memories, setMemories] = useState([]);
  const [error, setError] = useState("");

  async function remember(e) {
    e.preventDefault();

    const value = note.trim();

    if (!value || busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/agents/echo", {
        note: value,
      });

      if (response?.entry) {
        setMemories((previous) => [
          response.entry,
          ...previous,
        ]);
      }

      setNote("");
    } catch (err) {
      setError(
        err?.message ||
          "Something went wrong while saving the memory."
      );
    } finally {
      setBusy(false);
    }
  }

  function useSuggestion(text) {
    setNote(text);
  }

  return (
    <div className="mx-auto w-full max-w-5xl">
      <AgentPageHeader
          agent="echo"
          title="Your persistent memory layer."
          description="Echo keeps useful information about you so IntelliTwin can use relevant context over time."
        />

      {/* REMEMBER */}
      <section className="mt-8">
        <div className="mb-4">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-text-dim">
            Remember
          </p>

          <h2 className="mt-2 text-lg font-medium text-text">
            Tell Echo something worth keeping.
          </h2>
        </div>

        <form onSubmit={remember}>
          <div className="border rounded-xl border-ink-700 bg-ink-900/70">
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="For example: I prefer concise technical explanations."
              rows={6}
              disabled={busy}
              className="w-full resize-none bg-transparent px-5 py-5 text-sm leading-6 text-text outline-none placeholder:text-text-dim/60 disabled:opacity-60"
            />

            <div className="flex flex-col gap-3 border-t border-ink-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-text-dim">
                Explicit memories are saved through Echo's memory system.
              </p>

              <button
                type="submit"
                disabled={!note.trim() || busy}
                className="border rounded-lg border-agent-echo/30 bg-agent-echo/10 px-5 py-2.5 text-xs font-medium text-agent-echo transition hover:border-agent-echo/50 hover:bg-agent-echo/15 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Remembering..." : "Remember"}
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
          Try Echo with
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {[
            "I prefer concise explanations.",
            "My current focus is building IntelliTwin.",
            "I usually want examples with technical explanations.",
          ].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => useSuggestion(suggestion)}
              className="border border-ink-700 px-3 py-2 text-xs text-text-dim transition hover:border-agent-echo/30 hover:text-text"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      {/* RECENT MEMORIES */}
      <section className="mt-12">
        <div className="flex items-end justify-between gap-4 border-b border-ink-700 pb-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
              Session activity
            </p>

            <h2 className="mt-2 text-lg font-medium text-text">
              Memories saved in this session
            </h2>
          </div>

          {memories.length > 0 && (
            <span className="text-xs text-text-dim">
              {memories.length}{" "}
              {memories.length === 1 ? "memory" : "memories"}
            </span>
          )}
        </div>

        {memories.length === 0 ? (
          <div className="mt-6 border border-dashed border-ink-700 px-6 py-10">
            <p className="text-sm text-text-dim">
              No memories saved from this session yet.
            </p>

            <p className="mt-2 max-w-xl text-xs leading-5 text-text-dim/70">
              When you explicitly tell Echo something worth remembering,
              the saved memory will appear here.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-3">
            {memories.map((entry, index) => (
              <MemoryCard
                key={
                  entry._id ||
                  entry.id ||
                  `${entry.title}-${index}`
                }
                entry={entry}
              />
            ))}
          </div>
        )}
      </section>

      {/* HOW ECHO WORKS */}
      <section className="mt-12 border-t border-ink-700 pt-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
          How Echo works
        </p>

        <div className="mt-5 grid gap-px border rounded-lg overflow-hidden border-ink-700 bg-ink-700 sm:grid-cols-3">
          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-echo">
              01 / Store
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Useful information becomes a structured memory entry.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-echo">
              02 / Understand
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Memory text can be represented as an embedding for semantic
              retrieval.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-echo">
              03 / Recall
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Relevant memories can later provide context to IntelliTwin's
              agents.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}