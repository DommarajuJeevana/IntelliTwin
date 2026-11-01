"""Nova's detailed-report pipeline.

"Write a detailed report on federated learning and save it as fl" becomes:
  parse request -> outline -> one model call per section -> completeness checks
  -> assemble -> sanitise -> save (idempotent) -> read back and verify -> link.

Nothing is reported as saved until the document has been read back from the
database. No references are fabricated: the report is written from the model's
background knowledge and says so.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import timedelta

from app.database import get_db
from app.llm import call_llm
from app.memory.embeddings import embed_text
from app.owned import new_owned_doc, now_utc
from app.sanitize import sanitize_rich_text
from app.serialization import doc_out

logger = logging.getLogger("intellitwin.docgen")

MAX_SECTIONS = 10
MIN_SECTION_WORDS = {"brief": 60, "standard": 120, "detailed": 200}
SECTION_TOKENS = {"brief": 450, "standard": 700, "detailed": 1000}
RETRY_WINDOW = timedelta(minutes=10)
_FAILED_MARKERS = ("[LLM request failed", "[offline placeholder")

_VERBS = r"(?:write|create|draft|generate|make|prepare|produce)"
_KINDS = r"(?:report|document|essay|article|paper|overview|guide|brief|summary|whitepaper)"
_REQUEST_RE = re.compile(
    rf"\b{_VERBS}\b\s+(?:me\s+)?(?:an?\s+|the\s+)?(?P<mods>[\w\- ,]{{0,60}}?)\b(?P<kind>{_KINDS})\b"
    r"(?:\s+(?:on|about|regarding|covering|for))?\s+(?P<rest>.+)$", re.I | re.S)
_SAVE_RE = re.compile(
    r"[,.;]?\s*(?:and\s+)?(?:then\s+)?(?:save|store|keep|name|call|title)\s+(?:it|this|the\s+\w+)?\s*"
    r"(?:as|to|in|under|named|called)\s+[\"'“]?(?P<name>[^\"'”\n]{1,80}?)[\"'”]?\s*[.!]?\s*$", re.I)
_DETAIL_WORDS = re.compile(r"\b(detailed|comprehensive|in-depth|in depth|thorough|long|extensive|full)\b", re.I)
_BRIEF_WORDS = re.compile(r"\b(short|brief|quick|concise|one[- ]page)\b", re.I)


def extract_report_request(message: str) -> dict | None:
    """Parse a document-creation request, or None if it isn't one."""
    text = (message or "").strip()
    m = _REQUEST_RE.search(text)
    if not m or not re.search(r"\b(?:save|store|name|call|title)\b|\b(?:detailed|comprehensive|report)\b", text, re.I):
        return None
    rest = m.group("rest").strip()
    filename = None
    s = _SAVE_RE.search(rest)
    if s:
        filename = s.group("name").strip(" .\"'")
        rest = rest[: s.start()].strip()
    topic = re.sub(r"^(?:on|about|regarding)\s+", "", rest, flags=re.I).strip(" .,:;\"'")
    if len(topic) < 2:
        return None
    mods = m.group("mods") or ""
    detail = "detailed" if _DETAIL_WORDS.search(mods + " " + text) else "brief" if _BRIEF_WORDS.search(mods) else "standard"
    return {"topic": topic[:200], "filename": filename, "detail": detail, "kind": m.group("kind").lower()}


# ------------------------------------------------------------------ model ----

def _bad(text: str | None) -> bool:
    return not text or text.startswith(_FAILED_MARKERS)


def _truncated(text: str) -> bool:
    t = text.rstrip()
    return not t or t[-1] not in ".!?)”\"'`:*" and not t.endswith(("```", "|"))


async def _outline(topic: str, kind: str, detail: str) -> list[str]:
    n = {"brief": 4, "standard": 6, "detailed": 9}[detail]
    prompt = (f"Plan a {detail} {kind} about: {topic}\nReturn ONLY a JSON array of {n} section titles "
              "suited to this topic (no numbering, no title page, no references section).")
    try:
        raw = await call_llm("You plan the structure of documents. Output JSON only.", prompt, max_tokens=300)
        if not _bad(raw):
            arr = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
            titles = [re.sub(r"^\s*\d+[.)]\s*", "", str(t)).strip() for t in arr if str(t).strip()]
            if len(titles) >= 3:
                return titles[:MAX_SECTIONS]
    except Exception:
        logger.info("Outline generation failed; using the default outline.")
    base = ["Introduction", "Background and Core Concepts", "How It Works", "Applications and Examples",
            "Benefits", "Limitations and Challenges", "Conclusion"]
    return base[:n] if n < len(base) else base


