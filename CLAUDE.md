# Reel-Werkstatt für André (@andrephysio)

André ist Physiotherapeut und Schmerztherapeut mit Online-Coaching. Dieses Repo macht aus seinem Rohmaterial
(Sprechvideos + Übungsclips) **so viele hochwertige Instagram-Reels wie das Material hergibt**, jedes mit Hook,
Aufbau und Payoff, und jede inhaltliche Aussage mit Quelle belegt.

Arbeitssprache mit André: Deutsch, locker, direkt. Kein KI-Deutsch.

## Grundsätze (nicht verhandelbar)

1. **Qualität vor Menge.** „So viele wie möglich“ heißt: so viele wie es *gute* Aussagen gibt. Lieber 3 starke
   Reels als 8 mittelmäßige. Material, das kein Reel trägt, wird nicht künstlich gestreckt.
2. **Kein Gelaber.** Raus kommt alles ohne inhaltlichen Wert: Begrüßungen, „ähm“, Wiederholungen,
   Anlauf-Sätze („Also, ich wollte heute mal…“), Abschweifungen, Versprecher, Denkpausen über ~0,4 s.
3. **Jede inhaltliche Aussage ist identifiziert und belegt.** Jede Aussage im Reel, ob gesprochen, eingeblendet
   oder in der Caption, steht in `aussagen` mit Quelle und Status `belegt` oder `konsens`. Was sich nicht belegen
   lässt, wird gestrichen oder vorsichtiger formuliert. Nie eine Quelle erfinden. Details: `docs/faktencheck.md`.
4. **Hook → Aufbau → Payoff.** Jedes Reel hat einen Spannungsbogen, bei dem sich das Dranbleiben lohnt.
   Details: `docs/skript-regeln.md`.
5. **Drei Hooks gleichzeitig in den ersten 3 Sekunden:** Audio-Hook, visueller Hook und Text-Hook (siehe Skill
   `reel-drei-hooks`).
6. **Kein Heilversprechen, kein Nocebo.** Hoffnungsvoller Ton. Nicht „schmerzfrei“, sondern „Übungen, die du
   ausprobieren kannst“. Bei Übungen immer: „Wenn etwas wehtut, nicht tiefer in die Bewegung gehen.“
7. **Übung passt zum Problem.** Typische Übung für typisches Problem. Fehlt passendes Material, sag André, welchen
   Clip er nachdrehen soll, statt etwas Unpassendes zu nehmen.

## Ablauf pro Rohmaterial-Lieferung

Projektordner: `projekte/JJJJ-MM-TT_<thema>/` mit `roh/`, `transkripte/`, `specs/`, `reels/`, `kandidaten.md`.

### 1. Sichten
```bash
python3 scripts/probe.py projekte/<p>/roh/* -o projekte/<p>/analyse.json
```
Dauer, Format, Ton, Pausen, Szenenwechsel. Von Übungsclips ohne Ton Standbilder ziehen und **anschauen**
(`ffmpeg -ss <t> -i clip -frames:v 1 bild.png`), damit klar ist, welche Übung gezeigt wird.

### 2. Transkribieren (Sprechvideos)
```bash
python3 scripts/transcribe.py projekte/<p>/roh/video.mp4 -o projekte/<p>/transkripte/video.json
```
Wenn Whisper nicht laden kann (in der Cloud-Sandbox normal, HuggingFace ist gesperrt): Das Skript legt eine MP3 ab.
Diese mit dem ElevenLabs-MCP transkribieren (`creative_transcribe_audio`, Upload über `creative_create_asset_upload`),
das Ergebnis-JSON speichern und dann:
```bash
python3 scripts/transcribe.py projekte/<p>/roh/video.mp4 --import scribe.json -o projekte/<p>/transkripte/video.json
```
Fachbegriffe im Transkript prüfen (z. B. „ISG“, „Iliosakralgelenk“, „Diskusprolaps“). Fehler kommen in die Spec unter
`untertitel_korrekturen`.

### 3. Aussagen identifizieren → `kandidaten.md`
Das Transkript Satz für Satz durchgehen und jede **inhaltliche Kernaussage** mit Zeitstempel herausziehen.
Pro Kandidat:

