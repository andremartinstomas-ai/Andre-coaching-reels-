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
    if not hook.get("sound"):
        fehler.append("Kein Audio-Hook (hook.sound).")
    elif not (SOUNDS / f"{hook['sound']}.wav").exists() and not Path(spec_dir, hook["sound"]).exists():
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
    W, H = BRAND["video"]["breite"], BRAND["video"]["hoehe"]
    f = BRAND["farben"]
    gr = BRAND["groessen"]
    schrift = BRAND["schrift"]["familie"]
    fett = -1 if BRAND["schrift"].get("fett", True) else 0
    weiss, gelb, teal = hex_ass(f["weiss"]), hex_ass(f["gelb"]), hex_ass(f["teal"])
    schatten = hex_ass(f["schatten"], 0x60)

    zeilen = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Hook,{schrift},{gr['hook']},{weiss},{weiss},&H00000000,{schatten},{fett},0,0,0,100,100,0,0,1,4,4,8,80,80,270,1",
        f"Style: Sub,{schrift},{gr['untertitel']},{weiss},{weiss},&H00000000,{schatten},{fett},0,0,0,100,100,0,0,1,5,3,2,90,90,560,1",
        f"Style: Info,{schrift},{gr['einblendung']},{weiss},{weiss},{teal},{schatten},{fett},0,0,0,100,100,0,0,3,18,0,5,90,90,0,1",
        f"Style: InfoOben,{schrift},{gr['einblendung']},{weiss},{weiss},{teal},{schatten},{fett},0,0,0,100,100,0,0,3,18,0,8,90,90,330,1",
        f"Style: Quelle,{schrift},{gr['quelle']},{weiss},{weiss},&H00000000,{schatten},0,1,0,0,100,100,0,0,1,2,1,2,90,90,420,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def ev(start, ende, stil, text, layer=1):
        zeilen.append(f"Dialogue: {layer},{ass_zeit(start)},{ass_zeit(ende)},{stil},,0,0,0,,{text}")

    # Text-Hook: Slam-Einblendung (gross -> normal), gelbe Hervorhebung mit *...*
    hook = spec["hook"]
    stil_anim = {
        "slam": "{\\fscx140\\fscy140\\t(0,160,\\fscx100\\fscy100)\\fad(40,200)}",
        "fade": "{\\fad(150,200)}",
        "pop": "{\\fscx80\\fscy80\\t(0,90,\\fscx108\\fscy108)\\t(90,180,\\fscx100\\fscy100)\\fad(30,200)}",
    }[hook.get("animation", "slam")]
    ev(0, hook.get("dauer", 3.0), "Hook", stil_anim + markup(hook["text"], gelb), layer=3)

    # Untertitel: Wortgruppen, aktives Wort gelb
    if spec.get("untertitel", True):
        woerter = woerter_auf_zeitachse(spec, spec_dir)
        for g in gruppen(woerter):
            for i, w in enumerate(g):
                ende = g[i + 1]["start"] if i + 1 < len(g) else max(w["ende"], g[-1]["ende"])
                teile = [(f"{{\\c{gelb}}}{x['text']}{{\\c{weiss}}}" if x is w else x["text"]) for x in g]
                ev(w["start"], ende, "Sub", " ".join(teile))
    for u in spec.get("untertitel_manuell", []):
        ev(u["start"], u["ende"], "Sub", "{\\fad(80,80)}" + markup(u["text"], gelb))

    # Einblendungen (Aufbau-Punkte, Payoff, Sicherheitssatz)
    for e in spec.get("einblendungen", []):
        stil = "InfoOben" if e.get("position") == "oben" else ("Sub" if e.get("position") == "unten" else "Info")
        ev(e["start"], e["ende"], stil, "{\\fad(120,120)}" + markup(e["text"], gelb), layer=2)

    q = spec.get("quelle_einblendung")
    if q:
        ev(q.get("start", 0), q.get("ende", dauer), "Quelle", "{\\fad(200,200)}" + markup(q["text"], gelb))

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

        verlauf_png(tmp / "oben.png", oben=True, staerke=0.75, anteil=0.42)
        verlauf_png(tmp / "unten.png", oben=False, staerke=0.55, anteil=0.4)
        ass_schreiben(spec, spec_dir, tmp / "text.ass", dauer)

        # Sounds: Hook-Sound bei t=0 (oder hook.sound_zeit) + optionale Effekte
        sounds = [{"name": spec["hook"]["sound"], "zeit": spec["hook"].get("sound_zeit", 0),
                   "lautstaerke": spec["hook"].get("sound_lautstaerke", 0.6)}] + spec.get("sounds", [])
        args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp / "roh.mp4"),
                "-i", str(tmp / "oben.png"), "-i", str(tmp / "unten.png")]
        for s in sounds:
            p = SOUNDS / f"{s['name']}.wav"
            args += ["-i", str(p if p.exists() else Path(spec_dir, s["name"]))]
        hd = spec["hook"].get("dauer", 3.0)
        ass = str(tmp / "text.ass").replace(":", "\\:")
        fc = [f"[0:v][1:v]overlay=0:0:enable='between(t,0,{hd + 0.3})'[v1]",
              "[v1][2:v]overlay=0:0[v2]",
              f"[v2]subtitles='{ass}':fontsdir='{FONTS}'[v]"]
        mix = ["[0:a]"]
        for i, s in enumerate(sounds):
            ms = int(float(s.get("zeit", 0)) * 1000)
            fc.append(f"[{3 + i}:a]aresample=48000,volume={s.get('lautstaerke', 0.6)},adelay={ms}|{ms}[s{i}]")
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
         f"- Audio-Hook: {h['sound']}" + (f" ({h['sound_hinweis']})" if h.get("sound_hinweis") else ""),
         f"- Visueller Hook: {h['visuell']}",
         f"- Text-Hook: {h['text'].replace('*', '').replace(chr(10), ' ')}", "",
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
