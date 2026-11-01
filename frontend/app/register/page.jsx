"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import AgentBootSequence from "../../components/ui/AgentBootSequence";

const FIRST_RUN_STEPS = [
  { id: "create", label: "Creating your twin" },
  { id: "compass", label: "Compass setting up your workspace" },
  { id: "atlas", label: "Atlas standing by" },
  { id: "echo", label: "Echo opening a memory timeline" },
  { id: "nova", label: "Nova ready to draft" },
];

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [phase, setPhase] = useState("form");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setPhase("authenticating");
    try {
      await register(name, email, password);
      setPhase("booting");
    } catch (err) {
      setError(err.message);
      setPhase("form");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/40 bg-cyan-400/10">
            <span className="font-display text-cyan-300 text-lg">◆</span>
          </div>
          <h1 className="font-display text-2xl text-text">Create your twin</h1>
          <p className="mt-1 text-sm text-text-dim">Echo, Atlas, Compass and Nova start with you.</p>
        </div>

        <Card className="p-6">
          {phase !== "booting" ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-dim">Name</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-sm text-text outline-none focus:border-cyan-400"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-dim">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-sm text-text outline-none focus:border-cyan-400"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-dim">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-sm text-text outline-none focus:border-cyan-400"
                />
              </div>

              {error ? <p className="text-sm text-rose-400">{error}</p> : null}

              <Button type="submit" className="w-full" disabled={phase === "authenticating"}>
                {phase === "authenticating" ? "Creating…" : "Create account"}
              </Button>

              <p className="text-center text-xs text-text-dim">
                Already have an account?{" "}
                <a href="/login" className="text-cyan-300 hover:underline">
                  Log in
                </a>
              </p>
            </form>
          ) : (
            <div>
              <p className="mb-4 text-sm font-medium text-text">Setting things up</p>
              <AgentBootSequence steps={FIRST_RUN_STEPS} onDone={() => router.replace("/dashboard")} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
