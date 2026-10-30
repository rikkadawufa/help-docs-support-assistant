# Support assistant that only answers from your help docs (Python RAG)

A customer support assistant that answers questions from a company's own help documents, shows the file and page each answer comes from, and hands the question to a person when the documents don't cover it.

This is a **portfolio project built from public job briefs**. The store ("Cinderpeak Outdoor"), its 16 help documents and every test question are made up. It has not been used with real customers.

## What it does

1. **Retrieves** the closest passages from the help docs (LangChain + Chroma, OpenAI embeddings).
2. **Screens out clearly off-topic questions** with a relevance floor. Below it, the model is never called.
3. **Answers in a fixed format**: `answerable`, `answer`, and `citations` (passage ID + quote), using OpenAI structured output.
4. **Checks every quote in code.** A quote counts only if every sentence in it appears word for word in a passage that was actually retrieved. Layout punctuation (a colon after a heading, the `|` between table cells) is ignored; the words are not.
5. **Hands off** when the model says the docs don't answer it, or when no quote survives the check: the customer gets a fixed reply, and the team gets a Slack message with the question and the closest passages.
6. **Doesn't crash** when the AI service fails: the API still returns 200 with a fallback reply, and Slack gets an alert.

```
question -> retrieve (Chroma) -> relevance floor -> OpenAI structured answer -> quote check -> answer + sources
                                      |                     |                       |
                                      +---------------------+-----------------------+--> hand off: fixed reply + Slack
```

Re-indexing only touches changed files. Each file's SHA-256 is kept in a manifest, so editing one PDF re-embeds that file and nothing else.

## Test results (made-up data)

21 fixed questions, run against this assistant and against a deliberately simple RAG written for comparison (same index, a one-line prompt, no relevance floor, no quote check, no handoff). The counts come from `scripts/collect_results.py`, not from the model.

| What was checked | Simple RAG | This assistant |
|---|---|---|
| Answerable questions (12): correct answer | 12/12, no sources shown | 12/12, each with a checked quote from the right file and page |
| Trap questions (6), on topics the docs never mention: answered anyway | 4/6 | 0/6 |

- The simple RAG's answers to the trap and account questions were labeled by a person (`eval/baseline-labels.json`). Its four answered traps read like policies that don't exist, for example "we do not offer price matching".
- The 3 account-specific questions (a double charge, a missing order, a dented stove) were all handed off.
- **These numbers come from the third round on the same questions.** Round 1 answered only 4 of 12 because the relevance floor was set too high. Round 2 answered 9 of 12; the remaining misses were table rows and headings quoted with different punctuation. Each fix was a general change (prompt rules, quote check, table handling), but all three rounds used the same 21 questions. The run logs for all three rounds are in [`results/`](results/), and the full record is in `docs/VERIFICATION.md`.

Two scenario tests, also live:

- **Document update**: the returns window changed from 30 to 14 days. Re-indexing reported `updated 1, unchanged 15`, and the answer changed from 30 to 14 days.
- **AI failure**: with a model name that doesn't exist, the API returned a fallback reply, Slack got an alert, and the next question was answered normally.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # macOS/Linux: .venv/bin/python
cp .env.example .env                                          # add OPENAI_API_KEY, optionally SLACK_WEBHOOK_URL
.venv/Scripts/python scripts/make_docs.py                     # generate the made-up documents
.venv/Scripts/python scripts/ingest.py                        # mock mode by default, no API calls
.venv/Scripts/python scripts/serve.py                         # http://127.0.0.1:8010
```

For real answers, set `LLM_MODE=live` in `.env` (or run `serve.py --live`), then run `ingest.py --rebuild` once. `/compare` shows the simple RAG and this assistant side by side.

See [docs/SETUP.md](docs/SETUP.md) for setup and [docs/OPERATIONS.md](docs/OPERATIONS.md) for adding documents, tuning, and reading the handoff log.

## Tests

```bash
.venv/Scripts/python -m pytest -q                              # 34 unit tests, no network
LLM_MODE=live .venv/Scripts/python scripts/run_eval.py --mode both
.venv/Scripts/python scripts/collect_results.py                # writes output/results.md
```

## What it doesn't do

- No per-user document permissions, and no SharePoint or Google Drive connectors.
- Not embedded in a real website, WhatsApp, or a help desk tool. The `/ask` API is where that would connect.
- No order or account lookup. Questions about a specific order are handed off.
- No OCR for scanned PDFs, no multiple languages, no conversation memory.
- Runs on localhost only. It has not been deployed.

## Running this for your own team

This repo runs a demo for a made-up store on localhost. Putting it to work for a real support team takes more:

- Hosting the API somewhere reachable, and adding the chat widget to your site or help desk
- Loading your own documents, including any scanned PDFs that need OCR first
- Writing the answer rules and the handoff reply for your business
- Building a test set from your real customer questions and checking the scores before launch
- Deciding who can see which documents, if that differs by person or team
- Keeping it working when your documents, OpenAI or Slack change

This is the part I do for clients.

## Project layout

```
app/          ingest, store, answer chain, quote check, handoff, FastAPI, static widget
app/prompts/  grounded.md (the rules the model follows), baseline.md
knowledge/    the 16 made-up help documents that get indexed
eval/         questions.json, calibration.json, baseline-labels.json
results/      run logs from the three live rounds and the scenario tests
scripts/      make_docs, ingest, ask, serve, run_eval, collect_results, swap_returns_policy
tests/        pytest
docs/         SPEC, SETUP, OPERATIONS, VERIFICATION
```

## License

Copyright © 2026 rikkadawufa. All rights reserved. No license is granted to use, copy, modify, or distribute this code.
