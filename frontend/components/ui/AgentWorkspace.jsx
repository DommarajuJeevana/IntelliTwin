"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkles, ArrowUp } from "lucide-react";
import { useApi } from "../../lib/useApi";
import { AGENT_LIST } from "../../lib/agents";

const AGENT_META = Object.fromEntries(
  AGENT_LIST.map((agent) => [
    agent.id,
    { name: agent.name, role: agent.role, dot: agent.dot, icon: agent.icon, text: agent.text },
  ])
);

const DEFAULT_SUGGESTIONS = [
  "What should I focus on next?",
  "Help me organize my current priorities.",
  "Review what I've been working on and suggest next steps.",
];

const DEFAULT_THREAD = "mission-control";

function normalizeMessage(message, index = 0) {
  return {
    id:
      message?._id ||
      message?.id ||
      `${message?.role || "message"}-${index}-${Date.now()}`,
    role: message?.role || "assistant",
    content: message?.content || "",
    agents: Array.isArray(message?.agents)
      ? message.agents
      : [],
    actions: Array.isArray(message?.actions)
      ? message.actions
      : [],
    createdAt: message?.createdAt,
  };
}

function agentName(agentId) {
  return AGENT_META[agentId]?.name || agentId;
}

function agentDot(agentId) {
  return AGENT_META[agentId]?.dot || "bg-text-dim";
}

function getAgentSummary(agents = []) {
  if (!agents.length) {
    return null;
  }

  const names = agents
    .map((agent) => agentName(agent))
    .filter(Boolean);

  if (!names.length) {
    return null;
  }

  if (names.length === 1) {
    return `Worked with ${names[0]}`;
  }

  if (names.length === 2) {
    return `Worked with ${names[0]} and ${names[1]}`;
  }

  return `Worked with ${names.slice(0, -1).join(", ")} and ${
    names[names.length - 1]
  }`;
}

function getSuccessfulActions(actions = []) {
  return actions.filter(
    (action) => action && action.success
  );
}

