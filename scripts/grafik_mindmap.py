#!/usr/bin/env python3
"""Erzeugt eine transparente Mindmap-Grafik (PNG) im Markenstil: Schmerz in der Mitte, Einflussfaktoren drumherum.

python3 scripts/grafik_mindmap.py ziel.png
Faktoren nach IASP-Definition (Raja et al. 2020): biologisch, psychologisch, sozial.
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = str(ROOT / "fonts" / "BebasNeue-Regular.ttf")
GELB, WEISS, TEAL, TEAL_HELL = (248, 184, 0, 255), (255, 255, 255, 255), (0, 80, 88, 235), (120, 210, 205, 255)

FAKTOREN = [  # (Text, Kategorie)
    ("Gewebe", "bio"), ("Entzündung", "bio"), ("Schlaf", "bio"), ("Bewegung", "bio"), ("Ernährung", "bio"),
    ("Stress", "psycho"), ("Angst", "psycho"), ("Erwartungen", "psycho"), ("Stimmung", "psycho"), ("Vorerfahrung", "psycho"),
    ("Arbeit", "sozial"), ("Familie", "sozial"), ("Umfeld", "sozial"),
]
FARBE = {"bio": GELB, "psycho": WEISS, "sozial": TEAL_HELL}


def text_mit_kontur(d, xy, txt, font, fill, anchor="mm", kontur=5):
    d.text(xy, txt, font=font, fill=fill, anchor=anchor, stroke_width=kontur, stroke_fill=(20, 20, 20, 255))


def main(ziel):
    W, H = 1120, 1100
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, 520
    f_klein, f_mitte, f_leg = ImageFont.truetype(FONT, 58), ImageFont.truetype(FONT, 80), ImageFont.truetype(FONT, 50)
    links = [f for i, f in enumerate(FAKTOREN) if i % 2 == 0]
    rechts = [f for i, f in enumerate(FAKTOREN) if i % 2 == 1]
    for spalte, x_text, anker, x_linie in ((links, 300, "rm", 316), (rechts, 820, "lm", 804)):
        n = len(spalte)
        for i, (txt, kat) in enumerate(spalte):
            y = 90 + i * (860 / max(1, n - 1))
            d.line([(cx + (-125 if anker == "rm" else 125), cy), (x_linie, y)], fill=(255, 255, 255, 160), width=4)
            text_mit_kontur(d, (x_text, y), txt.upper(), f_klein, FARBE[kat], anchor=anker)
    d.ellipse([cx - 135, cy - 80, cx + 135, cy + 80], fill=TEAL, outline=GELB, width=7)
    text_mit_kontur(d, (cx, cy + 4), "SCHMERZ", f_mitte, WEISS, kontur=0)
    y = H - 40
    teile = [("BIO", GELB), (" · ", WEISS), ("PSYCHO", WEISS), (" · ", WEISS), ("SOZIAL", TEAL_HELL)]
    breite = sum(d.textlength(t, font=f_leg) for t, _ in teile)
    x = cx - breite / 2
    for t, c in teile:
        text_mit_kontur(d, (x, y), t, f_leg, c, anchor="lm", kontur=4)
        x += d.textlength(t, font=f_leg)
    img.save(ziel)
    print(ziel)


if __name__ == "__main__":
    main(sys.argv[1])
