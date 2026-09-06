# Regelkatalog

Alle 98 Prüfregeln des Drawing Checkers – Grundlage für die Abstimmung mit
dem Fachbereich. Jede Regel ist über `drawing_checker/rules/profiles.yaml`
(bzw. ein eigenes Paket in `regeln/`) einzeln abschaltbar, und ihre Severity
ist frei einstellbar. Die aktuell aktiven Regeln zeigt
`drawing-checker --list-rules`.

**Severity-Konvention:** `K.O.` = Paket unbrauchbar/Geometrie passt nicht ·
`Fehler` = klare Beanstandung · `Prüfen` = nicht sicher entscheidbar,
Sichtprüfung nötig · `Hinweis` = informativ.

---

## Dokument und Paket (DOC)

| Code | Severity | Prüfung |
|---|---|---|
| `DOC.NO_PDF` | K.O. | Kein PDF im YMATDOCS-Paket – Zeichnung fehlt |
| `DOC.MULTI_PDF` | Hinweis | Mehrere PDFs im Paket; nennt das geprüfte |
| `DOC.NO_STEP` | Hinweis | Kein STEP – Geometrieprüfung entfällt |
| `DOC.NO_TEXT` | Prüfen | Kein Textlayer und kein OCR – textbasierte Checks entfallen |
| `DOC.OCR` | Prüfen | Prüfung basiert auf OCR (eingeschränkte Zuverlässigkeit) |
| `DOC.BALLOONS` | Prüfen | Stückliste vorhanden, aber keine Positionsballone erkennbar |
| `DOC.GDT_GRAPHIC` | Hinweis | Toleranzrahmen nur als Grafik – Toleranzart visuell prüfen |
| `DOC.SHEET_COUNT` | Fehler | „Blatt 1 von 3", geliefert wurde weniger – Zeichnung unvollständig |
| `DOC.ANNOTATIONS` | Prüfen | Nachträgliche PDF-Kommentare/Stempel/Freihandeinträge (Rotstift) |
| `DOC.DATE_FUTURE` | Prüfen | Datum auf der Zeichnung liegt in der Zukunft |
| `DOC.DECIMAL_MIXED` | Prüfen | Dezimalkomma und -punkt gemischt – international mehrdeutig |

## Schriftfeld (TB) – ISO 7200

| Code | Severity | Prüfung |
|---|---|---|
| `TB.DRAWNO` | Fehler | Zeichnungsnummer nicht nachweisbar |
| `TB.MATERIAL` | Fehler | Werkstoff-Feld nicht nachweisbar |
| `TB.SCALE` | Fehler | Maßstab nicht nachweisbar |
| `TB.WEIGHT` | Prüfen | Gewichtsangabe nicht nachweisbar |
| `TB.REVISION` | Prüfen | Änderungsindex/Revision nicht nachweisbar |
| `TB.APPROVAL` | Prüfen | Prüf-/Freigabevermerk nicht nachweisbar |

