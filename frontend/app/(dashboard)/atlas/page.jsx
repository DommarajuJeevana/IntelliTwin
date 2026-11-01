"use client";

import { useState } from "react";
import { useApi } from "@/lib/useApi";
import AgentPageHeader from "@/components/ui/AgentPageHeader";

const suggestions = [
  "What are the latest developments in cloud computing?",
  "Compare machine learning and deep learning",
  "How is AI changing software development?",
];

function getSummary(item) {
  if (!item) return "";

  return (
    item.summary ||
    item.content ||
    item.answer ||
    item.description ||
    ""
  );
}

function getTitle(item, fallback) {
  if (!item) return fallback;

  return item.title || item.query || fallback;
}

function SourceList({ sources }) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-ink-700 px-5 py-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim">
          Sources
        </p>

        <span className="text-[10px] text-text-dim/70">
          {sources.length}
        </span>
      </div>

      <div className="space-y-2">
        {sources.map((source, index) => {
          const url =
            typeof source === "string"
              ? source
              : source?.url;

          const title =
            typeof source === "string"
              ? source
              : source?.title ||
                source?.url ||
                `Source ${index + 1}`;

          if (!url) {
            return (
              <div
                key={index}
                className="text-xs text-text-dim"
              >
                {title}
              </div>
            );
          }

          return (
            <a
              key={`${url}-${index}`}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="
                group
                flex
                items-start
                gap-3
                border rounded-lg
                border-ink-700
                bg-white/[0.015]
                px-3
                py-2.5
                transition
                hover:border-agent-atlas/30
                hover:bg-agent-atlas/[0.03]
              "
            >
              <span className="mt-0.5 text-[10px] font-semibold text-agent-atlas">
                {String(index + 1).padStart(2, "0")}
              </span>

              <span className="min-w-0 text-xs leading-5 text-text-dim group-hover:text-text">
                {title}
              </span>
            </a>
          );
        })}
      </div>
    </div>
  );
}

function ResearchResult({ result }) {
  const item = result.item;
  const summary = getSummary(item);

  return (
    <article className="border rounded-xl border-ink-700 bg-ink-900/70">
      <div className="border-b border-ink-700 px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-agent-atlas">
              Research result
            </p>

            <h2 className="mt-1 text-lg font-medium tracking-tight text-text">
              {getTitle(item, result.query)}
            </h2>
          </div>

          <span className="hidden text-[10px] uppercase tracking-[0.2em] text-text-dim/70 sm:block">
            ATLAS
          </span>
        </div>
      </div>

      <div className="px-5 py-5">
        {summary ? (
          <div className="whitespace-pre-wrap text-sm leading-7 text-text/80">
            {summary}
          </div>
        ) : (
          <pre className="whitespace-pre-wrap break-words text-xs leading-6 text-text-dim">
            {JSON.stringify(item, null, 2)}
          </pre>
        )}
      </div>

      <SourceList sources={item?.sources} />

      {result.explanation && (
        <div className="border-t border-ink-700 bg-white/[0.015] px-5 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim">
            Atlas note
          </p>

          <p className="mt-2 text-xs leading-6 text-text-dim">
            {typeof result.explanation === "string"
              ? result.explanation
              : result.explanation?.summary ||
                result.explanation?.message ||
                ""}
          </p>
        </div>
      )}
    </article>
  );
}

