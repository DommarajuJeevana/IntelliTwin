# IntelliTwin

An AI-powered intelligent workspace: Echo (memory), Atlas (research), Compass (planning)
and Nova (creation) agents on top of a Goals / Tasks / Calendar / Notes / Documents /
Research / Projects workspace, with generation by **Llama 3.2 running locally through Ollama**.

```
intellitwin/
├── backend/    FastAPI + MongoDB + agents      (port 5000)
└── frontend/   Next.js 14 + Tailwind           (port 3000)
```

## 1. Prerequisites

| Tool | Why |
|---|---|
| Python 3.11+ | backend |
| Node 18.18+ (20 recommended) | frontend |
| MongoDB 6+ | storage. `docker compose up -d` in `backend/` starts one, or use a local install / Atlas |
| [Ollama](https://ollama.com) | runs Llama 3.2 |

## 2. Start Llama 3.2

```bash
ollama pull llama3.2
ollama serve          # skip if Ollama is already running as a service
```

Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`; the backend talks to
it with the OpenAI client (`LLM_PROVIDER=ollama`, `OLLAMA_MODEL=llama3.2`).

## 3. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    
uvicorn app.main:app --reload --port 5000
```

Check `http://localhost:5000/api/health` - it reports the configured model and whether
Ollama is reachable and has the model installed.

## 4. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local      # NEXT_PUBLIC_API_URL=http://localhost:5000/api
npm run dev
```

Open http://localhost:3000, register an account and go to the dashboard.

## Configuration notes

- **Generation vs. embeddings are separate.** Llama 3.2 does the generation. Echo's memory
  embeddings use OpenAI `text-embedding-3-small` if `OPENAI_API_KEY` is set, otherwise a
  built-in offline embedding (works with no key, lower recall quality).
- **Atlas web search** needs `TAVILY_API_KEY`; without it Atlas says search is offline.
- **Other providers**: set `LLM_PROVIDER=openai` (+ `OPENAI_API_KEY`) or `anthropic`
  (+ `ANTHROPIC_API_KEY`, `pip install anthropic`).
- **Echo MCP server** (optional): `pip install -r requirements-mcp.txt` (pins `mcp<2`), set `ECHO_MCP_USER_EMAIL` to an existing
  account, then `python -m app.mcp.echo_server` from `backend/`.
- llama3.2 (3B) is small: it can be slow on CPU and is less reliable at multi-step tool use
  than larger models. If agent quality matters more than speed, try `OLLAMA_MODEL=llama3.1:8b`.

## What changed from the supplied zips

Backend: added `app/main.py` (router wiring, CORS, indexes, notification worker, health),
`requirements.txt`, `.env.example`, `docker-compose.yml`, `app/mcp/echo_server.py`; defaulted
config to Ollama + `llama3.2`; hardened `app/llm.py` for llama3.2 (tool calls detected even if
`finish_reason` isn't `tool_calls`, fallback without tools, longer timeout, readable Ollama
errors); anthropic SDK made optional; errors now include a plain-string `error` field.

Frontend: UI untouched. Added `package.json`, Tailwind/PostCSS/Next config, `jsconfig.json`;
`lib/api.js` now reads the backend's error format, reports an unreachable server clearly and
signs out on an expired token.

## Audit changes (summary)
- Calendar: deterministic half-open date ranges (`backend/app/date_range.py`); default event duration 60 min; idempotent creates.
- Chat history now uses the most recent messages; "Tomorrow?" follow-ups resolved from conversation context.
- Memory: secret guard, semantic-duplicate merge, offline-aware correction threshold.
- Search rewritten (keyword first, semantic labelled, filters, pagination, result links).
- Full-screen editor at `/editor/notes|documents/[id]` (BACK top-left, autosave, sanitised HTML).
- Nova detailed reports: `backend/app/doc_generation.py`.
- Tests: `cd backend && pip install -r requirements-dev.txt && python -m pytest -q` (previously reported 61 passing; re-run needed, see AUDIT_REPORT.md).
- Not done yet: real-SDK MCP verification, activity timeline, agent-tool permission audit.

## Proactive suggestions (API)
`GET /api/suggestions` (auth) returns read-only, rule-based suggestions (overdue/due-soon tasks, goal dates, calendar overlaps); `POST /api/suggestions/dismiss {"key": "...", "days": 7}` hides one (rule-based or AI) for that user.

### Compass AI suggestions
The dashboard's "Next up" also shows suggestions written by the configured LLM (`LLM_PROVIDER`), labelled **AI** in the UI.
- `GET /api/suggestions/ai` returns the cached result and never calls the model. `status` is `none`, `ready` (with `stale: true` if your data changed since), `unavailable` (with a `message`) or `disabled`.
- `POST /api/suggestions/ai/refresh` generates now (`{"force": true}` bypasses the cache). With a local model this can take a while; the dashboard calls it in the background.
- **Grounded:** the model only sees a snapshot of your open tasks, goals and upcoming events plus the rule-based findings, addressed by short aliases. Items that don't cite a real record are dropped. Nothing is created or changed; they are advice only.
- **Cached** per user, keyed on the snapshot and your local date. A failed generation is not retried for `AI_SUGGESTIONS_FAILURE_COOLDOWN_SECONDS`, so an offline Ollama isn't hit on every page load.
- If the model is unavailable, the rule-based suggestions still show. Set `AI_SUGGESTIONS_ENABLED=false` to turn the AI layer off.
- Privacy: the snapshot is sent to whichever provider `LLM_PROVIDER` selects (stays on your machine with Ollama).

## Destructive agent actions
`workspace_crud` delete returns `needs_confirmation` until called again with `confirm: true`.
