# Reporting standards for eval runs

**Why:** in the project this came from, two eval reports in a row stated a headline claim their
own raw data contradicted. One blamed retrieval when the cause was a harness bug. The other said
a failure "wasn't retrieval" when the per-question rows showed that 2 of the 5 failures were.
Both were catchable by reading the rows. These rules make a report show the rows a claim rests
on, so a claim can't get ahead of its evidence.

Advisory, except the checklist at the bottom. Rules 1 and 2 carry the most weight.

## The rules

1. **Claim-to-evidence.** A claim about a *subset* ("temporal questions fail because…") or a
   *cause* ("retrieval isn't the problem") needs a per-question table of the fields it rests on:
   question, evidence notes, retrieved notes, reply, label. An average alone is never enough.
   `run_eval.py`'s report prints this table for every answer that isn't right.

2. **Run and analysis are separate passes.** The run produces data. A separate error analysis,
   ideally by someone who didn't build the run, writes the failure report
   ([ERROR_ANALYSIS_PROMPT.md](ERROR_ANALYSIS_PROMPT.md)). An author defending a story they just
   wrote is how overstatements survive.

3. **Keep failures verbatim.** Keep every field for every failing question. Successes can be
   summarised. Failures are the signal and there are few of them.

4. **Match the metric to the question.** A multi-note question needs *all* its evidence notes.
   Report all@K for those, not just hit@K (one evidence note found), which flatters them.

5. **Name the judge.** Say which model judged. If it also wrote the answers, flag self-grading
   and make the human check mandatory. Report where the human disagreed with the judge. The
   corpus is fictional, so a stronger judge from a different model family is fine to use.

6. **Check joins and IDs.** This corpus mixes `N_`, `n_`, `note_` and `E_` note IDs. A
   mismatched join fakes both recall and failure counts. In 2026-10-28 the checked-in
   `qa_pairs.json` pointed at notes from a different generation run, so no answerable question's
   evidence existed. `check_dataset()` and the tests now catch that. Don't assume a join; verify it.

7. **Say which kind of agreement you have.** `temperature: 0` makes repeats within one run agree.
   It does not guarantee a re-run reproduces the same text. "5 repeats agreed" describes one run's
   stability, not reproducibility. Quote from the committed run files, not from memory.

## How to deviate

If a rule is wrong for an experiment, write one line saying which rule and why, then go ahead.

## The blocking checklist

A report's claims are a draft until its cold-reader pass has run. `run_eval.py` puts this line at
the top of every report, to be filled in:

```
Cold-reader pass (REPORTING_STANDARDS rule 2): ___________  (DRAFT until filled)
```

While it's blank, the report's headline may not be quoted or acted on as a finding.
