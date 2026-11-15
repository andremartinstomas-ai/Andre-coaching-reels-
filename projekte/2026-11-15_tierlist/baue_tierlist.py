#!/usr/bin/env python3
"""Tierlist-Serie (Teil 1 + 2): Tierboard-Grafiken (PIL) + Reel-Specs fuer scripts/render_reel.py."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from pausen_schnitt import sprechbereiche  # noqa: E402

BEBAS = str(ROOT / "fonts" / "BebasNeue-Regular.ttf")
INTER = str(ROOT / "fonts" / "Inter-SemiBold.otf")
TIERS = [("S", (255, 127, 127)), ("A", (255, 191, 127)), ("B", (255, 223, 127)), ("C", (191, 255, 127)), ("D", (127, 191, 255))]
GELB = (248, 184, 0, 255)

# Passagen: (teil, start, ende) -> Pausen werden automatisch entfernt
PASS = {
    "intro":       [("1", 0.0, 4.1)],
    "aktiv":       [("1", 17.8, 25.5)],
    "pilates":     [("1", 105.0, 105.8), ("2", 87.1, 96.2)],
    "dehnen":      [("3", 19.1, 37.5)],
    "akupunktur":  [("3", 37.6, 57.3)],
    "kraft":       [("1", 59.4, 61.9), ("1", 77.8, 83.5)],
    "aufklaerung": [("1", 27.0, 28.8), ("1", 51.8, 58.4)],
    "schlaf":      [("2", 97.2, 98.7), ("3", 2.2, 17.7)],
    "psycho":      [("1", 85.2, 104.2)],
    "bandagen":    [("3", 57.9, 61.8), ("3", 70.2, 82.0)],
    "pause":       [("1", 12.1, 15.9)],  # stiller Schluss fuer Endkarte (Ton aus)
}
# Wann faellt die Einstufung (Quellzeit des Tier-Worts) + Tier + Label
RANG = {
    "aktiv": ("1", 20.64, "S", "Aktiv bleiben"),
    "pilates": ("2", 88.76, "A", "Pilates"),
    "dehnen": ("3", 22.30, "B", "Dehnen"),
    "akupunktur": ("3", 42.38, "C", "Akupunktur"),
    "kraft": ("1", 79.98, "S", "Krafttraining"),
    "aufklaerung": ("1", 53.16, "S", "Schmerz verstehen"),
    "schlaf": ("3", 5.26, "A", "Schlaf & Stress"),
    "psycho": ("1", 103.9, "B", "Psycho. Ansätze"),
    "bandagen": ("3", 72.44, "C", "Bandagen"),
}

QUELLEN = {
    "aktiv": {"text": "Bei Rückenschmerzen aktiv bleiben und den Alltag weiterführen statt Schonung.",
              "quelle": "NVL Nicht-spezifischer Kreuzschmerz, 2. Aufl. 2017; NICE NG59 (2016/2020)", "status": "konsens"},
    "pilates": {"text": "Pilates gehört bei chronischem unspezifischem Rückenschmerz zu den wirksamsten Übungsformen (Schmerz).",
                "quelle": "Owen PJ et al. Which specific modes of exercise training are most effective for treating low back pain? Network meta-analysis. Br J Sports Med 2020;54(21):1279–1287",
                "status": "belegt", "beleg": "NMA, 89 Studien; Pilates höchste SUCRA für Schmerz, Evidenz niedrige Qualität."},
    "dehnen": {"text": "Dehnen kann Schmerzen lindern, als alleinige Maßnahme aber begrenzt; ergänzend sinnvoll.",
               "quelle": "Owen PJ et al. Br J Sports Med 2020 (Dehnen nicht unter den wirksamsten Formen); Hayden JA et al. Exercise therapy for chronic low back pain. Cochrane 2021",
               "status": "konsens"},
    "akupunktur": {"text": "Akupunktur: bescheidene Evidenz, NICE empfiehlt sie bei Rückenschmerz nicht.",
                   "quelle": "NICE NG59 Low back pain and sciatica in over 16s, Empfehlung 1.2.8 ('Do not offer acupuncture')",
                   "status": "belegt"},
    "kraft": {"text": "Langsam gesteigertes Krafttraining baut Belastungstoleranz auf und gehört zu den wirksamsten Übungsformen.",
              "quelle": "Owen PJ et al. Br J Sports Med 2020; Hayden JA et al. Cochrane 2021", "status": "belegt"},
    "aufklaerung": {"text": "Schmerz muss nicht immer strukturell bedingt sein; Schmerzaufklärung hilft, das zu verstehen.",
                    "quelle": "Raja SN et al. Revised IASP definition of pain. Pain 2020; Louw A et al. Physiother Theory Pract 2016",
                    "status": "konsens"},
    "schlaf": {"text": "Schlaf und Stress beeinflussen das Schmerzerleben.",
               "quelle": "Finan PH et al. The association of sleep and pain. J Pain 2013; Raja SN et al. Pain 2020", "status": "konsens"},
    "psycho": {"text": "Psychologische Ansätze (v. a. KVT) helfen bei chronischen Schmerzen, Effekte sind aber klein und nicht für jeden passend.",
               "quelle": "Williams ACdC et al. Psychological therapies for the management of chronic pain (excluding headache) in adults. Cochrane 2020",
               "status": "belegt"},
    "bandagen": {"text": "Bandagen/Stützgürtel können Sicherheit vermitteln, werden bei Rückenschmerz aber nicht empfohlen.",
                 "quelle": "NICE NG59, Empfehlung 1.2.3 ('Do not offer belts or corsets')", "status": "belegt"},
}


def chip_breite(d, text, font):
    return int(d.textlength(text, font=font)) + 30


def board_png(ziel, eintraege, neu=None):
    """eintraege: Liste (tier, label). neu = label, das gelb umrandet wird."""
    B, LB, RH = 540, 96, 116
    f_tier = ImageFont.truetype(BEBAS, 92)
    f_chip = ImageFont.truetype(INTER, 34)
    f_titel = ImageFont.truetype(BEBAS, 64)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    # Zeilen mit Umbruch berechnen
    layout, y = [], 96
    for t, farbe in TIERS:
        items = [lab for tt, lab in eintraege if tt == t]
        zeilen, akt, x = [], [], 0
        for lab in items:
            w = chip_breite(tmp, lab, f_chip)
            if akt and x + w > B - LB - 20:
                zeilen.append(akt); akt, x = [], 0
            akt.append((lab, w)); x += w + 8
        if akt:
            zeilen.append(akt)
        h = max(RH, 20 + len(zeilen) * 58)
        layout.append((t, farbe, zeilen, y, h))
        y += h + 6
    img = Image.new("RGBA", (B + 20, y + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "SCHMERZ-TIERLIST", font=f_titel, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(20, 20, 20, 255))
    for t, farbe, zeilen, y0, h in layout:
        d.rounded_rectangle([10, y0, 10 + LB, y0 + h], radius=10, fill=farbe + (255,))
        d.text((10 + LB / 2, y0 + h / 2 + 3), t, font=f_tier, fill=(25, 25, 25, 255), anchor="mm")
        d.rounded_rectangle([10 + LB + 6, y0, 10 + B, y0 + h], radius=10, fill=(20, 20, 20, 190))
        cy = y0 + (h - len(zeilen) * 58) / 2 + 4
        for z in zeilen:
            x = 10 + LB + 18
            for lab, w in z:
                rand = GELB if lab == neu else (255, 255, 255, 60)
                d.rounded_rectangle([x, cy, x + w, cy + 50], radius=25, fill=(255, 255, 255, 235), outline=rand,
                                    width=5 if lab == neu else 1)
                d.text((x + w / 2, cy + 26), lab, font=f_chip, fill=(20, 20, 20, 255), anchor="mm")
                x += w + 8
            cy += 58
    img.save(ziel)


def baue(name, reihe, vorher, titel, unterzeile, endtext, caption, tags):
    segs, t, marken, quellzeit = [], 0.0, {}, []
    zoom = [1.18, 1.28]
    for key in reihe:
        marken[key] = [t, None]
        for teil, a, e in PASS[key]:
            for s0, s1 in sprechbereiche(str(P / f"roh/teil_{teil}.mov"), a, e):
                ton = key != "pause"
                segs.append({"quelle": f"../roh/teil_{teil}.mov", "start": s0, "ende": s1, "ton": ton,
                             "transkript": f"../transkripte/teil_{teil}.json", "zoom": zoom[len(segs) % 2],
                             "fokus_x": 0.05, "fokus_y": 0.2})
                quellzeit.append((teil, s0, s1, t))
                t += s1 - s0
        marken[key][1] = t

    def aus(teil, q):
        for tl, s0, s1, o in quellzeit:
            if tl == teil and s0 <= q <= s1:
                return round(o + q - s0, 2)
        best = min((x for x in quellzeit if x[0] == teil), key=lambda x: min(abs(q - x[1]), abs(q - x[2])))
        return round(best[3] + (0 if q < best[1] else best[2] - best[1]), 2)

    # Board-Zustaende
    bilder, stand, zeit = [], list(vorher), 3.2
    gr = P / "grafiken"
    gr.mkdir(exist_ok=True)
    zustaende = [(zeit, None)]
    for key in reihe:
        if key in RANG:
            teil, q, tier, lab = RANG[key]
            zustaende.append((aus(teil, q), (tier, lab)))
    for i, (start, neu) in enumerate(zustaende):
        if neu:
            stand.append(neu)
        ende = zustaende[i + 1][0] if i + 1 < len(zustaende) else marken[reihe[-1]][0]
        f = gr / f"{name}_board_{i}.png"
        board_png(f, stand, neu[1] if neu else None)
        bilder.append({"datei": f"../grafiken/{f.name}", "start": round(start, 2), "ende": round(ende + 0.02, 2),
                       "x": 10, "y": 250, "breite": 560, "ein": 0.12})
    a_end = marken["pause"][0]
    einbl = [{"start": round(a_end, 2), "ende": round(t, 2), "text": endtext}]
    aussagen = [QUELLEN[k] for k in reihe if k in QUELLEN]
    spec = {
        "titel": name, "ausgabe": f"../reels/{name}.mp4", "uebung": False, "ton_reparatur": True,
        "skript": {"hook": "Was hilft eigentlich bei Schmerzen? Tierlist.",
                   "aufbau": "Behandlungen werden nacheinander eingeordnet, das Board füllt sich live.",
                   "payoff": "Fertiges Board + Hinweis: Caption lesen (Ranking nach Nachhaltigkeit)."},
        "hook": {"text": titel, "unterzeile": unterzeile, "dauer": 3.0, "animation": "slam", "punch_in": True,
                 "visuell": "Punch-in auf André, Tierlist-Board erscheint direkt nach dem Hook"},
        "segmente": segs, "untertitel": True,
        "untertitel_korrekturen": {"esstier,": "S-Tier,", "esstier": "S-Tier", "Belastungstheoranz": "Belastungstoleranz",
                                   "Rutebete": "Rote Bete", "Komplette": "Komponente", "Den?": "Dehnen?",
                                   "Den": "Dehnen", "Stutzgürtel?": "Stützgürtel?", "Pilatus?": "Pilates?",
                                   "Art": "A-", "hier": "Tier", "hier.": "Tier.", "esst": "S-",
                                   "Verschehen": "Verstehen"},
        "einblendungen": einbl, "bilder": bilder,
        "aussagen": aussagen, "caption": caption, "hashtags": tags,
        "hinweise": ["Board-Grafik füllt sich genau dann, wenn André die Stufe ausspricht.",
                     "'Dehnen' aus dem Ton erschlossen (Transkript: 'Den?'), bitte bestätigen.",
                     "Psychologische Ansätze: keine Stufe ausgesprochen, vorläufig B (Evidenz: kleine Effekte, Cochrane 2020).",
                     "Keine Soundeffekte; Trend-Sound optional leise in Instagram darunter."],
    }
    (P / "specs" / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    return stand, t


DISCLAIMER = ("Wichtig: Wir haben nach NACHHALTIGKEIT gerankt, also danach, wie gut etwas deine Schmerzen auf lange Sicht "
              "in den Griff bekommt. Nicht danach, ob es überhaupt wirkt. Eine Bandage oder Akupunktur kann kurzfristig "
              "helfen, macht dich aber langfristig nicht belastbarer. Und: Jeder Schmerz ist individuell, das ersetzt "
              "keine Untersuchung.")
TAGS = ["#schmerztherapie", "#physiotherapie", "#rückenschmerzen", "#tierlist", "#schmerzverstehen"]

if __name__ == "__main__":
    stand1, d1 = baue("01_tierlist_teil1", ["intro", "aktiv", "akupunktur", "pilates", "dehnen", "pause"], [],
                      "Was hilft *wirklich*\nbei Schmerzen?", "Tierlist · Teil 1", "Teil 2 folgt\n*Lies die Caption!*",
                      "Was hilft eigentlich bei Schmerzen? Teil 1 unserer Schmerz-Tierlist.\n\n" + DISCLAIMER +
                      "\n\nWo würdest du anders ranken? Schreib's in die Kommentare und speicher dir das Reel für Teil 2.",
                      TAGS)
    stand2, d2 = baue("02_tierlist_teil2", ["intro", "kraft", "bandagen", "aufklaerung", "psycho", "schlaf", "pause"],
                      stand1, "Was hilft *wirklich*\nbei Schmerzen?", "Tierlist · Teil 2", "Das ist die Liste\n*Lies die Caption!*",
                      "Teil 2 unserer Schmerz-Tierlist, jetzt ist das Board komplett.\n\n" + DISCLAIMER +
                      "\n\nStimmst du zu? Schreib's in die Kommentare und speicher dir die Liste.", TAGS)
    print(f"Teil 1: {d1:.1f}s  Teil 2: {d2:.1f}s")
    print("Endstand:", stand2)
