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
    ("IMG_4164", 0.30, 2.90, 1.00, 0.5, False, "Hook: fertige Pasta in der Hand"),
    ("IMG_4159", 0.00, 2.10, 1.00, 0.5, False, "Zutaten"),
    ("IMG_4161", 0.00, 2.00, 1.00, 0.5, False, "Soße: Zutaten im Mixbecher"),
    ("IMG_4162", 0.00, 2.20, 1.00, 0.5, False, "Soße: fertig gemixt"),
    ("IMG_4160", 0.30, 3.80, 1.30, 1.0, False, "Tofu + Champignons anbraten (Topf oben weggeschnitten)"),
    ("IMG_4163", 1.50, 5.50, 1.00, 0.5, True, "Alles vermischen"),
    ("IMG_4167", 3.50, 6.87, 1.00, 0.5, False, "Zitronenzeste (Nahfahrt)"),
    ("IMG_4165", 0.30, 3.30, 1.00, 0.5, False, "Fertiger Teller"),
]
PINK, GELB, DUNKEL = (255, 45, 120, 255), (255, 210, 63, 255), (18, 18, 18, 205)

# Hook: zwei Zeilen, Zeile 2 pink
HOOK = (["Diese pinke Buchweizenpasta", "macht irgendwas mit dir."], 0.0, 2.6, 200, 84)
BADGES = (["VEGETARISCH", "GLUTENFREI", "HIGH PROTEIN", "NITRATREICH"], 0.35, 2.6, 470)
ENDE = (["Jetzt speichern.", "Und bloß nicht nachkochen."], 20.0, 22.8, 200, 84)
TON_NUR = {"IMG_4163"}  # Originalton nur beim cremigen Umruehren, sonst stumm

# Zutatenliste (Soße): erscheint nach und nach, Bild darunter abgedunkelt
LISTE_START, LISTE_ENDE = 2.6, 8.9
LISTE_KOPF = "1. Die pinke Soße"
ZUTATEN = [("Rote Bete", None), ("Körniger Frischkäse", "UNGLAUBLICH WICHTIG"), ("Tomaten", None), ("Tomatenmark", None),
           ("Etwas Pastawasser", None), ("Etwas Honig", None), ("Salz, Pfeffer, Gewürze", None)]

# Schritt-Pills: (Nummer, Text, Start, Ende, y)
SCHRITTE = [
    ("2", "Tofu + Champignons anbraten", 8.9, 12.4, 210),
    ("3", "Alles cremig vermischen", 12.4, 16.4, 300),
    ("4", "Zitronenzeste drüber", 16.4, 18.3, 300),
]


def _schatten(img, radius=10, deckung=1.6):
    a = img.split()[3].filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: min(255, int(v * deckung)))
    sch = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sch.putalpha(a)
    return sch