export default function AgentWorkspace({
  briefing = [],
  className = "",
}) {
  const apiClient = useApi();

  const [threadId, setThreadId] =
    useState(DEFAULT_THREAD);

  const [input, setInput] = useState("");

  const [messages, setMessages] = useState([]);

  const [busy, setBusy] = useState(false);

  const [loadingHistory, setLoadingHistory] =
    useState(true);

  const [error, setError] = useState("");

  const chatContainerRef = useRef(null);

  const previousMessageCount =
    useRef(0);

  /*
   * Load the persistent Mission Control conversation.
   *
   * This is deliberately separate from the dashboard briefing.
   * Briefing items are suggestions, not conversation messages.
   */
  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setLoadingHistory(true);
      setError("");

      try {
        const response = await apiClient.get(
          "/agents/chat"
        );

        if (cancelled) {
          return;
        }

        const loadedMessages = Array.isArray(
          response?.messages
        )
          ? response.messages.map(normalizeMessage)
          : [];

        setThreadId(
          response?.thread || DEFAULT_THREAD
        );

        setMessages(loadedMessages);

        previousMessageCount.current =
          loadedMessages.length;
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err?.message ||
            "Couldn't load your conversation."
        );
      } finally {
        if (!cancelled) {
          setLoadingHistory(false);
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, []);

  /*
   * Scroll ONLY the chat container.
   *
   * Do not use scrollIntoView() because that can move the
   * entire dashboard page.
   */
  useEffect(() => {
    const container =
      chatContainerRef.current;

    if (!container) {
      return;
    }

    const messageCountChanged =
      messages.length !==
      previousMessageCount.current;

    if (!messageCountChanged) {
      return;
    }

    previousMessageCount.current =
      messages.length;

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  /*
   * Briefing items become composer suggestions.
   *
   * They are NEVER inserted into the persistent conversation.
   * This prevents proactive messages from appearing again
   * every time the dashboard renders.
   */
  const briefingSuggestions = useMemo(() => {
    if (!Array.isArray(briefing)) {
      return [];
    }

    return briefing
      .map((item) => {
        if (!item) {
          return null;
        }

        return (
          item.message ||
          item.prompt ||
          item.text ||
          null
        );
      })
      .filter(Boolean);
  }, [briefing]);

  const suggestions = useMemo(() => {
    const combined = [
      ...briefingSuggestions,
      ...DEFAULT_SUGGESTIONS,
    ];

    const seen = new Set();

    return combined.filter((suggestion) => {
      const normalized =
        suggestion.trim().toLowerCase();

      if (!normalized || seen.has(normalized)) {
        return false;
      }

      seen.add(normalized);
      return true;
    });
  }, [briefingSuggestions]);

  function selectSuggestion(text) {
    setInput(text);
    setError("");
  }

  async function sendMessage(e) {
    e?.preventDefault();

    const message = input.trim();

    if (!message || busy) {
      return;
    }

    setError("");

    const userMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      agents: [],
      actions: [],
    };

    setMessages((previous) => [
      ...previous,
      userMessage,
    ]);

    setInput("");
    setBusy(true);

    try {
      const response = await apiClient.post(
        "/agents/chat",
        {
          message,
          thread: threadId,
        }
      );

      const assistantMessage =
        response?.assistantMessage ||
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content:
            response?.message ||
            "Done.",
          agents:
            response?.agents || [],
          actions:
            response?.actions || [],
        };

      setThreadId(
        response?.thread || threadId
      );

      setMessages((previous) => [
        ...previous,
        normalizeMessage(
          assistantMessage
        ),
      ]);
    } catch (err) {
      setError(
        err?.message ||
          "Something went wrong. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-label="Ask IntelliTwin"
      className={`panel relative min-h-[560px] overflow-hidden ${className}`}
    >
      <div className="flex h-full flex-col xl:absolute xl:inset-0">
        {/* HEADER */}
        <div className="border-b border-ink-700 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-ink-600 bg-ink-800"
            >
              <Sparkles className="h-3.5 w-3.5 text-accent" strokeWidth={1.75} />
            </span>
            <h2 className="font-display text-sm font-semibold text-text">Ask IntelliTwin</h2>
          </div>

          <p className="mt-2 text-xs leading-5 text-text-dim">
            One conversation. The right agents join in behind the scenes.
          </p>

          {/* AGENT IDENTITIES */}
          <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Agents">
            {Object.entries(AGENT_META).map(([id, agent]) => {
              const Icon = agent.icon;
              return (
                <li
                  key={id}
                  className="flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-800/60 px-2.5 py-1"
                >
                  <Icon aria-hidden="true" className={`h-3 w-3 ${agent.text}`} strokeWidth={1.75} />
                  <span className="text-[11px] text-text-dim">
                    {agent.name}
                    <span className="sr-only"> ({agent.role})</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* CHAT AREA */}
        <div
          ref={chatContainerRef}
          role="log"
          aria-live="polite"
          aria-label="Conversation"
          className="h-[380px] overflow-y-auto overscroll-contain px-4 py-5 xl:h-auto xl:min-h-0 xl:flex-1"
        >
          <div className="space-y-4">
            {loadingHistory ? (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md border border-ink-700 bg-ink-800/80 px-3.5 py-2.5">
                  <div className="flex items-center gap-2 text-xs text-text-dim">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />
                    Loading your conversation…
                  </div>
                </div>
              </div>
            ) : null}

            {!loadingHistory &&
            messages.length === 0 ? (
              <div className="flex justify-start">
                <div className="max-w-[88%] rounded-2xl rounded-bl-md border border-ink-700 bg-ink-800/80 px-3.5 py-2.5">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />

                    <span className="text-[10px] font-medium uppercase tracking-wider text-text-dim">
                      IntelliTwin
                    </span>
                  </div>

                  <p className="whitespace-pre-wrap text-sm leading-6 text-text">
                    I&apos;m here. Tell me what you
                    want to work on, and I&apos;ll bring
                    in the right agents.
                  </p>
                </div>
              </div>
            ) : null}

            {messages.map((message) => {
              const isUser =
                message.role === "user";

              const agentSummary =
                getAgentSummary(
                  message.agents
                );

              const successfulActions =
                getSuccessfulActions(
                  message.actions
                );

              return (
                <div
                  key={message.id}
                  className={`flex ${
                    isUser
                      ? "justify-end"
                      : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[88%] ${
                      isUser
                        ? "rounded-2xl rounded-br-md bg-ink-700 px-3.5 py-2.5"
                        : "rounded-2xl rounded-bl-md border border-ink-700 bg-ink-800/80 px-3.5 py-2.5"
                    }`}
                  >
                    {!isUser ? (
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />

                        <span className="text-[10px] font-medium uppercase tracking-wider text-text-dim">
                          IntelliTwin
                        </span>

                        {agentSummary ? (
                          <>
                            <span className="text-[10px] text-text-dim/50">
                              ·
                            </span>

                            <span className="text-[10px] text-text-dim">
                              {agentSummary}
                            </span>
                          </>
                        ) : null}
                      </div>
                    ) : null}

                    <p className="whitespace-pre-wrap text-sm leading-6 text-text">
                      {message.content}
                    </p>

                    {!isUser &&
                    successfulActions.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {successfulActions.map(
                          (action, index) => (
                            <span
                              key={`${action.tool}-${index}`}
                              className="rounded-full border border-ink-600 bg-ink-900/50 px-2.5 py-1 text-[10px] text-text-dim"
                            >
                              {action.tool
                                ?.replaceAll(
                                  "_",
                                  " "
                                )}
                            </span>
                          )
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}

            {busy ? (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-md border border-ink-700 bg-ink-800/80 px-3.5 py-2.5">
                  <div className="flex items-center gap-2 text-xs text-text-dim">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-cyan-400" />

                    Working on it…
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* ERROR */}
        {error ? (
          <div className="mx-4 mb-3 rounded-xl border border-rose-400/20 bg-rose-400/5 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        ) : null}

        {/* SUGGESTIONS / BRIEFINGS */}
        <div className="border-t border-ink-700 px-4 pt-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-text-dim">
              {briefingSuggestions.length
                ? "Continue"
                : "Suggestions"}
            </p>

            {briefingSuggestions.length ? (
              <p className="text-[10px] text-text-dim/60">
                Fills the composer only
              </p>
            ) : null}
          </div>

          <div className="flex gap-2 overflow-x-auto pb-3">
            {suggestions.slice(0, 4).map(
              (suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() =>
                    selectSuggestion(
                      suggestion
                    )
                  }
                  className="shrink-0 rounded-full border border-ink-600 px-3 py-1.5 text-xs text-text-dim transition-colors hover:border-ink-500 hover:text-text"
                >
                  {briefingSuggestions.includes(
                    suggestion
                  )
                    ? "Continue: "
                    : ""}
                  {suggestion}
                </button>
              )
            )}
          </div>
        </div>

        {/* INPUT */}
        <div className="px-4 pb-4">
          <form
            onSubmit={sendMessage}
            className="rounded-2xl border border-ink-600 bg-ink-800 p-2 transition-colors focus-within:border-ink-500"
          >
            <textarea
              value={input}
              onChange={(e) =>
                setInput(e.target.value)
              }
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey
                ) {
                  e.preventDefault();
                  sendMessage(e);
                }
              }}
              rows={2}
              placeholder="Ask anything about your work…"
              aria-label="Message IntelliTwin"
              disabled={busy}
              className="w-full resize-none bg-transparent px-3 py-2 text-sm text-text outline-none placeholder:text-text-dim/60"
            />

            <div className="flex items-center justify-between px-2 pb-1">
              <p className="text-[10px] text-text-dim">
                Enter to send · Shift+Enter for a new line
              </p>

              <button
                type="submit"
                disabled={
                  busy || !input.trim()
                }
                aria-label={busy ? "Working" : "Send message"}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-ink-950 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
              >
                <ArrowUp aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}