# coffee

AI-powered coffee bean recommendation app.

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL

## Setup

### Backend

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Copy env file and fill in values
cp .env.example .env
```

Required `.env` values:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `GOOGLE_API_KEY` | Gemini API key |
| `BRAVE_API_KEY` | Brave Search API key |

### Frontend

```bash
cd frontend
npm install
```

## Running locally

Open two terminals:

```bash
# Terminal 1 — backend (port 8000)
uvicorn app.main:app --reload

# Terminal 2 — frontend (port 5173)
cd frontend
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

The frontend proxies `/api/*` requests to the backend, so no extra CORS configuration is needed during development.

## Running tests

```bash
# Unit tests
pytest

# Integration tests (requires .env with real API keys)
pytest --integration
```
