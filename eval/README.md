# eval/ — testing a RAG chatbot on the pipeline corpus

**Why:** the root pipeline makes a journal corpus whose questions come with an answer key, but
the key is a set of evidence *notes*, not a sentence. This folder runs a RAG chatbot on that
corpus and says, per question, whether search found the evidence and whether the reply matched
it. It was ported from the REFLECT project's RAG harness, without REFLECT's backend.

**What:** one run = embed the notes, fetch the top K per question, ask a local model, then score.

- **Code scores what it can, with no LLM:** precision/recall/hit/all@K and MRR against the
  evidence notes; refusals on unanswerable questions; and refusals on answerable ones, split by
  whether *all*, *some* or *none* of the evidence was shown. "All shown, still refused" is a
  reading failure; "none shown" is a retrieval failure. They need opposite fixes.
- **An LLM judge (optional) grades the rest:** answers to answerable questions. It sees the
  question, the evidence notes, the other notes the chatbot was shown, and the reply. It never
  sees code's labels or retrieval scores. Its labels are advisory (see the first run's notes).

```bash
.venv/bin/python -m pytest -q tests/test_eval.py            # no LLM
.venv/bin/python eval/run_eval.py                           # qwen3:4b, K=5, no judge
.venv/bin/python eval/run_eval.py --judge-model qwen3:30b   # with the judge
.venv/bin/python eval/run_eval.py --score eval/runs/<run> --judge-model <model>   # re-score only
```

Needs Ollama with `nomic-embed-text` and the models you name. A run writes
`eval/runs/<timestamp>/`: `config.json` (models, K, corpus version, manifest check),
`raw.jsonl`, `scored.jsonl` and `report.md`.

| File | What it does |
|---|---|
| `run_eval.py` | load + check the corpus, retrieve, answer, score, write the report |
| `judge.py` | the judge prompt and the strict parser for its verdicts |
| `REPORTING_STANDARDS.md` | how a report built on these runs must show its evidence |
| `ERROR_ANALYSIS_PROMPT.md` | the brief for the independent "cold reader" pass on a run |
| `runs/20261028_122655/` | the first run, with `NOTES.md` explaining what it does and doesn't show |

## Before trusting a number

- `run_eval.py` refuses to run if any evidence ID is missing from `notes.json`. A missing ID
  would silently count as a retrieval miss. `tests/test_eval.py` checks the same on the
  checked-in data, and that every data file matches `data/MANIFEST.json`.
- Use all@K for multi-note questions; hit@K flatters them.
- The judge changed the score by six points when only its prompt changed. Don't quote a judged
  score until a human has checked the judged rows. Start with the ones the report lists as
  "judged correct without all the evidence shown".

## How this relates to `demo/`

`demo/evaluate.py` scores its own small corpus with no judge at all, because every demo answer
is a short exact string. The pipeline corpus has open questions ("why did I…"), so it needs the
judge for that last step. The two evals share the metric definitions but no code: `demo/` imports
nothing from the rest of the repo by design.
