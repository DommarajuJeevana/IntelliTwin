"use client";
import { useEffect, useState } from "react";
import { useApi } from "../../lib/useApi";
import Card from "./Card";
import Button from "./Button";
import Badge from "./Badge";
import EmptyState from "./EmptyState";

/**
 * Generic module screen: fetches a list from `endpoint`, renders each item
 * through `renderItem`, and creates new ones via `fields` + `endpoint`.
 * Every "future module" from the spec (goals, tasks, notes, documents,
 * research, projects, memory) is just this component with a
 * different config - see app/(dashboard)/<module>/page.jsx for examples.
 */
export default function ModulePage({ title, description, endpoint, fields, renderItem, agentBadge }) {
  const apiClient = useApi();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(() => Object.fromEntries(fields.map((f) => [f.name, f.default || ""])));
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiClient.get(endpoint);
      setItems(data.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoint]);

  async function handleCreate(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await apiClient.post(endpoint, form);
      setForm(Object.fromEntries(fields.map((f) => [f.name, f.default || ""])));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl text-text">{title}</h1>
          {description ? <p className="mt-1 text-sm text-text-dim">{description}</p> : null}
        </div>
        {agentBadge ? <Badge>{agentBadge}</Badge> : null}
      </div>

      <Card className="mb-6">
        <form onSubmit={handleCreate} className="grid gap-3 sm:grid-cols-2">
          {fields.map((f) => (
            <div key={f.name} className={f.wide ? "sm:col-span-2" : ""}>
              <label className="mb-1 block text-xs font-medium text-text-dim">{f.label}</label>
              {f.type === "textarea" ? (
                <textarea
                  value={form[f.name]}
                  onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
                  rows={3}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text outline-none focus:border-cyan-400"
                />
              ) : (
                <input
                  type={f.type || "text"}
                  required={f.required}
                  value={form[f.name]}
                  onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text outline-none focus:border-cyan-400"
                />
              )}
            </div>
          ))}
          <div className="sm:col-span-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : `Add to ${title}`}
            </Button>
          </div>
        </form>
      </Card>

      {error ? <p className="mb-4 text-sm text-rose-400">{error}</p> : null}

      {loading ? (
        <p className="text-sm text-text-dim">Loading…</p>
      ) : items.length === 0 ? (
        <EmptyState title={`No ${title.toLowerCase()} yet`} hint="Add your first one above." />
      ) : (
        <div className="space-y-3">{items.map((item) => renderItem(item))}</div>
      )}
    </div>
  );
}
