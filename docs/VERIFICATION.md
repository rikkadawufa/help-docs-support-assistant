# Verification log (what was run, results, open decisions)

> This file records only results from runs that actually happened. Model: `gpt-4o-mini`; embeddings: `text-embedding-3-small`. All documents and questions are fictional.

## Environment
- Python 3.12.10, packages installed in `demo/.venv`, versions in `requirements.txt`
- The user approved the install on 2026-10-29. The user filled in the OpenAI key and Slack webhook in `.env`; I never read or printed them

## Differences from SPEC (decided during implementation)
| Item | SPEC | Actual | Why |
|---|---|---|---|
| PDF loading | `PyMuPDFLoader` from `langchain-community` | Read pages with PyMuPDF directly, then wrap them in LangChain `Document`s | `langchain-community` prints a deprecation warning on import, and a portfolio piece shouldn't depend on it. Removed from requirements and uninstalled; all 34 tests still pass |
| Where retrieval and the decision function live | `app/retrieve.py`, `decide()` in `answer.py` | Retrieval is in `app/store.py`, `decide()` is in `app/citations.py` | Retrieval shares settings with the store; `decide()` is a pure function and is easier to test next to the citation checks |
| Starting the server | `uvicorn app.server:app` | `python scripts/serve.py [--live] [--slack]` | A factory avoids opening Chroma at import time |
| v1/v2 switch | Regenerate v1 | `make_docs.py` saves both v1 and v2 to `knowledge_updates/`, and the switch just copies one over | PyMuPDF produces a different hash every time it generates a PDF, so regenerating would mark the other 7 PDFs as "updated" too |
| Threshold rule | Take the midpoint from the calibration questions, then never change it | From round 2: "the lowest score among answerable calibration questions minus 0.05", used only to block clearly off-topic questions | See the round 1 review below |
| Citation matching | Continuous substring after normalization | From round 2, matched sentence by sentence; from version 3, layout punctuation (colons, commas, table `|`) is ignored, but **the words must still match exactly** | See the reviews below |
| PDF tables | Not specified | From version 3, `find_tables()` detects tables and each row is stored as `cell | cell | cell` | See the reviews below |
| Number of eval rounds | At most 2 | 3 rounds run | Round 3 went past the SPEC limit and was run only after the user approved it on 2026-10-29 |

## Document and trap question checks
- `make_docs.py`: 8 PDFs and 8 Markdown files, plus v1 and v2 of the returns policy
- Trap keywords (price match, rent, military, student, retail store, solar, stock, mobile app, gift wrap, guided trip, and others) have **0** hits across all documents

## Unit tests
- `pytest`: **34 passed** (citation checks, sentence-by-sentence and punctuation-tolerant matching, the decision table, no model call below the threshold, incremental manifest, malformed output, API 422 / degraded 200 / 200 even when Slack fails / source 404)

## Mock E2E
- `LLM_MODE=mock`: ingest → A–D in both modes → E → F → collect_results all ran to the end with correct formats. Scores aren't checked in mock mode

## Round 1 (live, 2026-10-29, logs in `output/round1/`)
- Calibration: K1–K6. Lowest answerable score 0.633, highest unanswerable 0.370, midpoint gives `RELEVANCE_MIN=0.50`
- Results: A+B **4/12**, trap questions answered **0/6**, C+D handed off **9/9**
- Review (too conservative):
  1. The threshold was too high. K1–K6 all used clear keywords, but the test questions are phrased casually and only scored 0.31–0.49, so A1, A2, A3, A6, and B2 were blocked before reaching the model. Also, the trap questions' scores (0.30–0.59) overlap with the answerable ones, so a threshold can't separate the two anyway
  2. A5: the model joined two sentences from the same passage into one quote, skipping a sentence in between, so the continuous substring check failed
  3. A4, A8: the documents say plainly "no" or "US and Canada only", but the model still declined because the prompt rules were too strict
  4. Header and footer boilerplate on every page diluted the embeddings