async def _section(topic: str, title: str, outline: list[str], detail: str) -> str | None:
    need = MIN_SECTION_WORDS[detail]
    system = ("You write one section of a technical document in clear prose. Use short paragraphs, and "
              "bullet lists (lines starting with '- ') or '### ' subheadings only where they help. "
              "Do not repeat the section title, do not write other sections, and never invent citations, "
              "statistics or experiments.")
    prompt = (f"Document topic: {topic}\nAll sections: {', '.join(outline)}\n\n"
              f"Write the section \"{title}\" in at least {need} words, with concrete detail.")
    for attempt in range(2):
        try:
            text = await call_llm(system, prompt, max_tokens=SECTION_TOKENS[detail])
        except Exception:
            logger.exception("Section generation failed: %s", title)
            continue
        if _bad(text):
            continue
        text = text.strip()
        if len(text.split()) >= need * 0.6 and not _truncated(text):
            return text
        prompt += "\n\nYour previous answer was too short or cut off. Write the complete section."
    return None


# ---------------------------------------------------------------- render ----

def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)


def markdown_to_html(md: str) -> str:
    out, para, items, kind = [], [], [], None

    def flush():
        nonlocal para, items, kind
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
        if items:
            tag = "ol" if kind == "ol" else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tag}>")
        para, items, kind = [], [], None

    for line in md.splitlines():
        s = line.strip()
        bullet = re.match(r"^[-*•]\s+(.*)", s)
        number = re.match(r"^\d+[.)]\s+(.*)", s)
        head = re.match(r"^#{1,6}\s+(.*)", s)
        if not s:
            flush()
        elif head:
            flush()
            out.append(f"<h3>{_inline(head.group(1))}</h3>")
        elif bullet or number:
            if para:
                flush()
            k = "ul" if bullet else "ol"
            if kind and kind != k:
                flush()
            kind = k
            items.append((bullet or number).group(1))
        else:
            if items:
                flush()
            para.append(s)
    flush()
    return "".join(out)


def _title_for(topic: str, filename: str | None) -> str:
    return (filename or topic).strip()[:120] or "Untitled report"


async def generate_and_save_report(user: dict, request: dict) -> dict:
    """Returns {"ok": bool, "message": str, "document": {...}|None}."""
    topic, detail = request["topic"], request["detail"]
    kind = request.get("kind", "report")
    uid = user["_id"]
    title = _title_for(topic, request.get("filename"))
    fingerprint = hashlib.sha256(f"{title}|{topic}|{detail}".lower().encode()).hexdigest()[:24]
    db = get_db()

    # Duplicate retry: the same request moments ago returns the saved document.
    recent = await db.documents.find_one({"user": uid, "generation.fingerprint": fingerprint,
                                          "createdAt": {"$gte": now_utc() - RETRY_WINDOW}})
    if recent:
        return _success(recent, "That report was already saved a moment ago, so I opened the existing one instead of creating a duplicate.")

    outline = await _outline(topic, kind, detail)
    sections, failed = [], []
    for heading in outline:
        body = await _section(topic, heading, outline, detail)
        (sections if body else failed).append((heading, body) if body else heading)
    if failed or not sections:
        return {"ok": False, "document": None, "message": (
            "I couldn't finish the report, so nothing was saved. "
            f"The model didn't return complete text for: {', '.join(failed) or 'every section'}. Please try again.")}

    parts = [f"<h1>{html.escape(title)}</h1>"]
    for heading, body in sections:
        parts.append(f"<h2>{html.escape(heading)}</h2>" + markdown_to_html(body))
    parts.append("<p><em>Note: this report was written from the model's general knowledge. "
                 "No web research was performed and no external sources are cited.</em></p>")
    content = sanitize_rich_text("".join(parts))

    # Never overwrite an existing document of the same name.
    final_title, n = title, 1
    while await db.documents.find_one({"user": uid, "title": final_title}, {"_id": 1}):
        n += 1
        final_title = f"{title} ({n})"

    doc = new_owned_doc(uid, agent="nova")
    doc.update({"title": final_title, "type": "report", "status": "draft", "content": content,
                "generation": {"fingerprint": fingerprint, "topic": topic, "sections": len(sections)}})
    try:
        doc["embedding"] = await embed_text(f"{final_title}\n{re.sub('<[^>]+>', ' ', content)[:4000]}")
    except Exception:
        pass
    inserted = await db.documents.insert_one(doc)
    saved = await db.documents.find_one({"_id": inserted.inserted_id, "user": uid})
    expected_words = sum(len(b.split()) for _, b in sections)
    if not saved or len(re.sub("<[^>]+>", " ", saved.get("content", "")).split()) < expected_words * 0.9:
        return {"ok": False, "document": None, "message": "The report was generated but I could not verify that it was saved, so please don't rely on it."}
    return _success(saved, f"I wrote “{saved['title']}” ({len(sections)} sections, about {expected_words} words) and saved it.")


def _success(saved: dict, lead: str) -> dict:
    out = doc_out(saved)
    link = f"/editor/documents/{out['_id']}"
    return {"ok": True, "document": out, "link": link,
            "message": f"{lead} Open it here: {link}\n\nNote: written from the model's general knowledge — no web research or citations were used."}
