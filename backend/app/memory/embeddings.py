"""
Phase 3 - Echo's embedding layer.

Single integration point for turning text into a vector, mirroring how
app/llm.py is the single integration point for text generation. Everything
else (vector_store.py, echo.py) calls `embed_text()` and never talks to
OpenAI directly.

Two backends:
  - OpenAI `text-embedding-3-small` (real semantic embeddings) when
    OPENAI_API_KEY is set.
  - A deterministic local fallback (hashed bag-of-words, L2-normalized) when
    it isn't, so memory + semantic search stay fully demoable offline -
    same "never hard-fail without a key" philosophy as call_llm().

Both backends produce a unit-length vector of settings.EMBEDDING_DIM floats,
so vector_store.py's cosine similarity never has to know which one made it.
"""
import hashlib
import logging
import re

from app.config import settings

logger = logging.getLogger("intellitwin.embeddings")

_client = None
if settings.OPENAI_API_KEY:
    try:
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    except ImportError:
        logger.warning("[embeddings] OPENAI_API_KEY set but the `openai` package isn't installed; "
                        "falling back to the offline embedding. Run `pip install openai`.")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Post-rating improvement: common function words were contributing to the
# offline embedding's baseline noise - two completely unrelated sentences
# would still score ~0.13-0.16 cosine similarity because they both contain
# "the", "is", "and", etc. Filtering these (plus very short tokens) means
# similarity is driven by the words that actually carry meaning, which is
# what made the relative-margin filtering in with_context() do most of the
# work before; this fixes it closer to the source.
_STOPWORDS = frozenset(
    """
    a an the and or but if then so of to in on at by for with without from
    into onto over under again further once here there when where why how
    all any both each few more most other some such no nor not only own
    same than too very can will just don should now is am are was were be
    been being have has had do does did this that these those i me my we
    our you your he him his she her it its they them their as
    """.split()
)


def _stem(tok: str) -> str:
    """
    A deliberately tiny suffix-stripping stemmer - not linguistically
    rigorous, just enough that "marathon"/"marathons" and "train"/"trains"/
    "training" hash to the same bucket instead of being treated as
    unrelated words. Without this, the offline embedding under-matches on
    completely ordinary plural/verb-form differences between a memory and a
    search query. Order matters: longer, more specific suffixes are checked
    first so e.g. "categories" -> "categori" -> not further truncated by a
    trailing "-ies" (already both suffixes as far as ies is concerned).
    """
    if len(tok) > 6 and tok.endswith("ing"):
        return tok[:-3]
    if len(tok) > 5 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 5 and tok.endswith("ed"):
        return tok[:-2]
    if len(tok) > 5 and tok.endswith("es"):
        return tok[:-2]
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _local_embedding(text: str, dim: int = settings.EMBEDDING_DIM) -> list[float]:
    """
    Deterministic, dependency-free fallback: hash every token into one of
    `dim` buckets (the "hashing trick") and count it, +1/-1 by a second hash
    bit so unrelated tokens partially cancel instead of only ever adding up.
    Not a learned embedding, but text with overlapping vocabulary reliably
    lands closer together than unrelated text under cosine similarity, which
    is all Echo's semantic search needs to keep working with no API key.

    Stopwords and very short tokens are dropped before hashing (see
    _STOPWORDS above) so common function words don't create spurious
    similarity between otherwise-unrelated text; remaining tokens are
    lightly stemmed (see _stem() above) so ordinary plural/verb-form
    differences between a memory and a search query still match.
    """
    vec = [0.0] * dim
    raw_tokens = _TOKEN_RE.findall((text or "").lower())
    filtered = [t for t in raw_tokens if len(t) >= 3 and t not in _STOPWORDS]
    tokens = [_stem(t) for t in filtered] if filtered else raw_tokens  # degenerate case: text is only stopwords
    if not tokens:
        return vec

    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[bucket] += sign

    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [v / norm for v in vec]


async def embed_text(text: str) -> list[float]:
    """Returns a unit-length embedding vector for `text`. Never raises -
    falls back to the local embedding on any API error so a flaky embeddings
    call never blocks remembering something."""
    text = (text or "").strip()
    if not text:
        return [0.0] * settings.EMBEDDING_DIM

    if _client is not None:
        try:
            response = await _client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text,
                dimensions=settings.EMBEDDING_DIM,
            )
            return response.data[0].embedding
        except Exception as exc:  # noqa: BLE001
            logger.error("[embeddings] OpenAI embedding call failed, using offline fallback: %s", exc)

    return _local_embedding(text)


def embedding_backend() -> str:
    return "openai" if _client is not None else "offline-local"
