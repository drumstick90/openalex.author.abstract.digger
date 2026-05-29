# Biomedical Abstract Explorer

Fetch a researcher’s publications from [OpenAlex](https://openalex.org) (with optional PubMed fallback), then explore and question their abstracts with AI.

**Requires Python 3.11+**

## Quick start

```bash
git clone https://github.com/drumstick90/openalex.author.abstract.digger.git
cd openalex.author.abstract.digger

python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements-rag.txt

cp .env.example .env
# Edit .env — add at least one LLM API key (see below)

# UI (recommended): build frontend, then run backend
cd frontend && npm install && npm run build && cd ..
python app.py
```

Open **http://localhost:5001**

### API keys

Put keys in `.env` (never commit this file):

| Variable | Provider |
|----------|----------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |

You need **at least one**. The app lets you pick provider and model in the UI.

Optional: `FLASK_SECRET_KEY` for sessions (defaults to a dev value).

## Development

Two terminals:

```bash
# Terminal 1 — API on :5001
source venv/bin/activate
python app.py

# Terminal 2 — Svelte UI on :5173 (proxies /api to Flask)
cd frontend && npm run dev
```

Use **http://localhost:5173** while developing.

Without Node: `python app.py` still works and serves `index.legacy.html` if `frontend/dist` is missing.

## CLI (no web UI)

```bash
python main.py --email you@example.com --author "Jane Doe" --output works.jsonl
```

## Deployment

On a VPS: `deploy/setup-droplet.sh`, then `./deploy.sh user@your-host`.  
Ensure `.env` with your API keys exists on the server. See `deploy/` for Caddy, systemd, and gunicorn.
