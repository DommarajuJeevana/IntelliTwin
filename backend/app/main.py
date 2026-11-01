"""
IntelliTwin API entry point.

Run from the `backend/` directory:

    uvicorn app.main:app --reload --port 5000

Everything the frontend calls lives under `/api`:

    /api/auth            register, login, me, profile
    /api/agents          Echo / Atlas / Compass / Nova, Mission Control chat, collaboration
    /api/chat            per-agent conversation endpoint
    /api/chat-history    every Mission Control chat, browsable by day
    /api/memory          Echo's semantic memory routes + plain CRUD
    /api/goals /tasks /calendar /notes /documents /research /projects
                         generic workspace CRUD (see modules_config.py)
    /api/milestones      earned milestones
    /api/notifications   due reminders
    /api/dashboard       dashboard summary + briefing
    /api/search          universal search
    /api/privacy         "what do agents know about me", export, wipe
    /api/health          liveness + which LLM is configured and whether it is reachable
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import close_db, connect_db, get_db
from app.modules_config import MODULES
from app.notification_worker import notification_worker
from app.routers import agents, auth, chat, chat_history, dashboard, memory, milestones, notifications, privacy, search, suggestions
from app.routers.generic_crud import build_module_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("intellitwin")


async def _ensure_indexes() -> None:
    """Indexes the app's own queries rely on. Safe to run on every start."""
    db = get_db()
    await db.users.create_index("email", unique=True)
    for collection in {config["collection"] for config in MODULES.values()}:
        await db[collection].create_index([("user", 1), ("createdAt", -1)])
    await db.milestones.create_index([("user", 1), ("earnedAt", -1)])
    await db.agent_messages.create_index([("user", 1), ("thread", 1), ("createdAt", 1)])
    await db.mission_control_messages.create_index([("user", 1), ("createdAt", -1)])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_db()
    await _ensure_indexes()
    worker = asyncio.create_task(notification_worker())
    logger.info("[llm] provider=%s model=%s", settings.LLM_PROVIDER, _configured_model())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        await close_db()


app = FastAPI(title="IntelliTwin API", version="1.0.0", lifespan=lifespan)

_origins = [origin.strip() for origin in settings.CLIENT_ORIGIN.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------- errors ----
#
# The frontend (lib/api.js) shows `data.error`. FastAPI's own errors use
# `detail`, so every error response carries both: `error` is always a plain
# string, `detail` keeps FastAPI's original payload (e.g. the calendar
# conflict list).

def _error_message(detail) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error") or "Request failed.")
    return "Request failed."


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": _error_message(exc.detail), "detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "Invalid request.")
    return JSONResponse(
        status_code=422,
        content={"error": f"{location}: {message}" if location else message, "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error."})


# --------------------------------------------------------------- routes ----

api_prefix = "/api"

app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["auth"])
app.include_router(agents.router, prefix=f"{api_prefix}/agents", tags=["agents"])
app.include_router(chat.router, prefix=api_prefix, tags=["chat"])

# Echo's fixed memory paths (/recent, /search, ...) must be registered before
# the generic memory router so its `/{item_id}` route doesn't swallow them.
app.include_router(memory.router, prefix=f"{api_prefix}/memory", tags=["memory"])
for module_key in MODULES:
    app.include_router(build_module_router(module_key), prefix=f"{api_prefix}/{module_key}", tags=[module_key])

app.include_router(milestones.router, prefix=f"{api_prefix}/milestones", tags=["milestones"])
app.include_router(notifications.router, prefix=f"{api_prefix}/notifications", tags=["notifications"])
app.include_router(dashboard.router, prefix=f"{api_prefix}/dashboard", tags=["dashboard"])
app.include_router(search.router, prefix=f"{api_prefix}/search", tags=["search"])
app.include_router(privacy.router, prefix=f"{api_prefix}/privacy", tags=["privacy"])
app.include_router(chat_history.router, prefix=f"{api_prefix}/chat-history", tags=["chat-history"])
app.include_router(suggestions.router, prefix=f"{api_prefix}/suggestions", tags=["suggestions"])


# --------------------------------------------------------------- health ----

def _configured_model() -> str:
    return {
        "ollama": settings.OLLAMA_MODEL,
        "openai": settings.OPENAI_MODEL,
        "anthropic": settings.ANTHROPIC_MODEL,
    }.get((settings.LLM_PROVIDER or "").lower(), "unknown")


async def _ollama_status() -> dict:
    """Is Ollama reachable, and has the configured model been pulled?"""
    root = settings.OLLAMA_BASE_URL.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{root}/api/tags")
            response.raise_for_status()
        names = [m.get("name", "") for m in response.json().get("models", [])]
        wanted = settings.OLLAMA_MODEL
        installed = any(n == wanted or n.split(":")[0] == wanted.split(":")[0] and ":" not in wanted for n in names)
        return {
            "reachable": True,
            "modelInstalled": installed,
            "hint": None if installed else f"Run: ollama pull {wanted}",
        }
    except Exception:  # noqa: BLE001 - this is a diagnostic, never an error
        return {"reachable": False, "modelInstalled": False, "hint": "Start Ollama with: ollama serve"}


@app.get(f"{api_prefix}/health")
async def health():
    llm = {"provider": settings.LLM_PROVIDER, "model": _configured_model()}
    if (settings.LLM_PROVIDER or "").lower() == "ollama":
        llm.update(await _ollama_status())
    return {"status": "ok", "llm": llm}
