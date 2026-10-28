# Operations guide

For the person who keeps the assistant running after handover. No code changes are needed for anything on this page.

## Add, change or remove a document

1. Put the PDF or Markdown file in `knowledge/` (or replace or delete the old one).
2. Run:
   ```bash
   .venv/Scripts/python scripts/ingest.py
   ```
3. Check the summary line. Editing one file should say `updated 1` and leave everything else `unchanged`.

The server reads the index on each question, so there's no need to restart it.

Tips that help answers:
- One topic per heading. In Markdown, `##` headings become sections, and the answer cites the section name.
- Keep tables as real tables in the PDF. Each row is stored as one line (`Coolers | Glacier 45 | 5 years`), so the assistant can quote a whole row.
- Scanned PDFs (images of text) are not read. Export them as text PDFs first.

## Questions that should be answered but get handed off

Open `output/handoff-log.jsonl`. Each line has the question, a `reason`, and the IDs of the closest passages.

| reason | What it means | What to try |
|---|---|---|
| `low_relevance` | No passage was close enough, so the model was never called | If the answer is in the docs, lower `RELEVANCE_MIN` a little (for example 0.39 to 0.35), or reword the document so it uses the words customers use |
| `model_declined` | The model read the passages and found no answer | Usually correct. If the answer is there, make it explicit in the document |
| `no_valid_citation` | The model answered, but its quote didn't match the passage | Look at the passage. Unusual formatting can cause this |
| `user_requested` | The customer pressed "Talk to a person" | Nothing to fix |
| `llm_error` | The OpenAI call failed | Check the API key, billing and model name |

## Change the rules the assistant follows

The rules are plain English in `app/prompts/grounded.md`, for example "silence is not a no" and "account-specific questions go to a person". Edit the file, then rerun the eval to check nothing got worse:

```bash
LLM_MODE=live .venv/Scripts/python scripts/run_eval.py --mode grounded
.venv/Scripts/python scripts/collect_results.py
```

## Re-check the relevance floor

After a big change to the documents, check the floor again:

```bash
LLM_MODE=live .venv/Scripts/python scripts/run_eval.py --calibrate
```

It prints the relevance score for the questions in `eval/calibration.json` and suggests a floor (the lowest score among answerable questions, minus 0.05). Add a few real customer questions to that file, using your own wording, before you rely on the number.

## Change the model

Set `CHAT_MODEL` in `.env`. Rerun the eval before switching for real. If you change `EMBED_MODEL`, run `ingest.py --rebuild`, because the old embeddings won't match.

## Slack

Set `SLACK_MODE=slack` and `SLACK_WEBHOOK_URL`. If Slack is down, the customer still gets their reply, and the log line records `"slack": "error: ..."`.
