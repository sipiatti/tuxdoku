#!/usr/bin/env python3
"""Synthesize all Tuxdoku sound effects and music loops from code.

Everything this script produces is original work for Tuxdoku, released under
CC0 1.0 (public domain dedication). Requires numpy; music is encoded to OGG
Vorbis with ffmpeg (libvorbis).

    python3 tools/make_sounds.py
"""
from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent.parent / "tuxdoku" / "assets"
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ basics
def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def env(n: int, a=0.005, d=0.1, s=0.0, r=0.05, dur=None) -> np.ndarray:
    """Linear attack, exponential-ish decay to sustain, linear release."""
    t = np.arange(n) / SR
    total = n / SR if dur is None else dur
    e = np.ones(n)
    e[t < a] = t[t < a] / max(a, 1e-6)
    after = t >= a
    e[after] = s + (1 - s) * np.exp(-(t[after] - a) / max(d, 1e-6))
    rel_start = max(0.0, total - r)
    rel = t >= rel_start
    e[rel] *= np.clip(1 - (t[rel] - rel_start) / max(r, 1e-6), 0, 1)
    return e


def sine(f, t, phase=0.0):
    return np.sin(2 * np.pi * f * t + phase)


def tri(f, t):
    return 2 * np.abs(2 * ((f * t) % 1.0) - 1) - 1


def soft_square(f, t, harmonics=7):
    out = np.zeros_like(t)
    for k in range(1, harmonics * 2, 2):
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * (4 / np.pi) * 0.6


def sweep(f0, f1, t, curve="exp"):
    dur = t[-1] if len(t) else 1
    if curve == "exp":
        f = f0 * (f1 / f0) ** (t / max(dur, 1e-6))
    else:
        f = f0 + (f1 - f0) * t / max(dur, 1e-6)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x, alpha=0.2):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def mix_at(buf, sig, start_s):
    i = int(start_s * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i]


def normalize(x, peak=0.85):
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


# ------------------------------------------------------------ instruments
def bell(midi, dur, vel=1.0):
    t = t_axis(dur)
    f = hz(midi)
    x = sine(f, t) + 0.35 * sine(2 * f, t) * np.exp(-t * 6) + 0.18 * sine(3.01 * f, t) * np.exp(-t * 9)
    return vel * x * env(len(t), a=0.003, d=dur * 0.35, r=min(0.05, dur * 0.3))


def pluck(midi, dur, vel=1.0):
    t = t_axis(dur)
    f = hz(midi)
    x = 0.7 * tri(f, t) + 0.3 * sine(2 * f, t) * np.exp(-t * 8)
    return vel * x * env(len(t), a=0.004, d=dur * 0.45, s=0.0, r=0.04)


def lead(midi, dur, vel=1.0):
    t = t_axis(dur)
    f = hz(midi) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t * 4, 0, 1))  # gentle vibrato
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    return vel * x * env(len(t), a=0.015, d=0.25, s=0.55, r=min(0.08, dur * 0.4))


def bass(midi, dur, vel=1.0):
    t = t_axis(dur)
    f = hz(midi)
    x = sine(f, t) + 0.25 * sine(2 * f, t) + 0.08 * tri(f, t)
    return vel * x * env(len(t), a=0.006, d=0.22, s=0.35, r=0.05)


def pad(midis, dur, vel=1.0):
    t = t_axis(dur)
    x = np.zeros_like(t)
    for m in midis:
        f = hz(m)
        x += sine(f * 1.002, t) + sine(f * 0.998, t) + 0.2 * sine(2 * f, t)
    x /= max(1, len(midis))
    return vel * x * env(len(t), a=dur * 0.3, d=10, s=1.0, r=dur * 0.35)


def kick(vel=1.0):
    t = t_axis(0.18)
    return vel * sweep(140, 48, t) * env(len(t), a=0.002, d=0.07, r=0.03)


def hat(vel=1.0, dur=0.05):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    hp = noise - lowpass(noise, 0.35)
    return vel * hp * env(n, a=0.001, d=dur * 0.3, r=0.01)


