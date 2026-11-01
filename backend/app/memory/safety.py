"""Guards that keep secrets out of long-term memory."""
import re

_SECRET_PATTERNS = [
    r"\b(?:password|passwd|passcode|pin)\b\s*(?:is|:|=)",
    r"\b(?:api[ _-]?key|secret[ _-]?key|access[ _-]?token|auth[ _-]?token|bearer)\b",
    r"\bsk-[A-Za-z0-9_-]{16,}",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    r"\b(?:\d[ -]?){13,19}\b",                 # card-like numbers
    r"\b\d{3}-\d{2}-\d{4}\b",                  # SSN-like
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bmongodb(?:\+srv)?://[^\s]*:[^\s]*@",   # connection string with credentials
]
_RE = re.compile("|".join(_SECRET_PATTERNS), re.I)


def contains_secret(text: str) -> bool:
    return bool(text and _RE.search(text))


SECRET_MESSAGE = "This looks like it contains a password, API key, card number or other secret, so it won't be saved to memory."


def reject_secret_memory(*texts) -> None:
    """Raise ValueError if any text looks like a secret (used by every memory write path)."""
    if contains_secret("\n".join(t for t in texts if isinstance(t, str))):
        raise ValueError(SECRET_MESSAGE)
