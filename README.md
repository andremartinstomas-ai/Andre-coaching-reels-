# Andre Coaching Reels

Werkzeug, mit dem Claude aus Andrés Rohmaterial (Sprechvideos und Übungsclips) fertige Instagram-Reels baut:
- Hook, Aufbau und Payoff in jedem Reel
- drei Hooks gleichzeitig in den ersten 3 Sekunden (Audio, Bild, Text)
- jede inhaltliche Aussage mit Quelle belegt
- Markenstil Teal, Gelb und Weiß, 1080x1920, -14 LUFS

## So benutzt du es
1. Neue Claude-Session auf diesem Repo starten.
2. Rohvideos hochladen und z. B. schreiben: „Mach aus diesen Videos Reels.“
3. Claude zeigt dir zuerst die Kandidatenliste (Aussagen, Quellen, Hook-Ideen). Du gibst frei.
4. Du bekommst pro Reel: MP4, Cover-Bild und Textdatei (Caption, Hashtags, Hooks, Quellen).

Der komplette Arbeitsablauf für Claude steht in `CLAUDE.md`.

## Aufbau
| Pfad | Inhalt |
|---|---|
| `CLAUDE.md` | Arbeitsablauf und feste Regeln |
| `docs/skript-regeln.md` | Hook, Aufbau, Payoff, Sprache, Längen |
| `docs/faktencheck.md` | Quelle pro Aussage: Ablauf und Evidenzstufen |
| `docs/quellen.md` | Leitlinien und Reviews als Startpunkt |
| `config/brand.json` | Farben, Schrift, Größen |
| `templates/reel_spec.example.json` | Vorlage für ein Reel |
| `scripts/probe.py` | Rohmaterial analysieren (Pausen, Szenenwechsel) |
| `scripts/transcribe.py` | Transkript mit Wort-Zeitstempeln (Whisper oder ElevenLabs) |
| `scripts/hook_sounds.py` | synthetische, lizenzfreie Hook-Sounds |
| `scripts/render_reel.py` | Regelprüfung und Rendering |
| `tests/make_test_media.py` | Testmaterial für einen Probelauf |

## Voraussetzungen
ffmpeg, Python 3 mit `numpy` und `Pillow` (`pip install -r requirements.txt`).
