"use client";

import { useCallback, useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { useApi } from "@/lib/useApi";
import { AGENT_LIST } from "@/lib/agents";
import { formatTime } from "@/lib/format";

const AGENT_NAMES = Object.fromEntries(AGENT_LIST.map((a) => [a.id, a.name]));

// "YYYY-MM-DD" is a calendar day, not a moment: build it in local time.
function parseDay(iso) {
  const [y, m, d] = String(iso).split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function dayLabel(iso) {
  const day = parseDay(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - day) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return day.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: day.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

function agentSummary(agents = []) {
  const names = agents.map((id) => AGENT_NAMES[id] || id).filter(Boolean);
  return names.length ? `Worked with ${names.join(", ")}` : null;
}

export default function ChatHistoryPage() {
  const apiClient = useApi();

  const [days, setDays] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingDays, setLoadingDays] = useState(true);
  const [loadingDay, setLoadingDay] = useState(false);
  const [error, setError] = useState("");

  const loadDays = useCallback(
    async (q) => {
      setLoadingDays(true);
      setError("");
      try {
        const params = q ? `?q=${encodeURIComponent(q)}` : "";
        const response = await apiClient.get(`/chat-history${params}`);
        const list = Array.isArray(response?.days) ? response.days : [];
        setDays(list);
        setTotal(response?.total || 0);
        setSelected((current) =>
          current && list.some((d) => d.date === current) ? current : list[0]?.date || null
        );
      } catch (err) {
        setError(err?.message || "Unable to load chat history.");
      } finally {
        setLoadingDays(false);
      }
    },
    [apiClient]
  );

  // Debounced so typing in the search box doesn't fire a request per key.
  useEffect(() => {
    const timer = setTimeout(() => loadDays(query.trim()), query ? 300 : 0);
    return () => clearTimeout(timer);
  }, [query, loadDays]);

  useEffect(() => {
    if (!selected) {
      setMessages([]);
      return undefined;
    }
    let cancelled = false;
    setLoadingDay(true);
    apiClient
      .get(`/chat-history/${selected}`)
      .then((response) => {
        if (!cancelled) setMessages(Array.isArray(response?.messages) ? response.messages : []);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || "Unable to load this day's chats.");
      })
      .finally(() => {
        if (!cancelled) setLoadingDay(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected, apiClient]);

  const needle = query.trim().toLowerCase();

  return (
    <div className="w-full">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-accent">
              Mission Control / Archive
            </p>
            <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight text-text sm:text-3xl">
              Chat History
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-dim">
              Every conversation you&apos;ve had with IntelliTwin, kept by day. Mission
              Control on the dashboard shows only today&apos;s chat; the rest lives here.
            </p>
          </div>
          <p className="self-start text-xs text-text-dim sm:self-auto">
            {total} {total === 1 ? "message" : "messages"} across {days.length}{" "}
            {days.length === 1 ? "day" : "days"}
            {needle ? " matching your search" : ""}
          </p>
        </header>

        {error && (
          <div
            role="alert"
            className="mb-6 flex flex-col justify-between gap-3 rounded-lg border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3 sm:flex-row sm:items-center"
          >
            <p className="text-sm text-rose-300">{error}</p>
            <button
              type="button"
              onClick={() => loadDays(query.trim())}
              className="self-start text-sm text-rose-200 underline underline-offset-4 hover:text-text sm:self-auto"
            >
              Try again
            </button>
          </div>
        )}

        <div className="mb-6 rounded-xl border border-ink-700 bg-ink-900/70 p-4 sm:p-5">
          <label
            htmlFor="chat-search"
            className="mb-2 block text-xs font-medium uppercase tracking-[0.12em] text-text-dim"
          >
            Search chats
          </label>
          <input
            id="chat-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search everything you and IntelliTwin have said..."
            className="w-full rounded-lg border border-ink-700 bg-ink-950/70 px-4 py-3 text-sm text-text outline-none placeholder:text-text-dim/70 focus:border-accent"
          />
        </div>

        {loadingDays ? (
          <div className="rounded-xl border border-ink-700 bg-ink-900/70 px-5 py-12 text-center">
            <div className="mx-auto mb-4 h-5 w-5 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
            <p className="text-sm text-text-dim">Loading chat history...</p>
          </div>
        ) : days.length === 0 ? (
          <div className="rounded-xl border border-dashed border-ink-700 bg-ink-900/70 px-5 py-16 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg border border-ink-700 bg-white/[0.03] text-text-dim">
              <MessagesSquare className="h-5 w-5" strokeWidth={1.75} />
            </div>
            <h2 className="mt-5 text-base font-medium text-text">
              {needle ? "No matching chats" : "No chats yet"}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-text-dim">
              {needle
                ? "Try another search term."
                : "Conversations from Mission Control will be stored here."}
            </p>
          </div>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
            {/* DAYS */}
            <nav aria-label="Days with chats" className="min-w-0">
              <ul className="max-h-[420px] space-y-2 overflow-y-auto overscroll-contain lg:max-h-[640px]">
                {days.map((day) => {
                  const active = day.date === selected;
                  return (
                    <li key={day.date}>
                      <button
                        type="button"
                        onClick={() => setSelected(day.date)}
                        aria-current={active ? "true" : undefined}
                        className={`w-full rounded-xl border p-4 text-left transition-colors ${
                          active
                            ? "border-accent/40 bg-accent/[0.06]"
                            : "border-ink-700 bg-ink-900/70 hover:border-ink-500"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-sm font-medium text-text">
                            {dayLabel(day.date)}
                          </span>
                          <span className="text-[11px] tabular-nums text-text-dim">
                            {day.count} {day.count === 1 ? "message" : "messages"}
                          </span>
                        </div>
                        {day.preview ? (
                          <p className="mt-1.5 line-clamp-2 break-words text-xs leading-5 text-text-dim">
                            {day.preview}
                          </p>
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </nav>

            {/* TRANSCRIPT */}
            <section
              aria-label="Conversation"
              className="min-w-0 rounded-xl border border-ink-700 bg-ink-900/70"
            >
              <div className="flex items-center justify-between border-b border-ink-700 px-5 py-4">
                <h2 className="font-display text-sm font-semibold text-text">
                  {selected ? dayLabel(selected) : ""}
                </h2>
                {selected ? (
                  <span className="text-xs text-text-dim">
                    {parseDay(selected).toLocaleDateString(undefined, {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </span>
                ) : null}
              </div>

              <div className="max-h-[560px] overflow-y-auto overscroll-contain px-4 py-5 lg:max-h-[580px]">
                {loadingDay ? (
                  <p className="text-xs text-text-dim">Loading conversation…</p>
                ) : (
                  <div className="space-y-4">
                    {messages.map((message, index) => {
                      const isUser = message.role === "user";
                      const summary = agentSummary(message.agents);
                      const hit =
                        needle && String(message.content || "").toLowerCase().includes(needle);
                      return (
                        <div
                          key={message._id || index}
                          className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[88%] px-3.5 py-2.5 ${
                              isUser
                                ? "rounded-2xl rounded-br-md bg-ink-700"
                                : "rounded-2xl rounded-bl-md border border-ink-700 bg-ink-800/80"
                            } ${hit ? "ring-1 ring-accent/60" : ""}`}
                          >
                            {!isUser ? (
                              <div className="mb-2 flex flex-wrap items-center gap-2">
                                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                                <span className="text-[10px] font-medium uppercase tracking-wider text-text-dim">
                                  IntelliTwin
                                </span>
                                {summary ? (
                                  <>
                                    <span className="text-[10px] text-text-dim/50">·</span>
                                    <span className="text-[10px] text-text-dim">{summary}</span>
                                  </>
                                ) : null}
                              </div>
                            ) : null}
                            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-text">
                              {message.content}
                            </p>
                            <p className="mt-2 text-[10px] text-text-dim/70">
                              {formatTime(message.createdAt)}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
