# Implementation spec: a support assistant that answers only from the company's own docs (RAG, Python + LangChain)

> The reasoning behind this project lives in internal planning notes that are not part of this repo. This file is the **spec to build from**. If something isn't covered here, or the real API behaves differently, log it under "Open decisions" in `docs/VERIFICATION.md`, then make the smallest change that keeps the original intent. Don't widen the scope.
> Code, comments, README, commit messages, and every file under `docs/` are in English.

---

## 0. Prerequisites (done by the user)
- `demo/.env` has `OPENAI_API_KEY` and `SLACK_WEBHOOK_URL` filled in.
- The user has agreed to install the §1.1 packages into `demo/.venv`.
- If any value is missing, only build the offline parts (`LLM_MODE=mock`, unit tests) and note in VERIFICATION.md what went untested.

## 1. Hard rules
1. **Packages:** install only what `requirements.txt` lists, into `demo/.venv`, with pinned versions (`==`). No global installs.
   - `langchain-core`, `langchain-text-splitters`, `langchain-community` (`PyMuPDFLoader`), `langchain-openai`, `langchain-chroma`, `chromadb`, `pymupdf`, `openai`, `python-dotenv`, `fastapi`, `uvicorn`, `httpx`, `pytest`
2. **Secrets** are never printed, logged, or written to any file that goes into git. Keys and webhook URLs in error messages are replaced with `***`.
3. **No `git push`** and no GitHub repo creation; the user decides. Local commits are fine.
4. **OpenAI usage:** development always runs with `LLM_MODE=mock` (`DeterministicFakeEmbedding` + fake chat replies). Real calls happen only in the §8.3 E2E run, with at most 2 full eval rounds. Mention it in the conversation before every live run.
5. **Fictional data:** the brand, products, and policies are all made up, and every document's header is marked `Fictional demo content`. No real brand names or real client documents.
6. **Numbers come from code:** result tables, question counts, and pass rates are all computed by `collect_results.py` from the run log. The LLM never produces any statistic.

## 2. File layout (final)
```
demo/
  README.md  requirements.txt  .env.example  .gitignore
  docs/  SPEC.md  SETUP.md  OPERATIONS.md  VERIFICATION.md
  knowledge/            # fictional brand documents (source for the live index)
  knowledge_updates/    # returns-policy v2 (for the E question; replaces v1 in knowledge/)
  scripts/
    make_docs.py        # generates the PDFs with PyMuPDF (including tables) + writes the Markdown
    ingest.py           # CLI: incremental indexing; --rebuild wipes and rebuilds
    ask.py              # CLI: ask one question; --mode grounded|baseline
    run_eval.py         # runs eval/questions.json; --mode grounded|baseline|both; --only A1,C3
    collect_results.py  # run log → output/results.md (comparison table)
    swap_returns_policy.py  # E question: switch v1↔v2
  app/
    config.py           # reads .env, defaults, masks secrets
    ingest.py           # load, split, chunk ids, incremental manifest (sha256)
    retrieve.py         # Chroma retrieval + relevance scores
    citations.py        # citation checks (pure functions)
    answer.py           # grounded chain: threshold → structured output → citation check → decision
    baseline.py         # naive chain
    handoff.py          # Slack notification (or SLACK_MODE=log writes jsonl)
    server.py           # FastAPI
    static/  index.html  compare.html  widget.css  widget.js
  eval/  questions.json  calibration.json
  tests/ test_citations.py  test_decision.py  test_ingest_manifest.py  test_schema.py  test_server.py
  output/  run-log/  results.md  handoff-log.jsonl   # not in git (keeps .gitkeep)
```

## 3. Fictional brand and documents
Brand: **Cinderpeak Outdoor (demo)**, which sells camp stoves, lanterns, coolers, sleeping bags, and power banks, and ships only to the US and Canada.

| File | Format | Key content (used by test questions) |
|---|---|---|
| returns-policy.pdf (v1) | PDF, 2 pages | 30-day returns, unused items only, refunds in 5–7 business days, fuel canisters can't be returned |
| knowledge_updates/returns-policy.pdf (v2) | PDF, 2 pages | Changed to **14 days**, everything else the same; the header shows v2's effective date |
| warranty.pdf | PDF, 3 pages, **with tables** | Warranty length per product line (stoves 3 years, lanterns 2 years, coolers 5 years, sleeping bags 1 year, power banks 1 year), exclusions, how to file a claim |
| shipping-rates.pdf | PDF, 2 pages, **with tables** | US/Canada shipping tiers, free shipping threshold (US$75), processing times |
| manual-ember-2-stove.pdf and other product manuals ×5 | PDF, 2–4 pages each | Specs, use, cleaning, common troubleshooting |
| faq.md | MD | Accounts, payment methods, order tracking |
| order-changes.md | MD | Orders can be changed within 1 hour, cancellation process |
| gift-cards-and-promos.md | MD | Gift cards don't expire, promo codes can't be combined |
| care-and-storage.md | MD | Care and storage |
| international-shipping.md | MD | US and Canada only; no other countries |
| spare-parts.md | MD | List of available spare parts (no prices) |

