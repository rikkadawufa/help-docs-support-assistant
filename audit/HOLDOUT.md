# Held-out test set

The numbers reported for this demo come from a question set that the person tuning the assistant never saw.

- Written by a different model (OpenAI Codex) from the documents in `knowledge/` and `knowledge_updates/` only, before any tuning against it.
- 65 questions: 40 the documents answer, 20 traps in four kinds (not covered, false premise, stitched across documents, outdated version) and 5 that need account access.
- Kept outside this repository. Its SHA-256, committed here before tuning started:

```
0de9affe0239fa799df57a07ccfe424fa6d6ef31685077c0513b3f0aee25526f  questions.json
```

- Tuning uses `eval/questions.json` only. When the settings are frozen (git tag), the held-out set is run once against that tag, and the result is reported as is. Any question whose expected answer turns out to be wrong is listed with the change, not silently fixed.
