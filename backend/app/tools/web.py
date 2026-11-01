
"""
Atlas multi-provider web and scholarly search tool.

Providers:
- Tavily: broad web search, when TAVILY_API_KEY is configured.
- OpenAlex: scholarly works and research publications.
- Crossref: scholarly publication metadata and DOI links.
- Wikipedia: supplementary background information.

The tool preserves the SEARCH_WEB Tool interface and returns
normalized results with source URLs and explicit provider statuses.

Important:
- Scholarly metadata is not the same as verified full-text evidence.
- Provider failures are reported separately.
- A successful provider does not imply every returned source is relevant.
"""

import asyncio
import html
import logging
import re
from urllib.parse import quote

import httpx

from app.config import settings
from app.tools.base import Tool

logger = logging.getLogger("intellitwin.tools.web")

_TAVILY_URL = "https://api.tavily.com/search"
_OPENALEX_URL = "https://api.openalex.org/works"
_CROSSREF_URL = "https://api.crossref.org/works"
_WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

_TIMEOUT_SECONDS = 15
_USER_AGENT = "IntelliTwin/1.0 (research assistant)"


def _clean_text(value) -> str:
    """Convert provider text to readable plain text."""
    if not value:
        return ""

    if isinstance(value, list):
        value = " ".join(str(part) for part in value)

    value = str(value)
    value = re.sub(r"<[^>]*>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _normalize_results(
    raw_results: list,
    limit: int,
    source_type: str,
) -> list:
    """Normalize results and discard missing or duplicate URLs."""
    normalized = []
    seen_urls = set()

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        title = _clean_text(item.get("title"))
        url = str(item.get("url") or "").strip()
        snippet = _clean_text(item.get("snippet"))

        if not title or not url:
            continue

        if not url.startswith(("https://", "http://")):
            continue

        # Remove URL fragments and trailing slashes for deduplication.
        dedupe_url = url.split("#", 1)[0].rstrip("/").lower()

        if dedupe_url in seen_urls:
            continue

        seen_urls.add(dedupe_url)

        normalized.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source_type": item.get("source_type") or source_type,
            }
        )

        if len(normalized) >= limit:
            break

    return normalized


def _author_names(authors: list, maximum: int = 4) -> str:
    """Extract a short author list from provider metadata."""
    names = []

    for author in authors or []:
        if not isinstance(author, dict):
            continue

        name = author.get("display_name") or author.get("family")
        if name:
            names.append(str(name))

        if len(names) >= maximum:
            break

    return ", ".join(names)


