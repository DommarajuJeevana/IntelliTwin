"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useApi } from "../../../lib/useApi";
import Card from "../../../components/ui/Card";
import Badge from "../../../components/ui/Badge";

const MODULES = [
  ["", "All"], ["goal", "Goals"], ["task", "Tasks"], ["calendar", "Calendar"], ["note", "Notes"],
  ["document", "Documents"], ["research", "Research"], ["project", "Projects"], ["memory", "Memory"],
];
const PAGE = 20;
const DEBOUNCE_MS = 350;

const titleOf = (r) => r.item.title || r.item.name || r.item.query || "Untitled";

export default function SearchPage() {
  const apiClient = useApi();
  const [q, setQ] = useState("");
  const [module, setModule] = useState("");
  const [results, setResults] = useState(null);
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const seq = useRef(0); // ignore responses from superseded queries

  const run = useCallback(async (query, mod, offset = 0) => {
    const mine = ++seq.current;
    setBusy(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: query, limit: String(PAGE), offset: String(offset) });
      if (mod) params.set("modules", mod);
      const data = await apiClient.get(`/search?${params}`);
      if (mine !== seq.current) return;
      setTotal(data.total ?? data.results.length);
      setResults((prev) => (offset ? [...(prev || []), ...data.results] : data.results));
    } catch (err) {
      if (mine === seq.current) setError(err.message || "Search failed.");
    } finally {
      if (mine === seq.current) setBusy(false);
    }
  }, [apiClient]);

  useEffect(() => {
    const query = q.trim();
    if (!query) { seq.current++; setResults(null); setBusy(false); setError(""); return; }
    const t = setTimeout(() => run(query, module, 0), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [q, module, run]);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-6 font-display text-2xl text-text">Search</h1>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search goals, tasks, events, notes, documents, research, projects, memory"
        aria-label="Search"
        className="mb-3 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text outline-none focus:border-accent"
      />
      <div className="mb-6 flex flex-wrap gap-2">
        {MODULES.map(([value, label]) => (
          <button key={value} onClick={() => setModule(value)}
            className={`rounded-full border px-3 py-1 text-xs ${module === value ? "border-accent text-accent" : "border-ink-600 text-text-dim"}`}>
            {label}
          </button>
        ))}
      </div>

      {busy && <p className="mb-3 text-sm text-text-dim">Searching…</p>}
      {error && <p className="mb-3 text-sm text-rose-400" role="alert">{error}</p>}
      {!results && !busy && !error && <p className="text-sm text-text-dim">Type to search across your workspace.</p>}

      {results && (
        <div className="space-y-3">
          {results.length === 0 && !busy && !error ? (
            <p className="text-sm text-text-dim">No matches for “{q.trim()}”.</p>
          ) : (
            results.map((r) => (
              <Link key={`${r.type}-${r.item._id}`} href={r.href} className="block">
                <Card className="flex items-start justify-between gap-3 hover:border-accent/40">
                  <div className="min-w-0">
                    <p className="truncate text-text">{titleOf(r)}</p>
                    {r.item.snippet ? <p className="mt-1 line-clamp-2 text-xs text-text-dim">{r.item.snippet}</p> : null}
                    {r.item.startsAt ? <p className="mt-1 text-xs text-text-dim">{new Date(r.item.startsAt).toLocaleString()}</p> : null}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    {r.match === "semantic" ? <Badge tone="dim">similar</Badge> : null}
                    <Badge tone="dim">{r.type}</Badge>
                  </div>
                </Card>
              </Link>
            ))
          )}
          {results.length < total && (
            <button onClick={() => run(q.trim(), module, results.length)} disabled={busy}
              className="text-sm text-accent hover:underline disabled:opacity-50">
              Load more ({total - results.length} more)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
