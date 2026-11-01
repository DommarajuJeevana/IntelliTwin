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
