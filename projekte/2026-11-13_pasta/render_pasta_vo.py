#!/usr/bin/env python3
"""Pasta-Reel mit Andrés Voice-over. Baut erst die Voice-Spur aus den besten Takes, passt dann die Szenenlängen an:
'Und jetzt hört mal' startet genau mit dem Umrühr-Clip, danach 3 s nur Umrühr-Sound, Outro über Zeste + Teller."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rp", HIER / "render_pasta.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
W, H, FPS, sh = rp.W, rp.H, rp.FPS, rp.sh

VO = HIER / "roh" / "voiceover.m4a"
# Takes (Quellzeiten im Memo); innerhalb eines Blocks Pausen rausgeschnitten
BLOECKE = {
    "A_hook":    [(2.00, 4.40), (4.85, 7.25)],                 # Ja, ihr seht richtig ... Rote Bete
    "B_nitrat":  [(15.90, 17.38), (17.50, 21.00), (21.20, 22.25)],
    "C_wirkung": [(27.70, 32.35), (33.10, 35.20)],             # ... Nicht bei jedem, aber kann dir helfen,
    "D_protein": [(43.60, 47.10)],
    "E_hoer":    [(93.00, 95.10)],                             # Und jetzt hört mal, wie sich das anhört
    "F_zeste":   [(98.70, 100.25), (101.80, 104.75)],
    "G_labels":  [(106.20, 109.45)],                           # glutenfrei, vegetarisch und high protein
    "H_ende":    [(114.55, 117.95)],                           # Speichert euch das ab und bloß nicht nachkochen
}
LUECKE_BLOCK, LUECKE_INNEN, NUR_SOUND = 0.25, 0.06, 3.0


def voice_spur(tmp):
    """Baut die Voice-Spur; gibt Pfad und Start/Ende jedes Blocks auf der Spur zurueck."""
    teile, t, marken = [], 0.0, {}
    for name, stuecke in BLOECKE.items():
        if name == "F_zeste":
            t += NUR_SOUND  # Platz fuers cremige Umruehren
            teile.append(("stille", NUR_SOUND))
        marken[name] = [t, None]
        for i, (a, e) in enumerate(stuecke):
            teile.append((a, e))
            t += e - a
            if i < len(stuecke) - 1:
                teile.append(("stille", LUECKE_INNEN)); t += LUECKE_INNEN
        marken[name][1] = t
        teile.append(("stille", LUECKE_BLOCK)); t += LUECKE_BLOCK
    fc, args = [], ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(VO)]
    for i, tl in enumerate(teile):
        if tl[0] == "stille":
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{tl[1]}[p{i}]")
        else:
            a, e = tl
            fc.append(f"[0:a]atrim={a}:{e},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
                      f"afade=t=in:d=0.02,afade=t=out:st={e - a - 0.03:.3f}:d=0.03[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(len(teile))) + f"concat=n={len(teile)}:v=0:a=1,"
              # Mikro war nah dran: Bass/Plopp runter, Zischlaute daempfen, leicht komprimieren
              "highpass=f=80,equalizer=f=170:t=q:w=1.2:g=-4,deesser=i=0.3,"
              "acompressor=threshold=-22dB:ratio=3:attack=8:release=150:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=7[vo]")
    ziel = tmp / "voice.wav"
    sh(args + ["-filter_complex", ";".join(fc), "-map", "[vo]", "-ar", "48000", str(ziel)])
    return ziel, {k: (round(a, 2), round(b, 2)) for k, (a, b) in marken.items()}, t


def main():
    roh = HIER / "roh"
    aus = HIER / "reels" / "pasta_reel_voiceover.mp4"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice, m, vo_len = voice_spur(tmp)
        gesamt = round(vo_len + 0.4, 2)
        # Teil 1 muss bis zum Start von 'Und jetzt hört mal' reichen
        teil1 = m["E_hoer"][0]
        fest1 = [("IMG_4164", 0.30, 3.07), ("IMG_4166", 0.00, 2.97), ("IMG_4159", 0.00, 2.10),
                 ("IMG_4161", 0.00, 2.53), ("IMG_4162", 0.00, 2.70)]
        rest = teil1 - sum(e - a for _, a, e in fest1)
        tofu_speed = max(0.6, min(1.0, 6.62 / rest))           # Tofu-Clip ggf. leicht verlangsamen
        szenen = [(d, a, e, 1.0) for d, a, e in fest1] + [("IMG_4160", 0.0, 6.62, tofu_speed)]
        dauer1 = sum((e - a) / s for _, a, e, s in szenen)
        if dauer1 < teil1 - 0.02:                               # falls noch Luecke: Teller-Hook verlaengern
            szenen[0] = ("IMG_4164", 0.30 - min(0.3, teil1 - dauer1), 3.07, 1.0)
        # Teil 2: Umruehren (Ton!), Zeste, Teller
        ruehr = ("IMG_4163", 1.50, 7.17, 1.0)
        teller = ("IMG_4165", 0.00, 3.47, 1.0)
        zeit_bis_teller = gesamt - 3.47
        start_zeste = sum((e - a) / s for _, a, e, s in szenen) + (ruehr[2] - ruehr[1])
        zeste_len = zeit_bis_teller - start_zeste
        zeste_speed = max(0.6, min(1.0, 6.87 / zeste_len))
        szenen += [ruehr, ("IMG_4167", 0.0, 6.87, zeste_speed), teller]

        liste, t, plan, grenzen = [], 0.0, [], {}
        for i, (datei, a, e, speed) in enumerate(szenen):
            seg = tmp / f"s{i:02d}.mp4"
            d = (e - a) / speed
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})/2:(ih-{H})*"
                  f"{1.0 if datei == 'IMG_4160' else 0.5},setpts=PTS/{speed},setsar=1,fps={FPS},"
                  f"eq=contrast=1.08:saturation=1.12" + (":brightness=0.06" if datei == "IMG_4163" else "") +
                  ",format=yuv420p")
            if datei == "IMG_4160":  # Topf oben wegschneiden
                vf = vf.replace(f"scale={W}:{H}", f"scale={int(W * 1.3 / 2) * 2}:{int(H * 1.3 / 2) * 2}")
            af = "loudnorm=I=-21:TP=-3:LRA=7," if datei == "IMG_4163" else "volume=0,"
            if speed != 1.0:
                af += f"atempo={speed},"
            af += f"aresample=48000,afade=t=in:d=0.08,afade=t=out:st={d - 0.08:.3f}:d=0.08"
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(a), "-to", str(e), "-i",
                str(roh / f"{datei}.mov"), "-vf", vf, "-af", af, "-ac", "2", "-ar", "48000", "-c:v", "libx264",
                "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-t", f"{d:.3f}", str(seg)])
            liste.append(f"file '{seg.name}'\n")
            grenzen[datei] = (round(t, 2), round(t + d, 2))
            plan.append({"datei": f"{datei}.mov", "quelle": [a, e], "tempo": round(speed, 2),
                         "reel": [round(t, 2), round(t + d, 2)]})
            t += d
        (tmp / "liste.txt").write_text("".join(liste))
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
            str(tmp / "liste.txt"), "-c", "copy", str(tmp / "roh.mp4")])

        # Text-Timing an Szenen + Voice koppeln
        g = grenzen
        rp.HOOK = (rp.HOOK[0], 0.0, m["A_hook"][1] + 0.2, rp.HOOK[3], rp.HOOK[4])
        rp.BADGES = (rp.BADGES[0], 0.4, m["A_hook"][1] + 0.2, rp.BADGES[3])
        rp.LISTE_START, rp.LISTE_ENDE = g["IMG_4159"][0], g["IMG_4162"][1]
        rp.SCHRITTE = [("2", "Tofu + Champignons anbraten", g["IMG_4160"][0], g["IMG_4160"][1], 210),
                       ("3", "Alles cremig vermischen", g["IMG_4163"][0], g["IMG_4163"][1], 300),
                       ("4", "Zitronenzeste drüber", g["IMG_4167"][0], g["IMG_4167"][1], 300)]
        rp.ENDE = (rp.ENDE[0], g["IMG_4165"][0], t - 0.05, rp.ENDE[3], rp.ENDE[4])

        args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp / "roh.mp4"), "-i", str(voice)]
        import numpy as np
        from PIL import Image
        gr = np.zeros((H, W, 4), np.uint8)
        x = np.linspace(0, 1, W)
        gr[..., 3] = (np.clip(1 - (x - 0.25) / 0.55, 0, 1) ** 1.3 * 175).astype(np.uint8)[None, :]
        Image.fromarray(gr, "RGBA").save(tmp / "verlauf.png")
        args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(tmp / "verlauf.png")]
        L0, L1 = rp.LISTE_START, rp.LISTE_ENDE
        fc = [f"[2:v]format=rgba,fade=t=in:st={L0}:d=0.25:alpha=1,fade=t=out:st={L1 - 0.25}:d=0.25:alpha=1[vl]",
              f"[0:v][vl]overlay=0:0:enable='between(t,{L0},{L1})'[d]"]
        letzter = "d"
        for i, (png, xz, y, a, e, anim) in enumerate(rp.elemente(tmp)):
            args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(png)]
            ein = "" if a == 0 else f"fade=t=in:st={a}:d=0.2:alpha=1,"
            fc.append(f"[{i + 3}:v]format=rgba,{ein}fade=t=out:st={e - 0.2}:d=0.2:alpha=1[e{i}]")
            k = "\\,"
            p = f"min(1{k}max(0{k}(t-{a})/0.35))"
            ease = f"(1-pow(1-{p}{k}3))"
            if a == 0:
                xe, ye = f"{xz}", f"{y}"
            elif anim == "links":
                xe, ye = f"-w+({xz}+w)*{ease}", f"{y}"
            else:
                xe, ye = f"{xz}", f"{y}-40*(1-{ease})"
            fc.append(f"[{letzter}][e{i}]overlay=x='{xe}':y='{ye}':enable='between(t,{a},{e})'[v{i}]")
            letzter = f"v{i}"
        fc.append("[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]")
        args += ["-filter_complex", ";".join(fc), "-map", f"[{letzter}]", "-map", "[a]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-maxrate", "12M", "-bufsize", "24M",
                 "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                 "-t", f"{t:.3f}", str(aus)]
        sh(args)
    (HIER / "reels" / "pasta_reel_voiceover_plan.json").write_text(
        json.dumps({"voice_bloecke": m, "szenen": plan}, ensure_ascii=False, indent=2))
    print(aus, f"{t:.2f}s")
    print("Voice:", json.dumps(m))
    for p in plan:
        print(" ", p)


if __name__ == "__main__":
    main()
