"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import AgentBootSequence from "../../components/ui/AgentBootSequence";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // phase: "form" -> "authenticating" -> "booting" -> done (redirect)
  const [phase, setPhase] = useState("form");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setPhase("authenticating");

    try {
      await login(email, password);
      // Credentials are valid - now play the boot sequence inside the button/card
      // before landing on the dashboard, instead of a bare spinner.
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
          <h1 className="font-display text-2xl text-text">IntelliTwin</h1>
          <p className="mt-1 text-sm text-text-dim">An AI Powered Intelligent Workspace</p>
        </div>

        <Card className="p-6">
          {phase !== "booting" ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-dim">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-sm text-text placeholder:text-text-dim focus:border-cyan-400 outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-text-dim">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-sm text-text placeholder:text-text-dim focus:border-cyan-400 outline-none"
                />
              </div>

              {error ? <p className="text-sm text-rose-400">{error}</p> : null}

              <Button type="submit" className="w-full" disabled={phase === "authenticating"}>
                {phase === "authenticating" ? (
                  <span className="flex items-center gap-2">
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink-950/40 border-t-ink-950" />
                    Verifying…
                  </span>
                ) : (
                  "Log in"
                )}
              </Button>

              <p className="text-center text-xs text-text-dim">
                No account yet?{" "}
                <a href="/register" className="text-cyan-300 hover:underline">
                  Create one
                </a>
              </p>
            </form>
          ) : (
            // The login button "becomes" this panel instead of the page just waiting.
            <div>
              <p className="mb-4 text-sm font-medium text-text">Waking up your twin</p>
              <AgentBootSequence onDone={() => router.replace("/dashboard")} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
