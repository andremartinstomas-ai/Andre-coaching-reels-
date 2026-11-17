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
INTER_MED = str(ROOT / "fonts" / "Inter-Medium.otf")
TIERS = [("S", (255, 138, 138)), ("A", (255, 196, 140)), ("B", (255, 226, 145)), ("C", (190, 236, 150)), ("D", (140, 196, 255))]
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

KORREKTUR = {"esstier,": "S-Tier,", "esstier": "S-Tier", "Belastungstheoranz": "Belastungstoleranz",
                                   "Rutebete": "Rote Bete", "Komplette": "Komponente", "Den?": "Dehnen?",
                                   "Den": "Dehnen", "Stutzgürtel?": "Stützgürtel?", "Pilatus?": "Pilates?",
                                   "Art": "A-", "hier": "Tier", "hier.": "Tier.", "esst": "S-",
                                   "Verschehen": "Verstehen"}

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
    """Modernes Board: dunkles Glas-Panel, leichte Schrift, keine Konturen. Neuester Eintrag gelb gefuellt."""
    B, LB, RH, GAP = 600, 80, 100, 10
    f_tier = ImageFont.truetype(INTER, 48)
    f_chip = ImageFont.truetype(INTER_MED, 35)
    f_titel = ImageFont.truetype(INTER, 44)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    layout, y = [], 86
    for t, farbe in TIERS:
        items = [lab for tt, lab in eintraege if tt == t]
        zeilen, akt, x = [], [], 0
        for lab in items:
            w = int(tmp.textlength(lab, font=f_chip)) + 32
            if akt and x + w > B - LB - 44:
                zeilen.append(akt); akt, x = [], 0
            akt.append((lab, w)); x += w + 8
        if akt:
            zeilen.append(akt)
        h = max(RH, 22 + len(zeilen) * 60)
        layout.append((t, farbe, zeilen, y, h))
        y += h + GAP
    img = Image.new("RGBA", (B + 20, y + 24), (0, 0, 0, 0))

    def ebene(zeichne):  # jede Form/Schrift auf eigener Ebene, dann echt ueberblenden
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        zeichne(ImageDraw.Draw(lay))
        img.alpha_composite(lay)

    ebene(lambda d: d.rounded_rectangle([0, 0, B + 20, y + 24], radius=28, fill=(14, 14, 16, 242)))
    ebene(lambda d: d.text((24, 24), "Schmerz-Tierlist", font=f_titel, fill=(255, 255, 255, 240)))
    for t, farbe, zeilen, y0, h in layout:
        ebene(lambda d: d.rounded_rectangle([20, y0, 20 + LB, y0 + h], radius=16, fill=farbe + (235,)))
        ebene(lambda d: d.text((20 + LB / 2, y0 + h / 2), t, font=f_tier, fill=(25, 25, 28, 255), anchor="mm"))
        ebene(lambda d: d.rounded_rectangle([20 + LB + 8, y0, B, y0 + h], radius=16, fill=(255, 255, 255, 14)))
        cy = y0 + (h - len(zeilen) * 60) / 2 + 5
        for z in zeilen:
            x = 20 + LB + 22
            for lab, w in z:
                ist_neu = lab == neu
                ebene(lambda d: d.rounded_rectangle([x, cy, x + w, cy + 52], radius=26,
                                                    fill=GELB if ist_neu else (255, 255, 255, 30)))
                ebene(lambda d: d.text((x + w / 2, cy + 26), lab, font=f_chip,
                                       fill=(20, 20, 20, 255) if ist_neu else (255, 255, 255, 245), anchor="mm"))
                x += w + 8
            cy += 60
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
        if key == "schlaf":
            regler = regler_standbild(segs, t)
            t = regler[1]

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
                       "x": 10, "y": 230, "breite": 600, "ein": 0.12})
    a_end = marken["pause"][0]
    einbl = [{"start": round(a_end, 2), "ende": round(t, 2), "text": endtext},
             *([{"start": round(regler[0], 2), "ende": round(regler[1], 2), "text": REGLER_TEXT, "y": 1000}]
               if "schlaf" in reihe else []),
             {"stil": "fussnote", "start": 3.3, "ende": round(regler[0] if "schlaf" in reihe else a_end, 2), "text": FUSSNOTE}]
    aussagen = [QUELLEN[k] for k in reihe if k in QUELLEN] + ([REGLER_AUSSAGE] if "schlaf" in reihe else [])
    if "schlaf" in reihe:
        caption = caption.replace("\n\nStimmst du zu?", REGLER_CAPTION + "\n\nStimmst du zu?")
    spec = {
        "titel": name, "ausgabe": f"../reels/{name}.mp4", "uebung": False, "ton_reparatur": True,
        "skript": {"hook": "Was hilft eigentlich bei Schmerzen? Tierlist.",
                   "aufbau": "Behandlungen werden nacheinander eingeordnet, das Board füllt sich live.",
                   "payoff": "Fertiges Board + Hinweis: Caption lesen (Ranking nach Nachhaltigkeit)."},
        "hook": {"text": titel, "unterzeile": unterzeile, "dauer": 3.0, "animation": "slam", "punch_in": True,
                 "visuell": "Punch-in auf André, Tierlist-Board erscheint direkt nach dem Hook"},
        "segmente": segs, "untertitel": True,
        "untertitel_korrekturen": KORREKTUR,
        "einblendungen": einbl, "bilder": bilder,
        "aussagen": aussagen, "caption": caption, "hashtags": tags,
        "hinweise": ["Board-Grafik füllt sich genau dann, wenn André die Stufe ausspricht.",
                     "'Dehnen' aus dem Ton erschlossen (Transkript: 'Den?'), bitte bestätigen.",
                     "Keine Soundeffekte; Trend-Sound optional leise in Instagram darunter."],
    }
    (P / "specs" / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))
    return stand, t


