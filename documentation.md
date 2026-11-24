# documentation.md — Complete Project Guide and Interview Preparation

**Project:** One AI chatbot, two brands (MarkGrid.ai and Two99), built with Retrieval-Augmented Generation (RAG).

**Labels used in this guide**

| Label | Meaning |
|---|---|
| **[Implemented]** | Exists in the code today |
| **[Measured]** | A number read from the project, the database or a test run (24 November 2026) |
| **[Estimate]** | My calculation, not a measurement |
| **[Improvement]** | Not built. Say "I would..." and never "I did..." |

**30-second summary to say first:**
"I built one RAG chatbot for two related brands, with one FastAPI backend and one JavaScript widget. In one chat window, a
router finds which brand the question is about, searches only that brand's Qdrant collection, and labels the answer; if
unclear, it asks. The same backend also runs as a single-brand bot on each website. Gemini answers only from retrieved text. A leak check blocks each brand's answer from naming the other, and a BM25 keyword search takes over if the
embedding service is unavailable."

---

# 1. Project Development – Step by Step

## 1.1 The problem
- Two brands need a chatbot: MarkGrid.ai and Two99. They are related (MarkGrid is built by Two99), so they are easy to mix up.
- Requirements: one chatbot (one backend, one widget), answers from each brand's own content, and no mixing.
- A plain LLM would not know private or recent facts, could invent them, and could mix the brands.
- **Why RAG:** it gives the LLM the right text at question time. Updating knowledge means re-ingesting, not re-training.

## 1.2 Stages in order

| Stage | What was done | Why |
|---|---|---|
| 1. Planning | README, architecture file, file layout | Agree the design before coding |
| 2. Configuration | `.env` for settings, JSON for brand text | No brand facts in the Python code |
| 3. Ingestion v1 | Crawl, clean, chunk, embed, upload; 60 pages per brand | Build the knowledge base |
| 4. Backend | Brand resolution, intent, retrieval, answer, leak check | The chat logic |
| 5. Widget and demo pages | One `widget.js`, two test sites | What visitors use |
| 6. Offline tests | Fake LLM, in-memory Qdrant | Test without keys or cost |
| 7. Provider change | OpenAI account had no credits, so moved to Gemini | Free tier |
| 8. Vector store | Local Qdrant, then Qdrant Cloud | Cloud is needed for deployment |
| 9. Quality fixes | Query rewriting, prompt rules, compare handling | Vague questions gave weak answers |
| 10. Ingestion v2 | Full crawl, boilerplate removal, resumable upload | 60 pages was too few |
| 11. Resilience | Keyword fallback, clear errors, OpenAI package removed | Daily limit broke the chat |
| 12. Combined window | One chat for both brands: router, labelled answers, "which company?" | "One chatbot for two brands, without confusion" (see 1.6) |

## 1.3 Architecture

```
 OFFLINE (run once per brand)
 website -> crawl -> clean -> save JSON -> dedupe -> chunk -> embed (Gemini) -> Qdrant collection

 ONLINE (every question)
 widget.js -> FastAPI /chat -> resolve brand -> classify intent
      -> fixed reply                                  (other brand, related, off-topic, injection)
      -> embed question -> Qdrant search -> top 5     (keyword search if embedding fails)
      -> Gemini answer -> leak check -> reply -> widget.js
```

**Two ways to use it** [Implemented]

| Mode | Port | Brand decided by |
|---|---|---|
| One window for both brands | 5502 | The router, from the question |
| One brand per website | 5500, 5501 | The server, from the Origin |

```
 COMBINED WINDOW (port 5502)
 question -> router: label + complete question
      -> one brand : search that collection -> labelled answer
      -> both      : each brand separately  -> two labelled answers
      -> compare   : each says what it does -> neutral introduction + two answers
      -> unclear   : "Which company do you mean?" + buttons
      -> greeting / related / off-topic / injection : fixed reply
```

Two separate pipelines are the key idea: **ingestion is slow and occasional; answering is frequent and must be fast.**

## 1.4 Current status [Measured]

| | MarkGrid | Two99 |
|---|---|---|
| Pages crawled | 512 (a site index page excluded) | 244 (217 after removing duplicates) |
| Chunks from the full crawl | 3,572 | 1,151 |
| New chunks saved in Qdrant | 960 | 0 |
| Points in Qdrant now | 1,235 (960 new + 275 from v1) | 203 (v1 only) |

Upload stopped at Gemini's free limit of 1,000 embeddings a day. **Be open about this in an interview**: it is a real
constraint, and the resumable upload was the response to it.

## 1.5 The assignment and how each requirement was solved

**The task:** one chatbot, one backend and one widget for MarkGrid.ai and Two99, without mixing them. The interviewer later
confirmed that one chatbot answers for both websites, and that the main challenge is keeping their content separate without
hallucinations. No video is needed.

