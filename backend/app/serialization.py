"""
Mongoose's `res.json(doc)` silently turns ObjectId -> hex string and
Date -> ISO string. Motor/pymongo return raw bson types, so every response
in this app is passed through `serialize()` first to reproduce that same
JSON shape for the frontend (which expects e.g. `item._id` as a string).
"""
from datetime import datetime
from bson import ObjectId


def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        # Mongoose/JS renders dates as e.g. "2026-08-03T10:00:00.000Z"
        iso = value.isoformat()
        if value.tzinfo is None:
            iso += "+00:00"
        if iso.endswith("+00:00"):
            iso = iso[:-6] + "Z"
        return iso
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


# Raw vectors are an internal index detail: large, useless to a browser, and they would
# otherwise flow into model prompts, MCP results and logs.
PRIVATE_FIELDS = ("embedding",)


def doc_out(doc: dict | None) -> dict | None:
    """Serialize a single Mongo document for a JSON response (internal vectors removed)."""
    if doc is None:
        return None
    return serialize({k: v for k, v in doc.items() if k not in PRIVATE_FIELDS})


def docs_out(docs: list[dict]) -> list[dict]:
    return [doc_out(d) for d in docs]
