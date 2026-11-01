"""Server-side sanitisation for rich-text note/document bodies.

Content is stored as sanitised HTML. Legacy plain-text bodies (no tags) are
left untouched so existing records keep working; the editor converts them to
paragraphs when opened.
"""
import re

import bleach

ALLOWED_TAGS = ["p", "br", "h1", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
                "a", "blockquote", "code", "pre", "hr", "span", "div"]
ALLOWED_ATTRS = {"a": ["href", "title", "target", "rel"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
MAX_RICH_CHARS = 2_000_000

_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def looks_like_html(text: str) -> bool:
    return bool(_TAG_RE.search(text or ""))


def sanitize_rich_text(value):
    if not isinstance(value, str):
        return value
    if len(value) > MAX_RICH_CHARS:
        raise ValueError("Content is too large.")
    if not looks_like_html(value):
        return value
    cleaned = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS,
                           protocols=ALLOWED_PROTOCOLS, strip=True, strip_comments=True)
    # Links never get window access or referrer leakage.
    cleaned = re.sub(r"<a\b(?![^>]*\brel=)", '<a rel="noopener noreferrer nofollow"', cleaned)
    return cleaned


MAX_TAGS = 20
MAX_TAG_LEN = 50


def clean_tags(value):
    """A short list of short strings, or None if `value` is not a list."""
    if not isinstance(value, list):
        return None
    return [t.strip()[:MAX_TAG_LEN] for t in value if isinstance(t, str) and t.strip()][:MAX_TAGS]
