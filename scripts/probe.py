#!/usr/bin/env python3
"""Analysiert Rohmaterial: Dauer, Aufloesung, Drehung, Ton, Pausen und Schnittwechsel.

Aufruf: python3 scripts/probe.py roh/*.mp4 [-o analyse.json]
Die Pausen (silencedetect) helfen, Fuellwoerter/Denkpausen herauszuschneiden.
"""
import argparse
import json
import re
import subprocess
import sys


def ffprobe(pfad):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", pfad],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def drehung(stream):
    for sd in stream.get("side_data_list", []):
        if "rotation" in sd:
            return int(sd["rotation"])
    return int(stream.get("tags", {}).get("rotate", 0))


def pausen(pfad, schwelle_db=-35, min_sek=0.4):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", pfad, "-af",
         f"silencedetect=noise={schwelle_db}dB:d={min_sek}", "-vn", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return [{"start": round(s, 2), "ende": round(e, 2)} for s, e in zip(starts, ends)]


def szenenwechsel(pfad, schwelle=0.35):
    err = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", pfad, "-vf",
         f"select='gt(scene,{schwelle})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    return [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", err)]


def analysiere(pfad, mit_szenen=True):
    info = ffprobe(pfad)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    erg = {"datei": pfad, "dauer": round(float(info["format"]["duration"]), 2), "ton": a is not None}
    if v:
        rot = drehung(v)
        b, h = v["width"], v["height"]
        if abs(rot) in (90, 270):
            b, h = h, b
        num, den = v.get("avg_frame_rate", "30/1").split("/")
        erg.update({"breite": b, "hoehe": h, "drehung": rot,
                    "fps": round(float(num) / float(den or 1), 2),
                    "format": "hochkant" if h > b else "quer"})
    if a:
        erg["pausen"] = pausen(pfad)
    if mit_szenen and v:
        erg["szenenwechsel"] = szenenwechsel(pfad)
    return erg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dateien", nargs="+")
    ap.add_argument("-o", "--ausgabe")
    ap.add_argument("--ohne-szenen", action="store_true")
    a = ap.parse_args()
    erg = [analysiere(p, not a.ohne_szenen) for p in a.dateien]
    txt = json.dumps(erg, indent=2, ensure_ascii=False)
    if a.ausgabe:
        open(a.ausgabe, "w").write(txt)
    print(txt if not a.ausgabe else f"geschrieben: {a.ausgabe}", file=sys.stdout)


if __name__ == "__main__":
    main()
