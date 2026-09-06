# Know-how einpflegen – ohne KI, ohne Programmierung

Das Prüfwissen des Tools liegt vollständig in **YAML-Wissenspaketen** unter
`drawing_checker/rules/`. Wer Fachwissen hat, erweitert Dateien – keinen Code.
Jede Datei `materials*.yaml` und `norms*.yaml` in dem Ordner wird automatisch
mitgeladen; Firmenpakete (z. B. `norms_firma.yaml`, `materials_firma.yaml`)
liegen neben den mitgelieferten und überstehen Updates des Tools.

## Die drei Wissensspeicher

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `rules/profiles.yaml` | Regeln je Materialgruppe: an/aus, Severity, Schlüsselwörter, Toleranzbänder für den Geometrieabgleich | Fachbereich |
| `rules/materials.yaml` | Werkstoffe: Erkennungsmuster + Eigenschaften (schweißgeeignet, härtbar, verzinkbar, eloxierbar, Guss) → speist die Widerspruchsprüfung | Fachbereich/Schweißaufsicht |
| `rules/norms.yaml` | Zurückgezogene/ersetzte Normen mit Hinweis auf den Nachfolger | Normenstelle |

## Massenimport statt Handarbeit

1. **Normenverwaltung anzapfen (größter Hebel):** Nautos/Perinorm können
   Trefferlisten mit Status und Nachfolgedokument als CSV exportieren.
   `python -m tools.import_norms_csv export.csv drawing_checker/rules/norms_firma.yaml`
   erzeugt daraus hunderte Prüfeinträge in einem Schritt.
2. **Firmennormen/Prüfkataloge:** Bestehende Prüf-Checklisten des Fachbereichs
   Zeile für Zeile in `profiles.yaml`-Regeln bzw. Schlüsselwortlisten gießen.
   Ein Eintrag = eine Zeile YAML.
3. **Werkstofffreigabelisten des Einkaufs:** Die intern freigegebenen
   Werkstoffe (inkl. Lieferanten-Alternativbezeichnungen) nach
   `materials_firma.yaml` übernehmen – dann erkennt das Tool auch exotische
   Hausbezeichnungen.
4. **Alte Prüfberichte als Regelquelle:** Jede wiederkehrende manuelle
   Beanstandung aus alten Prüfungen ist ein Regelkandidat. Faustregel: Was
   dreimal manuell beanstandet wurde, wird eine YAML-Regel.

## Qualitätssicherung beim Einpflegen (Golden Set)

- `mockdata/echt_quellen/` enthält echte Zeichnungen; `mockdata/inject_errors.py`
  erzeugt daraus Pakete mit dokumentierten Soll-Fehlern (`MANIFEST.txt`).
- Nach jeder Wissensänderung: `python -m pytest tests/ -q` und einen
  Kalibrierlauf über das Golden Set – neue Regeln dürfen die Referenzpakete
  (unveränderte Originale) nicht plötzlich rot färben.
- Regex-Tippfehler in den YAMLs fallen beim Start auf (Validierung beim Laden)
  und brechen den Lauf nicht stumm ab.

## Grundsätze

- **Konservativ formulieren:** Muster so eng, dass sie nur den gemeinten Fall
  treffen („2768" nur mit ISO davor). Lieber ein übersehener Fund als
  Fehlalarm-Rauschen – Rauschen zerstört das Vertrauen in die Triage.
- **Unsicheres ist gelb, nicht rot:** Was auf der Zeichnung nicht sicher
  entscheidbar ist, wird „Prüfen" (warning), niemals hart „Fehler".
- **Jede Regel hat einen Code** (z. B. `MAT.WELD_CONFLICT`) – der taucht in
  Excel und Bild auf und macht Beanstandungen diskutierbar/abschaltbar.
