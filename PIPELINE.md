# Pipeline reference

The 5-stage pipeline in the repo root generates a richer corpus than `demo/`: story arcs,
contradictions, deliberately messy notes, and a QA set whose answer key is a set of evidence
note IDs. `demo/` is separate and documented in [`demo/README.md`](demo/README.md).

## How it works

```
stage_01_world_state.py     →  data/world_state.json     hidden truth: people, arcs, latent facts
stage_02_event_timeline.py  →  data/events_raw.json      event skeletons from a graph walk, text from the LLM
stage_03_repair.py          →  data/events_repaired.json structural fixes in code, no LLM
stage_04_note_generation.py →  data/notes.json           one messy note per event (the retrieval corpus)
stage_05_qa_generation.py   →  data/qa_pairs.json        questions with an answer key, checked by a second model
validate_corpus.py          →  hard gate; corpus_manifest.py then writes data/MANIFEST.json
```

Shared modules: [`config.py`](config.py) (every model, path and parameter), [`prompts.py`](prompts.py)
(every LLM prompt), [`llm.py`](llm.py) (`call_llm()`, Ollama or Anthropic, retries on bad JSON) and
[`knowledge_graph.py`](knowledge_graph.py) (a `networkx` graph of the world, used by stages 02 and 03).

Key choices:
- **Structure in code, text from the LLM.** Stage 02 fills each event's arc, people and timestamp
  with a biased random walk over the graph; the LLM only writes the text. Stage 03 repairs
  structure deterministically.
- **The answer key is computed, not written.** Stage 05 picks the evidence first, from facts the
  pipeline already knows, and asks the LLM only to phrase the question. An independent model
  (`VERIFIER_MODEL`, a different family) checks that each pinned fact is in its note and that
  unanswerable questions can't be answered blind. Pairs that fail are discarded.
- **Contradictions on purpose.** For each unresolved arc, stage 02 adds `CONTRADICTIONS_PER_ARC`
  later events that revise an earlier fact, so `conflict_resolution` questions exist.
- **Messy notes on purpose.** Each note gets one to three random rules (OMISSION, ABRUPT_END,
  IMPLICIT_REFERENCE, UNCERTAINTY, LATENT_FACT_AS_TEXTURE) so facts aren't stated outright.

## Setup

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Ollama (default, local):**

```bash
ollama serve
ollama pull qwen3:30b     # generator (OLLAMA_MODEL)
ollama pull gemma3:27b    # stage 05 verifier (VERIFIER_MODEL)
```

The defaults suit a 48 GB machine. `llm.py` turns qwen3's thinking off; remove that flag if you
switch to a model without thinking support. `OLLAMA_TIMEOUT_SECONDS` and `OLLAMA_KEEP_ALIVE` in
`config.py` are set for multi-hour runs (long timeout, model kept loaded); set keep-alive back to
`"5m"` on a shared Ollama instance.

**Anthropic API:** `export ANTHROPIC_API_KEY=...` and set `BACKEND = "anthropic"` in `config.py`.
The stage 05 verifier still runs on Ollama, so `gemma3:27b` is needed either way.

## Run

```bash
.venv/bin/python run_pipeline.py                  # all 5 stages, then the gate and manifest
.venv/bin/python run_pipeline.py --validate-only  # gate and manifest only, no LLM calls
.venv/bin/python stage_03_repair.py               # any single stage
```

The runner stops at the first failing stage and logs to `pipeline_run.log`. Stages whose output
is already in `data/` don't need re-running. **A run overwrites the checked-in corpus in `data/`.**

After the stages, `validate_corpus.py` runs as a hard gate; if it fails, the run exits non-zero
and the corpus must not be used:
- F1: no invented proper names outside the world roster.
- F2: every involved entity appears in its note.
- F3: every event has a well-formed affect.
- F4: one note schema, no duplicate IDs, all IDs across files resolve.

Pass or fail, `data/MANIFEST.json` records a `corpus_version`, a SHA-256 per file, the generator
settings and the gate result. Cite the `corpus_version` in eval reports.

[`grounding_gate.py`](grounding_gate.py) is an optional, read-only second-model check over an
existing `qa_pairs.json`. Its verdicts are another model's judgement, so treat them as advisory.

## Main settings (`config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `BACKEND` | `"ollama"` | or `"anthropic"` |
| `OLLAMA_MODEL` / `ANTHROPIC_MODEL` | `qwen3:30b` / `claude-sonnet-5` | generator |
| `VERIFIER_MODEL` | `gemma3:27b` | stage 05 check, different model family |
| `DURATION_DAYS`, `EVENTS_PER_DAY` | 90, 0.8 | together set the event count (see limitations) |
| `MIN_ENTITIES`, `MIN_STORY_ARCS` | 15, 6 | enforced by stage 01 |
| `CONTRADICTIONS_PER_ARC` | 1 | revising events per unresolved arc |
| `ARC_CONTEXT_NOTES` | 0 | earlier notes of the same arc shown when writing the next |
| `RARE_ENTITY_COUNT` | 0 | entities given rare, distinctive names |
| `QA_COUNT` | 6 per type | single_hop, multi_hop, temporal_reasoning, conflict_resolution, unanswerable, belief_currency |

## Data files

| File | Contents |
|---|---|
| `data/world_state.json` | hidden truth: profile, entities, story arcs, latent facts |
| `data/events_raw.json`, `events_repaired.json` | the event stream before and after stage 03 |
| `data/notes.json` | the notes: the corpus a RAG system searches |
| `data/qa_pairs.json` | questions; `answer_key.evidence` lists the note IDs that answer each one (empty for unanswerable). `supporting_notes` records the note a question was built from. |
| `data/qa_gen_discards.json` | candidates stage 05 rejected, with reasons |
| `data/MANIFEST.json` | corpus version, file hashes, settings, gate result |
| `data/qa_pairs_v1_snapshot.json` | an older QA set where one LLM call wrote question and answer together; kept for comparison |
| `data/grounding_gate_*.json` | `grounding_gate.py` outputs |

A new run also writes `data/mutation_log.json` (stage 04's fact-level change log).

## Known limitations of the checked-in corpus

- **It predates the `phase_state` note field**, so `validate_corpus.py` reports 154 F4 failures
  (two per note, 77 notes). Everything else passes. A new run produces the field. Don't add it by
  hand: that breaks the hashes in `MANIFEST.json`.
- **It spans 22 days, not 90.** `DURATION_DAYS` only sets the event count; the span comes from
  random gaps between events. `validate_corpus.py` warns about this.
- **20 questions in 5 types.** 28 of 48 candidates (58%) were discarded by stage 05's checks, and
  the `belief_currency` type isn't in this set.
- **Some answer keys may be stale or wrong.** Activities repeat on several days, so a "latest state"
  key can point at an older note. Suspect questions are listed in
  [`eval/runs/20261028_122655/NOTES.md`](eval/runs/20261028_122655/NOTES.md).
