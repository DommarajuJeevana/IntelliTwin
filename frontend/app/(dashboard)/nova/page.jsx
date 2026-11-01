"use client";

import { useState } from "react";
import { useApi } from "../../../lib/useApi";
import AgentPageHeader from "../../../components/ui/AgentPageHeader";

function DocumentCard({ document }) {
  return (
    <article className="border rounded-xl border-ink-700 bg-ink-900/60">
      <div className="border-b border-ink-700 px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-agent-nova">
              Generated document
            </p>

            <h3 className="mt-2 text-base font-medium text-text">
              {document?.title || "Untitled document"}
            </h3>
          </div>

          <span className="shrink-0 border border-agent-nova/20 px-2 py-1 text-[10px] uppercase tracking-wider text-agent-nova">
            Draft
          </span>
        </div>
      </div>

      <div className="px-5 py-6">
        {document?.content ? (
          <div className="whitespace-pre-wrap text-sm leading-7 text-text-dim">
            {document.content}
          </div>
        ) : document?.body ? (
          <div className="whitespace-pre-wrap text-sm leading-7 text-text-dim">
            {document.body}
          </div>
        ) : (
          <p className="text-sm text-text-dim">
            Nova created the document, but no readable content was returned.
          </p>
        )}
      </div>
    </article>
  );
}

export default function NovaPage() {
  const apiClient = useApi();

  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");

  async function createDocument(e) {
    e.preventDefault();

    const cleanTitle = title.trim();
    const cleanBrief = brief.trim();

    if (!cleanTitle || !cleanBrief || busy) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const response = await apiClient.post("/agents/nova", {
        title: cleanTitle,
        brief: cleanBrief,
      });

      if (response?.document) {
        setDocuments((previous) => [
          response.document,
          ...previous,
        ]);
      }

      setTitle("");
      setBrief("");
    } catch (err) {
      setError(
        err?.message ||
          "Something went wrong while creating the document."
      );
    } finally {
      setBusy(false);
    }
  }

  function useExample(example) {
    setTitle(example.title);
    setBrief(example.brief);
  }

  const examples = [
    {
      title: "Project presentation",
      brief:
        "Create a clear presentation draft explaining the project problem, proposed solution, key features, technology stack, and expected outcome.",
    },
    {
      title: "Internship introduction",
      brief:
        "Create a concise professional introduction that explains my technical interests, strengths, academic background, and what I hope to learn from an internship.",
    },
    {
      title: "Project documentation",
      brief:
        "Create structured documentation for a software project covering its purpose, main features, architecture, workflow, and future improvements.",
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl">
      <AgentPageHeader
          agent="nova"
          title="Turn ideas into finished work."
          description="Nova uses your request and available workspace context to create structured documents and drafts."
        />

      <section className="mt-8">
        <div className="mb-5">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-text-dim">
            Create something
          </p>

          <h2 className="mt-2 text-lg font-medium text-text">
            What do you want Nova to create?
          </h2>
        </div>

        <form onSubmit={createDocument}>
          <div className="border rounded-xl border-ink-700 bg-ink-900/70">
            <div className="border-b border-ink-700 px-5 py-4">
              <label className="block text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
                Title
              </label>

              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="For example: Final-year project presentation"
                disabled={busy}
                className="mt-3 w-full bg-transparent text-sm text-text outline-none placeholder:text-text-dim/60 disabled:opacity-60"
              />
            </div>

            <div className="px-5 py-5">
              <label className="block text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
                Brief
              </label>

              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="Describe what you want Nova to create, the information it should cover, and the kind of result you need."
                rows={7}
                disabled={busy}
                className="mt-3 w-full resize-none bg-transparent text-sm leading-6 text-text outline-none placeholder:text-text-dim/60 disabled:opacity-60"
              />
            </div>

            <div className="flex flex-col gap-3 border-t border-ink-700 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs text-text-dim">
                Nova will create a structured draft from your brief.
              </p>

              <button
                type="submit"
                disabled={!title.trim() || !brief.trim() || busy}
                className="border rounded-lg border-agent-nova/30 bg-agent-nova/10 px-5 py-2.5 text-xs font-medium text-agent-nova transition hover:border-agent-nova/50 hover:bg-agent-nova/15 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Creating..." : "Create draft"}
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

      <section className="mt-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
          Start with an example
        </p>

        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {examples.map((example) => (
            <button
              key={example.title}
              type="button"
              onClick={() => useExample(example)}
              className="border border-ink-700 px-4 py-4 text-left transition hover:border-agent-nova/30"
            >
              <p className="text-sm font-medium text-text">
                {example.title}
              </p>

              <p className="mt-2 text-xs leading-5 text-text-dim">
                {example.brief}
              </p>
            </button>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <div className="flex items-end justify-between gap-4 border-b border-ink-700 pb-4">
          <div>
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
              Creation activity
            </p>

            <h2 className="mt-2 text-lg font-medium text-text">
              Drafts created in this session
            </h2>
          </div>

          {documents.length > 0 && (
            <span className="text-xs text-text-dim">
              {documents.length}{" "}
              {documents.length === 1 ? "draft" : "drafts"}
            </span>
          )}
        </div>

        {documents.length === 0 ? (
          <div className="mt-6 border border-dashed border-ink-700 px-6 py-10">
            <p className="text-sm text-text-dim">
              No drafts created from this session yet.
            </p>

            <p className="mt-2 max-w-xl text-xs leading-5 text-text-dim/70">
              Give Nova a title and a brief. Your generated document will
              appear here.
            </p>
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {documents.map((document, index) => (
              <DocumentCard
                key={
                  document?._id ||
                  document?.id ||
                  `document-${index}`
                }
                document={document}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mt-12 border-t border-ink-700 pt-8">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-text-dim">
          How Nova works
        </p>

        <div className="mt-5 grid gap-px border rounded-lg overflow-hidden border-ink-700 bg-ink-700 sm:grid-cols-3">
          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-nova">
              01 / Brief
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Tell Nova what you need and provide the important context.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-nova">
              02 / Context
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              Nova can use relevant information already available in the
              IntelliTwin workspace.
            </p>
          </div>

          <div className="bg-ink-950 px-5 py-5">
            <p className="text-xs font-medium text-agent-nova">
              03 / Draft
            </p>

            <p className="mt-2 text-sm leading-6 text-text-dim">
              The result is returned as a structured document that can be
              refined later.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}