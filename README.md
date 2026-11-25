# One Chatbot, Two Brands: MarkGrid.ai & Two99

One AI chatbot (one backend, one embeddable widget) that answers for both brands without mixing them.

## Live Demo

| Page | Link | Answers as |
|---|---|---|
| MarkGrid.ai | _link to be added_ | MarkGrid only |
| Two99 | _link to be added_ | Two99 only |
| Both brands | _link to be added_ | Either brand, with labelled answers |

On free hosting, the first request after a quiet period can take about a minute.

## Tech Stack

- **Backend:** Python, FastAPI
- **AI:** Google Gemini (Flash-Lite for chat, `gemini-embedding-001` for embeddings)
- **Vector database:** Qdrant, with BM25 keyword search as a fallback
- **Ingestion:** requests, BeautifulSoup
- **Widget:** vanilla JavaScript, Shadow DOM
- **Hosting:** Render (`render.yaml`)

## Architecture

```
MarkGrid page ─┐                          ┌─ Qdrant: markgrid_kb
Two99 page ────┼─ widget.js ── FastAPI ───┤
Combined page ─┘                          └─ Qdrant: two99_kb
```

Each question: find the brand → classify → search only that brand's collection → answer from the retrieved text →
check the answer for the other brand's name. Ingestion (crawl → clean → chunk → embed → upload) runs separately.

## How the Bot Tells the Sites Apart

- **Brand pages:** the widget sends `data-site`, and the server checks it against the request's `Origin`.
  A mismatch gets 403. The visitor's message can't change the brand.
- **Combined page:** a router (Gemini) finds the brand in each question. A single company named in the message
  overrides it. If the brand is unclear, the bot asks.

## How Each Brand's Knowledge Is Kept Separate

- Separate crawls and separate Qdrant collections; lines naming the other brand are removed.
- Each answer call gets only one brand's text.
- Separate brand profiles (`brands/*.json`).
- Every generated reply is checked: if it names the other brand, it is regenerated once, then replaced with a safe reply.

## Questions Across Brands and Guardrails

| Question | Brand pages | Combined page |
|---|---|---|
| About the other brand | Declines, links to the other site | Answers from that brand's data |
| Could apply to either ("What is your pricing?") | Current brand | Asks which company |
| Compare / which is better? | Describes the current brand only | Describes each, picks no winner |
| Are they related? | "MarkGrid is built by Two99." | Same |
| Greeting | Friendly reply with suggestions | Same |
| Off-topic or prompt injection | Politely declines | Same |
| Not in the knowledge base | Says it doesn't know, shares the contact link | Same |

## Setup

Requires Python 3.11+, a Gemini API key, and Windows PowerShell.

```powershell
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # set GEMINI_API_KEY; for local storage, leave QDRANT_URL empty
venv\Scripts\python -m ingestion.ingest --brand markgrid
venv\Scripts\python -m ingestion.ingest --brand two99
.\start.bat
```

Open http://localhost:5500 (MarkGrid), http://localhost:5501 (Two99) or http://localhost:5502 (both).
If ingestion stops with error 429, run it again with `--cached` after the limit resets.

Tests: `venv\Scripts\python -m pytest -q` (40 offline tests). Manual checks: `sample.md`.

## Deployment

Create a Render Blueprint from `render.yaml` and enter the keys it asks for. Set `BACKEND_URL` to the backend address, and
`ORIGIN_BRAND_MAP` to each page's address and site, such as `https://<backend>=combined` (the backend serves the
combined page at `/`).

## Known Limitations

- Knowledge is a snapshot, and not all extracted content is uploaded yet (Gemini free-tier limit).
- On Gemini's free tier, replies can be slow or rate limited at busy times.
- The router can misjudge a question that names neither brand.
- There is no rate limiting, and non-browser clients can fake `Origin`.
- AI checks reduce brand mixing and invented answers but can't guarantee zero.

More detail: [Documentation.md](Documentation.md)
