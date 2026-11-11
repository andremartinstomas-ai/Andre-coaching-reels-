#!/usr/bin/env python3
"""Erzeugt synthetisches Testmaterial + Fake-Transkript, um die Pipeline ohne echtes Video zu pruefen."""
import json
import subprocess
from pathlib import Path

D = Path(__file__).resolve().parent / "testprojekt" / "roh"
D.mkdir(parents=True, exist_ok=True)
ff = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
# Querformat "Sprechvideo" 20s mit Ton
subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=20", "-f", "lavfi",
                     "-i", "sine=f=220:d=20,volume=0.3", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                     "-c:a", "aac", str(D / "sprechen.mp4")], check=True)
# Hochkant-Uebungsclip 8s ohne Ton
subprocess.run(ff + ["-f", "lavfi", "-i", "mandelbrot=s=1080x1920:r=30", "-t", "8", "-c:v", "libx264",
                     "-preset", "ultrafast", str(D / "uebung.mp4")], check=True)
satz = ("Rund ein Drittel der Zwanzigjaehrigen ohne Rueckenschmerzen hat im MRT eine Bandscheibenveraenderung. "
        "Das Bild allein sagt also wenig ueber deinen Schmerz. Bewegung hilft dir mehr als Schonung.").split()
woerter, t = [], 2.0
for w in satz:
    d = 0.18 + 0.045 * len(w)
    woerter.append({"text": w, "start": round(t, 2), "ende": round(t + d, 2)})
    t += d + 0.08
out = D.parent / "transkripte"
out.mkdir(exist_ok=True)
(out / "sprechen.json").write_text(json.dumps({"datei": "roh/sprechen.mp4", "sprache": "de", "woerter": woerter},
                                              ensure_ascii=False, indent=1))
print("ok, Sprechende bei", round(t, 2))