FUSSNOTE = "Gerankt nach Nachhaltigkeit, nicht nach Wirkung"
REGLER_DAUER = 5.5
REGLER_TEXT = "Gut zu wissen:\nSchlaf & Stress sind nicht\nimmer die Ursache.\nEher ein *Lautstärkeregler*,\nwie laut Schmerz wird."
REGLER_AUSSAGE = {
    "text": "Schlaf und Stress müssen nicht die Ursache von Schmerz sein, beeinflussen aber, wie stark er wahrgenommen wird "
            "(Schlafmangel senkt die Schmerzschwelle; chronischer Stress kann das Schmerzsystem sensibilisieren).",
    "quelle": "Krause AJ et al. The Pain of Sleep Loss: A Brain Characterization in Humans. J Neurosci 2019;39(12):2291–2300; "
              "Hannibal KE, Bishop MD. Chronic stress, cortisol dysfunction, and pain. Phys Ther 2014;94(12):1816–1825; "
              "Finan PH et al. J Pain 2013",
    "status": "belegt",
    "beleg": "Krause: Schlafentzug senkt Schmerzschwelle, schlechtere Nacht -> mehr Schmerz am Folgetag. Hannibal & Bishop: Übersicht Stress/Cortisol und Schmerz."}
REGLER_CAPTION = ("\n\nÜbrigens: Schlaf und Stress sind nicht immer die Ursache von Schmerz. Studien zeigen aber, dass sie "
                  "wie ein Lautstärkeregler wirken: Schlechter Schlaf und Dauerstress können Schmerz lauter machen.")


def regler_standbild(segs, t):
    """Friert das letzte Bild ein (Schlaf/Stress-Hinweis) und gibt Start/Ende auf der Reel-Zeitachse zurueck."""
    letzt = segs[-1]
    segs.append({"quelle": letzt["quelle"], "start": letzt["ende"] - 0.05, "ende": round(letzt["ende"] - 0.05 + REGLER_DAUER, 2),
                 "ton": False, "standbild": True, "zoom": letzt["zoom"], "fokus_x": letzt["fokus_x"], "fokus_y": letzt["fokus_y"]})
    return t, t + REGLER_DAUER
DISCLAIMER = ("Wichtig: Wir haben nach NACHHALTIGKEIT gerankt, also danach, wie gut etwas deine Schmerzen auf lange Sicht "
              "in den Griff bekommt. Nicht danach, ob es überhaupt wirkt. Eine Bandage oder Akupunktur kann kurzfristig "
              "helfen, macht dich aber langfristig nicht belastbarer. Und: Jeder Schmerz ist individuell, das ersetzt "
              "keine Untersuchung.")
TAGS = ["#schmerztherapie", "#physiotherapie", "#rückenschmerzen", "#tierlist", "#schmerzverstehen"]

