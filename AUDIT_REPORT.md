# IntelliTwin – Continuation Audit & Implementation Report

## Environment of this session (verified)
- No Git repository in the uploaded ZIP (no history/commits to inspect).
- Sandbox had **no network**: `pip install` and `npm ci` failed (name resolution). No Python packages
  (pytest, fastapi, motor, pydantic, bleach, mcp…) and no `node_modules` were available.
- No MongoDB or Ollama available.
- **Therefore: backend tests and `next build` could NOT be run.** The earlier "61 passing / build OK"
  claim remains **unverified**.
- What WAS verified: every `.py` file compiles (`py_compile`), files named in the brief exist
  (`date_range.py`, `doc_generation.py`, `memory/echo.py`, `routers/search.py`, `mcp/echo_server.py`, tests).

## Architecture (from reading the tree)
FastAPI + Motor/MongoDB backend (`backend/app`), Next.js 14 frontend; agents Echo/Atlas/Compass/Nova
via `orchestrator.py`, `routers/agents.py`, tool modules in `app/tools/`; Echo memory in `memory/`;
search in `routers/search.py`; sanitiser in `sanitize.py`.

## Changes made this session
1. `app/mcp/echo_server.py`: dispatch extracted into SDK-independent `run_tool()`; exception text is no
   longer returned to MCP clients (previously `str(exc)`), only logged; non-object arguments rejected.
2. `requirements-mcp.txt` (`mcp>=1.2,<2`) and `requirements-dev.txt` added.
3. `tests/test_mcp.py` added (3 tests, **written but not executed**).
4. README: MCP/test instructions corrected.

## Update after user ran tests locally (verified by user output)
- Frontend `npm run build` (Next.js 14.2.15): compiled, type-checked, 23/23 pages incl. `/editor/[module]/[id]`.
- Backend: `python -m pytest -q --ignore=tests/test_mission_control_regressions.py` -> **64 passed** (61 earlier + 3 MCP dispatch tests), Python 3.14.5, pytest 9.1.1.
- `tests/test_mission_control_regressions.py` exists only in the user's local project (not in the ZIP I received) and fails to
  import `_resolve_short_calendar_followup` from `app.routers.agents`. **Unresolved**: local code and ZIP differ.

## Verified by user (round 2): 93 of 94 passed; 1 failure caused by my change
`test_update_and_delete_only_target_event`: moving a start time left the old end behind, and my new end>start check rejected it.
Fixed: updating `startsAt` without `endsAt` now preserves the event's duration (default 60 min). Added a regression test. Re-run needed.
`test_mission_control_regressions.py` no longer appears in collection locally (94 collected); `_resolve_short_calendar_followup`
exists nowhere in the code (only `_is_date_followup` in `workspace_actions.py`).

## Changes in this round (written, NOT yet run - run the suite)
- `app/tools/workspace_universal.py` (shared CRUD used by all four agents):
  delete now requires `confirm: true` (otherwise returns `needs_confirmation`, nothing deleted); delete verifies the record was removed;
  calendar *update* now rejects end <= start (naive/aware datetimes normalised); `status` filter accepts plain strings only;
  tags cleaned (<=20 strings, <=50 chars); model-supplied `agent` limited to known agents.
- `tests/test_agent_tools.py` (new): registry per agent, validation, cross-user isolation on every module, delete confirmation,
  failed-insert never reports success, tool-execution error normalisation.
- `tests/test_calendar.py`: the one delete call now passes `confirm: True`.
- Phase F: `app/suggestions.py`, `app/routers/suggestions.py` (`GET /api/suggestions`, `POST /api/suggestions/dismiss`), wired in `main.py`;
  `tests/test_suggestions.py` (new). Read-only: overdue / due today / due soon tasks, goal target dates, overlapping events
  (half-open), one aggregate "tasks without due date"; user timezone; dismissals (default 7 days) per user; never writes workspace records.
  Limitations: no frontend widget yet; date-only dues are stored as midnight UTC and read as that calendar date; capped at 500 records and 20 suggestions.

## Phase status (honest)
| Phase | Status |
|---|---|
| A baseline audit | Partial – static only; tests/build not runnable here |
| B agent tool audit | Shared CRUD hardened + tests written (not yet run). Orchestrator/agents.py loop limits and per-agent prompts not re-audited |
| C Echo memory | Not re-verified; secret guard exists in `memory/safety.py` (static read only) |
| D MCP | Code adapted/hardened; **not started against a real SDK**. Pinned `<2` per the 1.x decorator API – unverified |
| E Memory Timeline | Not audited |
| F Proactive suggestions | Backend implemented + tests written (not yet run); no UI yet |
| G Security review | Partial static findings below |

