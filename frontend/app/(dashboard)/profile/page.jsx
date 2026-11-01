"use client";
import { useState } from "react";
import { useApi } from "../../../lib/useApi";
import { useAuth } from "../../../context/AuthContext";
import Card from "../../../components/ui/Card";
import Button from "../../../components/ui/Button";

const FIELDS = [
  {
    name: "currentFocus",
    label: "What are you focused on right now?",
    placeholder: "e.g. Shipping the Q3 launch",
    type: "text",
  },
  {
    name: "interests",
    label: "Interests (comma separated)",
    placeholder: "e.g. distance running, product design, sci-fi",
    type: "text",
    isList: true,
  },
  {
    name: "workingHours",
    label: "Working hours",
    placeholder: "e.g. 9am-6pm IST, no meetings before 10",
    type: "text",
  },
  { name: "timezone", label: "Timezone", placeholder: "e.g. Asia/Kolkata", type: "text" },
  {
    name: "communicationStyle",
    label: "How should agents talk to you?",
    placeholder: "e.g. brief, bullet points, no fluff",
    type: "text",
  },
  { name: "bio", label: "Anything else worth knowing", placeholder: "A few sentences about you", type: "textarea" },
];

export default function ProfilePage() {
  const apiClient = useApi();
  const { user, setUser } = useAuth();
  const p = user?.profile || {};

  const [form, setForm] = useState({
    currentFocus: p.currentFocus || "",
    interests: (p.interests || []).join(", "),
    workingHours: p.workingHours || "",
    timezone: p.timezone || "",
    communicationStyle: p.communicationStyle || "",
    bio: p.bio || "",
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError("");
    try {
      const payload = {
        ...form,
        interests: form.interests
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const { user: updated } = await apiClient.put("/auth/profile", payload);
      setUser(updated);
      localStorage.setItem("intellitwin_user", JSON.stringify(updated));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <h1 className="font-display text-2xl text-text">Your profile</h1>
        <p className="mt-1 text-sm text-text-dim">
          This is what Echo, Atlas, Compass and Nova read before responding — not a public bio.
        </p>
      </div>

      <Card>
        <form onSubmit={handleSave} className="space-y-4">
          {FIELDS.map((f) => (
            <div key={f.name}>
              <label className="mb-1.5 block text-xs font-medium text-text-dim">{f.label}</label>
              {f.type === "textarea" ? (
                <textarea
                  rows={3}
                  value={form[f.name]}
                  onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text placeholder:text-text-dim outline-none focus:border-accent"
                />
              ) : (
                <input
                  value={form[f.name]}
                  onChange={(e) => setForm((s) => ({ ...s, [f.name]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-text placeholder:text-text-dim outline-none focus:border-accent"
                />
              )}
            </div>
          ))}

          {error ? <p className="text-sm text-rose-400">{error}</p> : null}

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save profile"}
            </Button>
            {saved ? <span className="text-xs text-accent">Saved — agents will use this from now on.</span> : null}
          </div>
        </form>
      </Card>
    </div>
  );
}
