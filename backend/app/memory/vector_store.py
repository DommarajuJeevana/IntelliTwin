"""
Phase 3 - Echo's vector store.

This is the "Vector DB" box in the Phase 2 architecture diagram. It's kept
as its own module with a narrow interface (upsert / delete / search) for
exactly one reason: today it's implemented as brute-force cosine similarity
over `embedding` arrays already sitting in MongoDB's memory_entries
collection (no new infrastructure needed to get real semantic search
working), but a personal digital twin's memory collection is small enough
(thousands, not millions, of entries per user) that this is genuinely fine.
If it ever needs to scale further, swap this module's internals for Atlas
Vector Search ($vectorSearch) or a dedicated store like Chroma/Pinecone -
nothing outside this file has to change, because callers only ever see
`SearchHit` objects, not how the similarity was computed.
"""
import logging
from dataclasses import dataclass

from bson import ObjectId

from app.database import get_db


logger = logging.getLogger("intellitwin.vector_store")


@dataclass
class SearchHit:
    doc: dict
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def upsert_embedding(collection_name: str, doc_id: ObjectId, embedding: list[float]) -> None:
    db = get_db()
    await db[collection_name].update_one({"_id": doc_id}, {"$set": {"embedding": embedding}})


async def search(
    collection_name: str,
    user_id: ObjectId,
    query_embedding: list[float],
    limit: int = 5,
    extra_filter: dict | None = None,
) -> list[SearchHit]:
    """
    Brute-force top-k cosine similarity search, scoped to one user's
    documents. Pulls candidates from Mongo (already filtered to this user
    and to documents that have an embedding), scores them in Python, and
    returns the best `limit`. Fine at this data scale; see module docstring.
    """
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    db = get_db()
    filt: dict = {"user": user_id, "embedding": {"$exists": True, "$ne": None}}
    if extra_filter:
        filt.update(extra_filter)

    candidates = await db[collection_name].find(filt).to_list(length=None)
    if not candidates:
        return []

    mismatched = sum(1 for c in candidates if len(c.get("embedding") or []) != len(query_embedding))
    if mismatched:
        # e.g. EMBEDDING_DIM or the embedding model changed: those records score 0 until re-embedded.
        logger.warning("[vector_store] %d of %d %s records have a different embedding dimension and will not match.",
                       mismatched, len(candidates), collection_name)

    scored = [SearchHit(doc=c, score=cosine_similarity(query_embedding, c.get("embedding") or [])) for c in candidates]
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:limit]
