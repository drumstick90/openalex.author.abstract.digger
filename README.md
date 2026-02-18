# OpenAlex Author Abstract Digger

Fetch all available abstracts for any author using OpenAlex + PubMed and talk to them with AI-powered analysis.

**Requires Python 3.11** (use `pyenv` or `.python-version`).

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/openalex.author.abstract.digger.git
cd openalex.author.abstract.digger

# Install dependencies (includes Gemini for AI analysis)
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements-rag.txt

# Add your API key
echo "GEMINI_API_KEY=your_key_here" > .env

# Run
python3.11 app.py
```

Open http://localhost:5001

## Get a Gemini API Key

→ https://aistudio.google.com/apikey

## Deployment

For production on a VPS (e.g. DigitalOcean droplet):

1. Run the setup script on the server: `deploy/setup-droplet.sh`
2. Deploy from your machine: `./deploy.sh user@your-droplet-ip`
3. Ensure `.env` with `GEMINI_API_KEY` exists on the server

See `deploy/` for Caddyfile, systemd service, and gunicorn config.

## Have fun