EINZEL = {
    "pilates": ("Pilates bei\n*Rückenschmerzen?*", "Und was Matcha damit zu tun hat",
                "Pilates bei Rückenschmerzen? Ja, kann richtig gut sein. Und ja, Matcha-Trinker sind klar im Vorteil.",
                ["#pilates", "#rückenschmerzen", "#physiotherapie", "#matcha", "#tierlist"]),
    "kraft": ("Was hilft *langfristig*\nbei Schmerzen?", "Platz 1 in meiner Tierlist",
              "Langsam gesteigertes Krafttraining baut Belastbarkeit auf, und genau das hilft auf lange Sicht.",
              ["#krafttraining", "#rückenschmerzen", "#physiotherapie", "#schmerztherapie", "#tierlist"]),
    "bandagen": ("Bandagen bei\n*Rückenschmerzen?*", "Warum ich sie nur auf C packe",
                 "Bandagen und Stützgürtel können Sicherheit geben, machen dich aber langfristig nicht belastbarer.",
                 ["#rückenschmerzen", "#bandage", "#physiotherapie", "#schmerztherapie", "#tierlist"]),
    "aufklaerung": ("Schmerz ist nicht\n*immer Schaden*", "Warum Verstehen S-Tier ist",
                    "Schmerz muss nicht immer strukturell sein. Wer versteht, wie Schmerz entsteht, geht anders damit um.",
                    ["#schmerzverstehen", "#schmerztherapie", "#physiotherapie", "#rückenschmerzen", "#tierlist"]),
    "schlaf": ("Schlecht geschlafen,\n*mehr Schmerzen?*", "Schlaf und Stress in meiner Tierlist",
               "Schlaf und Stress beeinflussen, wie stark du Schmerz wahrnimmst. Je nach Ursache S- oder A-Tier.",
               ["#schlaf", "#stress", "#schmerztherapie", "#physiotherapie", "#tierlist"]),
}


def baue_einzel(nr, key):
    hook, unter, satz, tags = EINZEL[key]
    reihe = ["pause_kurz", key] if False else [key]
    segs, t, quellzeit = [], 0.0, []
    for teil, a, e in PASS[key]:
        for s0, s1 in sprechbereiche(str(P / f"roh/teil_{teil}.mov"), a, e):
            segs.append({"quelle": f"../roh/teil_{teil}.mov", "start": s0, "ende": s1,
                         "transkript": f"../transkripte/teil_{teil}.json", "zoom": [1.18, 1.3][len(segs) % 2],
                         "fokus_x": 0.05, "fokus_y": 0.2})
            quellzeit.append((teil, s0, s1, t)); t += s1 - s0
    regler = regler_standbild(segs, t) if key == "schlaf" else None
    if regler:
        t = regler[1]
    sprech_ende = t
    for teil, a, e in PASS["pause"]:
        for s0, s1 in [(a, a + 2.6)]:
            segs.append({"quelle": f"../roh/teil_{teil}.mov", "start": s0, "ende": s1, "ton": False,
                         "zoom": 1.18, "fokus_x": 0.05, "fokus_y": 0.2})
            t += s1 - s0
    teil, q, tier, lab = RANG[key]
    rang = next(o + q - s0 for tl, s0, s1, o in quellzeit if tl == teil and s0 <= q <= s1)
    rang = max(rang, 3.3)
    f = P / "grafiken" / f"einzel_{key}.png"
    board_png(f, [(tier, lab)], lab)
    name = f"{nr:02d}_clip_{key}"
    spec = {
        "titel": name, "ausgabe": f"../reels/{name}.mp4", "uebung": False, "ton_reparatur": True,
        "skript": {"hook": hook.replace("*", "").replace("\n", " "), "aufbau": satz,
                   "payoff": f"Einordnung: {tier}-Tier + Verweis auf die ganze Tierlist"},
        "hook": {"text": hook, "unterzeile": unter, "dauer": 3.0, "animation": "slam", "punch_in": True,
                 "visuell": "Punch-in auf André"},
        "segmente": segs, "untertitel": True, "untertitel_korrekturen": KORREKTUR,
        "einblendungen": [{"stil": "fussnote", "start": 3.3, "ende": round(regler[0] if regler else sprech_ende, 2), "text": FUSSNOTE},
                          *([{"start": round(regler[0], 2), "ende": round(regler[1], 2), "text": REGLER_TEXT, "y": 1000}]
                            if regler else []),
                          {"start": round(sprech_ende, 2), "ende": round(t, 2),
                           "text": "Ganze Tierlist\n*auf meinem Profil*"}],
        "bilder": [{"datei": f"../grafiken/{f.name}", "start": round(rang, 2), "ende": round(sprech_ende, 2),
                    "x": 10, "y": 230, "breite": 600, "ein": 0.15}],
        "aussagen": [QUELLEN[key]] + ([REGLER_AUSSAGE] if regler else []),
        "caption": satz + (REGLER_CAPTION if regler else "") + "\n\nGerankt nach Nachhaltigkeit, also danach, wie gut etwas auf lange Sicht hilft, nicht ob es "
                   "überhaupt wirkt. Jeder Schmerz ist individuell.\n\nSpeicher dir das Reel. Die ganze Tierlist findest du auf meinem Profil.",
        "hashtags": tags,
        "hinweise": ["Ausschnitt aus der Tierlist-Serie als eigenständiger Clip."],
    }
    (P / "specs" / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))


