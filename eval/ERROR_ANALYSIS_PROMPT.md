# Error-analysis brief (the cold-reader pass)

**Why:** rule 2 of [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) says the run and the analysis
of its failures are separate passes, ideally by someone who didn't build the run. This is the
brief for that pass: fill in the run folder and give it to a fresh session or a colleague. It is
reference material, not something to run automatically.

---

TASK: error analysis of one eval run. You did NOT produce this run. Your job is to check its
failures against the raw evidence, not to defend its story. Read `eval/REPORTING_STANDARDS.md`
and the run's `report.md` (and `NOTES.md` if there is one) first.

INPUT: the run folder `eval/runs/<RUN>/` (`config.json`, `raw.jsonl`, `scored.jsonl`,
`report.md`) and the corpus it used (`data/notes.json`, `data/qa_pairs.json`).

DO:

1. Split the rows into right and not right by label. Keep only a count of the right ones, except
   the rows the report lists as "judged correct without all the evidence shown". Check those too.
2. For every failure, find the real cause from the raw fields, not from the label. Pick one:
   (a) retrieval-starved: an evidence note the answer needs was not retrieved;
   (b) near-duplicate confusion: the evidence was there, but the reply used a similar note from
       another day;
   (c) reasoning failure: the notes were there and distinct, the reasoning was wrong;
   (d) answer-key defect: the question or its evidence is wrong, for example it asks for the
       "current" state but points at an older note;
   (e) harsh judge: the reply was right and the judge marked it down.
   Cite the evidence-vs-retrieved fact that decides each call. A claim without a cited row isn't
   allowed (rule 1).
3. For multi-note types (multi_hop, temporal_reasoning, conflict_resolution), report all@K, not
   just hit@K. Check the ID join is exact (rule 6).
4. Name the judge and whether it equals the answering model. List every row where you disagree
   with the judge (rule 5).

DELIVER: `eval/runs/<RUN>/REPORT_erroranalysis.md`, one page, headline first: your corrected
cause counts, all@K for multi-note types, the clearest examples per cause with their cited rows,
and any claim in `report.md` or `NOTES.md` the data does NOT support. Then fill in the
cold-reader line at the top of `report.md` with a link to your file. Plain language.

OUT OF SCOPE: re-running models, changing prompts or retrieval, building anything.
