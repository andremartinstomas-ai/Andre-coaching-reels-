#!/usr/bin/env python3
"""Rendert ein fertiges Instagram-Reel (1080x1920) aus einer Reel-Spec (JSON).

  python3 scripts/render_reel.py projekte/<projekt>/specs/01_xyz.json
  python3 scripts/render_reel.py spec.json --nur-pruefen     # nur Regelpruefung
  python3 scripts/render_reel.py spec.json --vorschau        # schneller, niedrige Qualitaet

Vor dem Rendern prueft das Skript Andres feste Regeln (Hook, Aufbau, Payoff, Quelle pro Aussage,
keine Heilversprechen, 5 Hashtags, Speichern-Aufruf, Sicherheitssatz bei Uebungen) und bricht bei
Verstoessen ab. Aufbau der Spec: siehe templates/reel_spec.example.json.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "config" / "brand.json").read_text())
SOUNDS = ROOT / "assets" / "sounds"
FONTS = ROOT / "fonts"

VERBOTEN = [r"schmerzfrei", r"\bheilt\b", r"heilung garantiert", r"garantiert", r"nie wieder schmerz",
            r"f[üu]r immer weg", r"wunder", r"100\s?%", r"sofort weg"]
SICHERHEITSSATZ = "wenn etwas wehtut"


# ------------------------------------------------------------------ Helfer
def sh(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg-Fehler:\n{' '.join(map(str, args))}\n{r.stderr[-2500:]}")
    return r


def probe(pfad):
    info = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(pfad)]).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    rot = rot or int(v.get("tags", {}).get("rotate", 0))
    b, h = v["width"], v["height"]
    if abs(rot) in (90, 270):
        b, h = h, b
    hat_ton = any(s["codec_type"] == "audio" for s in info["streams"])
    return b, h, hat_ton


def hex_ass(hexfarbe, alpha=0):
    h = hexfarbe.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_zeit(s):
    s = max(0, s)
    h, rest = divmod(s, 3600)
    m, sek = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{sek:05.2f}"


_FONT_CACHE = {}


def textbreite(text, groesse):
    """Breite in Pixeln fuer die Markenschrift (gemessen mit fontTools, Grossbuchstaben)."""
    if "font" not in _FONT_CACHE:
        from fontTools.ttLib import TTFont
        datei = next((f for f in FONTS.glob("*.[ot]tf")
                      if TTFont(f)["name"].getDebugName(1) == BRAND["schrift"]["familie"]), None)
        if datei is None:
            return len(text) * groesse * 0.45
        ft = TTFont(datei)
        # libass skaliert die Schriftgroesse auf winAscent+winDescent, nicht auf unitsPerEm
        _FONT_CACHE["font"] = (ft.getBestCmap(), ft["hmtx"], ft["OS/2"].usWinAscent + ft["OS/2"].usWinDescent)
    cmap, hmtx, upm = _FONT_CACHE["font"]
    breite = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm * 0.4 for c in text.replace("*", "").upper())
    return breite / upm * groesse


def passende_groesse(zeilen, max_groesse, max_breite, fett=False):
    faktor = 1.04 if fett else 1.0
    breitest = max(textbreite(z, 100) * faktor for z in zeilen) or 1
    return min(max_groesse, int(max_breite / breitest * 100))


def markup(text, gelb):
    """*wort* -> gelb hervorgehoben; \\n -> Zeilenumbruch."""
    text = text.replace("{", "(").replace("}", ")").replace("\n", "\\N")
    return re.sub(r"\*(.+?)\*", lambda m: f"{{\\c{gelb}}}{m.group(1)}{{\\c&H00FFFFFF&}}", text)


# ------------------------------------------------------------------ Regelpruefung
def pruefe(spec, spec_dir):
    fehler, warn = [], []
    hook = spec.get("hook", {})
    if not hook.get("text"):
        fehler.append("Kein Text-Hook (hook.text).")
    if hook.get("sound") and not (SOUNDS / f"{hook['sound']}.wav").exists() and not Path(spec_dir, hook["sound"]).exists():
        fehler.append(f"Hook-Sound '{hook['sound']}' nicht gefunden (python3 scripts/hook_sounds.py ausfuehren).")
    if not hook.get("visuell"):
        fehler.append("Visueller Hook nicht beschrieben (hook.visuell).")
    if hook.get("dauer", 3) > 3.5:
        fehler.append("Hook-Text muss in den ersten ~3 Sekunden wirken (hook.dauer <= 3.5).")

    skript = spec.get("skript", {})
    for teil in ("hook", "aufbau", "payoff"):
        if not skript.get(teil):
            fehler.append(f"Skript unvollstaendig: skript.{teil} fehlt.")

    aussagen = spec.get("aussagen", [])
    if not aussagen:
        fehler.append("Keine Aussagen gelistet. Jede inhaltliche Aussage muss mit Quelle in 'aussagen' stehen.")
    for i, a in enumerate(aussagen):
        if not a.get("quelle"):
            fehler.append(f"Aussage {i + 1} ohne Quelle: \"{a.get('text', '')[:60]}\"")
        if a.get("status") not in ("belegt", "konsens"):
            fehler.append(f"Aussage {i + 1} nicht als 'belegt'/'konsens' markiert (status={a.get('status')}).")

    alle_texte = " ".join([hook.get("text", ""), spec.get("caption", ""),
                           *[e.get("text", "") for e in spec.get("einblendungen", []) + spec.get("untertitel_manuell", [])]]).lower()
    for muster in VERBOTEN:
        if re.search(muster, alle_texte):
            fehler.append(f"Heilversprechen/Uebertreibung gefunden: '{muster}'.")

    tags = spec.get("hashtags", [])
    if len(tags) != 5:
        fehler.append(f"Genau 5 Hashtags noetig (sind {len(tags)}).")
    if "speicher" not in spec.get("caption", "").lower():
        fehler.append("Caption braucht einen Speichern-Aufruf.")
    if spec.get("uebung") and SICHERHEITSSATZ not in alle_texte:
        fehler.append("Uebungs-Reel ohne Sicherheitssatz ('Wenn etwas wehtut, nicht tiefer in die Bewegung gehen.').")

    dauer = sum(s["ende"] - s["start"] for s in spec.get("segmente", []))
    if not spec.get("segmente"):
        fehler.append("Keine Segmente.")
    elif dauer > 90:
        fehler.append(f"Reel zu lang ({dauer:.1f}s > 90s).")
    elif dauer < 6:
        warn.append(f"Reel sehr kurz ({dauer:.1f}s).")
    for s in spec.get("segmente", []):
        if not Path(spec_dir, s["quelle"]).exists():
            fehler.append(f"Quelle fehlt: {s['quelle']}")
        if s["ende"] <= s["start"]:
            fehler.append(f"Segment mit ende <= start: {s}")
    if len(spec.get("caption", "")) > 600:
        warn.append("Caption ist lang; kurz halten.")
    return fehler, warn, dauer


# ------------------------------------------------------------------ Video-Bausteine
def segment_rendern(seg, idx, spec, spec_dir, tmp, punch_in, qualitaet):
    W, H, FPS = BRAND["video"]["breite"], BRAND["video"]["hoehe"], BRAND["video"]["fps"]
    quelle = Path(spec_dir, seg["quelle"])
    ib, ih, hat_ton = probe(quelle)
    z = float(seg.get("zoom", 1.0))
    s = max(W / ib, H / ih) * z
    bw, bh = ib * s, ih * s
    fx, fy = float(seg.get("fokus_x", 0.5)), float(seg.get("fokus_y", 0.5))
    if punch_in:
        p = "(1+0.18*max(0\\,1-t/0.5))"
        vf = (f"scale=w='trunc({bw:.1f}*{p}/2)*2':h='trunc({bh:.1f}*{p}/2)*2':eval=frame,"
              f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}")
    else:
        vf = f"scale={int(bw / 2) * 2 + 2}:{int(bh / 2) * 2 + 2},crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}"
    if seg.get("filter"):  # z. B. Helligkeit: "eq=brightness=0.05:gamma=1.15"
        vf += "," + seg["filter"]
    if seg.get("geschwindigkeit"):
        vf += f",setpts=PTS/{seg['geschwindigkeit']}"
    vf += f",fps={FPS},setsar=1,format=yuv420p"
    dauer = (seg["ende"] - seg["start"]) / float(seg.get("geschwindigkeit", 1))

    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{seg['start']}", "-to", f"{seg['ende']}", "-i", str(quelle)]
    nutze_ton = seg.get("ton", True) and hat_ton
    if not nutze_ton:
        args += ["-f", "lavfi", "-t", f"{dauer}", "-i", "anullsrc=r=48000:cl=stereo"]
    af = (f"volume={seg.get('lautstaerke', 1.0)},afade=t=in:d=0.015,"
          f"afade=t=out:st={max(0, dauer - 0.02):.3f}:d=0.02,aresample=48000")
    if seg.get("geschwindigkeit"):
        af = f"atempo={seg['geschwindigkeit']}," + af
    args += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0" if nutze_ton else "1:a:0"]
    if nutze_ton:
        args += ["-af", af]
    args += ["-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
             "-c:v", "libx264", "-preset", qualitaet["preset"], "-crf", qualitaet["crf"],
             "-t", f"{dauer}", str(tmp / f"seg_{idx:02d}.mp4")]
    sh(args)
    return dauer


def abdunkeln_png(pfad, staerke):
    W, H = BRAND["video"]["breite"], BRAND["video"]["hoehe"]
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = int(staerke * 255)
    Image.fromarray(rgba, "RGBA").save(pfad)


def verlauf_png(pfad, oben=True, staerke=0.7, anteil=0.45):
    W, H = BRAND["video"]["breite"], BRAND["video"]["hoehe"]
    y = np.linspace(0, 1, H)
    a = np.clip(1 - y / anteil, 0, 1) if oben else np.clip((y - (1 - anteil)) / anteil, 0, 1)
    a = (a ** 1.6 * staerke * 255).astype(np.uint8)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = a[:, None]
    Image.fromarray(rgba, "RGBA").save(pfad)


# ------------------------------------------------------------------ Untertitel
def woerter_auf_zeitachse(spec, spec_dir):
    """Mappt Transkript-Woerter jedes Segments auf die Reel-Zeitachse."""
    korrektur = spec.get("untertitel_korrekturen", {})
    out, offset = [], 0.0
    for seg in spec["segmente"]:
        speed = float(seg.get("geschwindigkeit", 1))
        if seg.get("transkript") and seg.get("ton", True):
            tr = json.loads(Path(spec_dir, seg["transkript"]).read_text())
            for w in tr["woerter"]:
                mitte = (w["start"] + w["ende"]) / 2
                if seg["start"] <= mitte < seg["ende"]:
                    text = korrektur.get(w["text"], w["text"])
                    out.append({"text": text,
                                "start": offset + (max(w["start"], seg["start"]) - seg["start"]) / speed,
                                "ende": offset + (min(w["ende"], seg["ende"]) - seg["start"]) / speed})
        offset += (seg["ende"] - seg["start"]) / speed
    return out


def gruppen(woerter, max_w=3, max_zeichen=22):
    gr, akt = [], []
    for i, w in enumerate(woerter):
        akt.append(w)
        nxt = woerter[i + 1] if i + 1 < len(woerter) else None
        zeichen = sum(len(x["text"]) + 1 for x in akt)
        if (not nxt or len(akt) >= max_w or zeichen >= max_zeichen or w["text"].endswith((".", "!", "?", ",", ":"))
                or nxt["start"] - w["ende"] > 0.45):
            gr.append(akt)
            akt = []
    return gr


def ass_schreiben(spec, spec_dir, pfad, dauer):
    """Textlayer im Stil von Andres Vorlage: Bebas Neue, Grossbuchstaben, Weiss/Gelb mit dunkler Kontur,
    Fortschrittsbalken oben, Kapitel-Label rechts ('UEBUNG 1 VON 3' + gelbe Linie + Uebungsname)."""
    W, H = BRAND["video"]["breite"], BRAND["video"]["hoehe"]
    f, gr = BRAND["farben"], BRAND["groessen"]
    schrift = BRAND["schrift"]["familie"]
    weiss, gelb = hex_ass(f["weiss"]), hex_ass(f["gelb"])
    teal = hex_ass(f.get("teal_dunkel", f["teal"]))
    kontur = hex_ass(f.get("kontur", "#141414"))
    rechts = W - BRAND["layout"]["rand"]
    links = BRAND["layout"]["rand"]

    def style(name, groesse, farbe, outline, align, margin_v=0, kontur_farbe=kontur):
        fett = -1 if name in BRAND["schrift"].get("fett_stile", []) else 0
        return (f"Style: {name},{schrift},{groesse},{farbe},{farbe},{kontur_farbe},&H80000000,{fett},0,0,0,100,100,1,0,"
                f"1,{outline},0,{align},60,60,{margin_v},1")

    zeilen = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        style("Hook", gr["hook"], weiss, 5, 5),
        style("HookUnter", gr["hook_unterzeile"], weiss, 3, 8),
        style("Fakt", gr["fakt"], weiss, 4, 8),
        style("Label", gr["label"], teal, 3, 9, kontur_farbe=weiss),
        style("Titel", gr["titel"], gelb, 4, 9),
        style("Info", gr["info"], weiss, 3, 9),
        style("Sub", gr["untertitel"], weiss, 5, 2, BRAND["layout"]["untertitel_abstand"]),
        style("Quelle", gr["quelle"], weiss, 2, 2, BRAND["layout"]["quelle_abstand"]),
        f"Style: Form,{schrift},20,{weiss},{weiss},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def ev(start, ende, stil, text, layer=1):
        zeilen.append(f"Dialogue: {layer},{ass_zeit(start)},{ass_zeit(ende)},{stil},,0,0,0,,{text}")

    def text(t):
        return markup(t.upper(), gelb)

    def zeilen_block(a, e, stil, roh, x, y, an, groesse, extra="", layer=3, abstand=0.86):
        """Setzt jede Zeile einzeln mit engem Zeilenabstand (Bebas hat grosse Standard-Zeilenhoehe).
        Gibt die y-Position unter dem Block zurueck."""
        for i, zeile in enumerate(roh.split("\n")):
            ev(a, e, stil, f"{{\\an{an}\\pos({x:.0f},{y + i * groesse * abstand:.0f}){extra}}}" + text(zeile), layer)
        return y + len(roh.split("\n")) * groesse * abstand

    def rechteck(x, y, b, h, farbe, alpha=0):
        return (f"{{\\an7\\pos({x:.0f},{y:.0f})\\c{farbe}\\alpha&H{alpha:02X}&\\bord0\\shad0\\p1}}"
                f"m 0 0 l {b:.0f} 0 {b:.0f} {h} 0 {h}{{\\p0}}")

    # --- Hook: mittig, Hauptzeilen gross (Weiss, *Gelb*), Unterzeile klein
    hook = spec["hook"]
    hd = hook.get("dauer", 3.0)
    anim = {"slam": "\\fscx118\\fscy118\\t(0,140,\\fscx100\\fscy100)\\fad(60,120)",
            "fade": "\\fad(150,150)",
            "pop": "\\fscx85\\fscy85\\t(0,100,\\fscx105\\fscy105)\\t(100,180,\\fscx100\\fscy100)\\fad(40,120)"}[
        hook.get("animation", "slam")]
    zeilen_hook = hook["text"].split("\n")
    hg = passende_groesse(zeilen_hook, gr["hook"], W - 2 * BRAND["layout"]["rand"], fett=True)
    hoehe = len(zeilen_hook) * hg * 0.86 + (gr["hook_unterzeile"] * 1.1 if hook.get("unterzeile") else 0)
    y0 = BRAND["layout"]["hook_y"] - hoehe / 2
    y = zeilen_block(0, hd, "Hook", hook["text"], W // 2, y0, 8, hg, anim + f"\\fs{hg}", layer=5)
    if hook.get("unterzeile"):
        zeilen_block(0, hd, "HookUnter", hook["unterzeile"], W // 2, y + 28, 8, gr["hook_unterzeile"], anim, layer=5)

    # --- Fakten (Aufbau) mittig oben, Quelle klein darunter
    for e in spec.get("einblendungen", []):
        fg = passende_groesse(e["text"].split("\n"), gr["fakt"], W - 2 * BRAND["layout"]["rand"], fett=True)
        zeilen_block(e["start"], e["ende"], "Fakt", e["text"], W // 2, BRAND["layout"]["fakt_y"], 8, fg,
                     f"\\fad(120,120)\\fs{fg}", layer=4)
    q = spec.get("quelle_einblendung")
    if q:
        ev(q.get("start", 0), q.get("ende", dauer), "Quelle", "{\\fad(150,150)}" + markup(q["text"], gelb))

    # --- Kapitel: Fortschrittsbalken + Label/Linie/Titel/Info rechts oben
    kapitel = spec.get("kapitel", [])
    mit_balken = [k for k in kapitel if k.get("fortschritt", True)]
    if mit_balken:
        n, by, bh, gap = len(mit_balken), BRAND["layout"]["balken_y"], 8, 14
        bb = (rechts - links - gap * (n - 1)) / n
        for i, k in enumerate(mit_balken):
            x = links + i * (bb + gap)
            ev(0, dauer, "Form", rechteck(x, by, bb, bh, weiss, 0x50), layer=1)
            d = int((k["ende"] - k["start"]) * 1000)
            ev(k["start"], k["ende"], "Form",
               rechteck(x, by, bb, bh, gelb).replace("\\p1}", f"\\fscx0\\t(0,{d},\\fscx100)\\p1}}"), layer=2)
            ev(k["ende"], dauer, "Form", rechteck(x, by, bb, bh, gelb), layer=2)
    ly = BRAND["layout"]["label_y"]
    for k in kapitel:
        a, e = k["start"], k["ende"]
        fad = "\\fad(120,100)"
        if k.get("label"):
            ev(a, e, "Label", f"{{\\an9\\pos({rechts},{ly}){fad}}}" + text(k["label"]), layer=3)
        linie_y = ly + gr["label"] * 0.95
        ev(a, e, "Form", rechteck(rechts - BRAND["layout"]["linie_breite"], linie_y, BRAND["layout"]["linie_breite"],
                                  6, gelb).replace("\\p1}", f"{fad}\\p1}}"), layer=3)
        titel_y = linie_y + 16
        tg = passende_groesse(k["titel"].split("\n"), gr["titel"], rechts - links, fett=True)
        unter = zeilen_block(a, e, "Titel", k["titel"], rechts, titel_y, 9, tg, fad + f"\\fs{tg}")
        if k.get("info"):
            zeilen_block(a, e, "Info", k["info"], rechts, unter + 6, 9, gr["info"], fad)

    # --- Untertitel (Sprechvideos): Wortgruppen, aktives Wort gelb
    if spec.get("untertitel", True):
        woerter = woerter_auf_zeitachse(spec, spec_dir)
        for g in gruppen(woerter):
            for i, w in enumerate(g):
                ende = g[i + 1]["start"] if i + 1 < len(g) else max(w["ende"], g[-1]["ende"])
                teile = [(f"{{\\c{gelb}}}{x['text'].upper()}{{\\c{weiss}}}" if x is w else x["text"].upper()) for x in g]
                ev(w["start"], ende, "Sub", " ".join(teile))
    for u in spec.get("untertitel_manuell", []):
        gross = f"\\fs{u['groesse']}" if u.get("groesse") else ""
        ev(u["start"], u["ende"], "Sub", f"{{\\fad(100,100){gross}}}" + text(u["text"]))

    Path(pfad).write_text("\n".join(zeilen) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ Hauptablauf
def rendern(spec_pfad, vorschau=False):
    spec_pfad = Path(spec_pfad)
    spec = json.loads(spec_pfad.read_text())
    spec_dir = spec_pfad.parent
    qualitaet = {"preset": "veryfast", "crf": "28"} if vorschau else {"preset": "slow", "crf": "18"}
    ausgabe = Path(spec_dir, spec["ausgabe"])
    ausgabe.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dauer = 0.0
        for i, seg in enumerate(spec["segmente"]):
            dauer += segment_rendern(seg, i, spec, spec_dir, tmp, i == 0 and spec["hook"].get("punch_in", True), qualitaet)
        liste = tmp / "liste.txt"
        liste.write_text("".join(f"file 'seg_{i:02d}.mp4'\n" for i in range(len(spec["segmente"]))))
        sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(liste), "-c", "copy", str(tmp / "roh.mp4")])

        abdunkeln_png(tmp / "dunkel.png", BRAND["layout"]["abdunkeln"])
        verlauf_png(tmp / "unten.png", oben=False, staerke=0.5, anteil=0.4)
        ass_schreiben(spec, spec_dir, tmp / "text.ass", dauer)

        # Sounds nur wenn explizit gewuenscht (Andre: keine Soundeffekte als Standard)
        sounds = list(spec.get("sounds", []))
        if spec["hook"].get("sound"):
            sounds.insert(0, {"name": spec["hook"]["sound"], "zeit": spec["hook"].get("sound_zeit", 0),
                              "lautstaerke": spec["hook"].get("sound_lautstaerke", 0.6)})
        args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp / "roh.mp4"),
                "-i", str(tmp / "dunkel.png"), "-i", str(tmp / "unten.png")]
        for snd in sounds:
            p = SOUNDS / f"{snd['name']}.wav"
            args += ["-i", str(p if p.exists() else Path(spec_dir, snd["name"]))]
        hd = spec["hook"].get("dauer", 3.0)
        dunkel_zeiten = [(0, hd)] + [(e["start"], e["ende"]) for e in spec.get("einblendungen", [])]
        enable = "+".join(f"between(t,{a},{b})" for a, b in dunkel_zeiten)
        ass = str(tmp / "text.ass").replace(":", "\\:")
        unten = "[v1][2:v]overlay=0:0[v2]" if spec.get("untertitel", True) or spec.get("untertitel_manuell") \
            else "[v1]null[v2]"
        look = BRAND.get("look", {})
        look_an = spec.get("look", look.get("aktiv", False))
        look_filter = look.get("filter", "null") if look_an else "null"
        fc = [f"[0:v]{look_filter}[v0]", f"[v0][1:v]overlay=0:0:enable='{enable}'[v1]", unten,
              f"[v2]subtitles='{ass}':fontsdir='{FONTS}'[v]"]
        mix = ["[0:a]"]
        for i, snd in enumerate(sounds):
            ms = int(float(snd.get("zeit", 0)) * 1000)
            fc.append(f"[{3 + i}:a]aresample=48000,volume={snd.get('lautstaerke', 0.6)},adelay={ms}|{ms}[s{i}]")
            mix.append(f"[s{i}]")
        lufs = BRAND["video"]["lautheit_lufs"]
        fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,"
                  f"loudnorm=I={lufs}:TP=-1.5:LRA=11:linear=true,aresample=48000[a]")
        args += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
                 "-c:v", "libx264", "-preset", qualitaet["preset"], "-crf", qualitaet["crf"],
                 "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(ausgabe)]
        sh(args)
        shutil.copy(tmp / "text.ass", ausgabe.with_suffix(".ass"))
        lautheit_angleichen(ausgabe, lufs, tmp)

    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{min(1.0, dauer / 2)}", "-i", str(ausgabe),
        "-frames:v", "1", "-q:v", "2", str(ausgabe.with_suffix(".cover.jpg"))])
    begleittext_schreiben(spec, ausgabe, dauer)
    return ausgabe, dauer


def lautheit_messen(pfad):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad), "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    peaks = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    return i, float(peaks[-1]) if peaks and peaks[-1] != "-inf" else -99.0


def lautheit_angleichen(pfad, ziel, tmp):
    """loudnorm im Einzeldurchlauf landet bei kurzen Clips oft 2-3 LU zu leise -> nachmessen und Gain anpassen."""
    ist, _ = lautheit_messen(pfad)
    if ist < -60:  # (fast) stille Tonspur -> nichts anheben
        return
    gain = min(ziel - ist, 10.0)  # Spitzen faengt der Limiter ab (-1 dBFS)
    if abs(gain) < 0.5:
        return
    zw = tmp / "laut.mp4"
    sh(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(pfad), "-c:v", "copy",
        "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:level=false", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(zw)])
    shutil.move(zw, pfad)


def begleittext_schreiben(spec, ausgabe, dauer):
    h = spec["hook"]
    z = [f"# {spec.get('titel', ausgabe.stem)}  ({dauer:.1f} s)", "",
         "## Caption (zum Posten)", spec["caption"].strip(), "", " ".join(spec["hashtags"]), "",
         "## Hooks",
         "- Audio-Hook: " + (h.get("sound") or h.get("sound_hinweis") or "kein Soundeffekt, Trend-Sound in Instagram darunterlegen"),
         f"- Visueller Hook: {h['visuell']}",
         f"- Text-Hook: {h['text'].replace('*', '').replace(chr(10), ' ')}" + (f" / {h['unterzeile']}" if h.get("unterzeile") else ""), "",
         "## Skript",
         f"- Hook: {spec['skript']['hook']}", f"- Aufbau: {spec['skript']['aufbau']}",
         f"- Payoff: {spec['skript']['payoff']}", "",
         "## Aussagen & Quellen"]
    for a in spec["aussagen"]:
        z.append(f"- \"{a['text']}\" -> {a['quelle']} [{a['status']}]" + (f" - {a['beleg']}" if a.get("beleg") else ""))
    if spec.get("hinweise"):
        z += ["", "## Hinweise fuer Andre", *[f"- {x}" for x in spec["hinweise"]]]
    ausgabe.with_suffix(".txt").write_text("\n".join(z) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--nur-pruefen", action="store_true")
    ap.add_argument("--vorschau", action="store_true")
    a = ap.parse_args()
    fehlgeschlagen = 0
    for sp in a.specs:
        spec = json.loads(Path(sp).read_text())
        fehler, warn, dauer = pruefe(spec, Path(sp).parent)
        print(f"\n== {sp}  ({dauer:.1f}s)")
        for w in warn:
            print(f"  WARNUNG: {w}")
        for f in fehler:
            print(f"  FEHLER:  {f}")
        if fehler:
            fehlgeschlagen += 1
            continue
        if a.nur_pruefen:
            print("  OK - alle Regeln erfuellt")
            continue
        out, d = rendern(sp, a.vorschau)
        print(f"  -> {out} ({d:.1f}s) + .txt + .cover.jpg")
    sys.exit(1 if fehlgeschlagen else 0)


if __name__ == "__main__":
    main()
