# Notes on run 20261028_122655 (first run of eval/)

**Status: DRAFT.** No cold-reader pass yet (REPORTING_STANDARDS rule 2). This run's job was to
show the eval works end to end, not to produce a quotable score. Written by the session that
built the eval, so it's the author's reading, not an independent one.

## What is solid (decided by code)

- The corpus joins cleanly: all 17 answerable questions' evidence notes exist in `notes.json`,
  and every data file matches `MANIFEST.json` (`config.json` → `files_match_manifest`).
- Retrieval with K=5 (`report.md`): hit@5 = 0.88 but all@5 = 0.59. Multi-note questions
  (multi_hop, temporal, conflict) often got only some of their evidence.
- 2 of 3 unanswerable questions were correctly refused. q_0045 was answered ("Ethan's unpaid
  payment") from notes that keep mentioning Ethan not paying. That may be an answer-key fault,
  not a made-up answer: see "Possible answer-key defects" below.

## What is not solid (decided by the judge)

The same 20 recorded answers were judged three times, changing only the judge prompt
(judge `qwen3:30b`, answering model `qwen3:4b`):

| judge prompt | right | what changed |
|---|---|---|
| v1: sees only the evidence notes | 10/20 | replies built on a non-evidence note were called hallucinations |
| v2: also sees the other notes shown | 16/20 | now accepted claims that only the other notes support |
| v3 (committed): "evidence first, OTHER_NOTES if the claim comes from elsewhere" | 12/20 | still calls q_0002/q_0003 correct with no evidence shown |

A six-point swing from wording alone means the judge's score can't be quoted without a human
check. Only v3's output is in `report.md`/`scored.jsonl`. The v1 and v2 numbers come from this
session's console output and weren't saved.

## Possible answer-key defects (need a human to confirm)

The corpus repeats activities on several days (for example "worked on The Art of War for two
hours straight, no distractions" on 13, 16, 17 and 22 January). Several questions ask about the
*current* or *last* state, but their answer key points at an earlier note:

- **q_0002** "Is The Art of War project currently active or paused?" The key is the 13 January
  note. The 22 January note says "the project's not paused anymore? just for now."
- **q_0007** "When did the user last work on The Art of War without distractions…" The key is 16
  and 17 January, but the 22 January note describes the same session type.
- **q_0011** "What is the current state of the couch…" The key is 5 and 6 January (fur
  everywhere). A 15 January note says the couch "is clean for once".

- **q_0045** (unanswerable) "What specific issue is causing the Art of War project to remain
  unresolved despite previous attempts?" Arguably answerable: seven notes tie the project to Ethan
  not paying ("same as last time with Ethan's unpaid stuff", 9 Jan; "Ethan still hasn't paid",
  12 Jan; "waiting for Ethan to pay", 13 Jan; also 16, 17 and 22 Jan), and two of them were
  retrieved. The reply "Ethan's unpaid payment" is labelled FAILED_REFUSAL by code, but may be
  the better answer. ("Remain unresolved" is also shaky: 17 Jan says Ethan sent half the payment.)

If confirmed, the first three questions mark a correct "latest state" answer as wrong, and q_0045
counts a supported answer as made up. It matches the
REFLECT finding that near-duplicate notes, not retrieval, limit answer accuracy on this corpus.
