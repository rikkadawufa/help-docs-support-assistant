# Eval results snapshot

Live runs from 2026-10-29 (OpenAI gpt-4o-mini, text-embedding-3-small) on the made-up Cinderpeak Outdoor documents. One JSON line per question, written by `scripts/run_eval.py`.

| Folder | What it is |
|---|---|
| `round-1/` | First live run. Relevance floor 0.50: 4 of 12 answerable questions answered |
| `round-2/` | After the prompt, quote-check and chunking fixes, floor 0.39: 9 of 12 |
| `round-3/` | After table rows and layout punctuation were handled: 12 of 12, 0 of 6 traps answered. The numbers in the main README come from here |
| `scenarios/` | E (returns policy 30 to 14 days) and F (AI service failure) |
| `results.md` | `scripts/collect_results.py` output for round 3 and the scenarios |

All three rounds used the same 21 questions in `eval/questions.json`. The baseline's trap and account answers were labeled by a person in `eval/baseline-labels.json`.

To rebuild the table from these files (it is written to `output/results.md`):

```bash
.venv/Scripts/python scripts/collect_results.py --grounded results/round-3/20261029-044207-grounded.jsonl --baseline results/round-3/20261029-044207-baseline.jsonl --update results/scenarios/20261029-061753-scenario-update.jsonl --llm-error results/scenarios/20261029-061802-scenario-llm-error.jsonl
```
