# Setup

## 1. Python environment

Python 3.12 is what this was tested on.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

On macOS or Linux, use `.venv/bin/python` wherever this guide says `.venv/Scripts/python`.

## 2. Settings (`.env`)

Copy `.env.example` to `.env`. Never commit `.env`; it's already in `.gitignore`.

| Setting | What it does | Default |
|---|---|---|
| `OPENAI_API_KEY` | Needed for `LLM_MODE=live` | empty |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook for handoffs and alerts | empty |
| `LLM_MODE` | `mock` uses fake embeddings and canned replies (no API calls). `live` uses OpenAI | `mock` |
| `SLACK_MODE` | `log` only writes `output/handoff-log.jsonl`. `slack` also posts to Slack | `log` |
| `CHAT_MODEL` | OpenAI chat model | `gpt-4o-mini` |
| `EMBED_MODEL` | OpenAI embedding model | `text-embedding-3-small` |
| `TOP_K` | Passages retrieved per question | `5` |
| `RELEVANCE_MIN` | Relevance floor. Questions below it are handed off without calling the model | `0.39` |

Mock and live keep separate indexes (`output/chroma-mock`, `output/chroma-live`), so switching modes doesn't mix embeddings.

## 3. Documents and index

```bash
.venv/Scripts/python scripts/make_docs.py      # writes the made-up documents to knowledge/
.venv/Scripts/python scripts/ingest.py         # embeds new or changed files only
.venv/Scripts/python scripts/ingest.py --rebuild   # deletes the index and embeds everything again
```

To use your own documents, put PDF or Markdown files in `knowledge/` instead and skip `make_docs.py`.

## 4. Start the server

```bash
.venv/Scripts/python scripts/serve.py                  # settings from .env
.venv/Scripts/python scripts/serve.py --live --slack   # override: real OpenAI + Slack
```

- `http://127.0.0.1:8010/`: the chat widget on a sample help page
- `http://127.0.0.1:8010/compare`: the simple RAG and this assistant, side by side
- `http://127.0.0.1:8010/health`: index size and current mode

## 5. Check it works

```bash
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/ask.py "How long is the cooler warranty?"
```

In live mode the second command should answer "5 years" with a citation to `warranty.pdf` page 2.
