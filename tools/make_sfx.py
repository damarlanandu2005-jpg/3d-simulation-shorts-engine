#!/usr/bin/env python3
"""Generate the bundled sound effects in assets/audio/sfx/ from scratch (no samples, no third-party audio).

Original synthesis (sine sweeps + filtered noise), deterministic, released under CC0 1.0.

    python tools/make_sfx.py [out_dir]
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def sweep(f0, f1, dur, tau):
    """Sine whose pitch glides exponentially f0 -> f1 (a thump), decaying with time constant tau."""
    t = t_axis(dur)
    freq = f1 + (f0 - f1) * np.exp(-t / (dur / 4))
    phase = 2 * np.pi * np.cumsum(freq) / SR
    return np.sin(phase) * np.exp(-t / tau)


def lowpass(x, cutoff, passes=2):
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    for _ in range(passes):
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += a * (v - acc)
            y[i] = acc
        x = y
    return x


def noise(dur, seed):
    return np.random.default_rng(seed).standard_normal(int(dur * SR))


def fit(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[: len(p)] += p
    return out


def finish(x, peak_db=-3.0, fade_ms=8):
    x = x - np.mean(x)
    x = x / np.max(np.abs(x)) * 10 ** (peak_db / 20)
    n = int(fade_ms / 1000 * SR)
    x[-n:] *= np.linspace(1, 0, n)
    x[:64] *= np.linspace(0, 1, 64)   # no click at the start
    return x


def soft_impact():
    body = sweep(110, 40, 0.9, 0.17)
    thud = 0.6 * sweep(190, 90, 0.25, 0.05)
    t = t_axis(0.25)
    air = 0.35 * lowpass(noise(0.25, 1), 900) * np.exp(-t / 0.035) * 6
    return finish(fit(body, thud, air))


def bounce():
    knock = sweep(150, 75, 0.45, 0.07)
    t = t_axis(0.05)
    tick = 0.25 * lowpass(noise(0.05, 2), 2500) * np.exp(-t / 0.008) * 6
    return finish(fit(knock, tick))


def soft_landing():
    t = t_axis(0.8)
    rustle = lowpass(noise(0.8, 3), 1400) - lowpass(noise(0.8, 3), 300)
    env = np.minimum(1, t / 0.03) * np.exp(-t / 0.2)
    thump = 0.5 * sweep(85, 50, 0.5, 0.1)
    return finish(fit(rustle * env * 4, thump))


def whoosh():
    dur = 0.9
    t = t_axis(dur)
    n = noise(dur, 4)
    low, high = lowpass(n, 250), lowpass(n, 3000)
    mix = np.sin(np.pi * t / dur)           # slow low->high->low morph
    env = np.sin(np.pi * t / dur) ** 2
    return finish((low * (1 - mix) + high * mix) * env)


SOUNDS = {"soft_impact": soft_impact, "bounce": bounce, "soft_landing": soft_landing, "whoosh": whoosh}


def write(path: Path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    for name, fn in SOUNDS.items():
        x = fn()
        write(out / f"{name}.wav", x)
        print(f"wrote {out / (name + '.wav')} ({len(x) / SR:.2f}s)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "assets/audio/sfx")
