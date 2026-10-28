"""corpus_manifest.py — corpus versioning.

WHY: regenerating this pipeline is destructive and non-deterministic —
event text, arcs, note wording, and every QA id shift on every run. Without a version,
nothing ties an eval report or a "known-bad id" list to the corpus it was written
against. This module gives every generated corpus a
`corpus_version` (a timestamp + content-hash id, so two regenerations never collide even
if nothing else changed) and writes it, plus a per-file hash manifest and the
generator/config identity, to `data/MANIFEST.json`. `run_pipeline.py` calls this
automatically at the end of every run — nobody has to remember to snapshot anything.

This also carries the validate_corpus.py stamp: `build_manifest()`
takes an optional `validation` dict and writes it straight into the manifest, so
"which corpus" and "did it pass the gate" always live in the same file.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import config

# The 5 pipeline outputs, in generation order. Keys match config.PATHS.
OUTPUT_FILE_KEYS = ["world_state", "events_raw", "events_repaired", "notes", "qa_pairs"]

MANIFEST_PATH = config.PATHS["manifest"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str | None:
    """Best-effort short commit hash of the repo this pipeline lives in. None if
    git isn't available or this isn't a git checkout — never fatal."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _model_identity() -> dict:
    if config.BACKEND == "anthropic":
        model = config.ANTHROPIC_MODEL
    else:
        model = config.OLLAMA_MODEL
    return {"backend": config.BACKEND, "model": model}


def build_manifest(validation: dict | None = None) -> dict:
    """Build the manifest dict for whatever is currently on disk in data/. Does not
    write anything — call write_manifest() with the result to persist it. Safe to
    call with a partial data/ directory (e.g. mid-pipeline); missing files are
    listed under "missing_files" rather than raising.
    """
    files = {}
    missing = []
    for key in OUTPUT_FILE_KEYS:
        path = config.PATHS[key]
        if not path.exists():
            missing.append(key)
            continue
        files[key] = {
            "path": str(path.as_posix()),
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        }

    # Content hash over the present files' own hashes, in a fixed key order, so the
    # combined hash is stable regardless of filesystem mtimes and independent of
    # dict ordering.
    combined = hashlib.sha256()
    for key in OUTPUT_FILE_KEYS:
        if key in files:
            combined.update(key.encode("utf-8"))
            combined.update(files[key]["sha256"].encode("utf-8"))
    content_hash = combined.hexdigest()[:12]

    now = datetime.now(timezone.utc)
    corpus_version = f"v{now.strftime('%Y%m%dT%H%M%SZ')}_{content_hash}"

    manifest = {
        "corpus_version": corpus_version,
        "generated_at": now.isoformat(),
        "generator": {
            "pipeline": "synthetic-journal-generator",
            "git_commit": _git_commit(),
            **_model_identity(),
            "verifier_model": getattr(config, "VERIFIER_MODEL", None),
            "duration_days": config.DURATION_DAYS,
            "events_per_day": config.EVENTS_PER_DAY,
            "qa_count": config.QA_COUNT,
        },
        "files": files,
        "missing_files": missing,
        # Filled in by run_pipeline.py after validate_corpus.py runs. None here
        # means "this manifest was built without running the gate" (e.g. a stage
        # failed before validation could run) — that absence is itself a signal,
        # never silently treated as a pass.
        "validation": validation,
    }
    return manifest


def write_manifest(manifest: dict, path: Path | None = None) -> Path:
    path = path or MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return path


if __name__ == "__main__":
    # Standalone use: regenerate MANIFEST.json for whatever is on disk right now,
    # without re-running validate_corpus.py (validation will be null). Mainly for
    # manual inspection / debugging — run_pipeline.py is the normal caller.
    m = build_manifest(validation=None)
    p = write_manifest(m)
    print(f"Wrote {p} (corpus_version={m['corpus_version']}, "
          f"{len(m['files'])} file(s), {len(m['missing_files'])} missing)")
