#!/usr/bin/env python3
"""Pasta-Reel-Varianten mit Voice-over 2 (voiceover2.m4a). Bild passt sich automatisch an die Voice-Spur an:
'hoeren'-Block startet genau mit dem Umruehr-Clip, danach 3 s nur Umruehr-Sound.
Aufruf: python3 render_pasta_vo2.py v1|v2|v3"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from pausen_schnitt import sprechbereiche  # noqa: E402

spec = importlib.util.spec_from_file_location("rp", HIER / "render_pasta.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
W, H, FPS, sh = rp.W, rp.H, rp.FPS, rp.sh
VO = HIER / "roh" / "voiceover2.m4a"

T = {  # Takes (Quellzeiten im Memo)
    "hook_rezept": [(3.6, 5.95), (16.2, 19.35)],          # So, heute mal keine Übung, sondern ein Rezept ... eine geile Buchweizenpasta mit Rote Bete
    "hook_saft": [(23.6, 27.6)],                           # Wenn du deinen Rote-Bete-Saft immer noch trinkst, dann mach dir diese Pasta hier
    "zutaten": [(41.2, 42.1), (46.8, 57.6)],               # Alles, was wir dafür brauchen ...
    "mixen": [(59.6, 62.9)],
    "tofu": [(65.6, 68.1)],                                # Dazu hab ich dann auch Tofu und Champignons angebraten
    "tofu_protein": [(70.5, 73.6)],                        # Für die Proteine hab ich nochmal Tofu und Champignons angebraten
    "hoeren_verruehren": [(75.9, 79.9)],                   # Und dann alles einmal zusammen verrühren, einmal ganz genau hinhören
    "hoeren_geil": [(83.1, 86.2)],                         # Hört euch mal an, wie geil das klingt
    "hoeren_jetzt": [(87.9, 90.3)],                        # Und jetzt einmal ganz genau hinhören
    "fertig": [(99.6, 103.9)],                             # Und schon habt ihr die Rote-Bete-Pasta fertig
    "nitrat_protein": [(105.6, 111.4)],                    # Rote Bete hat richtig viel Nitrat und Tofu plus Frischkäse bringen ordentlich Proteine
    "nitrat_kurz": [(105.6, 107.4)],                       # Rote Bete hat richtig viel Nitrat
    "no": [(145.8, 150.1)],                                # Und aus den Nitraten der Rote Bete wird Stickstoffmonoxid gemacht
    "wirkung": [(158.2, 162.2)],                           # Stickstoffmonoxid kann die Gefäße weiten und die Muskeln sparsamer arbeiten lassen
    "effekt": [(175.2, 181.6)],                            # Wie groß ist der Effekt? Klein bis moderat. Vor allem bei untrainierten ...
    "outro": [(197.6, 200.7)],                             # So und jetzt abspeichern und nicht nachkochen
}

VERSIONEN = {
    "v1": {"titel": "Physio-Twist", "hook": ["Heute keine Übung,", "sondern ein Rezept."],
           "teil1": ["hook_rezept", "zutaten", "mixen", "tofu"], "hoeren": "hoeren_verruehren",
           "teil2": ["fertig", "nitrat_protein", "outro"],
           "pills": {}},
    "v2": {"titel": "Rote-Bete-Saft", "hook": ["Trinkst du noch", "Rote-Bete-Saft?"],
           "teil1": ["hook_saft", "zutaten", "mixen", "tofu_protein"], "hoeren": "hoeren_jetzt",
           "teil2": ["fertig", "nitrat_protein", "no", "wirkung", "effekt", "outro"],
           "pills": {"no": "Nitrat → Stickstoffmonoxid", "wirkung": "Gefäße weiten, Muskeln sparsamer",
                     "effekt": "Effekt: klein bis moderat"}},
    "v3": {"titel": "Wissen zuerst", "hook": ["Was Rote Bete", "in deinem Körper macht"],
           "teil1": ["nitrat_kurz", "no", "wirkung", "effekt", "tofu_protein"], "hoeren": "hoeren_geil",
           "teil2": ["fertig", "outro"],
           "pills": {"no": "Nitrat → Stickstoffmonoxid", "wirkung": "Gefäße weiten, Muskeln sparsamer",
                     "effekt": "Effekt: klein bis moderat"}},
}
LUECKE, NUR_SOUND = 0.22, 3.0


def voice_spur(tmp, v):
    folge = v["teil1"] + [v["hoeren"], "_sound"] + v["teil2"]
    teile, t, m = [], 0.0, {}
    for key in folge:
        if key == "_sound":
            teile.append(("stille", NUR_SOUND)); t += NUR_SOUND
            continue
        m[key] = [t, None]
        stuecke = [s for a, e in T[key] for s in sprechbereiche(str(VO), a, e)]
        for i, (a, e) in enumerate(stuecke):
            teile.append((a, e)); t += e - a
            if i < len(stuecke) - 1:
                teile.append(("stille", 0.06)); t += 0.06
        m[key][1] = t
        teile.append(("stille", LUECKE)); t += LUECKE
    fc = []
    for i, tl in enumerate(teile):
        if tl[0] == "stille":
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{tl[1]}[p{i}]")
        else:
            a, e = tl
            fc.append(f"[0:a]atrim={a}:{e},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
                      f"afade=t=in:d=0.02,afade=t=out:st={e - a - 0.03:.3f}:d=0.03[p{i}]")
    fc.append("".join(f"[p{i}]" for i in range(len(teile))) + f"concat=n={len(teile)}:v=0:a=1,"
              "highpass=f=80,equalizer=f=170:t=q:w=1.2:g=-4,deesser=i=0.3,"
              "acompressor=threshold=-22dB:ratio=3:attack=8:release=150:makeup=2,loudnorm=I=-16:TP=-1.5:LRA=7[vo]")
    ziel = tmp / "voice.wav"
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(VO), "-filter_complex", ";".join(fc),
        "-map", "[vo]", "-ar", "48000", str(ziel)])
    return ziel, {k: (round(a, 2), round(b, 2)) for k, (a, b) in m.items()}, t


def szenen_planen(teil1, teil2):
    """Teil 1 endet genau, wenn der 'hoeren'-Block startet. Teil 2 fuellt den Rest."""
    hook = [("IMG_4164", 0.30, 3.07, 1.0), ("IMG_4166", 0.0, 2.97, 1.0)]
    sosse = [("IMG_4159", 0.0, 2.10, 1.0), ("IMG_4161", 0.0, 2.53, 1.0), ("IMG_4162", 0.0, 2.70, 1.0)]
    fest = sum(e - a for _, a, e, _ in hook + sosse)
    tofu_len = teil1 - fest
    if tofu_len < 3.0:                       # zu wenig Platz: zweiten Teller-Clip weglassen
        hook = hook[:1]
        tofu_len += 2.97
    extra = []
    if tofu_len > 6.62 / 0.75:               # zu viel Platz: weiteren Teller-Clip einschieben
        extra = [("IMG_4167", 0.0, min(3.4, tofu_len - 6.62 / 0.75), 1.0)]
        tofu_len -= extra[0][2]
    if tofu_len >= 6.62:
        tofu = ("IMG_4160", 0.0, 6.62, 6.62 / tofu_len)
    else:
        tofu = ("IMG_4160", 0.0, tofu_len, 1.0)
    s1 = hook + extra + sosse + [tofu]
    ruehr = ("IMG_4163", 1.50, 7.17, 1.0)
    rest = teil2 - 5.67
    fueller = [("IMG_4167", 3.5, 6.87), ("IMG_4165", 0.0, 3.47), ("IMG_4167", 0.0, 3.5), ("IMG_4166", 0.0, 2.97),
               ("IMG_4164", 0.3, 3.07), ("IMG_4165", 0.0, 3.47)]  # genug Teller-Bilder auch fuer lange Voice-Spuren
    s2, summe = [ruehr], 0.0
    for d, a, e in fueller:
        if summe >= rest - 0.05:
            break
        laenge = e - a
        if summe + laenge >= rest:
            s2.append((d, a, a + (rest - summe), 1.0)); summe = rest
        else:
            s2.append((d, a, e, 1.0)); summe += laenge
    if summe < rest - 0.05:                  # immer noch kurz: letzten Clip verlangsamen
        d, a, e, _ = s2[-1]
        s2[-1] = (d, a, e, max(0.6, (e - a) / (e - a + rest - summe)))
    return s1 + s2


def main(vname):
    v = VERSIONEN[vname]
    aus = HIER / "reels" / f"pasta_vo2_{vname}.mp4"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice, m, vo_len = voice_spur(tmp, v)
        gesamt = round(vo_len + 0.4, 2)
        teil1 = m[v["hoeren"]][0]
        szenen = szenen_planen(teil1, gesamt - teil1)
        liste, t, plan, grenzen = [], 0.0, [], []
        for i, (datei, a, e, speed) in enumerate(szenen):
            seg = tmp / f"s{i:02d}.mp4"
            d = (e - a) / speed
            zoom = 1.3 if datei == "IMG_4160" else 1.0
            fy = 1.0 if datei == "IMG_4160" else 0.5
            vf = (f"scale={int(W * zoom / 2) * 2}:{int(H * zoom / 2) * 2}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H}:(iw-{W})/2:(ih-{H})*{fy},setpts=PTS/{speed},setsar=1,fps={FPS},"
                  f"eq=contrast=1.08:saturation=1.12" + (":brightness=0.06" if datei == "IMG_4163" else "") + ",format=yuv420p")
            af = "loudnorm=I=-21:TP=-3:LRA=7," if datei == "IMG_4163" else "volume=0,"
            if speed != 1.0:
                af += f"atempo={max(0.5, speed)},"
            af += f"aresample=48000,afade=t=in:d=0.08,afade=t=out:st={max(0, d - 0.08):.3f}:d=0.08"
            sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(a), "-to", str(e), "-i",
                str(HIER / "roh" / f"{datei}.mov"), "-vf", vf, "-af", af, "-ac", "2", "-ar", "48000", "-c:v", "libx264",
                "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-t", f"{d:.3f}", str(seg)])
            liste.append(f"file '{seg.name}'\n")
            grenzen.append((datei, round(t, 2), round(t + d, 2)))
            plan.append({"datei": f"{datei}.mov", "quelle": [round(a, 2), round(e, 2)], "tempo": round(speed, 2),
                         "reel": [round(t, 2), round(t + d, 2)]})
            t += d
        (tmp / "liste.txt").write_text("".join(liste))
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i",
            str(tmp / "liste.txt"), "-c", "copy", str(tmp / "roh.mp4")])

        def zeit(datei, welche=0):
            treffer = [g for g in grenzen if g[0] == datei]
            return treffer[welche] if treffer else None

        hook_ende = m[v["teil1"][0]][1] + 0.2
        rp.HOOK = (v["hook"], 0.0, hook_ende, 200, 84)
        rp.BADGES = (rp.BADGES[0], 0.4, hook_ende, rp.BADGES[3])
        rp.LISTE_START, rp.LISTE_ENDE = zeit("IMG_4159")[1], zeit("IMG_4162")[2]
        tofu, ruehr, zeste = zeit("IMG_4160"), zeit("IMG_4163"), zeit("IMG_4167", -1 if vname == "v3" else 0)
        zeste_nah = next((g for g in grenzen if g[0] == "IMG_4167" and g[1] >= ruehr[2] - 0.01), None)
        rp.SCHRITTE = [("2", "Tofu + Champignons anbraten", tofu[1], tofu[2], 210),
                       ("3", "Alles cremig vermischen", ruehr[1], ruehr[2], 300)]
        if zeste_nah:
            rp.SCHRITTE.append(("4", "Zitronenzeste drüber", zeste_nah[1], zeste_nah[2], 300))
        ende_start = m["outro"][0]
        rp.ENDE = (rp.ENDE[0], ende_start, t - 0.05, rp.ENDE[3], rp.ENDE[4])

        args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp / "roh.mp4"), "-i", str(voice)]
        gr = np.zeros((H, W, 4), np.uint8)
        x = np.linspace(0, 1, W)
        gr[..., 3] = (np.clip(1 - (x - 0.25) / 0.55, 0, 1) ** 1.3 * 175).astype(np.uint8)[None, :]
        Image.fromarray(gr, "RGBA").save(tmp / "verlauf.png")
        args += ["-loop", "1", "-t", f"{t:.3f}", "-i", str(tmp / "verlauf.png")]
        L0, L1 = rp.LISTE_START, rp.LISTE_ENDE
        fc = [f"[2:v]format=rgba,fade=t=in:st={L0}:d=0.25:alpha=1,fade=t=out:st={L1 - 0.25}:d=0.25:alpha=1[vl]",
              f"[0:v][vl]overlay=0:0:enable='between(t,{L0},{L1})'[d]"]
        elemente = list(rp.elemente(tmp))
        # Wissens-Pills (Nitrat) unten mittig, jeweils zum passenden Satz
        for j, (key, txt) in enumerate(v["pills"].items()):
            f = tmp / f"wissen{j}.png"
            pw, ph = rp.pill_png(f, txt, 54, bullet=False, fuellung=(18, 18, 18, 215))
            a, e = m[key]
            elemente.append((f, (W - pw) // 2, 1360, a + 0.1, e + 0.3, "links"))
        letzter = "d"
        for i, (png, xz, y, a, e, anim) in enumerate(elemente):
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
    (HIER / "reels" / f"pasta_vo2_{vname}_plan.json").write_text(
        json.dumps({"voice": m, "szenen": plan}, ensure_ascii=False, indent=2))
    print(aus, f"{t:.2f}s")


if __name__ == "__main__":
    for vn in sys.argv[1:] or ["v1", "v2", "v3"]:
        main(vn)