## Security findings (static reading, unconfirmed by tests)
- FIXED: MCP server leaked raw exception text to clients.
- `llm.py:289` includes `str(exc)[:200]` of a tool failure in the message fed back to the model; low risk,
  but could surface internal details into prompts/UI. Unresolved.
- `generic_crud.py:49` returns `str(exc)` with a 413 (message is the sanitiser's fixed text) – acceptable.
- `sanitize.py` uses a bleach allow-list (no `script`, no inline styles, http/https/mailto only) – looks sound.
- `memory/safety.py` card-number regex may reject long numeric strings (false positives); intentionally conservative.
- Not reviewed in depth: ownership filters in `generic_crud.py`, `workspace.py`, `search.py`; ObjectId validation;
  doc-generation filename handling; tool-call loop limits in `llm.py`.

## Remaining work (next session, with network)
1. `pip install -r requirements-dev.txt && python -m pytest -q`; `cd frontend && npm ci && npm run build`. Record results.
2. Phase B tests per agent (ownership, invalid args, DB failure).
3. Real MCP check: `pip install -r requirements-mcp.txt`, start server, list/call tools with the SDK client.
4. Phase E/F, remaining Phase G items above.


---
# Round 3 - Phases C, E, G (code + tests written; NOT yet run - run `python -m pytest`)

## Phase C - Echo memory (read from source; behaviour of extraction/dedupe/supersede code left unchanged)
Existing and kept: extraction + "is this worth remembering" filters, semantic merge threshold 0.93, evolution/supersede flow
(old memory kept with `status: superseded`, `supersededBy`), offline-aware thresholds, soft-delete/restore, consolidation, secret guard in `remember()`.
Defects found and fixed:
1. **Raw embedding vectors were returned** by memory search/recent/archived/update/restore, by every generic REST module
   (list/get), and by the shared agent CRUD tool - i.e. to the browser, into model prompts and through MCP.
   Fix: `doc_out`/`docs_out` (app/serialization.py) now drop `embedding`. Internal code reads raw Mongo docs, so ranking is unaffected.
2. **Secret guard covered only `remember()`.** Memories could be created/edited with passwords/keys via `PUT/POST /api/memory` and
   `echo.update_memory` (agent + MCP tool). Fix: `reject_secret_memory()` (memory/safety.py) now used in generic memory create/update and `update_memory`.
3. `update_memory` accepted any importance value: now clamped 1-5, non-numeric rejected.
4. Embedding-dimension changes silently produced score 0: `vector_store.search` now logs a warning with counts of mismatched records.
   (Re-embedding existing records after changing EMBEDDING_DIM/model is still a manual step - unresolved.)
Thresholds were not changed.

## Phase E - Memory Timeline
Before: page listed `/memory` (everything mixed, archived/superseded indistinguishable), showed titles only (no details), delete only.
Now: new `GET /api/memory/timeline?view=all|active|superseded|archived` (labels each item `lifecycle`, includes the title of the
replacing memory for superseded ones, ownership-scoped); page shows status, importance, details, "Replaced by ..." note,
inline Edit (PUT /api/memory/{id} with `expectedUpdatedAt` -> 409 handled, list refreshed), Restore for archived, Delete (permanent, confirmed).
Frontend verified only by a tag-balance check here; **run `npm run build` and click through it.**

## Phase G - security review (static + tests)
| Area | Result |
|---|---|
| Auth / ownership | All generic CRUD, shared agent CRUD, memory, search, suggestions queries filter on the authenticated user id. Tests cover cross-user read/update/delete/list. |
| Malformed IDs | Invalid ObjectIds return 404/error everywhere inspected. |
| Query injection | Shared tool `status` accepts strings only; search regexes use `re.escape`. |
| Rich text | bleach allow-list; scripts, handlers, javascript: URLs, iframes/img removed (test added); links get rel=noopener. |
| Tags | Generic PUT accepted any JSON as tags -> now validated (<=20 short strings); same helper in shared tool. |
| Embeddings exposure | FIXED (see C.1). Universal search already stripped them. |
| Secrets in memory | FIXED on all write paths (C.2). |
| Error disclosure | MCP no longer returns exception text (round 1). Remaining: `llm.py` feeds `Type: message[:200]` of tool exceptions back to the model. |
| Destructive actions | Agent delete needs `confirm: true` (round 2); memory REST delete is permanent after UI confirm; archive/restore exists. |
| Tool loops | `AGENT_MAX_TOOL_TURNS=6` and `AGENT_MAX_CONSECUTIVE_TOOL_FAILURES=2` exist in config/llm.py (read, not load-tested). |
Unresolved / not verified: no live auth/JWT tests (no test client in suite); CORS and JWT secret strength depend on your `.env`;
doc-generation filename handling was not re-reviewed; no rate limiting; `generic_crud` list endpoints have no pagination;
MCP not exercised against a real SDK; no live MongoDB/Ollama runs.