## Round 2 (live, logs `20261029-043234-*`)
- Fixes:
  - The prompt now says a "no" stated in the documents can be answered, but something the documents don't mention can't be treated as "no"
  - Citations are matched sentence by sentence
  - Headers and footers removed, the document title added to the start of each chunk, chunks changed to 500/80
  - 8 new casually phrased calibration questions, K7–K14 (none taken from the test questions)
  - New threshold rule, "lowest answerable score minus 0.05", giving `RELEVANCE_MIN=0.39`; the threshold alone blocks 4 of the 6 unanswerable questions
- Results: A+B **9/12**, trap questions answered **0/6**, C+D handed off **9/9**
- The remaining 3 (A3, B1, B3) were all `no_valid_citation`. The facts were right, but the quote format didn't match the source text:
  - B1, B3: PDF tables were extracted one cell per line, so the model reassembled them as "Coolers, Glacier 45, 5 years" or skipped the first half of a cell
  - A3: the model added its own colon after a heading

## Round 3 (live, logs `20261029-044207-*`; the portfolio uses this round)
- Fixes:
  - Each table row is stored as one line (`Coolers | Glacier 45 | 5 years`)
  - Citation matching ignores layout punctuation, but the words must still match exactly. Added 4 tests, including "7 years must not pass" and "skipping words within the same sentence must not pass"
  - After rebuilding the index, recalibrated with the same rule; `RELEVANCE_MIN` is still **0.39**
- Before the run: `pytest` 34 passed; ingest unchanged 16
- Results (computed by code):
  - A+B **12/12** correct, each with at least one valid citation pointing to the right file and page
  - Trap questions answered **0/6**
  - C+D handed off **9/9** (3 blocked by the threshold, 6 where the model returned answerable=false)
  - Across the 12 answered questions, the check didn't reject a single citation
- Baseline: A+B facts correct 12/12 (no sources); the 9 C/D questions were waiting for manual labels, using the worksheet in `eval/baseline-review.md`
- Note: the fact regexes for A3, A7, and A8 are loose (they only look for words like no/not/only), so passing them depends mainly on the "citation must point to the right page" condition. I read all three actual answers by hand, and they're correct:
  - A3: "No, fuel canisters cannot be returned for safety and hygiene reasons."
  - A7: "No, promo codes cannot be combined with each other."
  - A8: "No, we do not ship to any other country."

## E. Document update (live, version 3 index, `20261029-043534-scenario-update.jsonl`)
- v1: ingest unchanged 16 → answered "30 days"
- Switched to v2: ingest **updated 1, unchanged 15** → answered "14 days", citing `returns-policy.pdf p.1`
- Switched back to v1 (hash matches `knowledge_updates/returns-policy-v1.pdf`)

## F. AI service outage (live, Slack mode, `20261029-043542-scenario-llm-error.jsonl`)
- `CHAT_MODEL=gpt-does-not-exist` → status `degraded`, reason `llm_error`, API returned 200, Slack **sent**
- Then asked about the Glacier 45 warranty with the normal model → answered "5 years"

