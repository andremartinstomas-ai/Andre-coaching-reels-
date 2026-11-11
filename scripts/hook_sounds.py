#!/usr/bin/env python3
"""Erzeugt synthetische Hook-Sounds (lizenzfrei, selbst generiert) nach assets/sounds/.

Sauber klingend: weiche Ein-/Ausblendungen, kein Clipping, Peak bei -3 dBFS.
Aufruf:  python3 scripts/hook_sounds.py            -> alle Sounds
         python3 scripts/hook_sounds.py --liste    -> Namen anzeigen
"""
import argparse
import wave
from pathlib import Path

import numpy as np

SR = 48000
ZIEL = Path(__file__).resolve().parent.parent / "assets" / "sounds"


def t(sek):
    return np.arange(int(SR * sek)) / SR


def fade(x, ein=0.005, aus=0.02):
    n_in, n_out = int(SR * ein), int(SR * aus)
    x = x.copy()
    if n_in:
        x[:n_in] *= np.linspace(0, 1, n_in) ** 2
    if n_out:
        x[-n_out:] *= np.linspace(1, 0, n_out) ** 2
    return x


def sweep(f0, f1, sek, kurve="exp"):
    tt = t(sek)
    if kurve == "exp":
        f = f0 * (f1 / f0) ** (tt / sek)
    else:
        f = f0 + (f1 - f0) * tt / sek
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def tiefpass(x, cutoff):
    """Einpoliger Tiefpass; cutoff darf Array (zeitvariabel) sein."""
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def hochpass(x, cutoff):
    return x - tiefpass(x, cutoff)


def platziere(laenge_sek, teile):
    out = np.zeros(int(SR * laenge_sek))
    for start, sig in teile:
        i = int(SR * start)
        n = min(len(sig), len(out) - i)
        out[i:i + n] += sig[:n]
    return out


# ---------------------------------------------------------------- Sounds
def pop(f0=700, f1=180, sek=0.09):
    tt = t(sek)
    s = sweep(f0, f1, sek) * np.exp(-tt * 38)
    return fade(s, 0.002, 0.01)


def blubb_pops():
    return platziere(0.5, [(0.0, pop(520, 160)), (0.13, pop(680, 200)), (0.26, pop(900, 260))])


def boom(sek=0.9):
    tt = t(sek)
    s = sweep(85, 38, sek) * np.exp(-tt * 4.5)
    s += 0.3 * sweep(170, 76, sek) * np.exp(-tt * 9)  # Oberton, damit es auf Handylautsprechern hoerbar ist
    return fade(s, 0.003, 0.05)


def riser_boom():
    sek = 1.0
    tt = t(sek)
    rausch = np.random.default_rng(1).standard_normal(len(tt))
    riser = tiefpass(rausch, 300 + 5000 * (tt / sek) ** 2) * (tt / sek) ** 2
    riser += 0.35 * sweep(220, 1200, sek) * (tt / sek) ** 3
    return platziere(1.9, [(0.0, fade(riser, 0.05, 0.01)), (1.0, boom())])


def whoosh():
    sek = 0.6
    tt = t(sek)
    rausch = np.random.default_rng(2).standard_normal(len(tt))
    huelle = np.sin(np.pi * tt / sek) ** 2
    cutoff = 400 + 3500 * np.sin(np.pi * tt / sek)
    s = hochpass(tiefpass(rausch, cutoff), 150) * huelle
    return fade(s, 0.01, 0.05)


def benachrichtigung():
    def ding(f, sek=0.45):
        tt = t(sek)
        s = np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt) + 0.1 * np.sin(2 * np.pi * 3 * f * tt)
        return fade(s * np.exp(-tt * 7), 0.003, 0.05)
    return platziere(0.65, [(0.0, ding(988)), (0.13, ding(1319))])


def kamera_klick():
    rng = np.random.default_rng(3)

    def klick(sek, decay):
        tt = t(sek)
        return hochpass(rng.standard_normal(len(tt)) * np.exp(-tt * decay), 1500)
    return fade(platziere(0.2, [(0.0, klick(0.012, 400)), (0.07, 0.8 * klick(0.025, 200))]), 0.001, 0.01)


SOUNDS = {
    "blubb_pops": blubb_pops,
    "riser_boom": riser_boom,
    "boom": boom,
    "whoosh": whoosh,
    "benachrichtigung": benachrichtigung,
    "kamera_klick": kamera_klick,
}



def schreibe(name, x):
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (-3 / 20)  # Peak -3 dBFS
    stereo = np.repeat((x * 32767).astype(np.int16)[:, None], 2, axis=1)
    ZIEL.mkdir(parents=True, exist_ok=True)
    pfad = ZIEL / f"{name}.wav"
    with wave.open(str(pfad), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
    return pfad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("namen", nargs="*")
    a = ap.parse_args()
    if a.liste:
        print("\n".join(SOUNDS))
        return
    for name in a.namen or SOUNDS:
        print(schreibe(name, SOUNDS[name]()))


if __name__ == "__main__":
    main()