| # | Zeit (Quelle) | Kernaussage | Belegbar? Quelle | Hook-Idee | Payoff | Übungsclip | Urteil |
|---|---|---|---|---|---|---|---|

Urteil: ✅ wird Reel / ⚠️ nur mit Umformulierung (welche?) / ❌ verworfen (warum?).
Faktencheck mit WebSearch gegen Leitlinien und Reviews (`docs/quellen.md` als Startpunkt). Unklare Aussagen
kommen **nicht** ins Reel.

**André die Kandidatenliste zeigen und freigeben lassen, bevor gerendert wird**, außer er sagt ausdrücklich
„mach einfach“.

### 4. Skript + Spec pro Reel
Pro freigegebenem Kandidat eine Spec `projekte/<p>/specs/NN_<slug>.json` nach `templates/reel_spec.example.json`.
Pfade in der Spec sind relativ zum `specs/`-Ordner.

- `skript.hook / aufbau / payoff`: der Bogen in einem Satz pro Teil
- `segmente`: Schnitte aus dem Rohmaterial, sekundengenau an Wortgrenzen aus dem Transkript (Start ca. 0,05 s vor
  dem ersten Wort, Ende ca. 0,15 s nach dem letzten Wort). Gelaber dazwischen herausschneiden = mehrere Segmente.
  Das erste Segment trägt den visuellen Hook (Bewegung oder Nahaufnahme, `punch_in: true`).
  `zoom` (1.0–1.3) im Wechsel nutzen, damit Jump-Cuts lebendig wirken.
- `hook`: Text (max. ~8 Wörter, Problem + Neugier, `*Wort*` = gelb), Sound, visuelle Beschreibung
- `einblendungen`: Kernzahlen und Aufbau-Punkte; `quelle_einblendung` bei Zahlen und Studien
- `untertitel_manuell`: Text für Übungsclips ohne Ton
- `aussagen`: **jede** Aussage mit Quelle und Status
- `caption` (kurz, Speichern-Aufruf), genau 5 `hashtags`, `uebung: true` bei Übungen

### 5. Prüfen und rendern
```bash
python3 scripts/hook_sounds.py                         # einmalig: Hook-Sounds erzeugen
python3 scripts/render_reel.py projekte/<p>/specs/*.json --nur-pruefen
python3 scripts/render_reel.py projekte/<p>/specs/*.json --vorschau   # schnell zum Checken
python3 scripts/render_reel.py projekte/<p>/specs/*.json              # final
```
Der Renderer bricht bei Regelverstößen ab (fehlende Quelle, Heilversprechen, keine 5 Hashtags…).

### 6. Selbst-Kontrolle vor Übergabe
- Standbilder bei 0,1 s / 1,5 s / Mitte / Payoff ziehen und **ansehen**: Text lesbar? Nichts abgeschnitten? Text nicht
  im unteren Instagram-UI-Bereich?
- Untertitel gegen das Gesagte prüfen (Fachbegriffe!)
- Lautheit liegt bei ca. -14 LUFS (macht der Renderer automatisch)
- Ehrlich sagen, dass der Sound nicht angehört werden konnte

### 7. Übergabe an André
Pro Reel: MP4, `.cover.jpg` und `.txt` (Caption, Hooks je eine Zeile, Skript, Aussagen mit Quellen).
Dazu eine Kurzübersicht: welche Reels, welche Kandidaten verworfen und warum, welche Clips nachgedreht werden sollten.
Fertige Videos nicht ins Git committen (zu groß, `.gitignore`), sondern per SendUserFile schicken.

## Markenstil Reels
Teal, Gelb, Weiß (`config/brand.json`). Hook-Text oben mit dunklem Verlauf, Untertitel unten mit gelbem aktiven
Wort, Einblendungen in Teal-Box. Eigene Schrift: `.ttf` in `fonts/` legen und in `brand.json` eintragen.

## Grenzen der Umgebung
- Keine Soundbibliotheken erreichbar → Hook-Sounds sind synthetisch (`scripts/hook_sounds.py`). Alternative: in
  Instagram einen Sound aus der Bibliothek darüberlegen (in `hinweise` notieren).
- Keine urheberrechtlich geschützte Musik einbauen.
