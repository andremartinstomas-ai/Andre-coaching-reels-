#!/usr/bin/env python3
"""Transkription mit Wort-Zeitstempeln -> einheitliches transcript.json.

Wege (in dieser Reihenfolge):
 1. faster-whisper lokal (nur wenn das Modell geladen werden kann; in der Cloud-Sandbox ist HuggingFace oft gesperrt)
 2. ElevenLabs Scribe ueber das verbundene MCP (creative_transcribe_audio). Dafuer erzeugt dieses Skript
    mit --nur-audio eine kompakte MP3. Das Ergebnis-JSON danach mit --import normalisieren.

Aufrufe:
  python3 scripts/transcribe.py roh/video.mp4 -o projekt/transkripte/video.json
  python3 scripts/transcribe.py roh/video.mp4 --nur-audio            # -> roh/video.mp3 zum Hochladen
  python3 scripts/transcribe.py roh/video.mp4 --import scribe.json -o projekt/transkripte/video.json

Ausgabeformat:
  {"datei": ..., "sprache": "de", "woerter": [{"text","start","ende"}], "saetze": [{"text","start","ende"}]}
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SATZENDE = (".", "!", "?", "…")


def audio_extrahieren(video, ziel, mp3=True):
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1"]
    args += (["-ar", "44100", "-b:a", "96k", str(ziel)] if mp3 else ["-ar", "16000", str(ziel)])
    subprocess.run(args, check=True)
    return ziel


def saetze_bilden(woerter, max_pause=0.8):
    saetze, aktuell = [], []
    for i, w in enumerate(woerter):
        aktuell.append(w)
        naechstes = woerter[i + 1] if i + 1 < len(woerter) else None
        pause = (naechstes["start"] - w["ende"]) if naechstes else 99
        if w["text"].rstrip().endswith(SATZENDE) or pause > max_pause:
            saetze.append({"text": " ".join(x["text"] for x in aktuell).strip(),
                           "start": aktuell[0]["start"], "ende": aktuell[-1]["ende"]})
            aktuell = []
    return saetze


def normalisieren(daten, datei):
    """Akzeptiert ElevenLabs-Scribe- und Whisper-artige JSONs."""
    woerter = []
    if isinstance(daten, dict) and "words" in daten:  # ElevenLabs Scribe
        for w in daten["words"]:
            if w.get("type", "word") != "word":
                continue
            woerter.append({"text": w["text"].strip(), "start": float(w["start"]), "ende": float(w["end"])})
        sprache = daten.get("language_code", "de")
    elif isinstance(daten, dict) and "segments" in daten:  # Whisper
        for seg in daten["segments"]:
            for w in seg.get("words", []):
                woerter.append({"text": w["word"].strip(), "start": float(w["start"]), "ende": float(w["end"])})
        sprache = daten.get("language", "de")
    elif isinstance(daten, dict) and "woerter" in daten:  # schon unser Format
        woerter, sprache = daten["woerter"], daten.get("sprache", "de")
    else:
        sys.exit("Unbekanntes Transkript-Format: erwartet 'words' (Scribe) oder 'segments' (Whisper).")
    woerter = [w for w in woerter if w["text"]]
    return {"datei": str(datei), "sprache": sprache, "woerter": woerter, "saetze": saetze_bilden(woerter)}


def whisper(video, modell):
    from faster_whisper import WhisperModel  # noqa: import nur wenn gebraucht
    m = WhisperModel(modell, device="cpu", compute_type="int8")
    # Audio selbst per ffmpeg dekodieren (PyAV-Versionen kollidieren gern mit faster-whisper)
    import numpy as np
    roh = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(roh, np.int16).astype(np.float32) / 32768
    segs, info = m.transcribe(audio, language="de", word_timestamps=True, vad_filter=False,
                              initial_prompt="Physiotherapie, MRT, Bandscheibe, Bandscheibenvorfall, Rückenschmerzen.")
    woerter = [{"text": w.word.strip(), "start": w.start, "ende": w.end} for s in segs for w in s.words]
    return {"woerter": woerter, "sprache": info.language}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--ausgabe")
    ap.add_argument("--nur-audio", action="store_true", help="nur MP3 fuer ElevenLabs erzeugen")
    ap.add_argument("--import", dest="import_json", help="vorhandenes Scribe/Whisper-JSON normalisieren")
    ap.add_argument("--modell", default="small")
    a = ap.parse_args()
    video = Path(a.video)

    if a.nur_audio:
        print(audio_extrahieren(video, video.with_suffix(".mp3")))
        return

    if a.import_json:
        roh = json.load(open(a.import_json))
    else:
        try:
            roh = whisper(video, a.modell)
        except Exception as e:  # Modell nicht ladbar -> ElevenLabs-Weg
            mp3 = audio_extrahieren(video, video.with_suffix(".mp3"))
            sys.exit(f"Whisper nicht verfuegbar ({type(e).__name__}). MP3 liegt bereit: {mp3}\n"
                     "-> mit ElevenLabs creative_transcribe_audio transkribieren, dann --import nutzen.")

    erg = normalisieren(roh, video)
    ziel = Path(a.ausgabe or video.with_suffix(".transcript.json"))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(erg, indent=1, ensure_ascii=False))
    print(f"{ziel}: {len(erg['woerter'])} Woerter, {len(erg['saetze'])} Saetze")


if __name__ == "__main__":
    main()
