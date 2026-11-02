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
