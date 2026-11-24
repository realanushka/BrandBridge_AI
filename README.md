# One Chatbot, Two Brands: MarkGrid.ai & Two99

One AI chatbot (one backend, one embeddable widget) that answers for both brands without mixing them.

## Live Demo

| Page | Link | Answers as |
|---|---|---|
| MarkGrid.ai | _add after deployment_ | MarkGrid only |
| Two99 | _add after deployment_ | Two99 only |
| Both brands | _add after deployment_ | Either brand, with labelled answers |

## Tech Stack

- **Backend:** Python, FastAPI
- **AI:** Google Gemini (Flash-Lite for chat, `gemini-embedding-001` for embeddings)
- **Vector database:** Qdrant, with BM25 keyword search as a fallback
- **Ingestion:** requests, BeautifulSoup
- **Widget:** vanilla JavaScript, Shadow DOM

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

Requires Python 3.11+ and a Gemini API key. Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # then set GEMINI_API_KEY

# Build the knowledge bases (once)
venv\Scripts\python -m ingestion.ingest --brand markgrid
venv\Scripts\python -m ingestion.ingest --brand two99

# Start the backend and the three pages
.\start.bat
```

Open http://localhost:5500 (MarkGrid), http://localhost:5501 (Two99) or http://localhost:5502 (both).

Data is stored locally unless `QDRANT_URL` is set. Gemini's free tier limits embeddings per day; if ingestion
stops with error 429, run it again with `--cached` after the reset.

Tests: `venv\Scripts\python -m pytest -q`

## Known Limitations

- Knowledge is a snapshot, and the full upload of both sites is still in progress.
- On Gemini's free tier, replies can be slow or rate limited at busy times.
- The router can misjudge a question that names neither brand.
- There is no rate limiting, and non-browser clients can fake `Origin`.