export default function AtlasPage() {
  const apiClient = useApi();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function research(value = query) {
    const cleanQuery = value.trim();

    if (!cleanQuery || busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/agents/atlas", {
        query: cleanQuery,
      });

      setResults((current) => [
        {
          query: cleanQuery,
          item: response?.item,
          explanation: response?.explanation,
        },
        ...current,
      ]);

      setQuery("");
    } catch (err) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Atlas could not complete the research request."
      );
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      research();
    }
  }

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">

      <AgentPageHeader
          agent="atlas"
          title="Research workspace"
          description="Investigate questions, connect relevant context, and turn findings into useful research."
          aside={
            <div className="hidden rounded-lg border border-ink-700 bg-ink-800/60 px-3 py-2 sm:block">
              <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">Status</p>
              <div className="mt-1.5 flex items-center gap-2" role="status">
                <span className={`h-1.5 w-1.5 rounded-full ${busy ? "animate-pulse bg-agent-atlas" : "bg-emerald-400"}`} />
                <span className="text-[11px] text-text-dim">{busy ? "Researching" : "Ready"}</span>
              </div>
            </div>
          }
        />

        {/* Workspace */}
        <section className="mt-7 grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">

          {/* Left control panel */}
          <aside className="h-fit border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim">
                  Research query
                </p>

                <span className="text-[10px] uppercase tracking-[0.16em] text-ink-500">
                  ATLAS / 01
                </span>
              </div>

              <p className="mt-2 text-xs leading-5 text-text-dim">
                Give Atlas a question or topic to investigate.
              </p>
            </div>

            <div className="p-5">
              <textarea
                value={query}
                onChange={(event) =>
                  setQuery(event.target.value)
                }
                onKeyDown={handleKeyDown}
                disabled={busy}
                rows={7}
                placeholder="What should Atlas investigate?"
                className="
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
                  focus:border-agent-atlas
                  disabled:opacity-50
                "
              />

              <button
                type="button"
                onClick={() => research()}
                disabled={!query.trim() || busy}
                className="
                  mt-3
                  flex
                  h-10
                  w-full
                  items-center
                  justify-center
                  gap-2
                  border rounded-lg
                  border-agent-atlas/20
                  bg-agent-atlas/[0.08]
                  px-4
                  text-xs
                  font-medium
                  text-agent-atlas
                  transition
                  hover:border-agent-atlas/40
                  hover:bg-agent-atlas/[0.12]
                  disabled:cursor-not-allowed
                  disabled:border-ink-700
                  disabled:bg-white/[0.03]
                  disabled:text-text-dim/70
                "
              >
                {busy ? (
                  <>
                    <span className="h-3 w-3 animate-spin rounded-full border border-agent-atlas/30 border-t-agent-atlas" />
                    Researching
                  </>
                ) : (
                  <>
                    Research
                    <span>→</span>
                  </>
                )}
              </button>

              <p className="mt-3 text-[10px] leading-5 text-text-dim/70">
                Enter to research · Shift + Enter for a new line
              </p>

              {error && (
                <div className="mt-4 border rounded-lg border-rose-400/20 bg-rose-400/[0.05] px-3 py-3 text-xs leading-5 text-rose-300">
                  {error}
                </div>
              )}
            </div>

            {/* Suggestions */}
            <div className="border-t border-ink-700">
              <div className="px-5 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim/70">
                  Suggested investigations
                </p>
              </div>

              <div className="border-t border-ink-700">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => research(suggestion)}
                    disabled={busy}
                    className="
                      flex
                      w-full
                      items-start
                      gap-3
                      border-b
                      border-ink-700
                      px-5
                      py-3.5
                      text-left
                      transition
                      last:border-b-0
                      hover:bg-white/[0.025]
                      disabled:cursor-not-allowed
                      disabled:opacity-40
                    "
                  >
                    <span className="pt-0.5 text-[10px] font-semibold text-agent-atlas">
                      0{index + 1}
                    </span>

                    <span className="text-xs leading-5 text-text-dim">
                      {suggestion}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          {/* Findings */}
          <section className="min-w-0">
            <div className="mb-4 flex items-end justify-between">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-dim/70">
                  Workspace
                </p>

                <h2 className="mt-1 text-lg font-medium text-text">
                  Research findings
                </h2>
              </div>

              {results.length > 0 && (
                <span className="text-[10px] text-text-dim/70">
                  {results.length}{" "}
                  {results.length === 1
                    ? "investigation"
                    : "investigations"}
                </span>
              )}
            </div>

            {results.length === 0 ? (
              <div className="flex min-h-[430px] flex-col items-center justify-center border rounded-xl border-dashed border-ink-700 bg-ink-900/70 px-8 text-center">
                <div
                  className="
                    flex
                    h-12
                    w-12
                    items-center
                    justify-center
                    border rounded-lg
                    border-agent-atlas/20
                    bg-agent-atlas/[0.04]
                    text-sm
                    font-semibold
                    text-agent-atlas
                  "
                >
                  A
                </div>

                <p className="mt-5 text-sm font-medium text-text/80">
                  Research workspace ready
                </p>

                <p className="mt-2 max-w-sm text-xs leading-6 text-text-dim/70">
                  Your findings will appear here after Atlas
                  investigates your first question.
                </p>

                <div className="mt-6 flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-ink-500">
                  <span>Question</span>
                  <span>→</span>
                  <span>Research</span>
                  <span>→</span>
                  <span>Findings</span>
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                {results.map((result, index) => (
                  <div key={`${result.query}-${index}`}>
                    <div className="mb-2 flex items-center gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
                        Investigation{" "}
                        {String(results.length - index).padStart(2, "0")}
                      </span>

                      <span className="h-px flex-1 bg-white/[0.06]" />
                    </div>

                    <div className="mb-3 border-l-2 border-agent-atlas/50 bg-ink-900/70 px-4 py-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-dim/70">
                        Question
                      </p>

                      <p className="mt-1 text-sm leading-6 text-text-dim">
                        {result.query}
                      </p>
                    </div>

                    <ResearchResult result={result} />
                  </div>
                ))}
              </div>
            )}
          </section>
        </section>
      </div>
    </div>
  );
}