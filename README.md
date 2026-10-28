# RAG Eval for Synthetic Journals

[![tests](https://github.com/imanmossavat/rag-eval-for-synthetic-journals/actions/workflows/tests.yml/badge.svg)](https://github.com/imanmossavat/rag-eval-for-synthetic-journals/actions/workflows/tests.yml)

Test a RAG or chatbot-memory system on fictional journals where every question has a known
answer and known evidence. Everything is made up, so no model can know the answers from
training and no real journal is touched.

**The idea: facts first, text last.** Write the hidden facts, turn them into notes (checked by
code), then build the questions from the facts. The answer key exists before any text does, so
you can score with plain code and tell *search missed the evidence* (fix retrieval) from *the
model had it and misread it* (fix the model or prompt).

## What's here

| Folder | What it does | Read |
|---|---|---|
| [`demo/`](demo/) | **Start here.** One fictional month (59 notes), 26 questions on 5 levels, 4 memory designs (full context, vector search, rolling summary, fact list), scored by code. Results included. | [`demo/README.md`](demo/README.md), [`demo/explainer.html`](demo/explainer.html) |
| repo root | A 5-stage LLM pipeline that generates a larger, messier corpus (story arcs, contradictions) with a QA set. | [`PIPELINE.md`](PIPELINE.md) |
| [`eval/`](eval/) | Runs a RAG chatbot on the pipeline corpus: retrieval and refusals scored by code, open answers by an optional LLM judge. | [`eval/README.md`](eval/README.md) |

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/     # no LLM, no network (what CI runs)
```

Then, with [Ollama](https://ollama.com) running:

| To | Pull | Run |
|---|---|---|
| run the demo eval | `qwen3:4b`, `qwen3:30b`, `nomic-embed-text` | `.venv/bin/python demo/evaluate.py` |
| eval RAG on the pipeline corpus | `qwen3:4b`, `nomic-embed-text` (+ a judge model, optional) | `.venv/bin/python eval/run_eval.py` |
| generate a new pipeline corpus | `qwen3:30b`, `gemma3:27b` | `.venv/bin/python run_pipeline.py` (overwrites `data/`) |

Each command's options are in its folder's README or `--help`.

## What the demo found

- At this size, pasting the whole diary into the prompt beats every memory design. The
  compressing designs (summary, fact list) lose meaning, not just words.
- hit@K was a perfect 1.00 while multi-note questions often lacked some of their proof.
  Measure *all* the proof, not *some*.
- A bigger model fixes reading mistakes, not retrieval mistakes.

Limits: 26 questions, one run each; a small diary; short factual answers only; the notes were
written by the same AI that designed the test. Details in the explainer.
