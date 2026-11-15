"""Regression tests that freeze the known-good V1.1 production pipeline (the cloth-on-sphere reference).

Static tests run everywhere. The end-to-end test needs the `bpy` module and FFmpeg and runs the REAL pipeline
(bake -> render -> events -> hook -> assemble -> music + SFX) on a tiny version of the reference config.

If you change the reference on purpose, run `python tools/update_golden.py` and review the diff.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import update_golden  # noqa: E402

from shorts_engine import timeline  # noqa: E402
from shorts_engine.config import from_dict, load_config  # noqa: E402

REFERENCE = ROOT / "configs" / "v1_1_a_baseline.json"
GOLDEN = ROOT / "tests" / "golden"
CFG = load_config(REFERENCE)


# ------------------------------------------------------------------ frozen production behaviour
def test_reference_config_matches_the_golden_snapshot():
    golden = json.loads((GOLDEN / "reference_config.json").read_text())
    assert asdict(CFG) == golden, "reference config changed; if intended run tools/update_golden.py"


def test_reference_plan_matches_the_golden_snapshot():
    golden = json.loads((GOLDEN / "reference_plan.json").read_text())
    assert update_golden.reference_plan_summary(CFG, str(REFERENCE)) == golden


def test_reference_production_properties_stated_explicitly():
    """The same facts as the golden files, spelled out so a failure says what broke."""
    assert (CFG.output.width, CFG.output.height) == (720, 1280)                   # 9:16
    assert CFG.output.width * 16 == CFG.output.height * 9
    assert CFG.fps == 30 and CFG.frame_count == 90                                # 3 s stages
    assert (CFG.render.samples, CFG.render.denoise) == (16, False)                # no-denoise is a valid mode
    assert CFG.resolutions == [64, 1024, 4096, 16384]
    assert [s.label for s in CFG.stages()] == ["64 FACES", "1,024 FACES", "4,096 FACES", "16,384 FACES"]
    assert CFG.video.hook.mode == "closeup" and "256×" in CFG.hook_text()
    assert not CFG.video.cards.enabled and CFG.cards() == []                      # no multiplier cards
    assert CFG.audio.enabled and CFG.audio.music_enabled and CFG.audio.sfx_enabled
    assert CFG.music_path().is_file() and CFG.audio.volume_db == -18
    assert timeline.total_seconds(CFG) == pytest.approx(14.0)
    assert [s.kind for s in timeline.segments(CFG)] == ["hook", "stage", "stage", "stage", "stage"]


def test_optix_denoiser_is_never_mandatory():
    assert CFG.render.denoise is False                                            # no-denoise is a valid production mode
    assert from_dict({}).render.denoiser != "OPTIX"                              # OptiX failed on the Kaggle T4
    assert from_dict({"render": {"denoise": False}}).render.denoise is False
    assert load_config(ROOT / "configs" / "v1_1_b_optix.json").render.denoiser == "OPTIX"  # opt-in test config only


def test_other_test_configs_only_differ_from_the_reference_where_intended():
    b = load_config(ROOT / "configs" / "v1_1_b_optix.json")
    c = load_config(ROOT / "configs" / "v1_1_c_1080p.json")
    ref = asdict(CFG)
    for other, allowed in ((b, {"name", "render"}), (c, {"name", "output"})):
        diff = {k for k, v in asdict(other).items() if v != ref[k]}
        assert diff == allowed


def test_v1_reference_config_still_loads_and_plans():
    from shorts_engine import render
    v1 = load_config(ROOT / "configs" / "example_cloth.json")
    jobs = render.plan_jobs(v1, str(ROOT / "configs" / "example_cloth.json"), ["blender"], True)
    assert [j.kind for j in jobs][-2:] == ["hook", "concat"]                       # V1 behaviour: tail hook, no audio


# ------------------------------------------------------------------ Kaggle / GitHub Actions
def test_kaggle_workflow_inputs_match_the_fixed_config_mapping():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "kaggle-gpu-test.yml").read_text())
    inputs = wf[True]["workflow_dispatch"]["inputs"]                              # `on:` parses as True in YAML 1.1
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("ka", ROOT / "kaggle" / "kaggle_automation.py")
    ka = module_from_spec(spec)
    spec.loader.exec_module(ka)
    assert inputs["test_config"]["options"] == list(ka.CONFIGS) == ["baseline", "optix", "1080p"]
    assert set(inputs["accelerator"]["options"]) == set(ka.ACCELERATORS)
    for path, _ in ka.CONFIGS.values():
        assert (ROOT / path).is_file()


def test_workflows_never_print_secrets_and_use_secrets_only_via_env():
    for wf in (ROOT / ".github" / "workflows").glob("kaggle-*.yml"):
        text = wf.read_text()
        assert "echo $KAGGLE_API_TOKEN" not in text and 'echo "$KAGGLE_API_TOKEN"' not in text
        assert "echo \"$RAW_KAGGLE_SECRET\"" not in text
        for line in text.splitlines():
            if "secrets." in line:
                assert "${{ secrets." in line and (line.strip().startswith(("KAGGLE_", "RAW_KAGGLE_SECRET")))


def test_kernel_result_folder_holds_only_the_required_files(tmp_path):
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("ka", ROOT / "kaggle" / "kaggle_automation.py")
    ka = module_from_spec(spec)
    spec.loader.exec_module(ka)
    assert ka.expected_result_files("baseline") == {"v1_1_a.mp4", "benchmark.json", "run_info.json", "render.log"}
    for name in ka.expected_result_files("baseline") | {"repo", "frames.zip"}:
        (tmp_path / name).write_bytes(b"x")
    assert ka.unexpected_files(tmp_path, "baseline") == ["frames.zip", "repo"]
    # the generated kernel copies exactly the mp4 + benchmark.json into the result folder
    src = ka.build_kernel_script("baseline", "b9b74223a4ff98d9560dc177288da9efdcdf4504")
    assert src.count("shutil.copy2(") == 2 and "BUILD = Path(\"/tmp/se_build\")" in src


# ------------------------------------------------------------------ real end-to-end (Blender + FFmpeg)
needs_real = pytest.mark.skipif(
    importlib.util.find_spec("bpy") is None or not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="needs the bpy module and ffmpeg")


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,avg_frame_rate,duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return {s["codec_type"]: s for s in json.loads(out)["streams"]}


@needs_real
def test_reference_pipeline_end_to_end_on_a_tiny_scene(tmp_path):
    """Same structure as production (closeup hook, labelled stages, no cards, music + physics SFX), just small."""
    data = json.loads(REFERENCE.read_text())
    data.update(name="reference_tiny", fps=24, duration=2.0, resolutions=[64, 256])
    data["output"].update(dir=str(tmp_path), width=180, height=320)
    data["render"]["samples"] = 2
    data["video"]["hook_seconds"] = 1.0
    data["video"]["hook"]["closeup"]["samples"] = 2
    data["camera"]["per_stage"] = data["camera"]["per_stage"][:2]
    cfg_path = tmp_path / "reference_tiny.json"
    cfg_path.write_text(json.dumps(data))

    proc = subprocess.run([sys.executable, "-m", "shorts_engine.render", "--config", str(cfg_path), "--use-bpy"],
                          cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stdout[-2500:] + proc.stderr[-2500:]

    cfg = load_config(cfg_path)
    root = cfg.root_dir
    # -- the final video: 9:16, right fps, video + audio, exact duration
    streams = _probe(cfg.final_video_path())
    assert (int(streams["video"]["width"]), int(streams["video"]["height"])) == (180, 320)
    assert streams["video"]["avg_frame_rate"] == "24/1" and streams["video"]["codec_name"] == "h264"
    assert streams["audio"]["codec_name"] == "aac"
    expected = timeline.total_seconds(cfg)                                          # hook 1 s + 2 stages x 2 s = 5 s
    assert expected == pytest.approx(5.0)
    assert float(streams["video"]["duration"]) == pytest.approx(expected, abs=0.05)
    assert float(streams["audio"]["duration"]) == pytest.approx(expected, abs=0.1)
    # -- every frame exists (no gaps) and nothing card-related was produced
    for st in cfg.stages():
        assert len(list(st.frames_dir.glob("frame_*.png"))) == cfg.frame_count
        assert st.clip_path.is_file() and (st.blend_path.parent / "events.json").is_file()
    assert not list(root.glob("card_*"))
    # -- concat order and metadata
    names = [Path(l.split("'")[1]).name for l in (root / "concat.txt").read_text().strip().splitlines()]
    assert names == ["hook.mp4", "stage_00_64.mp4", "stage_01_256.mp4"]
    bench = json.loads((root / "benchmark.json").read_text())
    assert bench["summary"]["frames_rendered"] > 0 and {j["kind"] for j in bench["jobs"]} >= {"bake", "render", "events", "audio"}
    timeline_json = json.loads((root / "audio_timeline.json").read_text())
    assert any(c["type"] == "impact" for c in timeline_json["sfx"])                 # the cloth hit the sphere
    assert all(0 <= c["time"] < expected for c in timeline_json["sfx"])
