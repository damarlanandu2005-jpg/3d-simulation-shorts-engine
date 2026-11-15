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
