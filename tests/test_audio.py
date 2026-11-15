import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from shorts_engine import assemble, render
from shorts_engine.config import ConfigError, from_dict, load_config

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")

ROOT = Path(__file__).resolve().parent.parent
A_PATH = str(ROOT / "configs" / "v1_1_a_baseline.json")


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def probe(path, kind):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", kind, "-show_entries",
                          "stream=codec_name,duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"]


def mean_volume(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr).group(1))


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    ff("-f", "lavfi", "-i", "testsrc=size=64x64:rate=10:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "video.mp4"))
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(d / "short.wav"))     # shorter than the 4 s video
    ff("-f", "lavfi", "-i", "sine=frequency=440:duration=10", str(d / "long.wav"))     # longer than the video
    return d


def mix(media, music, out, **kw):
    ff_cmd = assemble.audio_mix_cmd(media / "video.mp4", media / music, out, 4.0, **kw)
    subprocess.run(ff_cmd, check=True)
    return out


def test_music_enabled_gives_an_audio_stream_and_keeps_the_video(media, tmp_path):
    out = mix(media, "long.wav", tmp_path / "o.mp4")
    assert [s["codec_name"] for s in probe(out, "a")] == ["aac"]
    assert [s["codec_name"] for s in probe(out, "v")] == ["h264"]


def test_music_disabled_final_video_has_no_audio(media):
    # the plan writes the concat output straight to the final path and adds no audio job
    cfg, jobs = _plan(audio=False)
    concat = next(j for j in jobs if j.kind == "concat")
    assert concat.cmd[-1] == str(cfg.final_video_path()) and not any(j.kind == "audio" for j in jobs)
    # and a plain concat of video-only clips really yields no audio stream
    lst = media / "list.txt"
    lst.write_text(assemble.concat_list_text([media / "video.mp4"]))
    out = media / "plain.mp4"
    subprocess.run(assemble.concat_cmd(lst, out), check=True)
    assert probe(out, "a") == []


@pytest.mark.parametrize("music", ["short.wav", "long.wav"])
def test_audio_never_outlasts_the_video(media, tmp_path, music):
    out = mix(media, music, tmp_path / "o.mp4")
    a, v = float(probe(out, "a")[0]["duration"]), float(probe(out, "v")[0]["duration"])
    assert a <= v + 0.03
    assert a >= 3.8           # short track was looped to fill the video; long one trimmed to it, not cut early


def test_short_music_is_looped_not_silent_after_it_ends(media, tmp_path):
    out = mix(media, "short.wav", tmp_path / "o.mp4", fade_in=0, fade_out=0)
    tail = tmp_path / "tail.wav"
    ff("-ss", "2.5", "-i", str(out), "-t", "1", str(tail))      # well after the 1 s source ended
    assert mean_volume(tail) > -40


def test_volume_setting_is_respected(media, tmp_path):
    loud = mix(media, "long.wav", tmp_path / "loud.mp4", volume_db=-12, fade_in=0, fade_out=0)
    quiet = mix(media, "long.wav", tmp_path / "quiet.mp4", volume_db=-24, fade_in=0, fade_out=0)
    assert mean_volume(loud) - mean_volume(quiet) == pytest.approx(12, abs=1.0)


def test_fades_are_applied(media, tmp_path):
    out = mix(media, "long.wav", tmp_path / "o.mp4", fade_in=1.0, fade_out=1.0, volume_db=-6)
    head, mid, end = tmp_path / "h.wav", tmp_path / "m.wav", tmp_path / "e.wav"
    ff("-i", str(out), "-t", "0.2", str(head))
    ff("-ss", "1.5", "-i", str(out), "-t", "1", str(mid))
    ff("-ss", "3.8", "-i", str(out), "-t", "0.2", str(end))
    assert mean_volume(head) < mean_volume(mid) - 6 and mean_volume(end) < mean_volume(mid) - 6


def test_fades_are_clamped_for_very_short_videos():
    cmd = assemble.audio_mix_cmd(Path("v.mp4"), Path("m.wav"), Path("o.mp4"), 1.0, fade_in=5, fade_out=5)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "afade=t=in:st=0:d=0.500" in graph and "afade=t=out:st=0.500:d=0.500" in graph
    with pytest.raises(ValueError):
        assemble.audio_mix_cmd(Path("v.mp4"), Path("m.wav"), Path("o.mp4"), 0)


def _plan(audio=True, music=None):
    data = json.loads(Path(A_PATH).read_text(encoding="utf-8"))
    data["audio"]["enabled"] = audio
    data["audio"]["sfx_enabled"] = False
    if music:
        data["audio"]["music"] = music
    cfg = from_dict(data)
    return cfg, render.plan_jobs(cfg, A_PATH, ["blender"], True)


def test_missing_music_file_is_a_clear_error():
    with pytest.raises(ConfigError, match="audio.music file not found"):
        _plan(music="assets/audio/does_not_exist.wav")


def test_plan_duration_matches_frame_counts_and_music_comes_after_concat():
    from shorts_engine import audio_mix, timeline
    cfg, jobs = _plan()
    kinds = [j.kind for j in jobs]
    assert kinds[-2:] == ["concat", "audio"]
    mix_job = jobs[-1]
    assert mix_job.cmd[1:3] == ["-m", "shorts_engine.audio_mix"]
    # hook (60 frames of the last stage) + 4 stages * 90 frames, no cards, at 30 fps = 14 s
    assert timeline.total_seconds(cfg) == pytest.approx(14.0)
    plan = audio_mix.plan_mix(_music_only(cfg))
    assert plan.cmd[plan.cmd.index("-t") + 1] == "14.000"
    assert plan.cmd[plan.cmd.index("-i") + 1] == str(cfg.silent_video_path())
    assert plan.cmd[-1] == str(cfg.final_video_path())


def _music_only(cfg):
    from dataclasses import replace
    return replace(cfg, audio=replace(cfg.audio, sfx_enabled=False))


def test_audio_config_validation():
    base = {"audio": {"enabled": True, "volume_db": 20}}
    with pytest.raises(ConfigError):
        from_dict(base)
    with pytest.raises(ConfigError):
        from_dict({"audio": {"enabled": True, "fade_in": -1}})
    with pytest.raises(ConfigError):
        from_dict({"audio": {"enabld": True}})


def test_bundled_default_track_exists_and_is_decodable():
    cfg = load_config(A_PATH)
    streams = probe(cfg.music_path(), "a")
    assert streams and float(streams[0]["duration"]) > 20
