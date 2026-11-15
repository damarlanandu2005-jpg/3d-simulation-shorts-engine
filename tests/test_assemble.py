from pathlib import Path

from shorts_engine import assemble


def test_stage_clip_cmd():
    cmd = assemble.stage_clip_cmd(Path("a/frames"), 30, Path("a/clip.mp4"), crf=20)
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-framerate") + 1] == "30"
    assert cmd[cmd.index("-i") + 1].endswith("frame_%04d.png")
    assert "yuv420p" in cmd and cmd[-1] == "a/clip.mp4"
    assert cmd[cmd.index("-crf") + 1] == "20"


def test_hook_cmd_takes_tail_of_clip():
    cmd = assemble.hook_cmd(Path("last.mp4"), 2.5, 30, Path("hook.mp4"))
    assert cmd[cmd.index("-sseof") + 1] == "-2.5"


def test_concat_list_quotes_paths(tmp_path):
    weird = tmp_path / "it's here.mp4"
    text = assemble.concat_list_text([weird, tmp_path / "b.mp4"])
    lines = text.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("file '") and "'\\''" in lines[0]


def test_concat_cmd_copies_streams():
    cmd = assemble.concat_cmd(Path("list.txt"), Path("out.mp4"))
    assert cmd[cmd.index("-c") + 1] == "copy" and "-safe" in cmd


def test_missing_frames(tmp_path):
    (tmp_path / "frame_0001.png").write_bytes(b"x")
    (tmp_path / "frame_0003.png").write_bytes(b"x")
    assert assemble.missing_frames(tmp_path, 4) == [2, 4]


def test_stage_clip_cmd_start_number():
    cmd = assemble.stage_clip_cmd(Path("f"), 30, Path("o.mp4"), start_number=31)
    assert cmd[cmd.index("-start_number") + 1] == "31"


def test_missing_frames_with_first(tmp_path):
    for n in (31, 33):
        (tmp_path / f"frame_{n:04d}.png").write_bytes(b"x")
    assert assemble.missing_frames(tmp_path, 34, first=31) == [32, 34]
