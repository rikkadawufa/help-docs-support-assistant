# RAG audit harness

Runs a question bank against any RAG system that has an HTTP API, grades every reply in code, repeats each question to check stability, and writes a report. It drives [promptfoo](https://www.promptfoo.dev/) (MIT) for the requests and repeats; the grading and the report are ours.

## What it checks

For each question the bank says what should happen (`expect`):

- **Answerable** (`status: answered`): every regex in `facts` must appear in the answer, and at least one citation must point to a file and page in `sources` (page 0 = any page of that file).
- **Should not answer** (`status: handoff`): the system must decline or hand off. Answering anyway counts as a made-up answer.

Failures get a type: made-up answer, retrieval miss (the right passage was never retrieved), over-refusal, wrong answer (with the right, wrong, or no source), and wrong citation. Retrieval is only graded when the API returns the passages it retrieved; citations only when it returns sources. No LLM grades anything.

Every failed run on a question the documents answer also gets a cause in the report (`report.py`, from grade.py's `retrieval_hit` score): search missed the expected file and page, search found it but the answer step failed, or unknown when the API doesn't return what it retrieved. An unknown is never counted as a miss. `per-question.csv` has a `retrieved` column (hit, miss or n/a) and a `cause` column, and `report.md` totals them per system.

## Run it

Needs Node 18+ (promptfoo runs through `npx`, pinned in `run.py`) and this repo's Python environment.

```bash
# 1. start the system under test (this demo: mock mode costs nothing, live mode calls OpenAI)
LLM_MODE=mock SLACK_MODE=log .venv/Scripts/python scripts/serve.py --port 8011

# 2. run the bank against one or more targets, 3 times per question
.venv/Scripts/python audit/run.py --bank eval/questions.json \
  --target audit/targets/cinderpeak-baseline.json --target audit/targets/cinderpeak-grounded.json \
  --repeat 3 --url http://127.0.0.1:8011/ask
```

Each run writes `output/audit/<time>/`: `promptfooconfig.yaml` (generated), `results.json` (promptfoo's raw output), `dataset.json`, `report.md` and `per-question.csv`. `npx promptfoo@0.124.1 view` opens promptfoo's own viewer on the same results.

`dataset.json` holds every count (per question, system and run, per question type, and per failure type). `report.md`, `per-question.csv` and client reports read it instead of counting again. Failure types are grade.py's types split by question type, for example a made-up answer on a question that needs two documents becomes `stitched_rule`; `findings.yaml` explains each one. To change a pass or fail after a run, add a ruling to `audit-notes.yaml` in the run folder and rebuild with `.venv/Scripts/python audit/report.py output/audit/<time> --bank <bank>`; the graded result stays next to the ruled one. `audit/notes.py` checks a client report's hand-written notes against the dataset (no numbers typed by hand except inside `[[file p.N: quote]]`, which must match the document word for word; examples must match a real failure; every failure type needs a fix estimate).

Telemetry and update checks are turned off in `run.py`. Nothing is shared unless you run `promptfoo share` yourself.

## Point it at another system

1. Copy `targets/cinderpeak-grounded.json` and change `url`, `headers` and `body` (`{{question}}` is replaced with each question).
2. Write a transform like `transforms/cinderpeak.js` that turns the API's reply into `{answered, answer, citations, retrieved}`. Use `answered: null` if the API only returns text (a refusal pattern decides) and `citations: null` if it never returns sources.
3. Write the question bank in the same format as `eval/questions.json`.

## Test assistants on new documents

The demo's two assistants (`app/`) can be pointed at another set of documents without code changes. Every setting defaults to the Cinderpeak demo, so an unset `.env` behaves exactly as in the held-out run (`tests/test_new_documents.py` checks the prompts against that run's hashes).

| Setting | What it changes |
|---|---|
| `KNOWLEDGE_DIR` | documents folder (relative paths start at `demo/`) |
| `INDEX_NAME` | gives these documents their own index; always set it, or ingest replaces the demo index |
| `BRAND_NAME` | the business name in both system prompts |
| `HANDOFF_REPLY` | what the guarded assistant says when it hands off |
| `PAGE_BANNER`, `PAGE_FOOTER` | regex for the banner and footer repeated on each PDF page; empty strips nothing |

`scripts/ingest.py --docs <folder> --index <name>` does the same for one run. Before any client question is asked, `scripts/freeze.py` records the code, every setting that changes an answer, both prompts and every document hash, and prints a fingerprint to post to the client. `audit/run.py --freeze <file>` copies it into the run folder, and the report states when the assistants were fixed. The step-by-step client procedure is in `catalog/delivery.md` (Starter).

## Report plans

`plans.yaml` sets each report layout and the notes it needs. Standard is the six-page sample with a fix plan and hours. Starter is a summary, the findings with one example of every failure type, and an appendix; it has no fix plan or hours, picks its verdict from go, fix_docs_first or no_go (labels in `plans.yaml`), and needs `freeze.json` from a live run. Its verdict thresholds are blank until they are decided, and no Starter report is built until they are set. A verdict that differs from the one the thresholds suggest needs `verdict_reason`.
