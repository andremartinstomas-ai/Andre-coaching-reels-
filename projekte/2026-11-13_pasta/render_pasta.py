#!/usr/bin/env python3
"""Rote-Bete-Buchweizenpasta-Reel: Schnitt, Look, Text (PIL), Ton. Ausgabe reels/pasta_reel.mp4 (1080x1920, 30 fps)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent.parent
FONT = str(ROOT / "fonts" / "BigShouldersDisplay-Bold.ttf")
W, H, FPS = 1080, 1920, 30

# Szenen: (Datei, Start, Ende, Zoom, Fokus-y, Aufhellen)  -> Reihenfolge = Schnitt
SZENEN = [
    ("IMG_4164", 0.30, 2.30, 1.00, 0.5, False, "Hook: fertige Pasta in der Hand"),
    ("IMG_4159", 0.20, 1.80, 1.00, 0.5, False, "Zutaten"),
    ("IMG_4161", 0.00, 2.00, 1.00, 0.5, False, "Soße: Zutaten im Mixbecher"),
    ("IMG_4162", 0.00, 2.20, 1.00, 0.5, False, "Soße: fertig gemixt"),
    ("IMG_4160", 0.30, 3.80, 1.30, 1.0, False, "Tofu + Gemüse anbraten (Topf oben weggeschnitten)"),
    ("IMG_4163", 1.50, 5.50, 1.00, 0.5, True, "Alles vermischen"),
    ("IMG_4167", 3.50, 6.87, 1.00, 0.5, False, "Zitronenzeste (Nahfahrt)"),
    ("IMG_4165", 0.30, 3.30, 1.00, 0.5, False, "Fertiger Teller"),
]
# Texte: (Text, Start, Ende, y-Mitte, Groesse)
TEXTE = [
    ("Mein Lieblingsessen nach dem Training", 0.0, 2.0, 250, 66),
    ("1. Soße: Rote Bete +\nFrischkäse + Tomate", 3.6, 5.6, 1640, 56),   # Becher oben -> Text unten
    ("1. Soße: Rote Bete +\nFrischkäse + Tomate", 5.6, 7.8, 260, 56),    # Becher reicht nach unten -> Text oben
    ("2. Tofu + Gemüse anbraten", 7.8, 11.3, 200, 56),                    # unten Hand/Pfannenwender -> oben
    ("3. Alles vermischen", 11.3, 15.3, 300, 56),
    ("4. Zitronenzeste", 15.3, 17.2, 300, 56),
]


def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-2000:])
    return r


def lautheit(pfad):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    zeilen = [z for z in err.splitlines() if z.strip().startswith("I:")]
    return float(zeilen[-1].split()[1]) if zeilen else -70.0


def text_png(text, groesse, ziel):
    font = ImageFont.truetype(FONT, groesse)
    zeilen = text.split("\n")
    for z in zeilen:
        assert len(z) <= 38, f"Zeile zu lang: {z}"
    zh = int(groesse * 1.15)
    breite = max(int(font.getlength(z)) for z in zeilen) + 80
    hoehe = zh * len(zeilen) + 80
    schatten = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
    ds = ImageDraw.Draw(schatten)
    for i, z in enumerate(zeilen):
        x = (breite - font.getlength(z)) / 2
        ds.text((x + 3, 40 + i * zh + 4), z, font=font, fill=(0, 0, 0, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
    schatten = schatten.filter(ImageFilter.GaussianBlur(9))
    schatten = Image.alpha_composite(schatten, schatten)  # Schatten verdichten: besser lesbar auf hellem Grund
    d = ImageDraw.Draw(schatten)
    for i, z in enumerate(zeilen):
        x = (breite - font.getlength(z)) / 2
        d.text((x, 40 + i * zh), z, font=font, fill=(255, 255, 255, 255))
    schatten.save(ziel)
    return breite, hoehe


def main():
    roh = HIER / "roh"
    aus = HIER / "reels" / "pasta_reel.mp4"
    aus.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        liste, t, plan = [], 0.0, []
        for i, (datei, a, e, z, fy, hell, inhalt) in enumerate(SZENEN):
            quelle = roh / f"{datei}.mov"
            seg = tmp / f"s{i:02d}.mp4"
            sw, shh = int(W * z / 2) * 2, int(H * z / 2) * 2
            vf = (f"scale={sw}:{shh}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})/2:(ih-{H})*{fy},"
                  f"setsar=1,fps={FPS},eq=contrast=1.08:saturation=1.12" + (":brightness=0.06" if hell else "") +
                  ",format=yuv420p")
            # Ton: Originalton; hoerbaren Ton (Zischen/Ruehren) gleichmaessig auf -20 LUFS, sehr leise Clips bleiben leise
            roh_lufs = lautheit(quelle)
            af = "aresample=48000,afade=t=in:d=0.02,afade=t=out:st=%.3f:d=0.03" % (e - a - 0.03)
            if roh_lufs > -50:
                af = "loudnorm=I=-20:TP=-2:LRA=7," + af
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(a), "-to", str(e), "-i", str(quelle),
                "-vf", vf, "-af", af, "-ac", "2", "-ar", "48000", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{e - a:.3f}", str(seg)])
            liste.append(f"file '{seg.name}'\n")
            plan.append({"szene": inhalt, "datei": f"{datei}.mov", "quelle_von": a, "quelle_bis": e,
                         "reel_von": round(t, 2), "reel_bis": round(t + e - a, 2), "ton_lufs_roh": round(roh_lufs, 1)})
            t += e - a
        (tmp / "liste.txt").write_text("".join(liste))
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
            str(tmp / "liste.txt"), "-c", "copy", str(tmp / "roh.mp4")])

        args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp / "roh.mp4")]
        fc, letzter = [], "0:v"
        for i, (txt, a, e, y, g) in enumerate(TEXTE):
            png = tmp / f"t{i}.png"
            bw, bh = text_png(txt, g, png)
            args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(png)]
            fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a}:d=0.2:alpha=1,fade=t=out:st={e - 0.2}:d=0.2:alpha=1[t{i}]")
            fc.append(f"[{letzter}][t{i}]overlay=(W-w)/2:{y}-h/2:enable='between(t,{a},{e})'[v{i}]")
            letzter = f"v{i}"
        args += ["-filter_complex", ";".join(fc), "-map", f"[{letzter}]", "-map", "0:a",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M",
                 "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(aus)]
        sh(args)
    (HIER / "reels" / "pasta_reel_schnittplan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    print(aus, f"{t:.2f}s")
    for p in plan:
        print(f"  {p['reel_von']:5.2f}-{p['reel_bis']:5.2f}s  {p['datei']} {p['quelle_von']:.2f}-{p['quelle_bis']:.2f}s  {p['szene']}")


if __name__ == "__main__":
    main()