16 in total. **The answer to a trap question must never appear in any document.** After `make_docs.py` writes them, run a grep to confirm the C-category keywords (e.g. price match, rental, military, store location) don't appear, and record the result in VERIFICATION.md.

## 4. Ingest (`app/ingest.py`)
- PDF: `PyMuPDFLoader`, one Document per page, with metadata keeping `source` (relative filename) and `page` (1-based). MD: read the whole file with `page=None`, split by heading (`MarkdownHeaderTextSplitter`), and add `section` to the metadata.
- Chunking: `RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)`.
- **chunk id:** `{source}#p{page}#c{idx}` (MD uses `#s{section_slug}#c{idx}`). Deterministic, identical across reruns.
- **manifest:** `output/index-manifest.json` stores `{source: sha256}`. For new or changed files, delete that source's old chunks first, then add. Anything in the manifest but not on disk is deleted. Unchanged files aren't touched. The CLI prints the `added / updated / removed / unchanged` counts.
- Embedding: `OpenAIEmbeddings(model=EMBED_MODEL)`, default `text-embedding-3-small`. Mock mode uses `DeterministicFakeEmbedding(size=256)`, and each mode has its own Chroma directory (`output/chroma-live`, `output/chroma-mock`).

## 5. Answer flow
### 5.1 Retrieval (`app/retrieve.py`)
`similarity_search_with_relevance_scores(question, k=TOP_K)`, with `TOP_K` defaulting to 5. Returns `[{chunk_id, source, page, text, score}]`.

### 5.2 Grounded (`app/answer.py`)
1. Top score `< RELEVANCE_MIN` → **don't call the LLM**; `status=handoff`, `reason=low_relevance`.
2. Call the chat model (`CHAT_MODEL`, `temperature=0`) and use `with_structured_output` to get:
   ```json
   {"answerable": true, "answer": "...", "citations": [{"chunk_id": "...", "quote": "..."}]}
   ```
   Prompt rules (`app/prompts/grounded.md`): use only the provided passages; if they don't clearly contain the answer, return `answerable=false`; every fact needs a citation; a quote must be a continuous span of the passage text, at most 200 characters.
