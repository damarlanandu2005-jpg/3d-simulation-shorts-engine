import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kaggle_automation", ROOT / "kaggle" / "kaggle_automation.py")
ka = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ka)

SHA = "b9b74223a4ff98d9560dc177288da9efdcdf4504"


def test_mapping_is_exactly_three_fixed_configs():
    assert ka.CONFIGS == {
        "baseline": ("configs/v1_1_a_baseline.json", "v1_1_a"),
        "optix": ("configs/v1_1_b_optix.json", "v1_1_b"),
        "1080p": ("configs/v1_1_c_1080p.json", "v1_1_c"),
    }


@pytest.mark.parametrize("key", list(ka.CONFIGS))
def test_mapped_configs_exist_and_names_match(key):
    path, name = ka.CONFIGS[key]
    cfg = json.loads((ROOT / path).read_text())
    assert cfg["name"] == name


def test_unknown_key_rejected():
    for bad in ["../x.json", "baseline; rm -rf /", "", "configs/example_cloth.json"]:
        with pytest.raises(ka.AutomationError):
            ka.resolve_config(bad)


@pytest.mark.parametrize("sha", ["main", SHA[:10], SHA.upper(), SHA + "; id", ""])
def test_bad_sha_rejected(sha):
    with pytest.raises(ka.AutomationError):
        ka.build_kernel_script("baseline", sha)


@pytest.mark.parametrize("key", list(ka.CONFIGS))
def test_kernel_script_valid_python_and_pinned(key):
    src = ka.build_kernel_script(key, SHA)
    ast.parse(src)
    assert "__" not in "".join(l for l in src.splitlines() if l.startswith(("REPO_URL", "SHA", "CONFIG", "OUT_NAME", "KEY")))
    assert json.dumps(SHA) in src and json.dumps(ka.CONFIGS[key][0]) in src
    assert "shorts_engine.render" in src and "--use-bpy" in src
    assert "setup_kaggle.sh" in src and "import bpy" in src and "nvidia-smi" in src
    # no credentials ever go into the kernel
    for word in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "KGAT_"):
        assert word not in src


def test_metadata_private_gpu_internet():
    m = ka.build_metadata("someuser", "se-v11-baseline-b9b7422-1")
    assert m["id"] == "someuser/se-v11-baseline-b9b7422-1"
    assert m["is_private"] is True and m["enable_gpu"] is True and m["enable_internet"] is True
    assert m["kernel_type"] == "script" and m["language"] == "python"
    with pytest.raises(ka.AutomationError):
        ka.build_metadata("bad user;rm", "x")


def test_prepare_writes_files(tmp_path):
    kernel = ka.prepare("optix", SHA, "someuser", "12345", tmp_path / "job")
    assert kernel == "someuser/se-v11-optix-b9b7422-12345"
    assert (tmp_path / "job" / "kernel.py").is_file()
    meta = json.loads((tmp_path / "job" / "kernel-metadata.json").read_text())
    assert meta["title"] == kernel.split("/")[1]
    with pytest.raises(ka.AutomationError):
        ka.prepare("optix", SHA, "someuser", "12 345", tmp_path / "j2")


@pytest.mark.parametrize("text,expected", [
    ('u/k has status "KernelWorkerStatus.COMPLETE"', "COMPLETE"),
    ('u/k has status "KernelWorkerStatus.RUNNING"', "RUNNING"),
    ('u/k has status "KernelWorkerStatus.ERROR"', "ERROR"),
    ("garbage", "UNKNOWN"),
])
def test_parse_status(text, expected):
    assert ka.parse_status(text) == expected


def _good(out: Path, name="v1_1_a"):
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.mp4").write_bytes(b"x")
    (out / "benchmark.json").write_text(json.dumps({"summary": {}, "jobs": []}))
    (out / "run_info.json").write_text(json.dumps({"status": "ok"}))


def test_verify_ok(tmp_path):
    _good(tmp_path)
    ka.verify_output(tmp_path, "baseline")


@pytest.mark.parametrize("remove", ["v1_1_a.mp4", "benchmark.json", "run_info.json"])
def test_verify_fails_on_missing(tmp_path, remove):
    _good(tmp_path)
    (tmp_path / remove).unlink()
    with pytest.raises(ka.AutomationError):
        ka.verify_output(tmp_path, "baseline")


def test_verify_fails_on_kernel_failure_and_bad_benchmark(tmp_path):
    _good(tmp_path)
    (tmp_path / "run_info.json").write_text(json.dumps({"status": "failed", "error": "no GPU"}))
    with pytest.raises(ka.AutomationError, match="no GPU"):
        ka.verify_output(tmp_path, "baseline")
    _good(tmp_path)
    (tmp_path / "benchmark.json").write_text("{}")
    with pytest.raises(ka.AutomationError):
        ka.verify_output(tmp_path, "baseline")


