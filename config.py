"""
config.py — Central configuration
===================================
All tunable parameters live here. Edit this file to change the model,
backend, data directory, or pipeline behaviour. Individual stage files
import from here and should not need to be edited for routine runs.
"""

from pathlib import Path

# ── Backend ───────────────────────────────────────────────────────────────────
# "ollama"     — local inference via Ollama (free, no internet required)
# "anthropic"  — Anthropic API (paid, highest quality)
# Owner decision 2026-07-11 (supersedes the earlier Anthropic pick the same
# day): benchmark runs generate locally with qwen3:30b — no API key.

BACKEND = "ollama"

# ── Model ─────────────────────────────────────────────────────────────────────
# Ollama model name (ignored when BACKEND = "anthropic").
# qwen3:30b is the owner's pick (2026-07-11) — the same model class his live
# Reflect instance runs. NOTE: qwen3 is a reasoning model; llm.py sends
# "think": false to suppress its thinking phase (JSON reliability + speed).
# Remove that flag if you switch to a model without thinking support.

OLLAMA_MODEL    = "qwen3:30b"
OLLAMA_BASE_URL = "http://localhost:11434/api/generate"

# Context window for Ollama calls (prompt + output together, unlike the
# Anthropic max_tokens below which is output-only). Stage 02 sends the full
# world state and gets ~70 events back in one JSON response; 16k risks silent
# context overflow, and this machine (48 GB) affords the KV cache for 32k.
OLLAMA_NUM_CTX = 32768

# Anthropic model (ignored when BACKEND = "ollama").
# claude-sonnet-5: owner's pick for data generation (2026-07-11) — near-Opus
# quality at Sonnet cost. Note: current models reject the `temperature`
# parameter, so the TEMPERATURE table below only applies to the Ollama
# backend — variety comes from the prompts' realism requirements.
ANTHROPIC_MODEL = "claude-sonnet-5"

# ── Generation parameters ─────────────────────────────────────────────────────

# Doubles as Anthropic max_tokens and Ollama num_ctx. Stage 02 returns the
# whole ~70-event timeline in one JSON response, which can overrun 8192.
MAX_TOKENS  = 16000
MAX_RETRIES = 3      # retry attempts on JSON parse failure (llm.py) or a
                      # schema-incomplete note (stage_04's generate_note)

# Ollama request timeout in seconds. Larger models (e.g. 70B) take
# considerably longer per call, especially on stage_02 where the full
# world state and event skeletons are sent in one prompt. 3600s (1 hour)
# gives a 70B model on CPU-only hardware enough headroom; lower this if
# you have GPU acceleration and want faster failure detection instead.
OLLAMA_TIMEOUT_SECONDS = 3600

# How long Ollama keeps the model loaded in memory after a response.
# Ollama's own default is "5m" — on a multi-hour 90-day pipeline run with
# gaps between calls (e.g. while this script does graph computation),
# that default would unload a 70B model between stages, forcing an
# expensive reload (can be 30-60+ seconds for a 70B model) on every call.
# "-1" keeps the model loaded indefinitely for the life of the Ollama
# server. Set back to "5m" if you are sharing this Ollama instance with
# other applications and need it to free memory automatically.
OLLAMA_KEEP_ALIVE = -1

# Per-stage temperature overrides.
# Higher = more creative output; lower = more structural reliability.
TEMPERATURE = {
    "stage_01": 0.7,   # world state — needs variety
    "stage_02": 0.7,   # event timeline — needs variety
    "stage_03": 0.3,   # repair — needs precision
    "stage_04": 0.8,   # note generation — needs creative realism
    "stage_05": 0.5,   # QA generation — balanced
}

# ── Pipeline parameters ───────────────────────────────────────────────────────

DURATION_DAYS   = 90    # number of days to simulate in the event timeline
EVENTS_PER_DAY  = 0.8   # average events per day (actual count varies)
START_DATE      = "2024-01-01"  # ISO date string, parsed in stage_02

# How many contradiction events to inject per unresolved arc. 1 = the original
# behaviour (one belief-revision per arc). Raise it to make a corpus's drift
# denser for eval; each contradiction gets a distinct event id.
CONTRADICTIONS_PER_ARC = 1

# How many of an arc's own recent already-generated notes to feed forward as
# context (+ the rolling phase_state snapshot) when writing its next note. 0 =
# the original behaviour (each note written blind, no cross-note context within
# an arc) -- the regression-guard default, so leaving this untouched reproduces
# today's stage_04 prompts byte-for-byte. This is the Bundle 21 Item B3
# duplicate-density dial: raise it at regen time to test whether arc-batched
# context reduces near-duplicate phrasing across an arc's notes.
ARC_CONTEXT_NOTES = 0

# Raised 2026-07-11 for the tag-mvp concept-resolution benchmark: more
# entities and arcs = more coreference/dedup signal per corpus. Injected
# into the stage-01 prompt and enforced by its validator.
MIN_ENTITIES    = 15    # minimum entities enforced by the validator
MAX_ENTITIES    = 25    # maximum entities instructed to the model
MIN_STORY_ARCS  = 6     # minimum story arcs (was ~3 in the smoke run)

# How many entities must be given deliberately RARE, distinctive proper names
# (unusual surnames, uncommon place/brand names). 0 = no such requirement (the
# original behaviour). Raise it to seed the rare-anchor lexical condition BM25's
# upside needs — the current corpora have none (REPORT_bundle14_bm25_features.md).
RARE_ENTITY_COUNT = 0

# Number of QA pairs to generate per type in stage_05.
# Raised 3->6/type (15->30 total) 2026-07-12 for Experiment 1 (eval/rag REPORT_syn_v1.md) --
# n=12 (2-3/type after generation failures) was too small to read failure-mode distribution.
QA_COUNT = {
    "single_hop":          6,
    "multi_hop":           6,
    "temporal_reasoning":  6,
    "conflict_resolution": 6,
    "unanswerable":        6,
    "belief_currency":     6,
}

# ── Verifier (stage_05 narrow grounding check) ──────────────────────────────────
# Independent model from the qwen3:30b generator (Google family, not Alibaba) so it
# never grades its own homework -- same choice grounding_gate.py made, validated by
# REPORT_datagen_grounding.md's calibration pass (3/4 known defects caught blind).
# stage_05 uses this for two narrow checks, not the old broad "grade the whole QA
# pair" gate: (1) does a note actually support the specific fact its answer is
# pinned to, (2) for unanswerable pairs, can this model answer the question blind.
VERIFIER_MODEL           = "gemma3:27b"
VERIFIER_TIMEOUT_SECONDS = 600

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")

PATHS = {
    "world_state":       DATA_DIR / "world_state.json",
    "events_raw":        DATA_DIR / "events_raw.json",
    "events_repaired":   DATA_DIR / "events_repaired.json",
    "notes":             DATA_DIR / "notes.json",
    "mutation_log":      DATA_DIR / "mutation_log.json",  # S6: ADD/UPDATE/INVALIDATE fact-level log
    "qa_pairs":          DATA_DIR / "qa_pairs.json",
    # Written by corpus_manifest.py (called automatically by run_pipeline.py at the
    # end of every run) — corpus_version, per-file hashes, generator identity, and
    # the validate_corpus.py stamp. See RECOMMENDATIONS.md #5 / #1.
    "manifest":          DATA_DIR / "MANIFEST.json",
}