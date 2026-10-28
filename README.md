# RAG Eval for Synthetic Journals

[![tests](https://github.com/imanmossavat/rag-eval-for-synthetic-journals/actions/workflows/tests.yml/badge.svg)](https://github.com/imanmossavat/rag-eval-for-synthetic-journals/actions/workflows/tests.yml)

**Goal:** show how to test a RAG or chatbot-memory system properly, using fictional journal
data where every test question has a known answer and known evidence. Every person, place
and event here is made up, so no model can know the answers from training and no real
journal is ever touched.

## The idea: facts first, text last

The usual way to test RAG is to ask a few questions about real documents and read the
replies. That can't tell you the right answer, how hard a question is, or whether a miss
came from search or from the model. This repo flips the order:

1. **Write the hidden facts first** (people, facts, things that change over time, things
   never mentioned).
2. **Turn the facts into journal notes,** and check each note with code (it must contain
   its fact and must not leak others).
3. **Build the questions from the facts,** with code. Each question comes with its answer
   and the exact notes that prove it.

Because the answer key exists before any text does, scoring is plain code with no AI judge,
and every failure can be split into *search didn't fetch the evidence* (fix retrieval) versus
*the model had the evidence and misread it* (fix the model or prompt).

## Where to start

| Part | What it is | Start with |
|---|---|---|
| [`demo/`](demo/) | **Start here.** A small, laptop-sized version of the idea: one fictional month (59 notes), 26 questions on 5 difficulty levels, and 4 chatbots that differ only in how they remember (full context, vector RAG, rolling summary, fact list). Results included. | [`demo/README.md`](demo/README.md), then [`demo/explainer.html`](demo/explainer.html) |
| Repo root | The larger 5-stage LLM pipeline that generates a richer corpus (story arcs, contradictions, messy notes) and a QA set. More realistic, less polished; see its known gaps. | [Pipeline reference](#pipeline-reference) below |

## What the demo shows

- At this size, pasting the whole diary into the prompt beats every memory design; the
  compressing designs (summary, fact list) lose meaning, not just words.
- hit@K ("at least one proof note found") was a perfect 1.00 while questions needing
  several notes often didn't get all of them. Measure *all* the proof, not *some*.
- A bigger model fixes reading mistakes, not retrieval mistakes.
- Built-in traps (look-alike values, stale values, counts larger than K) expose each
  design's weak spot within 26 questions.

## Limits

26 questions, one run each, so differences of one or two answers are noise. The diary is
small, so the "too big to fit" case isn't shown. Short factual answers only. The notes were
written by the same AI that designed the test. Full list in the explainer's "limits" section.

## Quick start

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/        # no LLM needed (this is what CI runs)
.venv/bin/python demo/evaluate.py           # needs Ollama: qwen3:4b, qwen3:30b, nomic-embed-text
.venv/bin/python run_pipeline.py            # the big pipeline; see Setup below
```

## Other docs

[`demo/README.md`](demo/README.md) covers the demo in detail, and [`demo/explainer.html`](demo/explainer.html)
is the illustrated one-page walkthrough with every result.

**Origin:** this started inside the REFLECT audio-journaling repo and was split out on
2026-10-24. It imports nothing from REFLECT. Code comments that mention REFLECT paths (`eval/...`,
`docs/...`) or internal reports refer to files not included here. Test comments citing
`cosmic-ray-bundle23.toml` refer to a one-off mutation-testing config left in REFLECT's history.

---

# Pipeline reference

Everything below is about the 5-stage pipeline in the repo root. `demo/` is separate and
documented in [`demo/README.md`](demo/README.md).

> **Current status and known gaps** (checked against the code on 2026-10-28):
> - **The timeline spans about 21 days, not 90.** `DURATION_DAYS` only sets the event
>   count; the span comes from random gaps between events. The checked-in corpus runs
>   2024-01-01 to 2024-01-22 (77 events, 77 notes). Not fixed yet.
> - **The checked-in QA set has 20 pairs and 5 types.** The code now also defines a sixth
>   type, `belief_currency`, which the checked-in corpus predates.
> - **About 58% of QA candidates were discarded** during the last generation run.
> - **The answer key is a set of note IDs, not a prose answer** (`answer_key.evidence`),
>   since the v2 rewrite. Score retrieval against it, not answer wording.
> - `config.py` is the source of truth for models and parameters. Older text quoting
>   other values is out of date.

## Architecture

```
config.py                  →  central configuration (model, backend, paths, parameters)
prompts.py                 →  all LLM prompts, imported by stages 01, 02, 04, 05
llm.py                     →  shared call_llm() client (Ollama / Anthropic)
         ↓
stage_01_world_state.py    →  data/world_state.json
         ↓
knowledge_graph.py         →  (in-memory graph, imported by stages 02 and 03)
         ↓
stage_02_event_timeline.py →  data/events_raw.json
         ↓
stage_03_repair.py         →  data/events_repaired.json      (no LLM)
         ↓
stage_04_note_generation.py → data/notes.json
         ↓
stage_05_qa_generation.py  →  data/qa_pairs.json             (+ independent verifier model)
         ↓
validate_corpus.py         →  hard gate, then corpus_manifest.py writes data/MANIFEST.json
```

`config.py`, `prompts.py` and `llm.py` are shared modules, not stages. `knowledge_graph.py`
is also shared: it builds a directed graph of the world state for deterministic validation,
and runs a biased random walk to generate event skeletons before the LLM writes any text.

## Setup

```bash
pip install -r requirements.txt
```

### Option A — Ollama (local, free, the default)

```bash
ollama serve
ollama pull qwen3:30b     # generator, OLLAMA_MODEL in config.py
ollama pull gemma3:27b    # verifier used by stage 05, VERIFIER_MODEL in config.py
```

`BACKEND = "ollama"` is the default. The defaults were chosen for a 48 GB machine;
`qwen3:30b` is a reasoning model, and `llm.py` sends `"think": false` to switch its
thinking off. If you switch to a model without thinking support, remove that flag.

### Option B — Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-...
```

Set `BACKEND = "anthropic"` in `config.py` (model: `ANTHROPIC_MODEL`). Stage 05's verifier
always calls Ollama, so you still need `ollama serve` with `gemma3:27b` pulled.

### Long runs on large local models

`config.py` sets two Ollama values that matter for multi-hour runs:

- `OLLAMA_TIMEOUT_SECONDS = 3600` so a slow response isn't cut off by the Python client.
  Raise it for slower hardware.
- `OLLAMA_KEEP_ALIVE = -1` so Ollama keeps the model loaded between calls. Its default
  (`"5m"`) would unload the model during the non-LLM work between calls and pay a reload
  every time. Set it back to `"5m"` if the Ollama instance is shared.

## Configuration

All tunable parameters live in [`config.py`](config.py). The main ones, as of 2026-10-28:

```python
BACKEND         = "ollama"           # "ollama" | "anthropic"
OLLAMA_MODEL    = "qwen3:30b"
ANTHROPIC_MODEL = "claude-sonnet-5"
VERIFIER_MODEL  = "gemma3:27b"       # stage 05 grounding check, different model family

DURATION_DAYS   = 90                 # sets the event count only, see status note above
EVENTS_PER_DAY  = 0.8
START_DATE      = "2024-01-01"
MIN_ENTITIES    = 15                 # enforced by stage 01's validator
MIN_STORY_ARCS  = 6
CONTRADICTIONS_PER_ARC = 1
ARC_CONTEXT_NOTES      = 0           # 0 = each note written without earlier notes as context
QA_COUNT = {...}                     # 6 per type, 6 types
```

`prompts.py` holds every prompt sent to the LLM. `llm.py`'s `call_llm(prompt, stage=...)`
reads the backend, model and temperature from `config.py` and retries up to `MAX_RETRIES`
times on JSON parse failure.

## Usage

### Unattended run

```bash
ollama serve                 # in a separate terminal
python run_pipeline.py
```

The runner runs all 5 stages in order, streams output to the console and to
`pipeline_run.log` (not committed), and stops at the first failing stage. Earlier stages
don't need re-running as long as their output files in `data/` are still there.

After all stages succeed, it runs `validate_corpus.py` as a **hard gate**: if any F1–F4
invariant fails, the run exits non-zero and the corpus must not be used. Pass or fail, it
writes `data/MANIFEST.json` with a `corpus_version` (timestamp + content hash), a SHA-256
per output file, the generator identity (backend, model, git commit, key parameters) and
the validation result. To re-run only the gate and manifest, with no LLM calls:

```bash
python run_pipeline.py --validate-only
```

### Stage by stage

```bash
python stage_01_world_state.py
python stage_02_event_timeline.py
python stage_03_repair.py
python stage_04_note_generation.py
python stage_05_qa_generation.py
python knowledge_graph.py          # inspect the graph for an existing world state
```

## Output files

| File | Contents |
|------|----------|
| `data/world_state.json` | Hidden truth: user profile, entities, story arcs, projects, latent facts |
| `data/events_raw.json` | Chronological event stream; skeletons from the graph, text from the LLM |
| `data/events_repaired.json` | Event stream after deterministic structural repair |
| `data/notes.json` | Human-like notes derived from events (the retrieval corpus) |
| `data/qa_pairs.json` | QA pairs with `answer_key` (evidence note IDs, ordered where order matters), `supporting_notes`, type and difficulty |
| `data/qa_gen_discards.json` | QA candidates stage 05 rejected, with reasons |
| `data/MANIFEST.json` | Corpus version, file hashes, generator identity and validation result. Cite this id in eval reports. |

Also in `data/`, not pipeline outputs: `qa_pairs_v1_snapshot.json` (the old v1 QA set, with
known-bad answers), the `grounding_gate_*.json` audit files and `mutation_log.json`.

## What gets checked

**Per-stage validators** (print warnings):
- Stage 01: schema, at least `MIN_ENTITIES` entities and `MIN_STORY_ARCS` arcs, valid arc-to-entity references.
- Stage 02: unique event IDs, ordered timestamps, entity and arc references exist, importance 1–5, `affect.valence` in {-1, 0, 1}, `affect.intensity` in {0–3}.
- Stage 03: no LLM. Strips unknown entities, nulls invalid arc IDs, clamps importance, re-sorts timestamps.
- Stage 04: unique note IDs, required keys present, no empty text, importance is `low`/`medium`/`high`. [`note_quality.py`](note_quality.py) checks single notes during generation (for example, a contradiction note must read as a change of mind).
- Stage 05: the answer key is computed in code from facts the pipeline already knows. An independent model (`VERIFIER_MODEL`) checks that each pinned fact is supported by its note, and that unanswerable questions can't be answered blind. Pairs that fail are discarded.

**Hard gate** ([`validate_corpus.py`](validate_corpus.py), run by `run_pipeline.py`):
- F1: no invented proper names outside the world roster.
- F2: every involved entity has a rendering in its note, and a rendering claimed as explicit appears in the text verbatim.
- F3: every event has a well-formed affect.
- F4: one note schema, no duplicate IDs, and all IDs across files resolve.

[`grounding_gate.py`](grounding_gate.py) is a separate, read-only cross-model check over an
existing `qa_pairs.json`. It was calibrated at 4/6 on known cases, so treat its verdicts as
advisory.

## Files

```
├── config.py, prompts.py, llm.py     # shared configuration, prompts, LLM client
├── run_pipeline.py                   # runs all 5 stages, then the gate and manifest
├── stage_01_world_state.py … stage_05_qa_generation.py
├── knowledge_graph.py                # graph + random-walk skeletons (stages 02, 03)
├── note_quality.py                   # per-note checks used by stage 04
├── validate_corpus.py                # F1–F4 hard gate
├── corpus_manifest.py                # writes data/MANIFEST.json
├── grounding_gate.py                 # optional cross-model QA check
├── tests/                            # pytest, no LLM needed
├── data/                             # checked-in corpus from the last run
└── demo/                             # the separate facts-first demo
```

## Design decisions

**Centralised configuration.** No stage hardcodes a model, URL or path; they all import from `config.py`.

**Shared LLM client.** One `call_llm()` replaces five near-identical per-stage clients and supports both backends behind one interface.

**Prompts separate from logic.** Editing a prompt never requires touching pipeline code.

**Knowledge graph as backbone.** `knowledge_graph.py` turns `world_state.json` into a `networkx` graph so stages 02 and 03 check structure in code instead of asking an LLM to guess valid IDs.

**Event skeletons.** Stage 02 pre-fills `story_arc_id`, `involved_entities` and `timestamp` with a biased random walk (scored on arc connectivity, recency and graph degree) before calling the LLM. The LLM only writes text, latent-fact updates, importance and affect.

**Contradiction injection.** For each unresolved arc, stage 02 adds `CONTRADICTIONS_PER_ARC` later events that revise an earlier fact, so `conflict_resolution` questions are possible.

**No LLM repair pass.** Stage 03 fixes structure deterministically. An LLM repair pass was removed because it was slow and risked silently rewriting content.

**Answer key computed in code (v2).** Stage 05 picks the evidence first, computes the key from known facts, and only asks the LLM to phrase the question. The earlier design let one LLM call write the question, the answer and the label, and about 17–20% of answers were wrong.

**Messiness rules in stage 04.** Each note gets one to three random rules (OMISSION, ABRUPT_END, IMPLICIT_REFERENCE, UNCERTAINTY, LATENT_FACT_AS_TEXTURE) so latent facts aren't stated outright, which would make retrieval unrealistically easy.

**Unattended runner with long-run-safe Ollama defaults.** See Usage and Setup.

## Ideas not yet started

**Evaluating summarisation.** The world state tracks every entity, arc and latent fact, so a
system's summaries of the timeline could be scored against it: did it link the right entities,
and did it leave anything out or make anything up?