def shaker(vel=1.0):
    n = int(0.09 * SR)
    noise = rng.standard_normal(n)
    hp = noise - lowpass(noise, 0.25)
    return vel * hp * env(n, a=0.02, d=0.03, r=0.02)


# ---------------------------------------------------------------- effects
def sfx_click():
    t = t_axis(0.045)
    return 0.5 * sine(1500, t) * env(len(t), a=0.001, d=0.012, r=0.01)


def sfx_hover():
    t = t_axis(0.03)
    return 0.22 * sine(2300, t) * env(len(t), a=0.001, d=0.008, r=0.01)


def sfx_mark():
    t = t_axis(0.07)
    return 0.6 * sweep(950, 520, t) * env(len(t), a=0.002, d=0.025, r=0.02)


def sfx_unmark():
    t = t_axis(0.07)
    return 0.5 * sweep(520, 380, t) * env(len(t), a=0.002, d=0.025, r=0.02)


def sfx_place():
    out = np.zeros(int(0.32 * SR))
    mix_at(out, bell(84, 0.22, 0.7), 0.0)        # C6
    mix_at(out, bell(91, 0.25, 0.8), 0.07)       # G6
    t = t_axis(0.09)
    mix_at(out, 0.35 * sweep(600, 1500, t) * env(len(t), a=0.003, d=0.04, r=0.02), 0.0)  # "boing" squeak
    return out