| Requirement | How it was solved | Where | Status |
|---|---|---|---|
| Knowledge from each brand's public pages | Each site is crawled, cleaned, chunked and embedded separately | `ingestion/ingest.py` | Built; upload incomplete (1.4) |
| Knowledge clearly separated | Two collections (`markgrid_kb`, `two99_kb`); lines naming the other brand removed | Qdrant, `clean()` | Done |
| One deployment, one backend | One FastAPI app serves every page | `backend/main.py` | Built; not deployed |
| One widget for both sites | Same `widget.js`; only `data-site` differs | `widget/widget.js` | Done |
| Bot knows which site it is on | The server checks `data-site` against `Origin`; a mismatch gets 403 | `resolve_brand()` | Done |
| Two styled test pages | One page per brand, plus the combined page | `demo/` | Done locally; links pending |
| One chatbot for both brands (interviewer's reply) | Combined window with a router | `backend/combined.py` | Done |
| Questions about the other brand | Brand page: decline and link. Combined page: answer from that brand's data | `shared.json`, `combined.py` | Done |
| Questions that fit either brand | Brand page: current brand. Combined page: ask which company | `resolve_brand()`, `route()` | Done |
| Greetings and detailed questions | Intent or router label; retrieval for real questions | `classify()`, `route()` | Done |
| Decline unrelated questions | `off_topic` and `injection` labels get a fixed reply | `shared.json`, `combined.json` | Done |
| No mixing | One collection per answer, no history in combined answers, leak check | `pipeline.answer()` | Built; reduces the risk, can't guarantee zero |
| No hallucination | Answer only from retrieved text, otherwise "I don't know" and the contact link | `system_prompt` | Built; reduces the risk, can't guarantee zero |
| Short README, clean code, repository | Short README, small files, settings outside the code | `README.md`, GitHub | README done; check the latest code is pushed |
| Live demo | Deployment settings prepared | `vercel.json` | **Not done yet** |

## 1.6 From two ports to one chat window

### What changed

| | Before | Now |
|---|---|---|
| Pages | 5500 MarkGrid, 5501 Two99 | Both kept, **plus 5502 for both brands** |
| Backend | 8000 | 8000 (the same one) |
| Widget | `widget.js` | `widget.js` (the same file, unchanged) |
| Knowledge | Two collections | The same two collections |
| Brand chosen by | The website | On 5502, the question |

**Be exact in the interview:** the two ports were not merged. They were never two chatbots, only two test websites using one
backend. I added a third page whose window covers both brands. A visitor needs only 5502.

```
 BEFORE                                NOW
 5500 page -> MarkGrid only            5500 page -> MarkGrid only
                                       5501 page -> Two99 only
 5501 page -> Two99 only               5502 page -> router -> MarkGrid or Two99

 all pages -> the same widget.js -> the same backend on 8000
```

### Why two ports first
The assignment asks for two test pages, where each answers only as its own brand. The server knows the brand from the
browser's `Origin`, and a different port is a different origin. So two ports act like two websites on one computer.

### Why one window was added
The interviewer confirmed one chatbot answering for both websites. With one page, `Origin` can't say which brand a question is
about, so the brand must come from the question itself.

### How it was made, step by step

| # | Change | File | Reason |
|---|---|---|---|
| 1 | New page with `data-site="combined"` | `demo/combined/` | The single window |
| 2 | Added `http://localhost:5502=combined` to the allowlist | `.env` (`ORIGIN_BRAND_MAP`) | The server accepts the page |
| 3 | `SITES` = the brands + `combined` | `backend/config.py` | `combined` is a site, not a third brand |
| 4 | Router prompt, labels, replies, welcome text | `brands/combined.json` | No text in the code |
| 5 | `route()` finds the brand and rewrites the question | `backend/combined.py` | Replaces the job of `Origin` |
| 6 | Moved the answer steps into a shared `answer()` | `backend/pipeline.py` | Both modes use the same retrieval and leak check |
| 7 | `/chat` sends a brand to `pipeline.chat`, and `combined` to `combined.chat` | `backend/main.py` | One endpoint for every page |
| 8 | One more server line | `start.bat` | Starts 5502 |
| 9 | New tests (40 in total) | `tests/test_chat.py` | Check routing and separation |

**Not changed:** the widget, the Qdrant data and the brand pages. No new ingestion was needed.

### Why one window doesn't mix the brands
1. The router only **chooses**; it doesn't write the answer.
2. Only the chosen brand's collection is searched.
3. If one company is named, that name beats the router's choice.
4. The answer call gets no chat history, so earlier text about the other brand can't enter.
5. For two-brand questions, there are two separate answers, each labelled and leak-checked.
6. If unclear, the bot asks instead of guessing.

### Examples on 5502

| Question | Router label | Result |
|---|---|---|
| What is Model Share? | `markgrid` | Searches `markgrid_kb` only |
| What is Beetle? | `two99` | Searches `two99_kb` only |
| What is your pricing? | `unclear` | Asks, with two buttons |
| Compare MarkGrid and Two99 | `compare` | Two separate labelled answers |
| Give me a pasta recipe | `off_topic` | Declines |

### Checked and not checked
40 offline tests pass. About 20 real messages were sent to the combined window, and it was opened in a headless browser
(question, "which company?", button, answer). Not checked: the 32 questions in `sample.md`, and a live deployment.

### One-minute answer to say
"I first made two test pages on two ports, because each website must answer only as its own brand and the server reads the
brand from the origin. Both already used one backend and one widget. Then the interviewer confirmed one chatbot for both
websites, so I added one page and a router. The router finds the brand in the question, and from there I reuse the same
retrieval, answer and leak-check code. I didn't merge the data: the window is shared, but the knowledge is still separate."

---

# 2. File-by-File Explanation

## 2.1 Map

```
backend/__init__.py        checks the Python environment
backend/config.py          settings, brands, text helpers
backend/clients.py         Gemini and Qdrant access
backend/keyword_search.py  BM25 fallback
backend/pipeline.py        single-brand chat logic and the shared answer()
backend/combined.py        one window for both brands
backend/main.py            HTTP endpoints
ingestion/ingest.py        the whole offline pipeline
brands/*.json              brand data, prompts, replies
widget/widget.js           chat widget
demo/<brand>/              test pages
tests/test_chat.py         offline tests
```

Dependency direction: `main -> combined -> pipeline -> (clients, keyword_search) -> config`. Ingestion reuses `clients` and
`config`, so both pipelines use the same embedding model and the same brand rules.

## 2.2 `backend/__init__.py` [Implemented]
- Runs when the `backend` package is imported.
- Uses `importlib.util.find_spec` to check for four key packages. If one is missing, it stops with the correct command.
- **Why:** the project was started with global Python by mistake and gave a confusing `ModuleNotFoundError`.

## 2.3 `backend/config.py` [Implemented]

| Name | Responsibility |
|---|---|
| `env` | `os.environ.__getitem__`; a missing setting raises `KeyError` when read, instead of silently using a default |
| `num(key, cast)` | Reads a setting as a number |
| `SHARED`, `BRANDS` | Load `shared.json` and every other file in `brands/` |
| `ORIGINS` | Turns `origin=brand` pairs into a dictionary; splits from the right, because a URL could contain `=` |
| unknown-brand check | Stops startup if an origin points to a brand that doesn't exist |
| `others(brand)` | All other brands |
| `leaks(brand, text)` | True if the text matches another brand's regex |
| `search_text(brand, text)` | Adds the brand name and removes other brands' names before searching |
| `fill(brand, template)` | Fills prompts and replies with brand details |

**Interaction:** every other module imports it. `leaks()` is used in three places: ingestion, keyword index and output.

## 2.4 `backend/clients.py` [Implemented]

| Name | Responsibility |
|---|---|
| `GeminiError` | Custom exception. `busy=True` means a limit or overload, so trying later can help |
| `http()` | One cached `httpx.Client` with base URL, timeout and bearer token; reuses connections |
| `call_gemini(path, body, retries)` | POST with retries. Retries 429, 5xx and network errors with waits of 1, 2, 4... up to 8 seconds. Stops at once on a "per day" limit or errors such as a bad key |
| `qdrant()` | Cached client: cloud if `QDRANT_URL` is set, otherwise a local folder |
| `embed(texts, retries)` | Returns one vector per text, and fails if the counts differ |
| `complete(model_key, system, messages)` | One chat completion |

**Why `lru_cache`:** creates one client per process, on first use. Tests can replace it.

## 2.5 `backend/keyword_search.py` [Implemented]

| Name | Responsibility |
|---|---|
| `words(text)` | Lowercase, split, remove stopwords |
| `query_words(text)` | Adds synonyms to the question only (call -> phone) |
| `labels(text)` | Adds the word "phone" or "email" when a text shows a number or address |
| `index(brand)` | Reads all that brand's chunks from Qdrant, once, and counts words |
| `search(brand, query, limit)` | BM25 ranking; uses the home page for vague questions |

Constants: `K1=1.5`, `B=0.75` (standard BM25), `LABEL_WEIGHT=5`.

## 2.6 `backend/pipeline.py` [Implemented]

| Function | Responsibility |
|---|---|
| `resolve_brand(site, origin)` | Looks up the Origin; the claimed site must agree |
| `classify(brand, messages)` | Small LLM call, returns one of 7 labels; unknown output becomes `brand` |
| `retrieve(brand, query)` | Embeds the question and searches; falls back to keywords |
| `chat(brand, message, history)` | Single-brand flow; returns `(intent, reply)` |
| `answer(brand, message, history, intent)` | Retrieval, Gemini answer, leak check. Used by both modes |

### `backend/combined.py` [Implemented]

| Function | Responsibility |
|---|---|
| `mentioned(text)` | Brands named in the text (regex) |
| `route(messages)` | One Gemini call returning `label \| standalone question`. Unknown label becomes `unclear`. One company named in the message beats the router's brand choice |
| `answer(brand, question)` | Calls `pipeline.answer` with **no history**, removes other brand names from the question, adds the brand label |
| `chat(message, history)` | One brand; `both` and `compare` (each brand answered separately in parallel threads); `unclear` (buttons); fixed replies |

**Why rewrite the question?** "What results has it delivered?" makes sense only with history. A complete question means the answer
call needs no history, so one brand's text can't enter the other brand's answer.

## 2.7 `backend/main.py` [Implemented]

| Item | Responsibility |
|---|---|
| `Turn`, `ChatRequest` | Pydantic models. Roles may only be `user` or `assistant`, so a client can't send a `system` message |
| CORS middleware | Allows only configured origins |
| `require_brand` | Returns 403 on mismatch |
| `GET /health` | Liveness check |
| `GET /widget.js` | Serves the widget |
| `GET /config` | Brand name, color, welcome, suggestions, limits |
| `POST /chat` | Trims history, calls the pipeline, maps errors: Gemini error -> 503, anything else -> 500 |

- At startup, a background thread loads the keyword indexes (`preload`).

Endpoints are normal `def`, not `async def`, so FastAPI runs them in a thread pool and blocking calls don't stop the event loop.

## 2.8 `ingestion/ingest.py` [Implemented]

| Function | Responsibility |
|---|---|
| `page_key(url)` | Same key for http/https and trailing slash |
| `clean(brand, soup)` | Extracts useful lines, removes other-brand lines |
| `crawl(brand)` | Breadth-first crawl that yields pages |
| `dedupe(brand, pages)` | Drops duplicate pages and moves repeated lines into one site-wide page |
| `chunk(text)` | Fixed-size chunks with overlap |
| `to_rows(brand, pages)` | Chunks plus metadata; adds the page title; sorts core pages first |
| `upload(brand, rows)` | Embeds and saves in batches, resumable |
| `__main__` | Options `--brand`, `--dry-run`, `--cached` |

## 2.9 Brand files [Implemented]
- `markgrid.json`, `two99.json`: name, collection, URL, contact, `terms` (regexes), color, tone, relation, welcome,
  suggestions, `topics`, `skip_pages`, `listing_pages`.
- `shared.json`: intents, prompts, replies, errors, stopwords, synonyms, patterns.
- **Why JSON:** changing a brand's text needs no Python change. Adding a third brand needs a JSON file, an origin
  entry and an ingestion run. The relation text was written for two brands and would need review.

## 2.10 `widget/widget.js` [Implemented]
- One self-running async function, no framework.
- `document.currentScript` gives the API address (the script's own origin) and `data-site`.
- Calls `/config`; if rejected, shows nothing.
- **Shadow DOM** isolates its CSS from the host website.
- Uses `textContent` and `append`, so a reply can't inject HTML (prevents XSS).
- Keeps history in page memory and sends the last 6 messages.

## 2.11 Other files
- `demo/<site>/index.html`, `config.js`: three test sites (markgrid, two99, combined) and the backend address.
- `brands/combined.json`: router prompt, labels, replies.
- `tests/test_chat.py`: 40 tests [Measured].
- `start.bat`: starts everything with the correct Python.
- `vercel.json`: backend deployment settings. **Deployment has not been tested.**
- `sample.md`: 32 manual checks. `explain.md`, `README.md`, `architecture_structural.md`: documents.

## 2.12 Execution flow between files

```
Startup:  uvicorn -> backend/__init__ -> main -> pipeline -> clients, keyword_search -> config -> .env + brands/*.json
Page:     demo/index.html -> widget.js (GET) -> GET /config
Question: widget -> POST /chat -> main.require_brand -> pipeline.chat
             -> classify -> clients.complete -> Gemini
             -> retrieve -> config.search_text -> clients.embed -> Gemini -> Qdrant
                              (GeminiError -> keyword_search.search -> chunks cached from Qdrant)
             -> clients.complete -> Gemini -> config.leaks -> reply
```

---

# 3. Technical Implementation

## 3.1 Technologies

| Technology | Version [Measured] | Role | Why | Alternatives |
|---|---|---|---|---|
| Python | 3.11.9 | Language | Strong AI ecosystem | Node.js, Go |
| FastAPI | 0.165.0 | API | Validation, speed, simple | Flask, Django |
| Uvicorn | 0.54.0 | ASGI server | Standard for FastAPI | Hypercorn |
| Pydantic | 2.14.4 | Request validation | Built into FastAPI | marshmallow |
| httpx | 0.28.1 | Calls Gemini | Small, testable (MockTransport) | `openai` or `google-genai` SDK |
| Gemini Flash-Lite | `gemini-3.5-flash-lite` | Intent and answers | Free tier; most reliable in tests | GPT, Claude, Llama |
| Gemini embeddings | `gemini-embedding-001` | Vectors | Same key; accepts batches | OpenAI, Cohere, BGE, E5 |
| Qdrant | client 1.20.0 | Vector database | Free cloud tier, local mode, payloads | Chroma, Pinecone, pgvector, FAISS |
| requests | 2.34.2 | Crawling | Simple | Scrapy, Playwright |
| BeautifulSoup + lxml | 4.15.0 + 6.1.3 | HTML parsing | Simple, tolerant | trafilatura, readability |
| python-dotenv | 1.2.4 | `.env` loading | Standard | pydantic-settings |
| pytest | 9.2.0 | Tests | Fixtures, parametrize | unittest |
| Vanilla JS + Shadow DOM | – | Widget | One tag, isolated | React, iframe |

**LangChain / LlamaIndex were not used.** The pipeline is small, and direct code is easier to debug and explain.

**Chroma versus Qdrant:** both store vectors and metadata. Chroma is fine locally, but the target host (Vercel) has no
persistent disk, so a hosted database is needed. Qdrant supports both local and cloud with one client.

## 3.2 RAG pipeline

### Step 1 – Document ingestion [Implemented]
- Breadth-first crawl from the brand URL, same host only. BFS reaches main pages before deep articles.
- Follows `robots.txt` and its crawl delay: `max(CRAWL_DELAY=1s, robots delay)`. Two99 asks for 3 seconds.
- Removes `#fragment` and `?query` from links. Request timeout 30 seconds.
- `skip_pages` are never fetched; `listing_pages` are followed for links but not stored.
- Limit: 1,000 pages. Pages under 200 characters are ignored.
- **Sitemaps were not used**, because Two99's `robots.txt` lists suspicious sitemap files that resemble SEO spam.

### Step 2 – Preprocessing [Implemented]
1. Add email and phone values hidden in `mailto:` and `tel:` links.
2. Remove `script, style, nav, header, form, noscript, svg`.
3. Keep the footer: MarkGrid's office addresses are only there.
4. Normalise spaces, drop repeated lines on the page, and drop lines naming the other brand.
5. Save the text to `data/extracted/<brand>.json`.

### Step 3 – Deduplication [Implemented]
- Same page by `page_key`; same text under different addresses keeps the shortest address.
- A line on more than 30% of pages (and more than 5 pages) is boilerplate. It is stored once as a site-wide page.

### Step 4 – Chunking [Implemented]
- **Fixed-size character chunks with overlap:** size 1,800, overlap 250, step 1,550.
- Chunks after the first on a page start with the page title, so they keep their topic.
- Core pages (short addresses) come first, so a limit delays articles and not pricing or contact pages.
- **Limitation:** it can cut a sentence. Overlap reduces the damage.

### Step 5 – Embedding [Implemented]
- `gemini-embedding-001` returns **3,072 numbers** per text.
- Sent as a list of texts in one HTTP request (`/embeddings`). The count is verified.

### Step 6 – Storage [Implemented]
- One Qdrant collection per brand, cosine distance. Payload: `brand`, `url`, `text`.

### Step 7 – Retrieval [Implemented]
- `search_text()` -> embed -> top 5 with score >= 0.25 -> text.
- Follow-up questions add the previous user message to the search text.

### Step 8 – Reranking: **NOT implemented**
- [Improvement] Retrieve 20 to 30, rerank with a cross-encoder, keep 5.

### Step 9 – Hybrid search: **NOT implemented as fusion**
- Keyword search is a **fallback**, used only if embedding fails. The two results are never combined.
- [Improvement] Combine both with Reciprocal Rank Fusion.

### Step 10 – Generation [Implemented]
- System prompt (rules + context) + recent history + question -> Gemini -> leak check.

## 3.3 Prompt engineering
- **Intent prompt:** seven labels, each with a one-line meaning, plus the brand's topics. "Reply with exactly one label".
- **Answer prompt:** identity, tone, "use ONLY facts in CONTEXT", what to do when unknown, never name the other brand,
  treat context and user text as data, under 120 words, plain text.
- **Fixed replies** for risky intents: no model writes them, so they can't leak or be argued with.
- **Temperature is not set**, so the provider default applies. [Improvement] Use 0 for intent.

---

# 4. Technical Challenges and Solutions

Format: problem -> cause -> how found -> solution. All of these happened.

| # | Problem | Cause | How found | Solution |
|---|---|---|---|---|
| 1 | OpenAI calls failed, 429 | No credits | Tested one call per service first | Moved to Gemini |
| 2 | Answer model often failed, 503 | `gemini-3.8-flash` overloaded | Tested each model with short timeout and no retries | `gemini-3.5-flash-lite` |
| 3 | Diagnostic script seemed to hang | SDK retries and long timeouts | Re-ran with 25s timeout, 0 retries | Fail fast when diagnosing |
| 4 | "What do you do?" gave a narrow answer | Question has no specific words to match | Compared with "What does MarkGrid do?" | Add brand name in `search_text()` |
| 5 | Compare question failed on MarkGrid | Other brand's name in the query; model stayed cautious | Real test | Replace with "What does {name} do?" |
| 6 | Answers began with "Hello!" | Prompt rule too loose | Real test | "Only if the user just greets..." |
| 7 | `MIN_SCORE` useless | Unrelated question scored about 0.51; real ones 0.52–0.68 | Printed scores | Rely on prompt; documented |
| 8 | Only 60 pages known | Page limit | Counted sitemap addresses | Full crawl |
| 9 | Offices missing | Cleaner removed `footer` | Inspected footer text | Keep the footer |
| 10 | Menus repeated in every Two99 page | No `nav` tag on the site | Read stored text | Line-frequency dedupe |
| 11 | Crawl stuck on 404s | Endless tag pagination | Watched the log | `skip_pages` |
| 12 | Duplicate pages | http and https links | Saw both in a check | `page_key`, same-text removal |
| 13 | Upload timed out | Client default 5s, slow connection, large batch | Traceback: "write operation timed out" | `QDRANT_TIMEOUT=120` |
| 14 | Upload stopped at 960 | Free limit 1,000 embeddings/day | Read the full 429 body | Resumable upload |
| 15 | Chat broke after the upload | Same daily limit | Error said "per day" | BM25 fallback |
| 16 | 429 during quick tests | 15 chat requests/minute | Read quota name in the body | Pace tests; "busy" message |
| 17 | "What is Beetle?" was off-topic | Intent model didn't know product names | Real test | `topics` in the prompt |
| 18 | Phone number not found | Page says "HR Contact", not "phone" | Printed ranked chunks | `patterns` labels, `synonyms` |
| 19 | `No module named 'openai'` | Global Python used | Path in the traceback | `venv`, `start.bat`, startup check; package removed |
| 20 | Port 8000 in use | Another backend running | Found the owning process | Stop it; start one way only |
| 21 | Old error after a fix | Backend not restarted | Traceback line numbers didn't match the code | Restart |
| 22 | First combined answer took 99 seconds | Partly the keyword index download from Qdrant, 23.5 s for MarkGrid; the rest was not profiled | Timed the index alone; search takes 4 ms | Load at startup |
| 23 | "CEO of both" read as a relationship question | Router label definitions overlapped | Real test | Clearer definitions |
| 24 | "Compare" and "Which is better?" gave weak answers | The router gave no usable question, and the answer prompt refuses comparisons | Read the replies | `compare` label: ask each brand what it does, with a neutral introduction |

## 4.1 Debugging approach to describe
1. Reproduce with the smallest call.
2. Isolate the layer: embed, chat, Qdrant, HTTP, widget.
3. Read the full response body: "per day" and "per minute" need different fixes.
4. Print intermediate data: scores, chunks, intent.
5. Fix the cause, add a test, retest with real calls.

## 4.2 Optimisations [Implemented]
Cached clients, connection reuse, fixed replies that skip retrieval, resumable upload, boilerplate removal, no retries on
hopeless errors, zero embedding retries in chat so the fallback starts quickly.

---

# 5. In-Depth Technical Details

## 5.1 Number sheet (memorise)

| Item | Value | Type |
|---|---|---|
| Chunk size / overlap / step | 1,800 / 250 / 1,550 characters | Implemented |
| Overlap share | 250 / 1,800 = 13.9% | Calculated |
| Chunks, full crawl | 3,572 + 1,151 = **4,723** | Measured |
| Chunks, first version | 275 + 203 = 478 | Measured |
| Chunk length, MarkGrid | min 327, median 1,865, mean 1,757, max 1,930 characters | Measured |
| Chunk length, Two99 | min 311, median 1,847, mean 1,696, max 1,901 characters | Measured |
| Text before / after dedupe, MarkGrid | 6.02M / 5.28M characters | Measured |
| Text before / after dedupe, Two99 | 2.14M / 1.67M characters | Measured |
| Embedding model / dimension | `gemini-embedding-001` / 3,072 | Measured |
| Embedding batch | **32 chunks per request** | Implemented |
| Pause between batches | 30 seconds | Implemented |
| Batches for a full upload | 112 (MarkGrid) + 36 (Two99) = 148 | Calculated |
| Time per batch | about 35 seconds including the pause | Measured |
| Distance | Cosine | Implemented |
| Top-K / minimum score | 5 / 0.25 | Implemented |
| Reranker | None | – |
| History | 6 messages (not 6 pairs) | Implemented |
| Message limit | 1,000 characters | Implemented |
| Answer limit | Under 120 words (prompt) | Implemented |
| Gemini timeout / retries | 60 s / 3 (0 for question embedding) | Implemented |
| Qdrant timeout | 120 s | Implemented |
| Written answer time | roughly 2–15 seconds normally; 53–118 seconds for both-brand answers while Gemini was returning 503 | Measured, small sample |
| Free limits seen | 1,000 embeddings/day, 15 chat requests/minute | From error messages |
| Tests | 40 automated, 32 manual checks | Measured |

A chunk can exceed 1,800 characters because the page title is added after splitting.

## 5.2 Answers to the specific questions

**What chunk size and overlap, and why?**
- 1,800 and 250 characters. Roughly 450 tokens and 60 tokens [Estimate, 4 characters per token].
- Large enough to hold a full idea, small enough to stay on one topic, and well below the embedding input limit.
- Overlap keeps a sentence cut at a boundary complete in one of the chunks.
- **Honest point:** these were reasonable starting values, not the result of a tuning experiment.

**Why characters and not tokens?** Simple and needs no tokenizer dependency. Downside: token count varies by text.

**What batch size for embeddings?** 32 chunks per request. The first design used 64; it was reduced for the free tier.
Batching reduces network round trips. The 30-second pause limits requests and tokens per minute. Each text in the batch
appears to count as one request towards the daily limit (960 saved chunks plus a few others reached 1,000).

**How does text become numbers?** The chunk is sent to the model. It splits text into tokens, runs a neural network, and
returns 3,072 floating-point numbers representing meaning. Texts with similar meaning have nearby vectors.

**Why this model?** Same key as the LLM, free tier, accepts a list of texts. The newer `gemini-embedding-2` merged a list
into one vector, per Google's documentation, so it wasn't suitable for this code.

**Are document and query task types used?** No. [Improvement] Gemini's native API supports task types for documents and queries.

**How are vectors stored?** Qdrant point = ID + 3,072-float vector + payload. About 12 KB per raw vector (3,072 x 4 bytes),
so about 58 MB raw for 4,723 [Estimate]. No quantization.

**What index is used?** Qdrant supports **HNSW**, and the collection has defaults `m=16`, `ef_construct=100`. But
`indexed_vectors_count` is **0** [Measured]: the collections are small (below the indexing threshold of 10,000 KB per
segment), so Qdrant currently does an **exact full scan**. That is accurate and fast enough at this size. HNSW would be
built when segments grow past the threshold.

**Which similarity?** Cosine: compares direction, not length. `cos(a,b) = a.b / (|a||b|)`.

| Method | Meaning | Note |
|---|---|---|
| Cosine | Angle | Good default for text |
| Dot product | Angle and length | Same ranking as cosine if vectors have length 1 |
| Euclidean | Straight-line distance | Same ranking as cosine if vectors have length 1 |

**Top-K?** 5. More gives better recall but more noise, tokens and delay. Not tuned by experiment.

**Metadata filters?** Not used. Brands are separated by **collection**, which is stronger: forgetting a filter can't leak
data. The payload holds `brand` as a label only. No payload index exists [Measured].

**How are chunk IDs managed?** `uuid5(namespace, model + url + text)`. The same input always gives the same ID:
- Already stored chunks are skipped (no repeat cost).
- Changed text gets a new ID; the old ID is deleted only after all new chunks are saved.
- The model is part of the ID, so a model change re-embeds. The collection must be recreated if dimensions differ.

**How is context passed?** Each chunk is written as `[url]` then its text, joined by blank lines, inside the system prompt
after `CONTEXT:`. History and the question follow as normal messages.

**How are token limits handled?**
- 5 chunks x about 1,865 characters = about 9,300 characters, or about 2,300 tokens [Estimate].
- Message and history entries are cut to 1,000 characters, and history to 6 messages.
- Answer length is limited by instruction. No `max_tokens` and no token counting. [Improvement] Add both.

**Accuracy?** Brand name in the query, boilerplate removal, titles on chunks, keyword fallback, "use only CONTEXT".
There is **no automated retrieval metric** yet.

**Latency?** Each written answer needs three Gemini calls in sequence (intent, embedding, answer) plus Qdrant.

---

# 6. Complete Workflow: one question

Example: a visitor on MarkGrid asks **"How much is MarkGrid Go in India?"**

| # | Component | Action | Data |
|---|---|---|---|
| 1 | Browser | Page loads `widget.js` | – |
| 2 | Widget | `GET /config?site=markgrid` | Name, color, suggestions |
| 3 | Widget | `POST /chat` | `site`, `message`, `history` |
| 4 | Browser | Adds `Origin` header | `http://localhost:5500` |
| 5 | FastAPI | CORS and Pydantic checks | 422 if invalid |
| 6 | `resolve_brand` | Origin -> markgrid, equals `site` | 403 if not |
| 7 | `classify` | Gemini returns `brand` | Label |
| 8 | `search_text` | "MarkGrid.ai: How much is MarkGrid Go in India?" | Query |
| 9 | `embed` | Gemini returns 3,072 numbers | Vector |
| 10 | Qdrant | Cosine search in `markgrid_kb` | Up to 5 chunks |
| 11 | `fill` | Builds the system prompt with context | Prompt |
| 12 | `complete` | Gemini writes the answer | Text |
| 13 | `leaks` | Checks for Two99 | Regenerate once if needed |
| 14 | FastAPI | Returns JSON | `reply`, `intent` |
| 15 | Widget | Shows "₹50,000 per month" with `textContent` | – |

**Other paths**

| Situation | What happens |
|---|---|
| "What does Two99 do?" on MarkGrid | Intent `other_brand` -> fixed reply with link |
| "Hi" | Answer model without retrieval |
| Compare | Replaced by "What does MarkGrid.ai do?", history cleared |
| Embedding limit | Keyword search |
| No chunks | Contact fallback |
| Leak twice | Contact fallback |
| Gemini busy | 503 and "I'm a little busy" |
| Wrong origin | 403 |

---

## 6.2 Combined window: one question

"What is your pricing?" in the window for both brands:

| # | Component | Action |
|---|---|---|
| 1 | `route` | Gemini returns `unclear` |
| 2 | `chat` | Replies "Which company do you mean: MarkGrid.ai or Two99?" with two buttons |
| 3 | Visitor | Clicks "MarkGrid.ai" |
| 4 | `route` | `markgrid \| What are your pricing plans?` (from the history) |
| 5 | `answer` | Searches `markgrid_kb` only, leak-checks, adds the label |
| 6 | Widget | Shows "MarkGrid.ai: ..." |

# 7. Interview Questions and Answers

## 7.1 Introduction

**Q1. Explain the project in two minutes.**
Use the 30-second summary, then add: full-site crawl, 4,723 chunks planned, Gemini embeddings (3,072), Qdrant with one
collection per brand, top 5 cosine search, intent routing, leak check, keyword fallback, 40 tests, and a combined window with a brand router.

**Q2. What was your role? Did you use AI tools?**
Answer truthfully. If you used an AI coding assistant, say so, then show you understand every decision, number and trade-off.

**Q3. What is RAG?** Retrieve relevant text, give it to the LLM, generate an answer grounded in it.

**Q4. Why RAG and not fine-tuning?** Facts change, sources must be controllable, and re-ingesting is cheaper. Fine-tuning
is better for style or format than for changing facts.

**Q5. Why one backend for two brands?** One codebase to maintain; isolation through collections, prompts and server checks.

**Q6. What is the hardest part?** Guaranteeing separation between two related brands, and staying available under provider limits.

## 7.2 Data ingestion

**Q7. How do you collect data?** Polite BFS crawler over public pages.
**Q8. Why BFS?** Main pages are found before deep articles.
**Q9. Do you respect robots.txt?** Yes, rules and crawl delay.
**Q10. JavaScript-rendered pages?** Not supported. The crawled pages returned text as HTML. [Improvement] Playwright.
**Q11. How do you avoid loops?** A `seen` set with normalised keys, same host, page limit.
**Q12. Why not use sitemaps?** Two99's listed suspicious files; link following was safer.
**Q13. How would you refresh data?** Re-run ingestion; only changed chunks are embedded. [Improvement] Schedule it, use ETag or lastmod.
**Q14. What about PDFs and images?** Not handled. [Improvement] PDF parser and OCR.
**Q15. What happens if a page fails?** Logged and skipped. [Improvement] Retry queue.

## 7.3 Preprocessing

**Q16. How do you remove boilerplate?** Tags first, then lines appearing on over 30% of pages.
**Q17. Why keep it once?** It can hold real facts, such as addresses and certifications.
**Q18. Why remove lines naming the other brand?** So the model never sees that content. Cost: some true facts are lost, such as text about the relationship.
**Q19. How do you detect duplicates?** Normalised address and exact text. [Improvement] MinHash for near-duplicates.

## 7.4 Chunking

**Q20. Which strategy?** Fixed 1,800 characters, 250 overlap, page title added.
**Q21. Why overlap?** To keep ideas that cross a boundary. Too much wastes storage and returns near-identical chunks.
**Q22. What if chunks are too small or large?** Small: lost context. Large: mixed topics, weaker match, more tokens.
**Q23. Other strategies?** Sentence, recursive, heading-aware, semantic, parent-child. [Improvement] Heading-aware first.
**Q24. How would you tune it?** Build a question set, test several sizes, compare recall@5 and answer correctness.
**Q25. How many chunks would 10,000 characters create?** Starts at 0, 1550, ... while below 9,750: **7 chunks**.
**Q26. Why does the loop stop at length minus overlap?** So the last chunk isn't just text already in the previous one.

## 7.5 Embeddings

**Q27. What is an embedding?** A list of numbers representing meaning.
**Q28. Dimension, and does higher mean better?** 3,072. Not always: more storage and slower search. Google's documentation shows smaller sizes can score comparably.
**Q29. Can you change the embedding model later?** Yes, but all content must be re-embedded. Vectors from different models can't be compared.
**Q30. Why batch?** Fewer requests. Batch 32 was chosen for free-tier limits.
**Q31. What if one batch fails?** Earlier batches are already saved. The next run continues.
**Q32. How do you check the response?** Vector count must equal text count, otherwise an error.
**Q33. Were vectors normalised?** The code doesn't normalise them. Qdrant handles cosine, so length doesn't affect ranking.

## 7.6 Vector database

**Q34. Why Qdrant?** Local and cloud with one client, payloads, free tier.
**Q35. Qdrant, Chroma, Pinecone, FAISS, pgvector?** Qdrant: self-hosted or cloud. Chroma: easy locally. Pinecone: managed.
FAISS: a library, not a database. pgvector: good if Postgres is already used.
**Q36. What is HNSW?** A layered graph for fast approximate search. `m` = links per node, `ef_construct` = build effort, `ef` = search effort.
**Q37. Is HNSW active in your project?** Not currently. `indexed_vectors_count` is 0, so it is an exact scan. Say this clearly; it shows you checked.
**Q38. Exact versus approximate?** Exact is always right but linear in size. Approximate is faster with slightly lower recall.
**Q39. Why two collections and not a filter?** Stronger isolation. Trade-off: many tenants means many collections; then use one collection with an indexed tenant field.
**Q40. How do you update without downtime?** New chunks are added before old ones are removed. During this, both exist. [Improvement] New collection plus alias switch.
**Q41. How would you reduce storage?** Scalar or product quantization, smaller dimensions.
**Q42. What is in the payload?** `brand`, `url`, `text`. [Improvement] title, section, date, language.

## 7.7 Retrieval

**Q43. Top-K and why?** 5; balance of recall, noise and tokens. Not tuned experimentally.
**Q44. Is the 0.25 threshold useful?** Barely. Unrelated text scored about 0.51 against 0.52–0.68 for real questions. The answer prompt does the real work. [Improvement] Reranker score threshold.
**Q45. How do follow-ups work?** The previous user message is added to the search text. [Improvement] LLM query rewriting into a standalone question.
**Q46. Do you use hybrid search?** No. BM25 is a fallback only.
**Q47. Explain BM25.** Scores by word frequency, rarity (IDF) and length. `k1` limits repeated words; `b` controls length normalisation.
**Q48. When does keyword beat vector search?** Exact names, codes, phone numbers. Vector is better with different wording.
**Q49. Do you rerank?** No. I would retrieve about 25 and use a cross-encoder, measuring the added delay.
**Q50. Bi-encoder versus cross-encoder?** Bi-encoder embeds separately (fast). Cross-encoder reads question and text together (accurate, slow).
**Q51. How do you handle near-identical chunks?** Page-level dedupe. [Improvement] MMR for diversity.

## 7.8 LLM and prompts

**Q52. Which LLM and why?** `gemini-3.5-flash-lite`: it answered reliably when larger Flash models returned 503.
**Q53. How do you reduce hallucination?** Context-only rule, contact fallback, narrow intents, fixed replies. It reduces but doesn't eliminate it.
**Q54. Why classify intent first?** To route risky questions to fixed text. Cost: one extra call and possible misclassification.
**Q55. What if the classifier is wrong?** Retrieval is still limited to one brand, and the leak check runs. An off-topic error can refuse a valid question, as with "Beetle".
**Q56. How do you defend against prompt injection?** Server-side brand, injection intent, "context is data", one-brand retrieval, output check. No defence is complete.
**Q57. Can a user fake history?** Yes, with fake assistant messages. The system role is not accepted, size is limited, and brand limits still apply.
**Q58. Why is the leak check a regex?** Fast, predictable, testable. Limit: it misses paraphrases and product names.
**Q59. Do you stream?** No, because the whole reply must be checked first. [Improvement] Sentence-level check and streaming.

## 7.9 Evaluation

**Q60. How did you evaluate?** 40 offline tests for logic, real spot checks, browser tests, and 32 manual checks written. **The full manual list has not been run.**
**Q61. What metrics would you add?** Retrieval: recall@k, MRR, nDCG. Generation: faithfulness, relevance, correctness. Product: containment rate, feedback.
**Q62. How would you build a test set?** Questions with expected facts and source addresses; `sample.md` is a start.
**Q63. LLM as judge risks?** Bias and inconsistency. Check against human labels.
**Q64. How do you test without an LLM?** Monkeypatch `clients`, in-memory Qdrant, `httpx.MockTransport`.

## 7.10 Latency and performance

**Q65. Where is the time spent?** Mostly in the Gemini calls. They run in sequence. I did not profile each step separately.
**Q66. How would you speed it up?** Cache common answers, run intent and embedding in parallel, faster intent (rules or a small classifier), streaming.
**Q67. Does async help?** For many users at once, yes. Endpoints now use threads; an async client would handle more waiting calls.
**Q68. Is keyword search fast?** It scores every chunk in Python. Fine for a few thousand; use an inverted index or Qdrant sparse vectors beyond that.

## 7.11 Scalability

**Q69. What breaks first?** Gemini limits: at 2 chat calls per answer and 15 per minute, about 7 answers a minute on the free tier.
**Q70. How would you serve 1,000 users?** Paid tier, several workers, cache, queue, rate limits, monitoring.
**Q71. 100 brands?** Single collection with tenant filter and index, brand config in a database.
**Q72. Is the backend stateless?** Yes for conversations, since the widget sends history. Each process has its own keyword cache.

## 7.12 Error handling

**Q73. What if Gemini is down?** Retry with growing waits; then 503 and a friendly message. Embedding failure uses keywords.
**Q74. Why not retry a daily limit?** It can't succeed, and delays the user.
**Q75. What if Qdrant is down?** 500 and a generic message. No fallback. [Improvement] Local snapshot of chunks.
**Q76. 429 versus 503?** 429: too many requests from you. 503: service overloaded or unavailable.

## 7.13 Security

**Q77. Can Origin be faked?** Yes, outside browsers. It stops other websites using the widget, not direct API calls.
**Q78. CORS versus authentication?** CORS is a browser rule, not authentication.
**Q79. How are secrets handled?** In `.env`, git-ignored; never sent to the browser. [Improvement] A secrets manager and key rotation.
**Q80. How is XSS prevented?** `textContent` and `append`; links must start with http(s); `rel="noopener"`.
**Q81. Is there rate limiting?** No. [Improvement] Per IP and per session.
**Q82. Privacy?** On the free tier Google may use prompts to improve products, so use a paid tier for real visitors. The app has no conversation storage.
**Q83. Can website content attack the bot?** Yes, indirect prompt injection. Content is treated as data and limited to the brand's own site.

## 7.14 Deployment

**Q84. How would you deploy?** Vercel for backend and two pages, Qdrant Cloud for vectors. Configured, **not tested**.
**Q85. Risks on Vercel?** Package size, function time limits against multi-second LLM calls, cold starts, read-only disk.
**Q86. Alternatives?** Docker on Cloud Run, Render or Fly.io.
**Q87. What would you monitor?** Latency, error rate, 429 count, fallback rate, leak-check hits, "don't know" rate.
**Q88. CI/CD?** Not built. [Improvement] Run pytest on each push.

## 7.15 Scenario questions

**Q89. The bot says "I don't know" though the page has the answer.**
Check in order: is the chunk in Qdrant? is it retrieved in the top 5? does it contain the fact? does the prompt block it?
**Q90. Answers are outdated.** Re-run ingestion; check old chunks were removed.
**Q91. The bot names the other brand.** Check the `terms` regex, stored chunks, then add a failing test.
**Q92. Chat fails right after ingestion.** Check the limit message; this happened here. Separate quotas or schedule ingestion.
**Q93. Retrieval is good but answers are bad.** Prompt, model, context order or too much context.
**Q94. Costs double.** Check retries, context size, Top-K, number of calls per question, duplicate ingestion.
**Q95. You changed the embedding model and search is poor.** Mixed vectors; recreate and re-ingest.
**Q96. A fix doesn't work.** Confirm the process was restarted. Mismatched traceback lines revealed this here.
**Q97. A third brand is added.** New JSON, origin entry, ingest; review `relation` and prompts; add tests.
**Q98. The user asks in Hindi.** Not tested. The models are multilingual, but keyword search and stopwords are English.

## 7.16 Deep follow-ups

**Q99. Why uuid5 and not uuid4?** uuid5 is repeatable, so uploads can resume and avoid duplicates.
**Q100. Why save after each batch?** A failure loses at most one batch. The first version embedded everything before saving.
**Q101. What if the process stops between embed and save?** That batch is embedded again.
**Q102. Race conditions?** Two ingestions for one brand could delete each other's chunks. [Improvement] A lock.
**Q103. Why does the keyword index need a restart?** It is cached once per process.
**Q104. Why is the classifier given all messages?** To understand follow-ups.
**Q105. What would you do with one more week?** Finish the upload, build an evaluation set, add hybrid search and reranking, rate limiting, deploy.
**Q106. Biggest weakness?** No automated quality evaluation, incomplete upload, untested deployment.
**Q107. What did you learn?** Check provider limits early, isolate layers when debugging, and design uploads to resume.

---

## 7.17 One chatbot, two brands

**Q108. Why are there three links if it is one chatbot?** They are test websites. All use the same backend and widget.
**Q109. How does one window avoid confusion?** A router picks the brand, only that collection is searched, the answer is labelled, and unclear questions are asked back.
**Q110. Why ask instead of guessing?** A wrong brand's price is worse than one extra question.
**Q111. What if the router is wrong?** A company named in the message overrides it. If no name is given, it can be wrong. [Improvement] Measure routing accuracy on a labelled set and use a confidence score.
**Q112. Why not search both collections and let the LLM choose?** The LLM would see both brands' text and could mix them.
**Q113. How are comparisons answered?** Each brand is answered separately, from its own data. The bot doesn't pick a winner.
**Q114. Why no history in the answer call?** The router already rewrote the question, and history could carry the other brand's text.
**Q115. Cost of the router?** It replaces the intent call, so a one-brand answer has the same number of calls. Both-brand answers need 5 Gemini calls (1 router, 2 embeddings, 2 answers), or more if a reply is regenerated.
**Q116. How would you add a third brand?** A JSON file, an origin entry and ingestion. The router reads brands from JSON; the relation text and comparison wording need review.
**Q117. How did you move from two ports to one?** I didn't merge them. I added a third page (5502) to the same backend, with a router that finds the brand in the question. The first two pages remain for the assignment.
**Q118. Why did you need different ports locally?** A port is part of the origin, so different ports act like different websites. When deployed, the domains do this job.
**Q119. Why not merge the two collections for the combined window?** One collection would make mixing easier. Separate collections mean a search can't return the other brand's points.
**Q120. Is it ready for production?** It is a working prototype. Remaining: deploy, finish the upload, add rate limiting, and measure routing and answer quality.

# 8. Implemented versus Possible Improvements

| Area | Implemented | Possible improvement |
|---|---|---|
| Crawl | HTML, robots, BFS | Playwright, PDF, schedule |
| Chunking | Fixed size, overlap, titles | Heading-aware, semantic, parent-child |
| Embedding | 3,072 dimensions, batch 32 | Task types, smaller dimensions |
| Brand routing | Origin, or one LLM router call + name check | Routing accuracy test, confidence score |
| Search | Vector, BM25 fallback | Hybrid fusion, MMR |
| Reranking | None | Cross-encoder |
| Filters | Separate collections | Date, language, section |
| Context | Fixed top 5 | Token budget, compression |
| Evaluation | Unit tests, manual list | Recall@k, faithfulness, judge model |
| Safety | Intents, leak check, server brand | Guard model, product-name checks |
| Operations | Local run, Vercel config | CI, monitoring, rate limits, cache |

# 9. Last-minute revision
- 1,800 / 250 characters; batch 32; 30 s pause; 3,072 dimensions; cosine; Top-K 5; minimum score 0.25.
- 4,723 chunks planned; 1,438 points stored now (1,235 + 203), of which 478 are from v1.
- Two collections, no filters, no reranker, no fused hybrid search, exact scan at present.
- Combined window: router labels are markgrid, two99, both, compare, unclear, greeting, related, off_topic, injection.
- 3 Gemini calls per written answer: intent or router, embedding, answer. 5 for both brands.
- Ports: 5502 both brands, 5500 MarkGrid, 5501 Two99, 8000 backend. Ports were added, not merged (1.6).
- The window is shared; the knowledge is separate.
- 40 automated tests. Not tested: Vercel, full manual list, load.
