# demo/ — testing chatbot memory with data you control

**Why:** a minimal, laptop-sized demo of the main idea behind this repo. If you write the
facts first, every test question has a known answer and known evidence, so you can see
*where* a RAG/memory chatbot breaks instead of eyeballing it. It is separate from the big
5-stage pipeline in the repo root and imports nothing from it.

**What:** one fictional month (59 diary notes), 26 questions on 5 difficulty levels, and
4 chatbots that differ only in their memory (full context, vector RAG, rolling summary,
fact list). Each is run on two local models and scored by string match, without an AI judge.

| File | What it does |
|---|---|
| `generate.py` | world (hidden facts) → note plan → notes (checked) → questions |
| `chatbots.py` | the 4 memory designs, ~20 lines each |
| `evaluate.py` | runs models × designs × questions; scores; writes `runs/<ts>/report.md` |
| `llm_clients.py` | Anthropic API (data generation) + Ollama (models under test, embeddings) |
| `data/` | the checked-in corpus: `world.json`, `notes_plan.json`, `note_texts.json`, `notes.json`, `questions.json` |
| `explainer.html` | the illustrated one-page explainer (published as a claude.ai artifact) |

```bash
.venv/bin/python -m pytest -q tests/test_demo.py   # answer-key sanity checks, no LLM
.venv/bin/python demo/evaluate.py                   # needs Ollama: qwen3:4b, qwen3:30b, nomic-embed-text
```

New data: `generate.py --step all` with `ANTHROPIC_API_KEY` set, or the no-API route in
`generate.py`'s docstring (paste prompts into a Claude chat, or write `world.json` by hand).
