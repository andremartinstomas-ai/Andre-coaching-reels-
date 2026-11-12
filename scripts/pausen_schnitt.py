#!/usr/bin/env python3
"""Zerlegt grobe Abschnitte eines Sprechvideos in Segmente ohne Denkpausen (Energie-basiert).

Als Modul:  from pausen_schnitt import sprechbereiche
            sprechbereiche("roh/teil_3.mov", 29.1, 49.2)  -> [(29.12, 31.40), (32.05, 33.62), ...]
Als Skript: python3 scripts/pausen_schnitt.py roh/teil_3.mov 29.1 49.2
"""
import subprocess
import sys

import numpy as np

SR = 16000


def _audio(pfad):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(pfad), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


_CACHE = {}


def sprechbereiche(pfad, start, ende, schwelle_db=-36.0, min_pause=0.35, vor=0.06, nach=0.12, min_stueck=0.25):
    """Liefert Sprech-Abschnitte zwischen start und ende; Pausen >= min_pause werden entfernt."""
    if pfad not in _CACHE:
        _CACHE[pfad] = _audio(pfad)
    x = _CACHE[pfad]
    hop = int(0.02 * SR)
    a, e = int(start * SR), int(min(ende * SR, len(x)))
    seg = x[a:e]
    if len(seg) < hop:
        return []
    n = len(seg) // hop
    db = 20 * np.log10(np.sqrt(np.mean(seg[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9)
    aktiv = db > schwelle_db
    # Glaetten: kurze Luecken (< min_pause) schliessen
    bereiche, i = [], 0
    while i < n:
        if aktiv[i]:
            j = i
            while j < n and aktiv[j]:
                j += 1
            bereiche.append([i, j])
            i = j
        else:
            i += 1
    zusammen = []
    for b in bereiche:
        if zusammen and (b[0] - zusammen[-1][1]) * 0.02 < min_pause:
            zusammen[-1][1] = b[1]
        else:
            zusammen.append(b)
    out = []
    for s, t in zusammen:
        s_t = max(start, start + s * 0.02 - vor)
        e_t = min(ende, start + t * 0.02 + nach)
        if e_t - s_t >= min_stueck:
            out.append((round(s_t, 2), round(e_t, 2)))
    return out


if __name__ == "__main__":
    for s, e in sprechbereiche(sys.argv[1], float(sys.argv[2]), float(sys.argv[3])):
        print(f"{s:7.2f} - {e:7.2f}  ({e - s:.2f}s)")