def sfx_wrong():
    t = t_axis(0.45)
    f = 330 * (180 / 330) ** (t / t[-1])
    f = f * (1 + 0.03 * np.sin(2 * np.pi * 14 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
    return 0.55 * x * env(len(t), a=0.005, d=0.25, s=0.3, r=0.08)


def sfx_hint():
    out = np.zeros(int(0.9 * SR))
    for i, m in enumerate((88, 92, 95, 100)):     # E6 G#6 B6 E7
        mix_at(out, bell(m, 0.45, 0.55), i * 0.07)
    for i in range(10):                           # sparkle
        mix_at(out, bell(100 + rng.integers(0, 8), 0.12, 0.15), 0.2 + i * 0.045)
    return out


def sfx_fanfare():
    out = np.zeros(int(2.2 * SR))
    notes = [(72, 0.0, 0.16), (76, 0.13, 0.16), (79, 0.26, 0.16), (84, 0.39, 0.32),
             (79, 0.62, 0.12), (84, 0.74, 0.9)]
    for m, st, d in notes:
        mix_at(out, lead(m, d + 0.1, 0.5), st)
        mix_at(out, bell(m + 12, d + 0.3, 0.25), st)
    mix_at(out, pad([60, 64, 67, 72], 1.4, 0.35), 0.74)
    mix_at(out, bass(48, 0.4, 0.5), 0.0)
    mix_at(out, bass(43, 0.3, 0.45), 0.39)
    mix_at(out, bass(48, 1.1, 0.5), 0.74)
    for i in range(14):
        mix_at(out, bell(96 + rng.integers(0, 12), 0.15, 0.12), 0.8 + i * 0.06)
    for st in (0.0, 0.39, 0.74):
        mix_at(out, kick(0.5), st)
    return out


def sfx_gameover():
    out = np.zeros(int(1.9 * SR))
    for i, m in enumerate((67, 66, 65)):
        mix_at(out, lead(m, 0.34, 0.5), i * 0.36)
    t = t_axis(0.8)                                 # final sliding "wah-wah-waaah"
    f = hz(64) * (1 - 0.06 * t / t[-1]) * (1 + 0.025 * np.sin(2 * np.pi * 6 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * env(len(t), a=0.02, d=0.6, s=0.4, r=0.2)
    mix_at(out, 0.5 * x, 1.08)
    mix_at(out, bass(40, 0.9, 0.35), 1.08)
    return out


# peak level of each effect (relative loudness is baked into the files)
SFX_LEVEL = {"hover": 0.22, "click": 0.4, "mark": 0.5, "unmark": 0.42, "place": 0.7, "wrong": 0.7,
             "hint": 0.65, "fanfare": 0.8, "gameover": 0.75}

SFX = {
    "click": sfx_click, "hover": sfx_hover, "mark": sfx_mark, "unmark": sfx_unmark, "place": sfx_place,
    "wrong": sfx_wrong, "hint": sfx_hint, "fanfare": sfx_fanfare, "gameover": sfx_gameover,
}


# ------------------------------------------------------------------- music
CHORD_TONES = {  # chord name -> (root midi in octave 3, triad intervals)
    "C": (48, (0, 4, 7)), "Am": (45, (0, 3, 7)), "F": (41, (0, 4, 7)), "G": (43, (0, 4, 7)),
    "Dm": (50, (0, 3, 7)), "Em": (52, (0, 3, 7)), "Bb": (46, (0, 4, 7)), "Gm": (43, (0, 3, 7)),
}

MENU_CHORDS = ["C", "Am", "F", "G", "C", "Am", "Dm", "G", "F", "G", "Em", "Am", "F", "G", "C", "G"]
R = None
MENU_MELODY = [  # (midi or None, length in eighths) – 8 eighths per bar
    [(76, 2), (79, 1), (76, 1), (84, 2), (79, 2)],
    [(81, 2), (79, 1), (76, 1), (72, 4)],
    [(77, 1), (81, 1), (84, 1), (81, 1), (77, 2), (81, 2)],
    [(79, 2), (83, 1), (86, 1), (79, 4)],
    [(76, 2), (79, 1), (76, 1), (84, 2), (79, 2)],
    [(81, 1), (84, 1), (88, 2), (86, 1), (84, 1), (81, 2)],
    [(77, 2), (81, 2), (86, 1), (84, 1), (81, 2)],
    [(83, 2), (86, 2), (91, 2), (R, 2)],
    [(81, 3), (79, 1), (77, 2), (81, 2)],
    [(83, 3), (81, 1), (79, 4)],
    [(79, 1), (83, 1), (88, 2), (86, 2), (83, 2)],
    [(84, 2), (81, 2), (76, 4)],
    [(77, 1), (79, 1), (81, 1), (84, 1), (86, 2), (84, 2)],
    [(83, 2), (86, 2), (79, 2), (83, 2)],
    [(84, 6), (R, 2)],
    [(79, 1), (81, 1), (83, 1), (86, 1), (R, 4)],
]

GAME_CHORDS = ["F", "C", "Dm", "Bb", "F", "Gm", "C", "C",
               "Dm", "Bb", "F", "C", "Bb", "C", "F", "F"]


def chord_notes(name, octave_shift=0):
    root, iv = CHORD_TONES[name]
    return [root + 12 * octave_shift + i for i in iv]


def render_loop(bars, bpm, render_bar, echo=0.22):
    beat = 60.0 / bpm
    bar_len = 4 * beat
    total = bars * bar_len
    n = int(round(total * SR))
    buf = np.zeros(n + int(4 * SR))
    for b in range(bars):
        render_bar(buf, b, b * bar_len, beat)
    # stereo-free echo (3/8 note), then fold the tail back to the start => seamless loop
    d = int(0.75 * beat * SR)
    wet = np.zeros_like(buf)
    wet[d:] += buf[:-d] * echo
    wet[2 * d:] += buf[:-2 * d] * echo * echo
    buf = buf + wet
    loop = buf[:n].copy()
    tail = buf[n:]
    k = min(len(tail), n)
    loop[:k] += tail[:k]
    return normalize(loop, 0.8)


def menu_bar(buf, b, start, beat):
    ch = MENU_CHORDS[b]
    tones = chord_notes(ch)
    e = beat / 2
    # bouncy bass: root, fifth, octave, fifth
    for i, m in enumerate((tones[0], tones[0] + 7, tones[0] + 12, tones[0] + 7)):
        mix_at(buf, bass(m - 12 if m > 52 else m, beat * 0.9, 0.55), start + i * beat)
    # music-box arpeggio in eighths
    arp = [tones[0] + 24, tones[1] + 24, tones[2] + 24, tones[1] + 24] * 2
    for i, m in enumerate(arp):
        mix_at(buf, bell(m, e * 1.6, 0.18 if i % 2 else 0.24), start + i * e)
    # melody
    pos = 0
    for m, length in MENU_MELODY[b]:
        if m is not None:
            mix_at(buf, lead(m, length * e * 0.95, 0.34), start + pos * e)
            mix_at(buf, bell(m + 12, length * e, 0.07), start + pos * e)
        pos += length
    # light percussion
    for i in range(4):
        mix_at(buf, kick(0.35 if i % 2 == 0 else 0.2), start + i * beat)
        mix_at(buf, shaker(0.08), start + i * beat + e)
    if b % 4 == 3:
        mix_at(buf, hat(0.1, 0.12), start + 3.5 * beat)


def make_game_melody(bars, seed=4):
    g = np.random.default_rng(seed)
    scale = [65, 67, 69, 70, 72, 74, 76, 77, 79, 81]   # F major, F4..A5
    mel = []
    cur = 72
    for b in range(bars):
        ch = GAME_CHORDS[b % len(GAME_CHORDS)]
        tones = {(n % 12) for n in chord_notes(ch)}
        if b % 8 in (0, 1) and b < 8:      # first phrase: breathe, music box only
            mel.append([(None, 8)])
            continue
        pattern = [[3, 1, 4], [2, 2, 4], [4, 2, 2], [2, 1, 1, 4], [6, 2]][g.integers(0, 5)]
        if b % 4 == 3:
            pattern = [4, 4]
        notes = []
        for i, length in enumerate(pattern):
            cands = [n for n in scale if abs(n - cur) <= 4]
            if i == 0:
                cands = [n for n in cands if n % 12 in tones] or cands
            cur = int(g.choice(cands))
            notes.append((cur, length))
        if b % 4 == 3:
            notes[-1] = (None, 4)
        mel.append(notes)
    return mel


GAME_MELODY = make_game_melody(32)


def game_bar(buf, b, start, beat):
    ch = GAME_CHORDS[b % len(GAME_CHORDS)]
    tones = chord_notes(ch)
    e = beat / 2
    mix_at(buf, pad([t + 12 for t in tones], 4 * beat + 0.3, 0.16), start)
    mix_at(buf, bass(tones[0], beat * 1.8, 0.45), start)
    mix_at(buf, bass(tones[0] + 7 if tones[0] + 7 < 56 else tones[0] - 5, beat * 1.8, 0.35), start + 2 * beat)
    patt = [0, 2, 1, 2, 0, 2, 1, 2] if b % 2 == 0 else [0, 1, 2, 1, 2, 1, 0, 2]
    for i, k in enumerate(patt):
        mix_at(buf, pluck(tones[k] + 24, e * 1.8, 0.2 if i % 2 == 0 else 0.13), start + i * e)
    pos = 0
    for m, length in GAME_MELODY[b]:
        if m is not None:
            mix_at(buf, bell(m + 12, length * e * 1.2, 0.2), start + pos * e)
        pos += length
    for i in range(4):
        mix_at(buf, shaker(0.05 if i % 2 else 0.035), start + i * beat + e)
    if b % 2 == 1:
        mix_at(buf, kick(0.18), start)


# --------------------------------------------------------------------- io
def write_wav(path: Path, x: np.ndarray):
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def write_ogg(path: Path, x: np.ndarray, quality=3):
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "tmp.wav"
        write_wav(wav, x)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis",
                        "-q:a", str(quality), "-metadata", "title=" + path.stem,
                        "-metadata", "artist=Tuxdoku", "-metadata", "copyright=CC0 1.0", str(path)], check=True)


def main():
    (ROOT / "sounds").mkdir(parents=True, exist_ok=True)
    (ROOT / "music").mkdir(parents=True, exist_ok=True)
    for name, fn in SFX.items():
        x = fn()
        fade = min(len(x), int(0.01 * SR))
        x[-fade:] *= np.linspace(1, 0, fade)
        write_wav(ROOT / "sounds" / f"{name}.wav", normalize(x, SFX_LEVEL[name]))
    write_ogg(ROOT / "music" / "menu.ogg", render_loop(len(MENU_CHORDS), 116, menu_bar))
    write_ogg(ROOT / "music" / "game.ogg", render_loop(32, 88, game_bar, echo=0.28))
    print("sounds written to", ROOT)


if __name__ == "__main__":
    main()
