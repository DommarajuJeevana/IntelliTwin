"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "../../lib/useApi";
import { buildWorkspaceIndex } from "../../lib/workspaceContext";

// Every source is an existing endpoint. Each loads independently, so one
// failing module shows its own error state instead of blanking the dashboard.
const SOURCES = {
  summary: { path: "/dashboard/summary", pick: (d) => d || {} },
  suggestions: { path: "/suggestions", pick: (d) => d?.suggestions || [] },
  // Cached Compass AI suggestions. This read never triggers the model.
  ai: { path: "/suggestions/ai", pick: (d) => d || { status: "none", suggestions: [] } },
  goals: { path: "/goals", pick: (d) => d?.items || [] },
  tasks: { path: "/tasks", pick: (d) => d?.items || [] },
  projects: { path: "/projects", pick: (d) => d?.items || [] },
  calendar: { path: "/calendar", pick: (d) => d?.items || [] },
  notes: { path: "/notes", pick: (d) => d?.items || [] },
  documents: { path: "/documents", pick: (d) => d?.items || [] },
  research: { path: "/research", pick: (d) => d?.items || [] },
};

const KEYS = Object.keys(SOURCES);
const loading = () => ({ status: "loading", data: null, error: "" });

function classify(err) {
  const status = err?.status;
  return {
    status: status === 404 || status === 501 ? "unavailable" : "error",
    data: null,
    error: err?.message || "Couldn't load this section.",
  };
}

export function useDashboardData() {
  const api = useApi();
  const alive = useRef(true);
  const [state, setState] = useState(() => Object.fromEntries(KEYS.map((k) => [k, loading()])));

  const load = useCallback(
    async (keys = KEYS) => {
      setState((s) => ({ ...s, ...Object.fromEntries(keys.map((k) => [k, loading()])) }));
      const results = await Promise.allSettled(keys.map((k) => api.get(SOURCES[k].path)));
      if (!alive.current) return;
      setState((s) => {
        const next = { ...s };
        results.forEach((r, i) => {
          const key = keys[i];
          next[key] =
            r.status === "fulfilled"
              ? { status: "ready", data: SOURCES[key].pick(r.value), error: "" }
              : classify(r.reason);
        });
        return next;
      });
    },
    [api]
  );

  useEffect(() => {
    alive.current = true;
    load();
    return () => {
      alive.current = false;
    };
  }, [load]);

  const reload = useCallback((key) => load([key]), [load]);

  // Generating can take a while with a local model, so it runs in the background
  // and the rest of the panel stays usable. The server reuses its cache when
  // nothing changed, so this is cheap unless `force` is set.
  const [aiRefreshing, setAiRefreshing] = useState(false);
  const aiInFlight = useRef(false);
  const aiAutoTried = useRef(false);

  const refreshAi = useCallback(
    async ({ force = false } = {}) => {
      if (aiInFlight.current) return;
      aiInFlight.current = true;
      setAiRefreshing(true);
      try {
        const data = await api.post("/suggestions/ai/refresh", { force });
        if (alive.current) setState((s) => ({ ...s, ai: { status: "ready", data, error: "" } }));
      } catch (err) {
        if (alive.current) {
          setState((s) => ({
            ...s,
            ai: {
              status: "ready",
              data: {
                status: "unavailable",
                suggestions: [],
                message: err?.message || "AI suggestions couldn't be generated.",
              },
              error: "",
            },
          }));
        }
      } finally {
        aiInFlight.current = false;
        if (alive.current) setAiRefreshing(false);
      }
    },
    [api]
  );

  // Once per page load: if there's nothing cached, or the cache predates a data
  // change, ask for a refresh. A recent failure reports "unavailable" instead,
  // so a model that is offline is not hit on every visit.
  useEffect(() => {
    if (aiAutoTried.current || state.ai.status !== "ready") return;
    const ai = state.ai.data;
    if (ai && (ai.status === "none" || (ai.status === "ready" && ai.stale))) {
      aiAutoTried.current = true;
      refreshAi();
    }
  }, [state.ai, refreshAi]);

  const dismissSuggestion = useCallback(
    async (key) => {
      // Optimistic: hide now, restore from the server if the write fails.
      setState((s) => {
        const next = { ...s };
        if (s.suggestions.status === "ready") {
          next.suggestions = { ...s.suggestions, data: s.suggestions.data.filter((x) => x.key !== key) };
        }
        if (s.ai.status === "ready" && s.ai.data?.suggestions) {
          next.ai = {
            ...s.ai,
            data: { ...s.ai.data, suggestions: s.ai.data.suggestions.filter((x) => x.key !== key) },
          };
        }
        return next;
      });
      try {
        await api.post("/suggestions/dismiss", { key, days: 7 });
      } catch {
        load(["suggestions", "ai"]);
      }
    },
    [api, load]
  );

  const index = useMemo(
    () =>
      buildWorkspaceIndex({
        goals: state.goals.data || [],
        tasks: state.tasks.data || [],
        research: state.research.data || [],
      }),
    [state.goals.data, state.tasks.data, state.research.data]
  );

  return { state, reload, dismissSuggestion, index, aiRefreshing, refreshAi };
}