def test_accelerator_option(tmp_path):
    assert ka.build_metadata("u", "s")["machine_shape"] == "NvidiaTeslaT4"
    assert "machine_shape" not in ka.build_metadata("u", "s", accelerator="default")
    with pytest.raises(ka.AutomationError):
        ka.build_metadata("u", "s", accelerator="x; rm")


def test_queue_timeout(monkeypatch):
    class R:
        returncode = 0
        stdout = 'u/k has status "KernelWorkerStatus.QUEUED"'
        stderr = ""
    monkeypatch.setattr(ka.subprocess, "run", lambda *a, **k: R())
    monkeypatch.setattr(ka.time, "sleep", lambda s: None)
    with pytest.raises(ka.AutomationError, match="still QUEUED"):
        ka.wait("u/k", timeout_s=100, interval_s=0, max_queue_s=0.0001)


def test_kernel_keeps_work_dir_small():
    src = ka.build_kernel_script("baseline", SHA)
    assert 'repo = BUILD / "repo"' in src and "/tmp/se_build" in src
    assert 'WORK / "repo"' not in src


# ---------------------------------------------------------------- Phase 9: generalized selection
def test_original_three_configs_are_untouched_and_experiments_are_added():
    assert set(ka.CONFIGS) == {"baseline", "optix", "1080p"}
    assert set(ka.ALL_CONFIGS) == set(ka.CONFIGS) | {"multiple_balls", "ball_funnel", "ring_toss", "cloth_objects"}


@pytest.mark.parametrize("key", list(ka.EXPERIMENT_CONFIGS))
def test_experiment_keys_map_to_real_valid_configs(key):
    path, name = ka.EXPERIMENT_CONFIGS[key]
    assert ka.resolve_config_path(path) == (path, name)
    assert json.loads((ROOT / path).read_text())["name"] == name


@pytest.mark.parametrize("bad", [
    "../etc/passwd", "/etc/passwd", "configs/../secrets.json", "configs//x.json", "configs/x.txt", "other/x.json",
    "configs/x.json; rm -rf /", "configs/$(id).json", "configs/missing.json", "", "configs/", "configs/ x.json",
    "configs/experiments/../../kaggle/kaggle_automation.py"])
def test_config_path_validation_rejects_everything_unsafe(bad):
    with pytest.raises(ka.AutomationError):
        ka.resolve_config_path(bad)


def test_config_path_must_load_as_a_valid_config(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "broken.json").write_text("{nope")
    (tmp_path / "configs" / "noname.json").write_text("{}")
    (tmp_path / "configs" / "invalid.json").write_text(json.dumps({"name": "ok", "resolutions": [7]}))
    (tmp_path / "configs" / "badname.json").write_text(json.dumps({"name": "a b"}))
    for f, msg in (("broken", "JSON"), ("noname", "name"), ("invalid", "invalid"), ("badname", "name")):
        with pytest.raises(ka.AutomationError, match=msg):
            ka.resolve_config_path(f"configs/{f}.json", root=tmp_path)


def test_config_path_symlink_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"name": "evil"}))
    root = tmp_path / "repo"; (root / "configs").mkdir(parents=True)
    (root / "configs" / "link.json").symlink_to(outside)
    with pytest.raises(ka.AutomationError, match="does not exist"):
        ka.resolve_config_path("configs/link.json", root=root)


@pytest.mark.parametrize("args,ok", [
    (("auto", 4, 7, "720p"), True), (("multiple_balls", "12", "999999", "1080p"), True),
    (("teleporter", 4, 7, "720p"), False), (("auto", 0, 7, "720p"), False), (("auto", 13, 7, "720p"), False),
    (("auto", 4, -1, "720p"), False), (("auto", 4, 10 ** 7, "720p"), False), (("auto", 4, 7, "4k"), False),
    (("auto; id", 4, 7, "720p"), False), (("auto", "x", 7, "720p"), False)])
def test_batch_validation(args, ok):
    if ok:
        assert ka.validate_batch(*args)["variations"] == int(args[1])
    else:
        with pytest.raises(ka.AutomationError):
            ka.validate_batch(*args)


def test_batch_kernel_script_runs_the_batch_command_and_carries_no_secrets():
    batch = ka.validate_batch("ring_toss", 3, 5, "720p")
    src = ka.build_kernel_script("baseline", SHA, batch=batch)
    ast.parse(src)
    assert "shorts_engine.batch" in src and '"ring_toss"' in src and "--use-bpy" in src and "--run" in src
    for word in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "KGAT_"):
        assert word not in src