async def _search_tavily(query: str, limit: int) -> dict:
    """Search the general web through Tavily."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                _TAVILY_URL,
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "advanced",
                },
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        raw_results = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("content"),
            }
            for item in data.get("results", [])
        ]

        results = _normalize_results(raw_results, limit, "tavily")

        return {
            "results": results,
            "search_status": "success" if results else "no_results",
            "source_type": "tavily",
        }

    except Exception as exc:
        logger.warning("[tools.web] Tavily failed: %s", exc)

        return {
            "results": [],
            "search_status": "failed",
            "source_type": "tavily",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _search_openalex(query: str, limit: int) -> dict:
    """Search OpenAlex for scholarly works."""
    try:
        params = {
            "search": query,
            "per-page": limit,
            "select": (
                "id,doi,title,publication_year,authorships,"
                "primary_location,best_oa_location,open_access"
            ),
        }

        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                _OPENALEX_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        raw_results = []

        for item in data.get("results", []):
            title = item.get("title")
            doi = item.get("doi")

            primary_location = item.get("primary_location") or {}
            best_oa_location = item.get("best_oa_location") or {}

            url = (
                doi
                or primary_location.get("landing_page_url")
                or best_oa_location.get("landing_page_url")
                or item.get("id")
            )

            authors = _author_names(item.get("authorships", []))
            year = item.get("publication_year")

            details = []
            if year:
                details.append(f"Year: {year}")
            if authors:
                details.append(f"Authors: {authors}")

            open_access = item.get("open_access") or {}
            if open_access.get("is_oa"):
                details.append("Open-access record")

            raw_results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": "; ".join(details),
                }
            )

        results = _normalize_results(raw_results, limit, "openalex")

        return {
            "results": results,
            "search_status": "success" if results else "no_results",
            "source_type": "openalex",
        }

    except Exception as exc:
        logger.warning("[tools.web] OpenAlex failed: %s", exc)

        return {
            "results": [],
            "search_status": "failed",
            "source_type": "openalex",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _search_crossref(query: str, limit: int) -> dict:
    """Search Crossref for scholarly publication metadata."""
    try:
        params = {
            "query.bibliographic": query,
            "rows": limit,
            "select": (
                "DOI,title,author,published,created,"
                "container-title,type,URL"
            ),
        }

        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                _CROSSREF_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {})
        raw_results = []

        for item in message.get("items", []):
            titles = item.get("title") or []
            title = titles[0] if titles else ""

            doi = item.get("DOI")
            url = (
                f"https://doi.org/{doi}"
                if doi
                else item.get("URL")
            )

            authors = _author_names(item.get("author", []))

            date_parts = (
                item.get("published", {}).get("date-parts")
                or item.get("created", {}).get("date-parts")
                or []
            )

            year = ""
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])

            journals = item.get("container-title") or []
            journal = journals[0] if journals else ""

            details = []
            if authors:
                details.append(f"Authors: {authors}")
            if year:
                details.append(f"Year: {year}")
            if journal:
                details.append(f"Publication: {journal}")

            raw_results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": "; ".join(details),
                }
            )

        results = _normalize_results(raw_results, limit, "crossref")

        return {
            "results": results,
            "search_status": "success" if results else "no_results",
            "source_type": "crossref",
        }

    except Exception as exc:
        logger.warning("[tools.web] Crossref failed: %s", exc)

        return {
            "results": [],
            "search_status": "failed",
            "source_type": "crossref",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _search_wikipedia(query: str, limit: int) -> dict:
    """Search Wikipedia for supplementary background information."""
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
            "utf8": 1,
        }

        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                _WIKIPEDIA_API_URL,
                params=params,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
            data = response.json()

        items = data.get("query", {}).get("search", [])
        raw_results = []

        for item in items:
            title = _clean_text(item.get("title"))
            if not title:
                continue

            raw_results.append(
                {
                    "title": title,
                    "url": (
                        "https://en.wikipedia.org/wiki/"
                        + quote(title.replace(" ", "_"), safe="()_,-")
                    ),
                    "snippet": item.get("snippet", ""),
                }
            )

        results = _normalize_results(raw_results, limit, "wikipedia")

        return {
            "results": results,
            "search_status": "success" if results else "no_results",
            "source_type": "wikipedia",
        }

    except Exception as exc:
        logger.warning("[tools.web] Wikipedia failed: %s", exc)

        return {
            "results": [],
            "search_status": "failed",
            "source_type": "wikipedia",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _search_web(user: dict, args: dict) -> dict:
    """Search multiple providers and merge their results."""
    query = str(args.get("query", "")).strip()

    if not query:
        return {
            "results": [],
            "search_status": "invalid_query",
            "error": "query is required.",
        }

    try:
        limit = int(args.get("limit", 5))
    except (TypeError, ValueError):
        limit = 5

    limit = max(1, min(limit, 10))

    # Search all available sources concurrently.
    # Tavily is included only when a key is configured.
    providers = []

    if settings.TAVILY_API_KEY:
        providers.append(("tavily", _search_tavily(query, limit)))
    else:
        logger.info(
            "[tools.web] Tavily skipped: API key is not configured."
        )

    providers.extend(
        [
            ("openalex", _search_openalex(query, limit)),
            ("crossref", _search_crossref(query, limit)),
            ("wikipedia", _search_wikipedia(query, limit)),
        ]
    )

    provider_names = [name for name, _ in providers]
    provider_results = await asyncio.gather(
        *(task for _, task in providers),
        return_exceptions=True,
    )

    merged_results = []
    seen_urls = set()
    provider_statuses = []
    provider_errors = []

    for name, result in zip(provider_names, provider_results):
        if isinstance(result, Exception):
            status = {
                "provider": name,
                "status": "failed",
            }
            provider_statuses.append(status)
            provider_errors.append(
                {
                    "provider": name,
                    "error": f"{type(result).__name__}: {result}",
                }
            )
            logger.warning(
                "[tools.web] Provider %s raised an exception: %s",
                name,
                result,
            )
            continue

        status = {
            "provider": name,
            "status": result.get("search_status", "unknown"),
            "result_count": len(result.get("results", [])),
        }
        provider_statuses.append(status)

        if result.get("error"):
            provider_errors.append(
                {
                    "provider": name,
                    "error": result["error"],
                }
            )

        for item in result.get("results", []):
            url = str(item.get("url") or "").strip()
            dedupe_url = url.split("#", 1)[0].rstrip("/").lower()

            if not dedupe_url or dedupe_url in seen_urls:
                continue

            seen_urls.add(dedupe_url)
            merged_results.append(item)

    if merged_results:
        return {
            "results": merged_results[:limit],
            "search_status": "success",
            "source_type": "multi_provider",
            "provider_statuses": provider_statuses,
            "provider_errors": provider_errors,
            "note": (
                "Results may include scholarly metadata and background "
                "sources. Verify source contents before treating them "
                "as evidence. Search result snippets are not full-text "
                "verification."
            ),
        }

    return {
        "results": [],
        "search_status": "unavailable",
        "source_type": "multi_provider",
        "provider_statuses": provider_statuses,
        "provider_errors": provider_errors,
        "note": (
            "No provider returned usable results. Do not invent sources, "
            "URLs, citations, or research findings. Clearly disclose "
            "that live search was unsuccessful."
        ),
    }


SEARCH_WEB = Tool(
    name="search_web",
    description=(
        "Search the web and scholarly indexes using multiple providers. "
        "Uses Tavily when configured, plus OpenAlex, Crossref, and "
        "Wikipedia. Returns normalized titles, source URLs, snippets, "
        "provider statuses, and provider-specific errors. Results may "
        "include publication metadata rather than full-text evidence; "
        "verify sources before making research claims."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The factual topic or research question to search."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": (
                    "Maximum number of combined results to return."
                ),
            },
        },
        "required": ["query"],
    },
    handler=_search_web,
)
