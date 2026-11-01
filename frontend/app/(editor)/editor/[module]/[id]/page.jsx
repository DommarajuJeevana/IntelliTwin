"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Bold, Italic, Underline, List, ListOrdered, Link2, Undo2, Redo2,
  Heading1, Heading2, Pilcrow, Loader2, Check, AlertTriangle,
} from "lucide-react";
import { useApi } from "@/lib/useApi";

// Notes and documents have different schemas; only the body field differs here.
const MODULES = {
  notes: { label: "Note", field: "body", listPath: "/notes", extra: {} },
  documents: { label: "Document", field: "content", listPath: "/documents", extra: { type: "draft", status: "draft" } },
};
const AUTOSAVE_MS = 1500;

const escapeHtml = (t) =>
  t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Legacy records were plain text; show them as paragraphs, never as raw markup.
function toEditorHtml(value) {
  const text = value || "";
  if (/<\/?[a-z][\s\S]*>/i.test(text)) return text; // already sanitised HTML from the server
  return text
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function safeUrl(raw) {
  try {
    const u = new URL(/^[a-z]+:/i.test(raw) ? raw : `https://${raw}`);
    return ["http:", "https:", "mailto:"].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}

export default function EditorPage() {
  const { module: moduleKey, id: routeId } = useParams();
  const cfg = MODULES[moduleKey];
  const router = useRouter();
  const api = useApi();

  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  // idle | dirty | saving | saved | error | conflict
  const [status, setStatus] = useState("idle");
  const [saveError, setSaveError] = useState("");
  const [savedAt, setSavedAt] = useState(null);

  const editorRef = useRef(null);
  const recordId = useRef(routeId === "new" ? null : routeId);
  const stamp = useRef(null);       // server updatedAt of the version we hold
  const revision = useRef(0);        // bumps on every local edit
  const savedRevision = useRef(0);   // last revision the server confirmed
  const inFlight = useRef(false);
  const timer = useRef(null);
  const titleRef = useRef("");


  // ---- load -------------------------------------------------------------
  useEffect(() => {
    if (!cfg) { setLoadError("Unknown editor type."); setLoading(false); return; }
    if (routeId === "new") { setLoading(false); return; }
    let cancelled = false;
    (async () => {
      try {
        const { item } = await api.get(`${cfg.listPath}/${routeId}`);
        if (cancelled) return;
        setTitle(item.title || "");
        titleRef.current = item.title || "";
        stamp.current = item.updatedAt || null;
        setSavedAt(item.updatedAt ? new Date(item.updatedAt) : null);
        setLoading(false);
        requestAnimationFrame(() => {
          if (editorRef.current) editorRef.current.innerHTML = toEditorHtml(item[cfg.field]);
        });
      } catch (err) {
        if (!cancelled) { setLoadError(err.status === 404 ? "This record doesn't exist or isn't yours." : err.message); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [api, cfg, routeId]);

  // ---- save (serialised: an older response can never overwrite newer edits) ----
  const save = useCallback(async () => {
    if (!cfg || inFlight.current) return false;
    if (revision.current === savedRevision.current) return true;
    const snapshotRev = revision.current;
    const snapshot = { title: titleRef.current.trim() || "Untitled", body: editorRef.current?.innerHTML || "" };
    inFlight.current = true;
    setStatus("saving");
    try {
      let res;
      if (!recordId.current) {
        res = await api.post(cfg.listPath, { title: snapshot.title, [cfg.field]: snapshot.body, ...cfg.extra });
        recordId.current = res.item._id;
        window.history.replaceState(null, "", `/editor/${moduleKey}/${recordId.current}`);
      } else {
        res = await api.put(`${cfg.listPath}/${recordId.current}`, {
          title: snapshot.title, [cfg.field]: snapshot.body, expectedUpdatedAt: stamp.current,
        });
      }
      stamp.current = res.item.updatedAt;       // confirmed by the backend
      savedRevision.current = snapshotRev;
      setSavedAt(new Date(res.item.updatedAt));
      setSaveError("");
      inFlight.current = false;
      if (revision.current !== snapshotRev) {   // user kept typing meanwhile
        setStatus("dirty");
        schedule();
      } else {
        setStatus("saved");
      }
      return true;
    } catch (err) {
      inFlight.current = false;
      if (err.status === 409) { setStatus("conflict"); setSaveError(err.message); }
      else { setStatus("error"); setSaveError(err.message || "Save failed."); }
      return false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, cfg, moduleKey]);

  const schedule = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { save(); }, AUTOSAVE_MS);
  }, [save]);

  const markEdited = useCallback(() => {
    revision.current += 1;
    setStatus((s) => (s === "conflict" ? s : "dirty"));
    schedule();
  }, [schedule]);

  useEffect(() => () => clearTimeout(timer.current), []);

  // ---- leaving the page --------------------------------------------------
  useEffect(() => {
    const warn = (e) => {
      if (revision.current !== savedRevision.current) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  async function goBack() {
    clearTimeout(timer.current);
    if (revision.current !== savedRevision.current) {
      // wait for any in-flight save, then try once more before leaving
      for (let i = 0; i < 50 && inFlight.current; i++) await new Promise((r) => setTimeout(r, 100));
      const ok = await save();
      if (!ok && !window.confirm("Your latest changes could not be saved. Leave anyway and lose them?")) return;
    }
    if (window.history.length > 1) router.back();
    else router.push(cfg?.listPath || "/dashboard");
  }

  // ---- toolbar -----------------------------------------------------------
  function exec(cmd, value = null) {
    editorRef.current?.focus();
    document.execCommand(cmd, false, value);
    markEdited();
  }
  function addLink() {
    const raw = window.prompt("Link address (https://…)");
    if (!raw) return;
    const url = safeUrl(raw.trim());
    if (!url) { window.alert("Only http, https and mailto links are allowed."); return; }
    exec("createLink", url);
  }
  function onPaste(e) {
    // Paste as plain text so foreign markup/scripts never enter the document.
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
    markEdited();
  }
  function onKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); addLink(); }
  }

  const tools = useMemo(() => [
    { icon: Undo2, label: "Undo", run: () => exec("undo") },
    { icon: Redo2, label: "Redo", run: () => exec("redo") },
    { icon: Heading1, label: "Heading", run: () => exec("formatBlock", "H2") },
    { icon: Heading2, label: "Subheading", run: () => exec("formatBlock", "H3") },
    { icon: Pilcrow, label: "Paragraph", run: () => exec("formatBlock", "P") },
    { icon: Bold, label: "Bold", run: () => exec("bold") },
    { icon: Italic, label: "Italic", run: () => exec("italic") },
    { icon: Underline, label: "Underline", run: () => exec("underline") },
    { icon: List, label: "Bulleted list", run: () => exec("insertUnorderedList") },
    { icon: ListOrdered, label: "Numbered list", run: () => exec("insertOrderedList") },
    { icon: Link2, label: "Link", run: addLink },
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [markEdited]);

  const statusView = {
    idle: { icon: null, text: savedAt ? `Last saved ${savedAt.toLocaleTimeString()}` : "Not saved yet", tone: "text-text-dim" },
    dirty: { icon: null, text: "Unsaved changes", tone: "text-amber-400" },
    saving: { icon: Loader2, text: "Saving…", tone: "text-text-dim", spin: true },
    saved: { icon: Check, text: `Saved ${savedAt ? savedAt.toLocaleTimeString() : ""}`, tone: "text-emerald-400" },
    error: { icon: AlertTriangle, text: `Save failed: ${saveError}`, tone: "text-rose-400" },
    conflict: { icon: AlertTriangle, text: saveError || "Changed elsewhere — reload before saving.", tone: "text-rose-400" },
  }[status];

  if (loading) return <div className="grid min-h-screen place-items-center bg-ink-950 text-sm text-text-dim">Loading…</div>;
  if (loadError) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-950 text-text">
        <div className="text-center">
          <p className="mb-4 text-sm text-rose-400">{loadError}</p>
          <button onClick={() => router.push(cfg?.listPath || "/dashboard")} className="text-sm text-accent hover:underline">← BACK</button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-ink-950 text-text">
      <header className="flex items-center gap-4 border-b border-ink-700 px-4 py-3">
        <button onClick={goBack} aria-label="Back" className="flex items-center gap-2 text-xs font-semibold tracking-widest text-text/80 hover:text-accent">
          <ArrowLeft size={16} /> BACK
        </button>
        <input
          value={title}
          onChange={(e) => { setTitle(e.target.value); titleRef.current = e.target.value; markEdited(); }}
          placeholder={`${cfg.label} title`}
          aria-label="Title"
          className="min-w-0 flex-1 bg-transparent text-lg font-medium outline-none placeholder:text-text-dim/70"
        />
        <span role="status" className={`flex items-center gap-1 text-xs ${statusView.tone}`}>
          {statusView.icon ? <statusView.icon size={14} className={statusView.spin ? "animate-spin" : ""} /> : null}
          {statusView.text}
        </span>
        {(status === "error" || status === "dirty") && (
          <button onClick={save} className="rounded border border-accent/40 px-3 py-1 text-xs text-accent hover:bg-accent/10">
            {status === "error" ? "Retry" : "Save"}
          </button>
        )}
        {status === "conflict" && (
          <button onClick={() => window.location.reload()} className="rounded border border-rose-400/40 px-3 py-1 text-xs text-rose-300">Reload</button>
        )}
      </header>

      <div role="toolbar" aria-label="Formatting" className="flex flex-wrap gap-1 border-b border-ink-700 px-4 py-2">
        {tools.map(({ icon: Icon, label, run }) => (
          <button key={label} type="button" title={label} aria-label={label}
            onMouseDown={(e) => e.preventDefault()} onClick={run}
            className="rounded p-2 text-text-dim hover:bg-white/5 hover:text-accent">
            <Icon size={16} />
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">
        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          role="textbox"
          aria-multiline="true"
          aria-label="Content"
          onInput={markEdited}
          onPaste={onPaste}
          onKeyDown={onKeyDown}
          className="editor-surface mx-auto min-h-full max-w-3xl px-6 py-8 text-[15px] leading-7 outline-none"
        />
      </div>
    </div>
  );
}
