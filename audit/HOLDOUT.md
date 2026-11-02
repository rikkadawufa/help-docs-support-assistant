# Held-out test set

The numbers reported for this demo come from a question set that the person tuning the assistant never saw.

- Written by a different model (OpenAI Codex) from the documents in `knowledge/` and `knowledge_updates/` only, before any tuning against it.
- 65 questions: 40 the documents answer, 20 traps in four kinds (not covered, false premise, stitched across documents, outdated version) and 5 that need account access.
- Kept outside this repository. Its SHA-256, committed here before tuning started:

```
3b142766f85338577b22225ca63b962a8194276f858f6e188f5afc1ecfffa986  questions.json
```

- One change was made before tuning, by the set's author: the first version expected every false-premise trap to be handed off. Where the documents can correct the premise (for example a "lifetime warranty" question when the documents say 3 years), the right behavior is to correct it with a source, so those 5 questions now expect a corrected answer. The first version's hash was `0de9affe0239fa799df57a07ccfe424fa6d6ef31685077c0513b3f0aee25526f`.
- The author also compared the tuning questions with this set. 11 newly drafted tuning questions asked the same thing as a held-out question and were dropped from `eval/questions.json` (only their IDs were reported back, not the held-out questions).

- Tuning uses `eval/questions.json` only. When the settings are frozen (git tag), the held-out set is run once against that tag, and the result is reported as is. Any question whose expected answer turns out to be wrong is listed with the change, not silently fixed.

## The run (2026-11-02)

- Settings frozen at tag `audit-freeze-1` (commit `0cd803e`). Tag, clean tree and the hash above were checked before the run.
- The set's author (Codex) was to run it, but its sandbox could not start Node: three attempts stopped before promptfoo asked a single question (no API calls). The one real run was then started by Claude against the same tag, with the same command, and was not repeated.
- 65 questions x 2 systems x 3 runs, gpt-4o-mini. Results folder: `output/audit/20261102-090609/` (not committed).

| | Simple RAG (baseline) | This assistant |
|---|---|---|
| Answerable questions answered correctly | 133/150 (89%) | 127/150 (85%) |
| Questions it should decline: answered anyway | 39/45 (87%) | 9/45 (20%) |
| Correct answers citing the right file and page | no sources returned | 127/127 (100%) |
| Right passage among the retrieved ones | 147/150 (98%) | 147/150 (98%) |

These numbers include one ruling made after the run (by the project owner, after the results were in; the question file was not edited, so its hash still matches):

- **H18 changed to pass** (affects this assistant's 3 runs only; the baseline passed it). The question asks whether the Drift 20 can stay in its compression sack all season. The expected fact was "store it in the mesh sack". The assistant answered "No, long-term compression reduces loft and warmth", citing the right page. The answer is correct; the expectation asked for more than the question did. Before the ruling the assistant's figures were 124/150 and 124/124.
- **H54 kept as is.** The question asks whether a missing tracking update means the address can still be changed. The assistant said no because the 1-hour window has passed, but the customer never said when they ordered, so the expected handoff stands.

On the tuning set the same settings scored 60/60 and 0/36. The gap is the point of a held-out set: the assistant still refuses all 5 questions built on a wrong premise that the documents correct, and both questions about the outdated 14-day policy, and it answered 3 of 5 questions that stitch two documents into a rule neither states. These results are reported as is; any change from here would need a new held-out set.