def pill_png(ziel, text, groesse=54, bullet=True, fuellung=DUNKEL, tag=None, nummer=None):
    """Abgerundete 'Pill' mit Text; optional pinker Punkt, pinke Nummer oder gelbes Tag."""
    font = ImageFont.truetype(FONT, groesse)
    tfont = ImageFont.truetype(FONT, int(groesse * 0.62))
    h = int(groesse * 1.55)
    pad = int(groesse * 0.55)
    links = pad + (int(h * 0.42) if bullet else 0) + (h if nummer else 0)
    tb = int(font.getlength(text))
    tag_b = int(tfont.getlength(tag)) + 2 * int(h * 0.25) if tag else 0
    b = links + tb + pad + (tag_b + pad if tag else 0)
    rand = 30
    img = Image.new("RGBA", (b + 2 * rand, h + 2 * rand), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([rand, rand, rand + b, rand + h], radius=h // 2, fill=fuellung)
    x = rand + pad
    if nummer:
        d.ellipse([rand + 6, rand + 6, rand + h - 6, rand + h - 6], fill=PINK)
        d.text((rand + h / 2, rand + h / 2 + 2), nummer, font=font, fill=(255, 255, 255, 255), anchor="mm")
        x = rand + h + int(pad * 0.5)
    if bullet:
        r = int(h * 0.13)
        cy = rand + h // 2
        d.ellipse([x, cy - r, x + 2 * r, cy + r], fill=PINK)
        x += int(h * 0.42)
    d.text((x, rand + h / 2 + 2), text, font=font, fill=(255, 255, 255, 255), anchor="lm")
    if tag:
        tx = x + tb + pad
        th = int(h * 0.62)
        ty = rand + (h - th) // 2
        d.rounded_rectangle([tx, ty, tx + tag_b, ty + th], radius=th // 2, fill=GELB)
        d.text((tx + tag_b / 2, ty + th / 2 + 1), tag, font=tfont, fill=(20, 20, 20, 255), anchor="mm")
    out = Image.alpha_composite(_schatten(img, 12, 0.9), img)
    out.save(ziel)
    return out.size


def hook_png(ziel, zeilen, groesse):
    font = ImageFont.truetype(FONT, groesse)
    zh = int(groesse * 1.12)
    b = max(int(font.getlength(z)) for z in zeilen) + 100
    h = zh * len(zeilen) + 100
    img = Image.new("RGBA", (b, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, z in enumerate(zeilen):
        assert len(z) <= 38, z
        farbe = PINK if i == 1 else (255, 255, 255, 255)
        d.text((b / 2, 50 + i * zh + zh / 2), z, font=font, fill=farbe, anchor="mm",
               stroke_width=3, stroke_fill=(15, 15, 15, 255))
    out = Image.alpha_composite(_schatten(img, 10, 2.0), img)
    out.save(ziel)
    return out.size


def elemente(tmp):
    """Liste aller Overlays: (png, x_ziel, y_oben, start, ende, animation)."""
    el = []
    bw, bh = hook_png(tmp / "hook.png", HOOK[0], HOOK[4])
    el.append((tmp / "hook.png", (W - bw) // 2, HOOK[3], HOOK[1], HOOK[2], "runter"))
    # Badges unter dem Hook: 2x2, ploppen nacheinander rein
    for i, b in enumerate(BADGES[0]):
        f = tmp / f"badge{i}.png"
        bwid, bhei = pill_png(f, b, 40, bullet=False, fuellung=(255, 255, 255, 235) if False else PINK)
        spalte, reihe = i % 2, i // 2
        x = W // 2 - 20 - bwid if spalte == 0 else W // 2 + 20 - 30
        x = x + (30 if spalte == 0 else 0)
        el.append((f, x, BADGES[3] + reihe * (bhei - 18), BADGES[1] + i * 0.18, BADGES[2], "links"))
    ew, eh = hook_png(tmp / "ende.png", ENDE[0], ENDE[4])
    el.append((tmp / "ende.png", (W - ew) // 2, ENDE[3], ENDE[1], ENDE[2], "runter"))
    kw, kh = pill_png(tmp / "kopf.png", LISTE_KOPF, 62, bullet=False, fuellung=PINK)
    el.append((tmp / "kopf.png", 70, 300, LISTE_START + 0.1, LISTE_ENDE, "links"))
    for i, (z, tag) in enumerate(ZUTATEN):
        f = tmp / f"z{i}.png"
        pill_png(f, z, 52, tag=tag)
        el.append((f, 70, 300 + kh - 10 + i * 102, LISTE_START + 0.55 + i * 0.6, LISTE_ENDE, "links"))
    for i, (n, txt, a, e, y) in enumerate(SCHRITTE):
        assert len(f"{n}. {txt}") <= 38
        f = tmp / f"s{i}.png"
        sw, sh_ = pill_png(f, txt, 56, bullet=False, nummer=n)
        el.append((f, (W - sw) // 2, y - sh_ // 2, a, e, "links"))
    return el


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
            af = "aresample=48000,afade=t=in:d=0.08,afade=t=out:st=%.3f:d=0.08" % (e - a - 0.08)
            af = ("loudnorm=I=-16:TP=-1.5:LRA=7," + af) if datei in TON_NUR else ("volume=0," + af)
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
        # Verlauf nur links hinter der Liste (Farbe rechts bleibt kraeftig)
        import numpy as np
        g = np.zeros((H, W, 4), np.uint8)
        x = np.linspace(0, 1, W)
        g[..., 3] = (np.clip(1 - (x - 0.25) / 0.55, 0, 1) ** 1.3 * 175).astype(np.uint8)[None, :]
        Image.fromarray(g, "RGBA").save(tmp / "verlauf.png")
        args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(tmp / "verlauf.png")]
        fc = [f"[1:v]format=rgba,fade=t=in:st={LISTE_START}:d=0.25:alpha=1,fade=t=out:st={LISTE_ENDE - 0.25}:d=0.25:alpha=1[vl]",
              f"[0:v][vl]overlay=0:0:enable='between(t,{LISTE_START},{LISTE_ENDE})'[d]"]
        letzter = "d"
        for i, (png, xz, y, a, e, anim) in enumerate(elemente(tmp)):
            args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(png)]
            ein = "" if a == 0 else f"fade=t=in:st={a}:d=0.2:alpha=1,"   # Hook ab Frame 0 voll sichtbar
            fc.append(f"[{i + 2}:v]format=rgba,{ein}fade=t=out:st={e - 0.2}:d=0.2:alpha=1[e{i}]")
            k = "\\,"
            p = f"min(1{k}max(0{k}(t-{a})/0.35))"
            ease = f"(1-pow(1-{p}{k}3))"
            if a == 0:
                xe, ye = f"{xz}", f"{y}"
            elif anim == "links":   # von links reingleiten, weich abbremsen
                xe, ye = f"-w+({xz}+w)*{ease}", f"{y}"
            else:                 # 'runter': leicht von oben einsinken
                xe, ye = f"{xz}", f"{y}-40*(1-{ease})"
            fc.append(f"[{letzter}][e{i}]overlay=x='{xe}':y='{ye}':enable='between(t,{a},{e})'[v{i}]")
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