Suchbegriffe je Feld sind in `profiles.yaml` als `keywords` gepflegt und
zweisprachig (inkl. ASME-Schreibweisen wie „DWG. NO.").

## Toleranzgrundlagen (GT)

| Code | Severity | Prüfung |
|---|---|---|
| `GT.GENERAL_TOL` | Fehler | Keine Allgemeintoleranz (ISO 2768/22081 oder ASME-Toleranzblock); auch „ISO 2768 ohne Toleranzklasse" |
| `GT.PRINCIPLE` | Prüfen | Tolerierungsgrundsatz fehlt (ISO 8015 bzw. ASME Y14.5) |

## Form- und Lagetolerierung (GPS)

| Code | Severity | Prüfung | Norm |
|---|---|---|---|
| `GPS.DATUM` | Fehler | Lagetoleranz verwendet, kein Bezug erkennbar | ISO 1101 |
| `GPS.DATUM_UNDEFINED` | Fehler | Toleranzrahmen verweist auf nicht definierte Bezüge | ISO 5459 |
| `GPS.DATUM_UNUSED` | Prüfen | Bezug definiert, aber nie verwendet | – |
| `GPS.FORM_WITH_DATUM` | Fehler | Formtoleranz **mit** Bezug = Widerspruch | ISO 1101 |
| `GPS.ZONE_NO_DATUM` | Fehler | ⌀-Toleranzzone ohne Bezug (nur Lagetoleranzen haben ⌀-Zonen) | ISO 1101 |
| `GPS.ENVELOPE` | Prüfen | Enge Passung ohne Hüllbedingung Ⓔ und ohne Formtoleranz | ISO 8015 |
| `GPS.POSITION_NO_TED` | Prüfen | Positionstoleranz ohne theoretisch genaue Maße | ISO 5458 |
| `GPS.MOD_ON_FORM` | Fehler | Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz | ISO 2692 |
| `GPS.DEPRECATED_SYMBOL` | Prüfen | Koaxialität ◎ / Symmetrie ⌯ (in ASME Y14.5-2018 gestrichen) | – |

`GPS.ENVELOPE` ist der in der Praxis teuerste Fall: Nach dem
Unabhängigkeitsprinzip begrenzt „⌀20 H7" nur das lokale Zweipunktmaß – die
Bohrung darf unrund oder krumm sein, solange die Messpunkte stimmen.

## Oberfläche und Kanten (SURF)

| Code | Severity | Prüfung |
|---|---|---|
| `SURF.ROUGHNESS` | Prüfen | Keine Oberflächenangabe (Ra/Rz, ISO 21920/1302 oder Freitext) |
| `SURF.EDGES` | Prüfen | Kein Kantenzustand (ISO 13715 oder „Kanten gebrochen") |
| `SURF.UNREALISTIC` | Fehler | Rauheit feiner als das genannte Verfahren liefert (z. B. Ra 0,8 auf Gussfläche) |
| `SURF.UNREALISTIC_MINOR` | Prüfen | Ra < 0,4 µm ohne Angabe eines Feinbearbeitungsverfahrens |
| `SURF.TOL_MISMATCH` | Prüfen | Rauheit zu grob für die engste Maßtoleranz (Rz > 50 % der Toleranzbreite) – das Maß ist so nicht reproduzierbar messbar |

## Darstellung und Bemaßung (VIEW, DIM, SCALE, THRD)

| Code | Severity | Prüfung |
|---|---|---|
| `VIEW.PROJECTION` | Prüfen | Projektionsmethode nicht nachweisbar (bei ASME Y14.5 impliziert) |
| `VIEW.UNIT` | Prüfen | Einheit nicht deklariert |
| `DIM.CHAIN` | Prüfen | Geschlossene Maßkette: Teilmaße auf einer Maßlinie summieren sich zum ebenfalls tolerierten Gesamtmaß |
| `DIM.TOL_ORDER` | Fehler | Grenzabmaße vertauscht (oberes Abmaß kleiner als unteres) – leeres Toleranzfeld, nicht fertigbar |
| `DIM.BASIC_TOL` | Fehler | Theoretisch genaues Maß (eingerahmt) zusätzlich toleriert – Widerspruch zu ISO 1101 |
| `THRD.DEPTH` | Fehler | Gewinde tiefer gefordert als die zugehörige Kernbohrung – nicht herstellbar |
| `THRD.SHORT` | Prüfen | Einschraubtiefe unter 1×D (Stahl) bzw. 1,5×D (Aluminium) – das Gewinde reißt vor der Schraube aus (VDI 2230) |
| `THRD.FIT_CLASS` | Fehler | Gewinde mit Passungsklasse bemaßt („M12 H7" statt 6H/6g, ISO 965) |
| `SCALE.MISMATCH` | *(aus)* | Gemessene Ansicht überschreitet das größte eingetragene Maß |

## Masse-Plausibilität ohne STEP (MASS)

| Code | Severity | Prüfung |
|---|---|---|
| `MASS.IMPOSSIBLE` | Fehler | Gewichtsangabe schwerer als ein **voller** Quader der Hüllmaße – physikalisch unmöglich; nennt den Faktor (1000 ≈ g/kg vertauscht) |
| `MASS.TOO_LIGHT` | Prüfen | Füllgrad unter 1 % des Hüllquaders – bei Blech/Schweißrahmen normal, sonst verdächtig |
| `MASS.DENSITY_HINT` | Prüfen | Mit STEP: Gewicht/Modellvolumen ergibt die Dichte eines **anderen** Werkstoffs (kopiertes Schriftfeld) |

Die Hüllmaße stammen aus den drei größten Zeichnungsmaßen und sind eher zu
groß geschätzt – das Urteil „unmöglich" ist damit auf der sicheren Seite.
Gewichtsangaben mit „Rohteil"/„brutto" werden erkannt und dem Fertiggewicht
nachgeordnet.

## Fertigungsgerechtigkeit (MFG)

| Code | Severity | Prüfung |
|---|---|---|
| `MFG.TIGHT_TOL` | Prüfen | Sehr enge Toleranz (IT ≤ 5 bzw. < 10 µm) – stärkster Kostentreiber der Zerspanung |
| `MFG.DEEP_HOLE` | Prüfen | Bohrung mit Tiefe/Durchmesser > 5 (Tiefbohren nötig) |
| `MFG.SHARP_CORNER` | Prüfen | „R0"/scharfe Innenecke – mit Fräser nicht herstellbar |

## Internationale Beschaffung (PUR)

| Code | Severity | Prüfung |
|---|---|---|
| `PUR.VAGUE_SPEC` | Prüfen | Unbestimmte Angaben („ca. 20", „nach Absprache", „sauber entgraten", „TBD") – nicht kalkulierbar, nicht abnahmefähig |
| `PUR.INTERNAL_NORM` | Prüfen | Verweis auf Werk-/Konzernnormen (WN, HN, TL, MBN, VW, DBL …), die ein externer Lieferant nicht beziehen kann |
| `PUR.STOCK_SIZE` | Hinweis | Blechdicke/Rundmaterial außerhalb der Vorzugsmaße – Sondermaß mit Preis- und Lieferzeitfolge |

Formulierungen, Hausnorm-Kürzel und Vorzugsmaße stehen in
`rules/beschaffung.yaml` und sind ohne Codeänderung erweiterbar.

## Sprache (LANG)

| Code | Severity | Prüfung |
|---|---|---|
| `LANG.GERMAN` | Fehler | Rein deutschsprachige Beschriftung (zweisprachig ist ok) – Sicht des internationalen Einkaufs |

## Werkstoff und fachliche Widersprüche (MAT, COAT, PROC, WELD, NORM)

| Code | Severity | Prüfung |
|---|---|---|
| `MAT.MISSING` | Fehler | Kein Werkstoff angegeben |
| `MAT.UNKNOWN` | Prüfen | Werkstoff-Feld vorhanden, Bezeichnung nicht erkannt (Datenbank erweitern) |
| `MAT.WELD_CONFLICT` | Fehler | Nicht schweißgeeigneter Werkstoff + Schweißangaben (1.4305, GJL, 7075, Automatenstähle) |
| `MAT.WELD_LIMITED` | Prüfen | Nur bedingt schweißgeeignet (42CrMo4, C45, GJS) |
| `MAT.HT_CONFLICT` | Fehler | Wärmebehandlung passt nicht zum Werkstoff (S235 „gehärtet") |
| `MAT.COATING_CONFLICT` | Fehler | Verzinken auf Edelstahl/Alu, Eloxieren auf Nicht-Alu, Brünieren auf Nichtstahl |
| `MAT.ANODIZE_ALLOY` | Fehler | Alu-Legierung zum Eloxieren ungeeignet (AlSi-Guss, 2007/2024) |
| `MAT.ANODIZE_LIMITED` | Prüfen | Nur bedingt eloxierbar (7075) |
| `MAT.CAST_CONFLICT` | Prüfen | Gusskontext ohne Gusswerkstoff |
| `COAT.FIT` | Prüfen | Beschichtung + Passung/Gewinde ohne Freihalte-/Nacharbeitsvermerk |
| `COAT.EMBRITTLEMENT` | Fehler | Galvanische Beschichtung an hochfestem Bauteil (≥ 1000 MPa / 320 HV / 32 HRC / Klasse 10.9) ohne geforderte Wasserstoffarmglühung nach EN ISO 4042 |
| `PROC.STUD_ON_ZINC` | Fehler | Schweißbolzen auf feuerverzinktem Teil |
| `PROC.WELD_ZINC_ORDER` | Prüfen | Schweißen und Verzinken ohne Reihenfolgeangabe |
| `WELD.MIXED` | Fehler | Aluminium + Stahl geschweißt |
| `WELD.MIXED_FILLER` | Prüfen | Schwarz-Weiß-Verbindung ohne Zusatzwerkstoff (309L) |
| `NORM.MATERIAL_MISMATCH` | Fehler | ISO 5817 bei Aluminium (statt ISO 10042) und umgekehrt |
| `NORM.OBSOLETE` | Prüfen | Zurückgezogene/ersetzte Norm (23 Einträge, per CSV erweiterbar) |
| `NORM.WELD_GENTOL` | Prüfen | Schweißkonstruktion nur mit ISO 2768, ISO 13920 fehlt |
| `CONS.MATNO` | Prüfen | Materialnummer der Anfrage auf der Zeichnung nicht gefunden |

## Verfahrensspezifische Vollständigkeit (WELD, CAST, SHEET, HT)

| Code | Severity | Prüfung | Norm |
|---|---|---|---|
| `WELD.QUALITY` | Fehler | Schweißteil ohne Bewertungsgruppe | ISO 5817 |
| `WELD.NO_SIZE` | Fehler | Schweißangaben ohne Nahtdicke (a-/z-Maß) | ISO 2553 |
| `WELD.AZ_MIXED` | Prüfen | a- und z-Maße gemischt (Faktor √2 ≈ 29 % Unterschied) | ISO 2553 |
| `WELD.NO_PREP` | Prüfen | Stumpf-/Fugennaht ohne Nahtvorbereitung | ISO 9692 |
| `CAST.TOL` | Fehler | Gussteil ohne Gusstoleranz | ISO 8062 |
| `CAST.NO_DRAFT` | Prüfen | Gussteil ohne Formschrägen | DIN EN 12890 |
| `CAST.NO_RMA` | Prüfen | Bearbeitetes Gussteil ohne Bearbeitungszugabe | ISO 8062-3 |
| `SHEET.NO_THICK` | Fehler | Blech-/Biegeteil ohne Blechdicke | – |
| `SHEET.NO_RADIUS` | Prüfen | Abkantung ohne Biegeradius | – |
| `HT.NO_HARDNESS` | Prüfen | Wärmebehandlung ohne Härtewert (entfällt bei +QT/+N und Festigkeitsangabe) | DIN 6773 |
| `HT.NO_DEPTH` | Prüfen | Randschichthärten ohne Einhärtetiefe (Eht/CHD/NHD) | DIN 6773 |
| `HT.HARDNESS_LIMIT` | Fehler | Härteforderung über dem Werkstoffmaximum (z. B. 64 HRC auf C45) | – |

## Geometrieabgleich mit STEP (GEO)

| Code | Severity | Prüfung |
|---|---|---|
| `GEO.MISMATCH` | K.O. | Hüllmaße passen nicht (Maß größer als Raumdiagonale oder Hauptmaß weit daneben) |
| `GEO.UNCERTAIN` | Prüfen | Nicht sicher bewertbar – manuelle Prüfung |
| `GEO.NO_DIMS` | Prüfen | Keine Maße extrahierbar, Abgleich nur eingeschränkt |
| `GEO.MASS` | Fehler | Gewichtsangabe vs. Volumen × Werkstoffdichte weicht stark ab |
| `GEO.MASS_MINOR` | Prüfen | Moderate Massenabweichung (bei Guss/Schweiß normal) |
| `GEO.HOLE_COUNT` | Fehler | „4×⌀18" der Zeichnung fehlt im Modell |
| `GEO.HOLE_COUNT_MINOR` | Prüfen | Bohrbild teilweise vorhanden |
| `GEO.THREAD` | Prüfen | Gewinde ohne passendes Kernloch im Modell |
| `GEO.UNIT_MISMATCH` | Fehler | Zoll/mm-Verwechslung beim STEP-Export (Faktor 25,4) |
| `GEO.ASSEMBLY` | Fehler | Räumlich getrennte Körper, aber Einzelteilzeichnung |
| `GEO.ASSEMBLY_MINOR` | Prüfen | Stückliste vorhanden, Modell hat nur einen Körper |
| `GEO.NOT_FUSED` | Hinweis | Sich berührende, nicht verschmolzene Körper |
| `GEO.CONTOUR` | Prüfen | Konturprojektion (bestätigt bzw. entkräftet das Maß-Urteil) |
| `GEO.MIRROR` | Fehler | Die Ansichten passen besser zum **gespiegelten** Modell – falsche Hand gespeichert. Hüllmaße, Volumen, Masse und Bohrbild sind bei gespiegelten Teilen identisch; nur die Kontur verrät den Fall |
| `GEO.VIEW_SIZE` | *(aus)* | Gemessene Ansicht größer als das Modell |

Der Geometrieabgleich stützt sich auf fünf unabhängige Indizien (Hüllmaße,
Masse, Bohrbild, Konturprojektion, Spiegelung) – siehe README.

**Richtung der Abweichung entscheidet über die Härte:** Ist ein bemaßtes Maß
*größer* als das Modell, kann das Teil es nicht enthalten – K.O. Ist
umgekehrt das *Modell* größer als jedes bemaßte Maß, fehlt meist nur das
Gesamtmaß auf dem Blatt (Maßkette, Folgeblatt); das gibt nur „Prüfen".
Am Kalibriersatz aus 84 echten Zeichnungen war das die Ursache für drei von
vier K.O.-Fehlurteilen. `SCALE.MISMATCH` und
`GEO.VIEW_SIZE` sind im Auslieferzustand deaktiviert, weil Blatt- und
Ansichtsmaßstab in vielen CAD-Systemen auseinanderfallen.

---

## Profile

| Profil | Besonderheit |
|---|---|
| `default` | Grundeinstellung für spanend gefertigte Teile |
| `guss` | Größere Geometrie- und Massetoleranzen (Rohteil vs. Fertigteil), `GEO.MISMATCH` nur als Warnung |
| `schweiss` | Größere Toleranzen wegen Verzug/Nahtaufbau, `WELD.QUALITY` als Fehler |

Eigene Profile je Materialgruppe legt man in `regeln/profiles_firma.yaml`
per `inherit` an – siehe [KNOWHOW.md](KNOWHOW.md).
