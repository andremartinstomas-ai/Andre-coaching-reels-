# Faktencheck: Quelle pro Aussage

## Was ist eine „Aussage“?
Alles, was eine Behauptung über Körper, Schmerz, Studien oder Wirkung macht: gesprochen, eingeblendet oder in der
Caption. Keine Aussage: Übungsanleitung („10 Wiederholungen langsam“), Sicherheitssatz, Aufforderung.

## Status in der Spec
- `belegt`: konkrete Studie, Review oder Leitlinie stützt **genau diese** Aussage (Zahl, Richtung, Population).
- `konsens`: Leitlinienempfehlung oder breit akzeptierter Fachkonsens (z. B. „aktiv bleiben statt Bettruhe“).
- Alles andere (`unklar`, `widerlegt`) kommt nicht ins Reel. Der Renderer verweigert das.

## Evidenz-Rangfolge
1. Aktuelle Leitlinien (AWMF/NVL, NICE, JOSPT-CPGs)
2. Systematische Reviews und Metaanalysen (Cochrane etc.)
3. Große RCTs
4. Einzelstudien oder Expertenmeinung: nur mit vorsichtiger Formulierung („erste Studien deuten an…“)

## Ablauf
1. Aussage wörtlich aus dem Transkript notieren.
2. Mit WebSearch die passende Quelle suchen und **prüfen, dass sie es wirklich sagt** (Abstract oder Leitlinientext lesen,
   nicht nur Titel). Zahlen exakt übernehmen.
3. Vollzitat in `aussagen[].quelle`: Autoren, Titel, Journal, Jahr. Kurzform für die Einblendung.
4. Wenn Andrés Formulierung über die Evidenz hinausgeht, umformulieren (Einblendung oder Schnitt anpassen) und
   André in `hinweise` sagen, was geändert wurde und warum.
5. **Niemals eine Quelle aus dem Gedächtnis zitieren, ohne sie geprüft zu haben. Niemals eine Quelle erfinden.**
   Wenn das Netz keine Prüfung erlaubt: Aussage als ungeprüft markieren und André fragen.

## Typische Fallen
- Zahlen aus Social Media ohne Ursprung („80 % aller Menschen…“): Ursprungsstudie finden oder weglassen.
- Übertragung von Population A auf B (Studie an Sportlern ≠ Büroangestellte).
- Korrelation als Ursache („Sitzen verursacht Rückenschmerzen“: Evidenz ist schwach, also vorsichtig formulieren).
- Absolute Wörter: „immer“, „nie“, „alle“ → fast immer falsch.
