"""
run_pipeline.py — Sequential pipeline runner
===============================================
Runs all 5 pipeline stages in order, one after another, without requiring
anyone to stay at the keyboard. Intended for long, unattended runs (e.g. a
90-day simulation on a 70B model, which can take hours).

Each stage is run as a subprocess. If a stage fails, the runner stops
immediately and prints which stage failed and why — it does not continue
to the next stage with broken or missing input data.

A full log of stdout/stderr from every stage is written to
pipeline_run.log in the project root, in addition to being printed live
to the console. This means you can walk away and check the log later
instead of having to watch the terminal the whole time.

After all 5 stages succeed, the runner runs `validate_corpus.py`'s checks
itself — nobody has to remember to
run it by hand. This is a **hard gate**: if validation fails, the run exits
non-zero and says so loudly, both on the console and in the log. Either way
(pass or fail) it writes `data/MANIFEST.json` recording a `corpus_version`, a hash of every output file, the
generator/config identity, and the validation result — see
`corpus_manifest.py` and `PIPELINE.md`.

Usage:
    python run_pipeline.py

    # Re-run just the hard gate + manifest against whatever is already in
    # data/, without regenerating anything (no LLM calls) — e.g. after
    # hand-editing a QA pair, or to test the gate itself:
    python run_pipeline.py --validate-only

To run only a subset of stages (e.g. to resume after a fix), edit the
STAGES list below and comment out the ones you don't want to re-run.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import config
import corpus_manifest
import validate_corpus

STAGES = [
    "stage_01_world_state.py",
    "stage_02_event_timeline.py",
    "stage_03_repair.py",
    "stage_04_note_generation.py",
    "stage_05_qa_generation.py",
]

LOG_FILE = Path("pipeline_run.log")


def log_line(text: str, log_handle) -> None:
    """Print to console and write to the log file simultaneously."""
    print(text)
    log_handle.write(text + "\n")
    log_handle.flush()


def run_stage(script: str, log_handle) -> bool:
    """
    Run one stage as a subprocess, streaming its output live.
    Returns True if the stage exited successfully, False otherwise.
    """
    log_line(f"\n{'=' * 70}", log_handle)
    log_line(f"  STARTING: {script}   ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})", log_handle)
    log_line(f"{'=' * 70}\n", log_handle)

    start = time.time()

    process = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        log_line(line.rstrip(), log_handle)

    process.wait()
    elapsed = time.time() - start
    minutes = elapsed / 60

    if process.returncode == 0:
        log_line(f"\n✓ {script} completed in {minutes:.1f} minutes.\n", log_handle)
        return True
    else:
        log_line(
            f"\n✗ {script} FAILED (exit code {process.returncode}) "
            f"after {minutes:.1f} minutes.\n",
            log_handle,
        )
        return False


def run_validation_and_manifest(log_handle) -> bool:
    """Run validate_corpus.py's checks against data/ and write data/MANIFEST.json
    Always writes a manifest —
    pass or fail — so "which corpus, was it checked, did it pass" always lives in
    one generated file instead of relying on someone remembering to run the
    validator by hand. Returns True if validation passed, False otherwise; the
    caller is responsible for turning False into a loud, non-zero-exit failure.
    """
    log_line(f"\n{'=' * 70}", log_handle)
    log_line("  RUNNING validate_corpus.py (hard gate — F1-F4 invariants)", log_handle)
    log_line(f"{'=' * 70}\n", log_handle)

    data_dir = str(config.PATHS["notes"].parent)
    fails, warns, stats = validate_corpus.validate(data_dir)
    ran_at = datetime.now(timezone.utc)
    validation_stamp = {
        "checker": "validate_corpus.py",
        "ran_at": ran_at.isoformat(),
        "status": "passed" if not fails else "failed",
        "stats": stats,
        "warnings": warns,
        "failures": fails,
    }

    manifest = corpus_manifest.build_manifest(validation=validation_stamp)
    manifest_path = corpus_manifest.write_manifest(manifest)
    log_line(
        f"Manifest written: {manifest_path} "
        f"(corpus_version={manifest['corpus_version']})",
        log_handle,
    )

    log_line(
        f"notes={stats['notes']} events={stats['events']} qa={stats['qa']} "
        f"f1_invented_notes={stats['f1_invented_notes']}",
        log_handle,
    )

    if fails:
        log_line(f"\n✗ VALIDATION FAILED — {len(fails)} hard failure(s):", log_handle)
        for f in fails[:60]:
            log_line("   " + f, log_handle)
        if len(fails) > 60:
            log_line(f"   … and {len(fails) - 60} more (see MANIFEST.json / re-run "
                      f"validate_corpus.py directly for the full list)", log_handle)
        return False

    log_line("\n✓ validate_corpus.py passed — all F1-F4 invariants hold.", log_handle)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1] if len(__doc__.splitlines()) > 1 else None)
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Skip the 5 generation stages (no LLM calls) and only run the hard "
             "gate + manifest step against whatever is already in data/. Useful "
             "for re-checking after a hand edit, or for testing the gate itself.",
    )
    args = parser.parse_args()

    overall_start = time.time()

    with open(LOG_FILE, "w", encoding="utf-8") as log_handle:
        log_line(f"Pipeline run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_handle)

        if args.validate_only:
            log_line("Mode: --validate-only (no generation stages, no LLM calls)", log_handle)
        else:
            log_line(f"Stages to run: {len(STAGES)}", log_handle)
            log_line(f"Full log: {LOG_FILE.resolve()}", log_handle)

            for script in STAGES:
                if not Path(script).exists():
                    log_line(f"\n✗ Cannot find '{script}' in the current directory. Stopping.", log_handle)
                    sys.exit(1)

                success = run_stage(script, log_handle)
                if not success:
                    log_line(
                        f"\nPipeline stopped at '{script}'. "
                        f"Check the output above (and {LOG_FILE}) for the error, fix it, "
                        f"then re-run this script. Earlier stages do not need to be repeated "
                        f"as long as their output files in data/ are still present. "
                        f"No MANIFEST.json was written for this failed run.",
                        log_handle,
                    )
                    sys.exit(1)

        validation_ok = run_validation_and_manifest(log_handle)

        total_minutes = (time.time() - overall_start) / 60
        log_line(f"\n{'=' * 70}", log_handle)
        if validation_ok:
            log_line(f"  ALL STAGES COMPLETE AND VALIDATED — total time: {total_minutes:.1f} minutes", log_handle)
        else:
            log_line(f"  STAGES COMPLETE BUT VALIDATION FAILED — total time: {total_minutes:.1f} minutes", log_handle)
        log_line(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", log_handle)
        log_line(f"{'=' * 70}", log_handle)

        if not validation_ok:
            log_line(
                "\nThis corpus FAILED validate_corpus.py and must not be treated as "
                "generated. See the failures above, data/MANIFEST.json's \"validation\" "
                "field, or run `python validate_corpus.py` directly for the full list. "
                "Fix the underlying stage/prompt and re-run.",
                log_handle,
            )
            sys.exit(1)

        log_line("\nOutputs are in the data/ directory:", log_handle)
        log_line("  data/world_state.json", log_handle)
        log_line("  data/events_raw.json", log_handle)
        log_line("  data/events_repaired.json", log_handle)
        log_line("  data/notes.json", log_handle)
        log_line("  data/qa_pairs.json", log_handle)
        log_line("  data/MANIFEST.json  (corpus_version + validation stamp)", log_handle)


if __name__ == "__main__":
    main()