## Browser test (live + Slack, version 3 index)
- `/`: Glacier 45 warranty → answered "5 years", source `warranty.pdf p.2`, quote "Coolers | Glacier 45 | 5 years"; expanding it shows the source text with that row highlighted
- `/`: "Can the Halo be charged with a solar panel?" → handed off (model_declined), Slack sent
- "Talk to a person" → Slack sent (user_requested)
- `/compare`: the price match question; the baseline replied "Cinderpeak Outdoor does not have a price matching policy..." (the documents have no such policy, so it's made up), while the grounded version handed off, Slack sent
- Mobile width 375px: layout is fine, no horizontal scrolling

## Observations to state honestly
- **The baseline is accurate on answerable questions**: 12/12 facts correct in both rounds (just without sources). The grounded version's advantage is on trap questions and handoffs, not accuracy on ordinary questions. The portfolio can't claim "the baseline gets a lot wrong"
- On trap questions the baseline often writes "we do not offer X", which sounds like a decline but actually **invents a policy that doesn't exist**. The rule counts these as "answered", and the manual labels have the final say

- All three rounds were fixed after looking at results on the same 21 questions. The round 2 and 3 fixes were general (prompt rules, citation matching, table handling), but strictly speaking they were all made after seeing the test results. The portfolio has to describe this as "the result after three rounds of iteration" and can't present 12/12 as a first-try result. A score on unseen questions would need a new question set and one more run

## Baseline manual labels (by the user, 2026-10-29, final)
- Final labels: C1–C4 answered, C5–C6 declined; D1 answered, D2 declined, D3 declined
- Where the keyword rule disagreed: C4, D1, D2, D3 (manual labels win)
- Process: in the first pass D1 was labeled declined and D2 answered. After discussing the definitions, the user changed D1 to answered (it used the return rules to turn down a customer who, per the documents, should have gone through a warranty claim, and added on its own that "a dent counts as normal wear") and D2 to declined (it passed the question to support without reaching a conclusion)
- Why C4 is answered: the documents mention no physical stores, yet it went along with the customer as if store locations could be looked up on the website
- Result: the baseline answered **4/6** trap questions (C1 price match, C2 rentals, C3 military discount, C4 implied a physical store); the grounded version **0/6**
- User feedback: labeling felt like nitpicking wording. The C standard is fairly clear (the documents don't say it, but the answer talks as if the rule exists); the D questions are more subjective

## Portfolio material prep (2026-10-29)
- Reran E and F with the new `run_eval.py` (log paths now relative); results unchanged: `20261029-061753-scenario-update.jsonl`, `20261029-061802-scenario-llm-error.jsonl`, Slack sent
- Verified the README's claim that "adding documents doesn't require a server restart": with the server running, switched to v2 and ran ingest (updated 1), then asked through the server's `/ask` and got "14 days". Switched back to v1 and ran ingest afterward
- Added `?expand=1` to the widget (auto-expands the first source, for screenshots); after expanding it scrolls to the highlighted line
- Screenshots come from `portfolio/src/shoot_demo.py` against the live server, with crop areas set in the script. The answers in the screenshots are that session's live output: the baseline said "we do not offer price matching for the Ember 2 Camp Stove...", worded differently from the eval log, but both invent a policy
- The output of `collect_results.py --summary` is used as is on board 04

## Explainer video (2026-10-29)
- Voice: HeyGen voice `28J6z3XNsqyMvvCqxUiK`, speed 0.9. The OAuth free quota was used up ("0 seconds of free voice-generation time left"), so per DESIGN §9 it switched to the API key in `_portfolio-design-system/.env` (`make-voice.sh --api`), with the same voice for all 8 segments. The key was never printed or written to any file
- 8 scenes, 89.48 seconds; the shared BGM track at volume 0.12
- `hyperframes check`: 0 errors and 0 warnings for both 16:9 and 9:16
- Renders: `video/help-docs-support-assistant-16x9.mp4` (1920×1080, 89.5 s), `video-reel/help-docs-support-assistant-9x16.mp4` (1080×1920, 89.5 s)
- Checked frames at 10 timestamps, including frame 0, each scene, the end card, and the circled parts of the flow: frame 0 isn't blank, 16:9 has no watermark, the 9:16 watermark jumps between safe positions, and captions don't cover the board
- **No one has listened to the audio yet**: the user needs to listen once to check volume balance and pronunciation (LangChain, Chroma, Cinderpeak)

## Comparison table decision (by the user, 2026-10-29)
- The before/after table in `collect_results.py` keeps only two rows: "answerable questions correct" 12/12 vs. 12/12, and "trap questions answered" 4/6 vs. 0/6
- The "C+D handed off" row was dropped for two reasons: the baseline has no handoff feature, so there's nothing to compare, and the D questions are too subjective. D results are still in the per-question details (grounded version 3/3 handed off)
- The design that came up while discussing D3 (look up whether the order exists first, then either answer from its actual status or hand off to support) needs an order system connection. This demo doesn't have one, so a proposal can only say it "can be added"

## Open decisions
- None
