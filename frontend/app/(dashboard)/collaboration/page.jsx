"use client";
import { useState } from "react";
import { useApi } from "../../../lib/useApi";
import Card from "../../../components/ui/Card";
import Button from "../../../components/ui/Button";
import Badge from "../../../components/ui/Badge";

const AGENT_TONE = { compass: "cyan", atlas: "cyan", nova: "cyan", echo: "cyan", user: "dim" };

export default function CollaborationPage() {
  const apiClient = useApi();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState([]);
  const [error, setError] = useState("");

  async function invoke(e) {
    e.preventDefault();
    if (!topic.trim()) return;
    setBusy(true);
    setError("");
    try {
      const data = await apiClient.post("/agents/collaborate", { topic });
      setLog(data.log);
      setTopic("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h1 className="font-display text-2xl text-text">Agent Collaboration</h1>
        <p className="mt-1 text-sm text-text-dim">
          Give the twin a topic - Compass, Atlas, Nova and Echo work through it together.
        </p>
      </div>

      <Card className="mb-6">
        <form onSubmit={invoke} className="flex gap-2">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Plan a launch update for our beta users"
            className="flex-1 rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text outline-none focus:border-accent"
          />
          <Button type="submit" disabled={busy}>
            {busy ? "Collaborating…" : "Start"}
          </Button>
        </form>
      </Card>

      {error ? <p className="mb-4 text-sm text-rose-400">{error}</p> : null}

      <div className="space-y-3">
        {log.map((msg) => (
          <Card key={msg._id} className="flex items-start gap-3">
            <Badge tone={AGENT_TONE[msg.author] || "dim"}>{msg.author}</Badge>
            <p className="text-sm text-text-dim">{msg.content}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