def test_single_kernel_script_has_no_batch():
    src = ka.build_kernel_script("ring_toss", SHA)
    ast.parse(src)
    assert "\nBATCH = None" in src and json.dumps("configs/experiments/ring_toss_smaller.json") in src


def test_prepare_custom_config_batch_and_job_file(tmp_path):
    k = ka.prepare("baseline", SHA, "u", "9", tmp_path / "j1", config_path="configs/experiments/ball_funnel_hole.json",
                   job_file=tmp_path / "job1.json")
    assert k.startswith("u/se-v11-custom-")
    job = json.loads((tmp_path / "job1.json").read_text())
    assert job == {"mode": "single", "key": "custom", "output_name": "ball_funnel_hole", "batch": None}
    ka.prepare("baseline", SHA, "u", "9", tmp_path / "j2", batch=ka.validate_batch("auto", 2, 1, "720p"), job_file=tmp_path / "job2.json")
    assert json.loads((tmp_path / "job2.json").read_text())["mode"] == "batch"
    assert not (tmp_path / "j2" / "job.json").exists(), "job info is never placed in the pushed folder"
    with pytest.raises(ka.AutomationError, match="either"):
        ka.prepare("baseline", SHA, "u", "9", tmp_path / "j3", config_path="configs/example_cloth.json",
                   batch=ka.validate_batch("auto", 2, 1, "720p"))


def make_result(tmp_path, names, qc_ok=True, status="ok"):
    (tmp_path / "run_info.json").write_text(json.dumps({"status": "ok"}))
    items = []
    for n in names:
        d = tmp_path / n
        d.mkdir()
        (d / f"{n}.mp4").write_bytes(b"x")
        (d / "benchmark.json").write_text('{"summary": {}}')
        (d / "metadata.json").write_text("{}")
        (d / "qc_report.json").write_text(json.dumps({"passed": qc_ok}))
        items.append({"name": n, "status": status})
    (tmp_path / "manifest.json").write_text(json.dumps({"items": items}))


def test_verify_batch_output(tmp_path):
    make_result(tmp_path, ["a_000", "a_001"])
    ka.verify_output(tmp_path, "batch", "batch", True)
    assert ka.unexpected_files(tmp_path, "batch", "batch", True) == []


def test_verify_batch_flags_failed_qc_status_and_missing_files(tmp_path):
    make_result(tmp_path, ["a_000"], qc_ok=False)
    with pytest.raises(ka.AutomationError, match="QC failed"):
        ka.verify_output(tmp_path, "batch", "batch", True)
    other = tmp_path / "o"; other.mkdir()
    make_result(other, ["b_000"], status="failed")
    with pytest.raises(ka.AutomationError, match="status failed"):
        ka.verify_output(other, "batch", "batch", True)
    (other / "b_000" / "b_000.mp4").unlink()
    with pytest.raises(ka.AutomationError, match="missing"):
        ka.verify_output(other, "batch", "batch", True)


def test_verify_single_requires_passing_qc_when_a_report_exists(tmp_path):
    (tmp_path / "run_info.json").write_text(json.dumps({"status": "ok"}))
    (tmp_path / "v1_1_a.mp4").write_bytes(b"x")
    (tmp_path / "benchmark.json").write_text('{"summary": {}}')
    ka.verify_output(tmp_path, "baseline")                                # old-style output (no QC file) still verifies
    (tmp_path / "qc_report.json").write_text(json.dumps({"passed": False, "checks": [{"name": "valid fps", "ok": False}]}))
    with pytest.raises(ka.AutomationError, match="valid fps"):
        ka.verify_output(tmp_path, "baseline")


def test_workflow_inputs_are_validated_and_secrets_stay_in_env():
    text = (ROOT / ".github" / "workflows" / "kaggle-gpu-test.yml").read_text()
    for name in ("config_path", "batch_variations", "batch_experiment", "batch_seed", "preset", "multiple_balls"):
        assert name in text
    runs = [blk for blk in text.split("run: |")[1:]]
    for blk in runs:
        body = blk.split("\n      - ")[0]
        assert "${{ inputs." not in body and "${{ secrets." not in body, "inputs/secrets must reach scripts via env only"
    assert "KAGGLE_API_TOKEN" in text and "echo \"$KAGGLE_API_TOKEN\"" not in text


def test_batch_kernel_does_not_require_a_config_file():
    import kaggle.kaggle_automation as ka
    script = ka.build_kernel_script("baseline", "a" * 40, None, {"experiment": "auto", "variations": 2, "seed": 1, "preset": "720p"})
    assert "if not BATCH and not (repo / CONFIG).is_file()" in script
    compile(script, "kernel.py", "exec")
