"""Content library: an index of every video the engine has produced (pure Python).

    python -m shorts_engine.library index  ROOT [ROOT...]     # scan for metadata.json, write ROOT/library.json
    python -m shorts_engine.library list   ROOT [--experiment NAME] [--failed]
    python -m shorts_engine.library experiments                # the experiment registry

A video is catalogued from the files the pipeline already writes: metadata.json (config, experiment, seed, labels),
qc_report.json and benchmark.json. The index feeds the diversity selector (what was already made?) and gives one
place to look up "which videos exist, with which physics, and did they pass QC".
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .templates import TEMPLATES


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def entry_from_dir(video_dir: Path) -> dict | None:
    meta = read_json(video_dir / "metadata.json")
    if not isinstance(meta, dict) or "experiment_config" not in meta:
        return None
    exp = meta["experiment_config"]
    qc = read_json(video_dir / "qc_report.json") or {}
    bench = (read_json(video_dir / "benchmark.json") or {}).get("summary", {})
    video = video_dir / f"{meta['name']}.mp4"
    return {
        "name": meta["name"],
        "experiment": meta["experiment"],
        "object": exp["experiment"]["object"],
        "params": exp["experiment"]["params"],
        "stage_values": [list(s["params"].values())[0] for s in exp["stages"]],
        "stage_labels": meta.get("stage_labels", []),
        "seed": meta.get("seed"),
        "resolution": meta.get("resolution"),
        "planned_seconds": meta.get("planned_seconds"),
        "created_utc": meta.get("created_utc"),
        "git_sha": meta.get("git_sha"),
        "variation": meta.get("variation"),
        "video": str(video),
        "video_exists": video.is_file(),
        "qc_passed": qc.get("passed"),
        "render_seconds": bench.get("total_wall_seconds"),
        "devices": bench.get("render_devices"),
        "path": str(video_dir),
    }


def scan(roots) -> list[dict]:
    seen: dict[str, dict] = {}
    for root in roots:
        for meta in sorted(Path(root).rglob("metadata.json")):
            e = entry_from_dir(meta.parent)
            if e:
                seen[e["path"]] = e
    return sorted(seen.values(), key=lambda e: (e.get("created_utc") or "", e["name"]))


def build_index(roots, out: Path | None = None) -> dict:
    entries = scan(roots)
    index = {"version": 1, "count": len(entries),
             "by_experiment": {n: sum(1 for e in entries if e["experiment"] == n) for n in TEMPLATES},
             "qc_failed": [e["name"] for e in entries if e["qc_passed"] is False],
             "entries": entries}
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(index, indent=1))
    return index


def history_vectors(entries) -> list[tuple[str, dict]]:
    """(experiment, vector) for each catalogued video that passed (or has not yet been checked), for diversity."""
    from .variation import vector_of
    out = []
    for e in entries:
        if e["experiment"] in TEMPLATES and e.get("qc_passed") is not False:
            try:
                out.append((e["experiment"], vector_of(e["experiment"], e["params"], e["stage_values"], e["object"])))
            except (KeyError, ValueError):
                continue
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shorts_engine.library")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("index"); i.add_argument("roots", nargs="+")
    ls = sub.add_parser("list"); ls.add_argument("root"); ls.add_argument("--experiment"); ls.add_argument("--failed", action="store_true")
    sub.add_parser("experiments")
    args = p.parse_args(argv)
    if args.cmd == "experiments":
        for t in TEMPLATES.values():
            print(f"{t.name:<16} {t.simulation:<10} stages: {t.stage_param} {list(t.default_stage_values)}  - {t.description}")
        return 0
    if args.cmd == "index":
        out = Path(args.roots[0]) / "library.json"
        idx = build_index(args.roots, out)
        print(f"{idx['count']} video(s) catalogued -> {out}")
        for name, n in idx["by_experiment"].items():
            print(f"  {name:<16} {n}")
        return 0
    entries = scan([args.root])
    for e in entries:
        if args.experiment and e["experiment"] != args.experiment:
            continue
        if args.failed and e["qc_passed"] is not False:
            continue
        print(f"{e['name']:<34} {e['experiment']:<15} seed={e['seed']} qc={e['qc_passed']} {e['resolution']} {e['video']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