def baue_outtakes(nr):
    stuecke = [("2", 47.7, 66.8), ("1", 40.4, 42.8), ("2", 17.0, 24.4)]
    segs, t = [], 0.0
    for teil, a, e in stuecke:
        for s0, s1 in sprechbereiche(str(P / f"roh/teil_{teil}.mov"), a, e, min_pause=0.6):
            segs.append({"quelle": f"../roh/teil_{teil}.mov", "start": s0, "ende": s1,
                         "transkript": f"../transkripte/teil_{teil}.json", "zoom": [1.0, 1.15][len(segs) % 2],
                         "fokus_x": 0.5, "fokus_y": 0.25})
            t += s1 - s0
    name = f"{nr:02d}_outtakes_tierlist"
    spec = {
        "titel": name, "ausgabe": f"../reels/{name}.mp4", "uebung": False, "ton_reparatur": True,
        "keine_aussagen": True,
        "skript": {"hook": "Behind the Scenes: So entsteht eine Tierlist", "aufbau": "Vergessen zu ranken, Neustart-Diskussion, Matcha-Gelaber",
                   "payoff": "Ehrlicher Einblick, macht nahbar"},
        "hook": {"text": "So entsteht\n*eine Tierlist*", "unterzeile": "Behind the Scenes", "dauer": 2.6,
                 "animation": "slam", "punch_in": True, "visuell": "Punch-in, André merkt, dass er vergessen hat zu ranken"},
        "segmente": segs, "untertitel": True,
        "untertitel_korrekturen": dict(KORREKTUR, **{"Bööön.": "Böööh.", "Sprecherplatz": "Sprechapparat"}),
        "effekte": [{"typ": "spirale", "quelle": "../roh/teil_2.mov", "start": 55.7, "ende": 56.9,
                     "zoom": 2.0, "drehungen": 1, "x": 0.62, "y": 0.32, "rein": 0.35, "raus": 0.2}],
        "einblendungen": [], "aussagen": [],
        "caption": "Was ihr nicht seht: wie oft ich vergesse zu ranken. Die fertige Tierlist gibt's auf meinem Profil.\n\n"
                   "Speicher dir die Serie und schreib mir, was ich als Nächstes ranken soll.",
        "hashtags": ["#behindthescenes", "#outtakes", "#physiotherapie", "#tierlist", "#physiohumor"],
        "hinweise": ["Outtakes ohne inhaltliche Aussagen. Spiral-Gag beim 'Böööh'."],
    }
    (P / "specs" / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    stand1, d1 = baue("01_tierlist_teil1", ["intro", "aktiv", "akupunktur", "pilates", "dehnen", "pause"], [],
                      "Was hilft *wirklich*\nbei Schmerzen?", "Tierlist · Teil 1", "Teil 2 folgt\n*Lies die Caption!*",
                      "Was hilft eigentlich bei Schmerzen? Teil 1 unserer Schmerz-Tierlist.\n\n" + DISCLAIMER +
                      "\n\nWo würdest du anders ranken? Schreib's in die Kommentare und speicher dir das Reel für Teil 2.",
                      TAGS)
    stand2, d2 = baue("02_tierlist_teil2", ["intro", "kraft", "bandagen", "aufklaerung", "schlaf", "pause"],
                      stand1, "Was hilft *wirklich*\nbei Schmerzen?", "Tierlist · Teil 2", "Das ist die Liste\n*Lies die Caption!*",
                      "Teil 2 unserer Schmerz-Tierlist, jetzt ist das Board komplett.\n\n" + DISCLAIMER +
                      "\n\nStimmst du zu? Schreib's in die Kommentare und speicher dir die Liste.", TAGS)
    print(f"Teil 1: {d1:.1f}s  Teil 2: {d2:.1f}s")
    print("Endstand:", stand2)
    for i, k in enumerate(["pilates", "kraft", "bandagen", "aufklaerung", "schlaf"], start=3):
        baue_einzel(i, k)
    baue_outtakes(8)
