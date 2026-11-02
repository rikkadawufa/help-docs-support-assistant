# RAG audit harness

Runs a question bank against any RAG system that has an HTTP API, grades every reply in code, repeats each question to check stability, and writes a report. It drives [promptfoo](https://www.promptfoo.dev/) (MIT) for the requests and repeats; the grading and the report are ours.

## What it checks

For each question the bank says what should happen (`expect`):

- **Answerable** (`status: answered`): every regex in `facts` must appear in the answer, and at least one citation must point to a file and page in `sources` (page 0 = any page of that file).
- **Should not answer** (`status: handoff`): the system must decline or hand off. Answering anyway counts as a made-up answer.

Failures get a type: made-up answer, retrieval miss (the right passage was never retrieved), over-refusal, wrong answer (with the right, wrong, or no source), and wrong citation. Retrieval is only graded when the API returns the passages it retrieved; citations only when it returns sources. No LLM grades anything.

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

Each run writes `output/audit/<time>/`: `promptfooconfig.yaml` (generated), `results.json` (promptfoo's raw output), `report.md` and `per-question.csv`. `npx promptfoo@0.124.1 view` opens promptfoo's own viewer on the same results.

Telemetry and update checks are turned off in `run.py`. Nothing is shared unless you run `promptfoo share` yourself.

## Point it at another system

1. Copy `targets/cinderpeak-grounded.json` and change `url`, `headers` and `body` (`{{question}}` is replaced with each question).
2. Write a transform like `transforms/cinderpeak.js` that turns the API's reply into `{answered, answer, citations, retrieved}`. Use `answered: null` if the API only returns text (a refusal pattern decides) and `citations: null` if it never returns sources.
3. Write the question bank in the same format as `eval/questions.json`.