3. **Citation check** (`app/citations.py`, pure functions):
   - `chunk_id` must be in this request's retrieval results;
   - after normalizing (lowercase, collapse whitespace, unify quotes and dashes), `quote` must be a substring of that passage's normalized text;
   - length ≥ 12 characters (so a quote can't be just "the").
4. Decision (pure function `decide()`):
   | Condition | status | reason |
   |---|---|---|
   | `answerable=false` | handoff | model_declined |
   | `answerable=true` but 0 valid citations | handoff | no_valid_citation |
   | `answerable=true`, some citations invalid | answered | n/a (show only valid citations; log the invalid ones) |
   | `answerable=true`, all valid | answered | n/a |
5. When `status=handoff`, return the fixed message "I couldn't find this in our help documents, so I've passed your question to our support team." and call `handoff.notify()`.
6. **Errors:** OpenAI exceptions (`APIError`, `APIConnectionError`, `RateLimitError`, `NotFoundError`, a 20-second timeout) retry once. If it still fails → `status=degraded`, `reason=llm_error`, return the fixed message "Our assistant is having trouble right now. Your question has been sent to our support team." plus an alert. **The API returns 200, never 500.**

### 5.3 Baseline (`app/baseline.py`)
Same index and same `TOP_K`. The prompt is only "You are a helpful support assistant for Cinderpeak Outdoor. Use the context below to answer the customer's question." + passages + question. Plain text output, with no threshold, no structured output, no citation check, and no handoff. The README and portfolio both have to say this is **a simplified version I wrote myself**, used for comparison.

### 5.4 Handoff (`app/handoff.py`)
- Slack Incoming Webhook. The message includes the question, reason, top 3 retrieved passages (`source p.N` + first 160 characters), time, and `request_id`.
- With `SLACK_MODE=log` (the mock default), it only writes `output/handoff-log.jsonl`.
- A Slack failure can't make `/ask` fail: log it and respond as usual.

## 6. API and web pages (`app/server.py`)
| Method | Path | Description |
|---|---|---|
| POST | `/ask` | `{question, mode: "grounded"\|"baseline"}` → `{request_id, status, answer, citations:[{chunk_id, source, page, quote}], reason}`; a blank question or one over 1000 characters returns 422 |
| POST | `/handoff` | `{question, note?}`; the user clicks "Talk to a person" → Slack, `reason=user_requested` |
| GET | `/source/{chunk_id}` | Returns that passage's text and metadata, for "show source" |
| GET | `/health` | Index chunk count and mode (no secrets) |
| GET | `/` | `index.html`: a support widget (a bubble in the bottom right that opens up), sources listed under the answer with expandable text, a Talk to a person button, and a demo/fictional label in the footer |
| GET | `/compare` | `compare.html`: the same question side by side (baseline vs. grounded), for recording |

The front end uses only plain HTML/CSS/JS, with no CDN.

## 7. Evaluation
### 7.1 Questions (`eval/questions.json`)
```json
{"id": "A1", "category": "A", "question": "...",
 "expect": {"status": "answered", "facts": ["30 days"], "sources": [{"source": "returns-policy.pdf", "page": 1}]},
 "note": "..."}
```
| Category | Count | How it's scored (by code) |
|---|---|---|
| A: answer is in the docs | 8 | status=answered, every `facts` entry matches as a case-insensitive regex, and at least 1 valid citation points to one of the `sources` (when page is null, only the source is compared) |
| B: tables / exact numbers | 4 | Same as above, with exact-number regexes for facts (e.g. `\$75`, `\b5[- ]year`) |
| C: trap questions | 6 | grounded: status=handoff; baseline: see 7.2 |
| D: ambiguous, needs a person | 3 | status=handoff (e.g. "my stove broke, can I get a new one?" with no purchase date or description of the problem → a handoff is enough. If it's answered with valid citations, record it separately as "answered (acceptable)", counted as neither a pass nor a failure, and note it in VERIFICATION) |
| E: document update | 1 | Ask on v1 first (expect 30 days) → `swap_returns_policy.py v2` → `ingest.py` → ask again (expect 14 days, citing the v2 page). Ingest output must be `updated 1` with everything else unchanged |
| F: model error | 1 | Run one question with `CHAT_MODEL=gpt-does-not-exist` → status=degraded, and the handoff log or Slack has one `llm_error` entry; the next question with the normal model then succeeds |

### 7.2 Scoring the baseline on category C
The baseline is free text, so a rule judges it first: if it matches the decline regex (`don't have|do not have|no information|not (mentioned|specified|covered|included)|couldn't find|can't find|unable to (find|confirm)|contact (our )?support`), it's recorded as "declined"; otherwise "answered (made up)". **The user also checks each question by hand once.** The manual labels go in `eval/baseline-labels.json`; the result table uses the manual labels and lists the question IDs where the rule and the manual label disagree.

### 7.3 Threshold calibration
`RELEVANCE_MIN` is calibrated once, using only `eval/calibration.json` (6 questions: 3 with answers, 3 traps, **none overlapping questions.json**). The results and the chosen value go in VERIFICATION.md. It isn't tuned again during the real eval.

### 7.4 Output
- `run_eval.py` writes one line per question to `output/run-log/<timestamp>-<mode>.jsonl`: question, status, reason, answer, citations (with whether each is valid), retrieval scores, duration, and model name.
- `collect_results.py` produces `output/results.md`:
  - A comparison table, baseline vs. grounded: "correct with the right source (A+B)", "trap questions answered (C)", "correct handoffs (C+D)"
  - Per-question details
  - A header noting that the questions and documents are fictional, plus the question count, model name, and run date

## 8. Tests
### 8.1 Unit tests (`pytest`, mocked, no network)
- `test_citations.py`: substring, normalization (case, whitespace, curly quotes), chunk_id not in the retrieval results, quotes that are too short
- `test_decision.py`: every row of the §5.2 decision table; below the threshold the chat model isn't called (counted with a fake object)
- `test_ingest_manifest.py`: counts and chunk deletes/adds for new, changed, deleted, and unchanged files
- `test_schema.py`: structured output with missing fields or wrong types → treated as no_valid_citation, no exception
- `test_server.py`: `/ask` 422, degraded returns 200, `/handoff` still returns 200 when Slack fails, `/source` 404

### 8.2 Mock E2E
With `LLM_MODE=mock`: `ingest.py --rebuild` → `run_eval.py --mode both` runs to the end with correctly formatted files (scores aren't checked).

### 8.3 Live E2E (after the user agrees)
1. `ingest.py --rebuild` (live embeddings)
2. Calibrate `RELEVANCE_MIN` (§7.3)
3. `run_eval.py --mode both` → `collect_results.py`
4. The E and F questions
5. Use `/` and `/compare` in a real browser: expand a source, click Talk to a person → Slack receives it

## 9. Documentation
- `README.md` (English): what it is, an architecture diagram, how to run it, a link to the results table, and limits (fictional data, the baseline is a simplified version I wrote, features not built)
- `docs/SETUP.md`: venv, `.env`, ingest, starting the server
- `docs/OPERATIONS.md`: adding or replacing documents → `ingest.py`; tuning `RELEVANCE_MIN` and `TOP_K`; reading the handoff log; switching models
- `docs/VERIFICATION.md` (English): what was actually run at each step, the results, and open decisions
