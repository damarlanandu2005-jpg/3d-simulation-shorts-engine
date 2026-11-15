#!/usr/bin/env python3
"""Generate assets/audio/default_music.wav -- an original, seamlessly looping ambient track.

Written for this project (no samples, no third-party music): soft sine pads on an Am-F-C-G
progression with a slow pentatonic pluck. Deterministic. Released under CC0 1.0 (public domain).

    python tools/make_default_music.py [out.wav]
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 84
BEATS_PER_BAR = 4
BARS = 16                    # 4 passes of the 4-chord loop
BAR = 60 / BPM * BEATS_PER_BAR
N = int(round(BAR * BARS * SR))

def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)

CHORDS = [  # root, third, fifth (MIDI), one octave band below the pluck
    (45, 48, 52),   # Am
    (41, 45, 48),   # F
    (48, 52, 55),   # C
    (43, 47, 50),   # G
]
PENTA = [57, 60, 62, 64, 67, 69, 72]  # A minor pentatonic-ish, matches all four chords


def add_wrapped(buf, start, sig):
    """Add `sig` at `start`, wrapping around the end so the loop is seamless."""
    idx = (start + np.arange(len(sig))) % len(buf)
    np.add.at(buf, idx, sig)


def pad(freqs, dur, vol):
    t = np.arange(int(dur * SR)) / SR
    sig = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.003 * t) for f in freqs)
    a, r = 1.2, 1.4
    env = np.minimum(1, t / a) * np.minimum(1, (dur - t) / r)
    return vol * sig * env / len(freqs)


def pluck(f, dur, vol):
    t = np.arange(int(dur * SR)) / SR
    sig = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    return vol * sig * np.exp(-3.2 * t) * np.minimum(1, t / 0.005)


def main(out: Path):
    rng = np.random.default_rng(7)
    buf = np.zeros(N)
    for bar in range(BARS):
        chord = CHORDS[bar % 4]
        add_wrapped(buf, int(bar * BAR * SR), pad([midi(m) for m in chord], BAR + 1.4, 0.55))
        add_wrapped(buf, int(bar * BAR * SR), pad([midi(chord[0] - 12)], BAR + 1.0, 0.35))
        step = BAR / 8
        for k in range(8):
            if rng.random() < 0.7:
                note = PENTA[int(rng.integers(0, len(PENTA)))]
                add_wrapped(buf, int((bar * BAR + k * step) * SR), pluck(midi(note), 1.6, 0.16))
    # gentle one-pole low-pass for warmth, then peak-normalise to -3 dBFS (the engine applies its own gain)
    y = np.empty_like(buf)
    acc = 0.0
    for i, x in enumerate(buf):
        acc += 0.35 * (x - acc)
        y[i] = acc
    y *= 10 ** (-3 / 20) / np.max(np.abs(y))
    pcm = (y * 32767).astype("<i2")
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out} ({N / SR:.1f} s, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "assets/audio/default_music.wav")
