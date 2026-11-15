#!/usr/bin/env python3
"""Regenerate tests/golden/* from the current reference config.

Run this ONLY when you deliberately change the production reference (configs/v1_1_a_baseline.json or the
pipeline structure). The golden files exist so that accidental changes fail the tests.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shorts_engine import render, timeline  # noqa: E402
from shorts_engine.config import load_config  # noqa: E402

REFERENCE = ROOT / "configs" / "v1_1_a_baseline.json"
GOLDEN = ROOT / "tests" / "golden"


def reference_plan_summary(cfg, config_path: str) -> dict:
    """Machine-independent summary of what the planner would run for the reference config."""
    jobs = render.plan_jobs(cfg, config_path, ["blender"], True)
    concat = next(j for j in jobs if j.kind == "concat")
    names = [Path(line.split("'")[1]).name for line in concat.write_text[1].strip().splitlines()]
    return {
        "job_kinds": [j.kind for j in jobs],
        "concat_order": names,
        "total_seconds": timeline.total_seconds(cfg),
        "segments": [[s.kind, s.stage, s.first, s.last, round(s.start_time, 6)] for s in timeline.segments(cfg)],
        "final_video": f"{cfg.name}/{cfg.name}.mp4",
        "silent_video": f"{cfg.name}/{cfg.name}_silent.mp4",
    }


def main() -> None:
    cfg = load_config(REFERENCE)
    GOLDEN.mkdir(exist_ok=True)
    (GOLDEN / "reference_config.json").write_text(json.dumps(asdict(cfg), indent=1, sort_keys=True) + "\n")
    (GOLDEN / "reference_plan.json").write_text(
        json.dumps(reference_plan_summary(cfg, str(REFERENCE)), indent=1) + "\n")
    print("updated", GOLDEN)


if __name__ == "__main__":
    main()
