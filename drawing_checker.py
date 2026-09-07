"""Drawing Checker - Pruefung technischer Zeichnungen je SAP-Materialnummer.

EINE Datei: Programm, Wissenspakete (YAML, eingebettet), Mockdaten,
Werkzeuge und Tests. Dazu gehoeren nur noch Start.bat (Einrichtung und
Menue fuer Windows) und README.md (alles Weitere).

    python drawing_checker.py                    GUI
    python drawing_checker.py --headless --excel liste.xlsx --column C
    python drawing_checker.py --check-rules      Wissenspakete pruefen
    python drawing_checker.py --export-rules     YAMLs zum Bearbeiten nach regeln/
    python drawing_checker.py --sap-import-vbs x.vbs   Mitschnitt -> Ablauf
    python drawing_checker.py --sap-dry-run 4711       Ablauf ohne SAP pruefen
    python drawing_checker.py mockdata bauen|quellen|fehler
    python drawing_checker.py messen ocr|langlauf|kalibrier|normen
    python drawing_checker.py paket [--nur zip|bat]
    python -m pytest drawing_checker.py -q       Tests (liegen am Dateiende)

Inhaltsverzeichnis: nach "# ====" suchen - jeder Abschnitt hat einen
Kopf mit Namen und Beschreibung.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger("drawing_checker")
WURZEL = Path(__file__).resolve().parent      # Ordner, in dem diese Datei liegt

# ========================================================================
# wissenspakete
# ========================================================================
# Das Fachwissen als YAML - eingebettet, damit das Programm eine Datei
# bleibt. Zum Bearbeiten:  python drawing_checker.py --export-rules
# schreibt die vier Dateien nach regeln/; dort gepflegte Fassungen
# ueberlagern die eingebauten (Ordner regeln/ neben dem Programm oder
# DRAWING_CHECKER_RULES).
EINGEBAUTE_REGELN: dict[str, str] = {
    "beschaffung.yaml": r"""# Wissenspaket „Internationale Beschaffung"
#
# Prüft die Zeichnung aus Sicht eines Lieferanten, der weder im Haus sitzt
# noch die Historie kennt. Alle Listen sind frei erweiterbar; nach dem
# Bearbeiten `drawing-checker --check-rules` laufen lassen.
#
#   vage:        Formulierungen, die keine prüfbare Anforderung sind.
#                pattern (Regex, case-insensitive) + message.
#   hausnormen:  Werk-/Konzernnormen, die ein externer Lieferant nicht
#                beziehen kann. Sie müssen der Anfrage beiliegen.
#   halbzeuge:   Vorzugsmaße gängiger Halbzeuge. Weicht ein Maß davon ab,
#                ist das Teil aus dem nächstgrößeren Halbzeug zu fertigen –
#                teurer und mit längerer Lieferzeit.

vage:
  - {pattern: '\bca\.\s*\d', message: '„ca." vor einem Maß ist keine prüfbare Angabe'}
  - {pattern: '\betwa\s+\d', message: '„etwa" vor einem Maß ist keine prüfbare Angabe'}
  - {pattern: 'nach\s+(?:Absprache|Vereinbarung|Bedarf|Muster|Rücksprache)',
     message: 'Anforderung „nach Absprache" – der Lieferant kann nicht kalkulieren'}
  - {pattern: 'wie\s+(?:Muster|Vorlage|bisher|gehabt)',
     message: 'Verweis auf ein Muster – für eine internationale Anfrage nicht nutzbar'}
  - {pattern: '\b(?:sauber|gut|ordentlich|einwandfrei|fachgerecht)\s+(?:entgrat|verputz|geschweiss|geschweiß|bearbeit|schleif)',
     message: 'Subjektive Anforderung – messbar angeben (z. B. Kantenzustand nach ISO 13715)'}
  - {pattern: 'scharfe?\s+Kanten\s+(?:brechen|entfernen)(?!\s*[:=]?\s*\d)',
     message: '„Kanten brechen" ohne Maß – Kantenzustand nach ISO 13715 angeben'}
  - {pattern: '\bggf\.|\bfalls\s+erforderlich|\bbei\s+Bedarf',
     message: 'Bedingte Anforderung ohne Kriterium – wer entscheidet, wann sie gilt?'}
  - {pattern: 'siehe\s+(?:Zeichnung|Skizze|Anlage)(?!\s*(?:Nr\.?\s*)?[\w.-]*\d)',
     message: 'Verweis ohne Dokumentnummer – das Bezugsdokument ist nicht identifizierbar'}
  - {pattern: '\bTBD\b|\bt\.b\.d\.|noch\s+festzulegen|offen\s*$',
     message: 'Unfertige Angabe (TBD) – die Zeichnung ist nicht anfragereif'}
  - {pattern: '\bhandelsüblich\b|\bmarktüblich\b',
     message: '„handelsüblich" ist länderabhängig – Norm und Bezeichnung angeben'}

hausnormen:
  - {pattern: '\bWN\s*\d{3,6}\b', message: 'Werknorm WN – dem Lieferanten nicht zugänglich'}
  - {pattern: '\bHN\s*\d{3,6}\b', message: 'Hausnorm HN – dem Lieferanten nicht zugänglich'}
  - {pattern: '\bFN\s*\d{3,6}\b', message: 'Firmennorm FN – dem Lieferanten nicht zugänglich'}
  - {pattern: '\bTL\s*\d{3,6}\b', message: 'Technische Lieferbedingung TL (OEM-Norm) – nur mit Bezugsberechtigung erhältlich'}
  - {pattern: '\bMBN\s*\d{3,6}\b', message: 'Mercedes-Benz-Norm MBN – nur mit Bezugsberechtigung erhältlich'}
  - {pattern: '\bVW\s*\d{5}\b', message: 'VW-Norm – nur mit Bezugsberechtigung erhältlich'}
  - {pattern: '\bDBL\s*\d{3,5}\b', message: 'DBL-Werkstoffblatt – nur mit Bezugsberechtigung erhältlich'}
  - {pattern: '\bBN\s*\d{3,6}\b', message: 'Betriebsnorm BN – dem Lieferanten nicht zugänglich'}
  - {pattern: '\bQAB\s*\d+|\bPV\s*\d{3,4}\b', message: 'Interne Prüfvorschrift – muss der Anfrage beiliegen'}

halbzeuge:
  # Blechdicken in mm (Kaltband/Warmband, gängige Lagerstärken)
  blech: [0.5, 0.6, 0.75, 0.8, 0.88, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0,
          4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 16.0, 20.0, 25.0, 30.0,
          35.0, 40.0, 50.0, 60.0, 80.0, 100.0]
  # Rundmaterial (Blankstahl/gezogen), Durchmesser in mm
  rund: [3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 36,
         40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 140,
         150, 160, 180, 200, 220, 250, 280, 300]
""",
    "materials.yaml": r"""# Werkstoff-Wissenspaket
#
# Hier wird Fach-Know-how OHNE Programmierung eingepflegt. Jeder Eintrag:
#   name:       Anzeigename in Findings
#   patterns:   Regex-Alternativen (Werkstoffnummer, Kurzname, US-Bezeichnung)
#   category:   baustahl | verguetung | einsatz | automaten | nirosta |
#               nirosta_auto | guss | stahlguss | alu | kupfer | titan |
#               magnesium | kunststoff | verbund
#   weldable:   ja | bedingt | nein
#   hardenable: [qt, case, nitr]   (vergüten/härten, einsatzhärten, nitrieren)
#   zinc:       true, wenn Verzinken fachlich sinnvoll ist
#   anodize:    true, wenn Eloxieren fachlich sinnvoll ist
#   castable:   true bei Gusswerkstoffen
#   density:    Dichte in g/cm3 (für den Masseabgleich Zeichnung vs. STEP)
#   max_hrc:    max. erreichbare Oberflächenhärte in HRC (Plausibilität von
#               Härteangaben); weglassen, wenn nicht härtbar
#   note:       erscheint als Detail im Finding
#
# Zusätzliche Pakete: jede weitere Datei materials*.yaml in diesem Ordner
# (z. B. materials_firma.yaml) wird automatisch mitgeladen.

materials:
  # ============================ Baustähle =================================
  - {name: S235JR, patterns: ['S\s*235\s*J?R?\w*', '1\.0038', '1\.0037', '\bSt\s*37\b'],
     category: baustahl, weldable: ja, zinc: true, density: 7.85}
  - {name: S275JR, patterns: ['S\s*275\s*(?:JR|J2|J0)?', '1\.0044'],
     category: baustahl, weldable: ja, zinc: true, density: 7.85}
  - {name: S355J2, patterns: ['S\s*355\s*(?:J2|JR|J0|K2|ML|NL)?(?:\+N|\+AR)?', '1\.0577', '1\.0570', '\bSt\s*52\b'],
     category: baustahl, weldable: ja, zinc: true, density: 7.85}
  - {name: S460, patterns: ['S\s*460\s*(?:N|NL|M|ML|QL)?', '1\.8905'],
     category: baustahl, weldable: ja, zinc: true, density: 7.85}
  - {name: S690QL, patterns: ['S\s*690\s*QL?1?', '1\.8931', '1\.8928'],
     category: baustahl, weldable: bedingt, zinc: true,
     note: 'Feinkornbaustahl hochfest: Schweißen nur mit qualifiziertem Verfahren (Vorwärmung, t8/5)', density: 7.85}
  - {name: E295/E335, patterns: ['\bE29[05]\b', '\bE33[05]\b', '1\.0050', '1\.0060', '\bSt\s*50\b', '\bSt\s*60\b'],
     category: baustahl, weldable: bedingt, zinc: true, density: 7.85}
  # ========================= Vergütungsstähle =============================
  - {name: C35/C40, patterns: ['\bC35(?:E|R)?\b', '\bC40(?:E|R)?\b', '1\.0501', '1\.1181'],
     category: verguetung, weldable: bedingt, hardenable: [qt], zinc: true, density: 7.85, max_hrc: 52}
  - {name: C45, patterns: ['\bC45(?:E|R)?\b', '1\.0503', '1\.1191'],
     category: verguetung, weldable: bedingt, hardenable: [qt], zinc: true,
     note: 'Schweißen nur mit Vorwärmung/Nachbehandlung', density: 7.85, max_hrc: 58}
  - {name: C60, patterns: ['\bC60(?:E|R)?\b', '1\.0601', '1\.1221'],
     category: verguetung, weldable: nein, hardenable: [qt],
     note: 'C-Gehalt 0,6 %: schmelzschweißen praktisch nicht zulässig', density: 7.85, max_hrc: 62}
  - {name: 25CrMo4, patterns: ['25\s*CrMo\s*4', '1\.7218'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr], density: 7.85, max_hrc: 50}
  - {name: 42CrMo4, patterns: ['42\s*CrMo\s*4(?:\s*\+QT)?', '1\.7225'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr],
     note: 'Schweißen nur mit Vorwärmung/Nachbehandlung', density: 7.85, max_hrc: 55}
  - {name: 34CrNiMo6, patterns: ['34\s*CrNiMo\s*6', '1\.6582'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr], density: 7.85, max_hrc: 55}
  - {name: 30CrNiMo8, patterns: ['30\s*CrNiMo\s*8', '1\.6580'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr], density: 7.85, max_hrc: 55}
  - {name: 51CrV4 (Federstahl), patterns: ['51\s*CrV\s*4', '1\.8159'],
     category: verguetung, weldable: nein, hardenable: [qt],
     note: 'Federstahl: schmelzschweißen nicht üblich/zulässig', density: 7.85, max_hrc: 58}
  - {name: 100Cr6 (Wälzlagerstahl), patterns: ['100\s*Cr\s*6', '1\.3505'],
     category: verguetung, weldable: nein, hardenable: [qt],
     note: 'Wälzlagerstahl: nicht schweißgeeignet', density: 7.85, max_hrc: 65}
  - {name: 'AISI 4140 (≈42CrMo4)', patterns: ['(?:AISI|SAE)\s*4140', '4140\s*(?:HT|PH)'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr], density: 7.85, max_hrc: 55}
  # ========================== Einsatzstähle ===============================
  - {name: C15, patterns: ['\bC15(?:E|R)?\b', '1\.0401'],
     category: einsatz, weldable: ja, hardenable: [case], zinc: true, density: 7.85, max_hrc: 62}
  - {name: 16MnCr5, patterns: ['16\s*MnCr\s*5', '1\.7131'],
     category: einsatz, weldable: bedingt, hardenable: [case, qt], density: 7.85, max_hrc: 62}
  - {name: 20MnCr5, patterns: ['20\s*MnCr\s*5', '1\.7147'],
     category: einsatz, weldable: bedingt, hardenable: [case, qt], density: 7.85, max_hrc: 62}
  - {name: 18CrNiMo7-6, patterns: ['18\s*CrNiMo\s*7-?6', '1\.6587'],
     category: einsatz, weldable: bedingt, hardenable: [case], density: 7.85, max_hrc: 62}
  - {name: 'AISI 1018', patterns: ['(?:AISI|SAE)\s*1018', '\bC1018\b'],
     category: einsatz, weldable: ja, hardenable: [case], zinc: true, density: 7.85, max_hrc: 60}
  # ======================== Nitrierstähle =================================
  - {name: 31CrMoV9, patterns: ['31\s*CrMoV\s*9', '1\.8519'],
     category: verguetung, weldable: bedingt, hardenable: [qt, nitr], density: 7.85, max_hrc: 70}
  # ========================= Automatenstähle ==============================
  - {name: 11SMnPb30, patterns: ['11\s*SMnPb\s*30', '1\.0718'],
     category: automaten, weldable: nein, zinc: true,
     note: 'Automatenstahl (Pb/S): nicht schweißgeeignet', density: 7.85}
  - {name: 11SMn30, patterns: ['11\s*SMn\s*30', '9\s*SMn\s*28', '1\.0715'],
     category: automaten, weldable: nein, zinc: true,
     note: 'Automatenstahl (S): nicht schweißgeeignet', density: 7.85}
  - {name: 35S20, patterns: ['35\s*S\s*20\b', '1\.0726'],
     category: automaten, weldable: nein, hardenable: [qt], zinc: true, density: 7.85, max_hrc: 45}
  # ====================== Nichtrostende Stähle ============================
  - {name: '1.4301 (X5CrNi18-10)',
     patterns: ['1\.4301', 'X5CrNi18-?10', '\bV2A\b', 'AISI\s*304\b',
                '(?:\bSS|STAINLESS(?:\s*STEEL)?|\bSST)\s*304', '\b304\s*SS\b', '\b18-8\b'],
     category: nirosta, weldable: ja, density: 7.9}
  - {name: '1.4307 (X2CrNi18-9)', patterns: ['1\.4307', 'X2CrNi18-?9', 'AISI\s*304L'],
     category: nirosta, weldable: ja, density: 7.9}
  - {name: '1.4404 (X2CrNiMo17-12-2)',
     patterns: ['1\.4404', 'X2CrNiMo17-?12-?2', '\bV4A\b', 'AISI\s*316L?\b',
                '(?:\bSS|STAINLESS(?:\s*STEEL)?)\s*316L?', '\b316L?\s*SS\b'],
     category: nirosta, weldable: ja, density: 7.9}
  - {name: '1.4571 (mit Ti)', patterns: ['1\.4571', 'X6CrNiMoTi17-?12-?2'],
     category: nirosta, weldable: ja, density: 7.9}
  - {name: '1.4305 (X8CrNiS18-9)', patterns: ['1\.4305', 'X8CrNiS18-?9', 'AISI\s*303\b'],
     category: nirosta_auto, weldable: nein,
     note: 'Automaten-Edelstahl (S-legiert): nicht schweißgeeignet – bei Schweißteilen 1.4301/1.4404 verwenden', density: 7.9}
  - {name: '1.4104 (Automat, martensitisch)', patterns: ['1\.4104', 'X14CrMoS17'],
     category: nirosta_auto, weldable: nein, hardenable: [qt], density: 7.9}
  - {name: '1.4057 (martensitisch)', patterns: ['1\.4057', 'X17CrNi16-?2'],
     category: nirosta, weldable: bedingt, hardenable: [qt], density: 7.9, max_hrc: 50}
  - {name: '1.4034/1.4021 (Messerstahl)', patterns: ['1\.4034', '1\.4021', 'X46Cr13', 'X20Cr13'],
     category: nirosta, weldable: bedingt, hardenable: [qt], density: 7.9, max_hrc: 56}
  - {name: '1.4310 (Federband)', patterns: ['1\.4310', 'X10CrNi18-?8'],
     category: nirosta, weldable: bedingt, density: 7.9, max_hrc: 45}
  - {name: '1.4462 (Duplex)', patterns: ['1\.4462', 'X2CrNiMoN22-?5-?3'],
     category: nirosta, weldable: ja, density: 7.9}
  # ========================== Gusswerkstoffe ==============================
  - {name: EN-GJL (Grauguss), patterns: ['EN[-\s]?GJL[-\s]?\d{3}', '\bGG[-\s]?[123][05]\b'],
     category: guss, weldable: nein, castable: true,
     note: 'Grauguss: Schmelzschweißen nicht zulässig (nur Sonderverfahren)', density: 7.2}
  - {name: EN-GJS (Sphäroguss), patterns: ['EN[-\s]?GJS[-\s]?\d{3}(?:[-\s]?\d{1,2})?', '\bGGG[-\s]?[4-7]0\b'],
     category: guss, weldable: bedingt, castable: true,
     note: 'Sphäroguss: Schweißen nur als qualifiziertes Sonderverfahren', density: 7.1}
  - {name: EN-GJMW/GJMB (Temperguss), patterns: ['EN[-\s]?GJM[WB][-\s]?\d{3}'],
     category: guss, weldable: bedingt, castable: true, density: 7.3}
  - {name: GS (Stahlguss), patterns: ['\bGS[-\s]?\d{2}\b', 'G20Mn5', '1\.6220', 'GE\s*240'],
     category: stahlguss, weldable: ja, castable: true, hardenable: [qt], density: 7.85}
  - {name: EN AC-AlSi10Mg/AlSi12, patterns: ['EN\s*AC[-\s]?4\d{4}', 'AlSi10Mg', 'AlSi12(?:Cu)?', 'AlSi9Cu3'],
     category: alu, weldable: bedingt, castable: true, anodize_quality: schlecht,
     note: 'Si-haltige Gusslegierung: Eloxalschicht wird grau/fleckig, dekoratives Eloxieren ungeeignet', density: 2.65}
  # =================== Aluminium-Knetlegierungen ==========================
  - {name: EN AW-5083 (AlMg4,5Mn), patterns: ['EN\s*AW[-\s]?5083', 'AlMg4[.,]5Mn', '3\.3547'],
     category: alu, weldable: ja, anodize: true, density: 2.7}
  - {name: EN AW-5754 (AlMg3), patterns: ['EN\s*AW[-\s]?5754', 'AlMg3\b', '3\.3535'],
     category: alu, weldable: ja, anodize: true, density: 2.67}
  - {name: AA 5052, patterns: ['\b5052[-\s]?[HO]\d{0,2}\b', 'ALUMIN\w*\s*5052'],
     category: alu, weldable: ja, anodize: true, density: 2.68}
  - {name: EN AW-6060/6063, patterns: ['EN\s*AW[-\s]?606[03]', 'AlMgSi0[,.]5', '3\.3206'],
     category: alu, weldable: ja, anodize: true, density: 2.7}
  - {name: AA 6061-T6, patterns: ['\b6061[-\s]?T\d{1,2}\b', 'ALUMIN\w*\s*6061', '\bAL\s*6061\b'],
     category: alu, weldable: ja, anodize: true, density: 2.7}
  - {name: EN AW-6082, patterns: ['EN\s*AW[-\s]?6082', 'AlSi1MgMn', 'AlMgSi1\b', '3\.2315'],
     category: alu, weldable: ja, anodize: true, density: 2.7}
  - {name: EN AW-7075, patterns: ['EN\s*AW[-\s]?7075', 'AlZn5[,.]5MgCu', '3\.4365',
                                  '\b7075[-\s]?T\d{1,2}\b', 'ALUMIN\w*\s*7075'],
     category: alu, weldable: nein, anodize: true, anodize_quality: bedingt,
     note: '7075: schmelzschweißen nicht zulässig (Heißrissneigung); Eloxal nur technisch, dekorativ eingeschränkt', density: 2.81}
  - {name: EN AW-2007/2024, patterns: ['EN\s*AW[-\s]?20(?:07|24)', 'AlCu4\w*', '3\.1645'],
     category: alu, weldable: nein, anodize: true, anodize_quality: schlecht,
     note: 'AlCu-Legierungen: nicht schmelzschweißgeeignet; Cu-Anteil ergibt schlechte, fleckige Eloxalschicht – für Eloxalteile 5xxx/6xxx wählen', density: 2.78}
  # ============================ Magnesium =================================
  - {name: AZ91 (Mg-Druckguss), patterns: ['\bAZ91\w?\b', '\bAZ31\b', '3\.5[12]\d{2}'],
     category: magnesium, weldable: bedingt, castable: true,
     note: 'Magnesium: Brandgefahr bei Bearbeitung, Schweißen nur Sonderverfahren', density: 1.81}
  # ============================= Titan ====================================
  - {name: Titan Grade 2, patterns: ['3\.7035', 'Ti\s*(?:Gr(?:ade)?\.?\s*2)\b', 'TITANIUM\s*(?:GRADE\s*)?2\b'],
     category: titan, weldable: ja,
     note: 'Schweißen nur unter Schutzgas-Vollabdeckung', density: 4.51}
  - {name: Titan Grade 5 (Ti6Al4V), patterns: ['3\.7165', 'Ti[-\s]?6Al[-\s]?4V', 'TITANIUM\s*(?:GRADE\s*)?5\b'],
     category: titan, weldable: bedingt,
     note: 'Ti6Al4V: Schweißen nur mit qualifiziertem Verfahren', density: 4.43, max_hrc: 41}
  # ========================= Kupferwerkstoffe =============================
  - {name: CuZn39Pb3 (Automatenmessing), patterns: ['CuZn39Pb3', '2\.0401', '\bMs58\b', '\bC360\b|BRASS\s*360'],
     category: kupfer, weldable: nein,
     note: 'Bleihaltiges Messing: nicht schweißgeeignet', density: 8.47}
  - {name: CuZn37, patterns: ['CuZn37\b', '2\.0321'], category: kupfer, weldable: bedingt, density: 8.44}
  - {name: Cu-ETP (C110), patterns: ['COPPER\s*C?11000|COPPER\s*C?110\b|\bC110\b', 'CU[-\s]?ETP', '2\.0065'],
     category: kupfer, weldable: bedingt, density: 8.9}
  - {name: CuSn8 (Bronze), patterns: ['CuSn[68]\b', '2\.1030'], category: kupfer, weldable: bedingt, density: 8.8}
  - {name: CuAl10Ni (Alu-Bronze), patterns: ['CuAl10(?:Ni|Fe)\w*', '2\.0966'],
     category: kupfer, weldable: bedingt, density: 7.6}
  # ================== Kunststoffe / Verbundwerkstoffe =====================
  - {name: PA6/PA66, patterns: ['\bPA\s*6(?:\.6|6)?(?:\s*GF\d{2})?\b'], category: kunststoff, weldable: nein, density: 1.14}
  - {name: POM, patterns: ['\bPOM(?:[-\s]?C|[-\s]?H)?\b', '\bDELRIN\b'], category: kunststoff, weldable: nein, density: 1.41}
  - {name: PTFE, patterns: ['\bPTFE\b', '\bTEFLON\b'], category: kunststoff, weldable: nein, density: 2.2}
  - {name: PE-HD/UHMW, patterns: ['\bPE[-\s]?(?:HD|1000|500)\b', '\bUHMW(?:[-\s]?PE)?\b', '\bHDPE\b'],
     category: kunststoff, weldable: nein, density: 0.95}
  - {name: PEEK, patterns: ['\bPEEK\b'], category: kunststoff, weldable: nein, density: 1.32}
  - {name: PC (Polycarbonat), patterns: ['\bPOLYCARBONATE?\b', 'MAKROLON'], category: kunststoff, weldable: nein, density: 1.2}
  - {name: PMMA, patterns: ['\bPMMA\b', 'PLEXIGLAS'], category: kunststoff, weldable: nein, density: 1.18}
  - {name: PVC, patterns: ['\bPVC(?:[-\s]?U)?\b'], category: kunststoff, weldable: nein, density: 1.4}
  - {name: ABS, patterns: ['\bABS\b(?!\s*\d)'], category: kunststoff, weldable: nein, density: 1.05}
  - {name: PET-P, patterns: ['\bPET(?:[-\s]?P)?\b(?!\s*\d)'], category: kunststoff, weldable: nein, density: 1.38}
  - {name: G10/FR4 (Glasfaserverbund), patterns: ['\bG-?10\b(?:\s*FIBERGLASS)?', '\bFR-?4\b'],
     category: verbund, weldable: nein, density: 1.85}
  - {name: CFK/GFK, patterns: ['\bCFK\b', '\bGFK\b', 'CARBON\s*FIBER', '\bCFRP\b'],
     category: verbund, weldable: nein, density: 1.6}
""",
    "norms.yaml": r"""# Normen-Wissenspaket
#
# obsolete: zurückgezogene oder ersetzte Normen. Jeder Eintrag:
#   pattern:  Regex auf den Zeichnungstext (case-insensitive)
#   message:  Meldung im Finding (was gilt stattdessen)
#
# Massenimport: Export aus der Normenverwaltung (Nautos/Perinorm, Spalten
# "Dokumentnummer;Status;Nachfolger") mit tools/import_norms_csv.py
# konvertieren. Zusätzliche Pakete: jede weitere Datei norms*.yaml in
# diesem Ordner (z. B. norms_firma.yaml) wird automatisch mitgeladen.

obsolete:
  # --- Oberflächen --------------------------------------------------------
  - {pattern: 'ISO\s*1302\b',
     message: 'ISO 1302 wurde durch ISO 21920-1 ersetzt'}
  - {pattern: '\bISO\s*4287\b',
     message: 'ISO 4287 (Rauheitskenngrößen) wurde durch ISO 21920-2 ersetzt'}
  - {pattern: '\bISO\s*4288\b',
     message: 'ISO 4288 (Rauheitsmessung) wurde durch ISO 21920-3 ersetzt'}
  - {pattern: 'DIN\s*4768\b',
     message: 'DIN 4768 ist zurückgezogen – Rauheit nach ISO 21920'}
  - {pattern: 'DIN\s*4766\b',
     message: 'DIN 4766 ist zurückgezogen – erreichbare Rauheiten nach ISO 21920'}
  - {pattern: 'DIN\s*3141\b',
     message: 'DIN 3141 (Oberflächendreiecke) ist zurückgezogen – ISO 21920 verwenden'}
  # --- Kanten -------------------------------------------------------------
  - {pattern: 'DIN\s*6784\b',
     message: 'DIN 6784 wurde durch ISO 13715 ersetzt'}
  # --- Toleranzen / GPS ---------------------------------------------------
  - {pattern: 'DIN\s*7168\b',
     message: 'DIN 7168 ist zurückgezogen – Allgemeintoleranzen nach ISO 2768/ISO 22081'}
  - {pattern: 'DIN\s*7184\b',
     message: 'DIN 7184 (Form-/Lagetoleranzen) ist zurückgezogen – ISO 1101 verwenden'}
  - {pattern: '\bEN\s*22768\b',
     message: 'EN 22768 ist die alte Nummerierung – heute ISO 2768 (bzw. ISO 22081) zitieren'}
  - {pattern: 'DIN\s*(?:ISO\s*)?1101\s*:\s*(?:19|200)\d',
     message: 'Veralteter Ausgabestand der ISO 1101 referenziert'}
  # --- Zeichnungswesen ----------------------------------------------------
  - {pattern: 'DIN\s*6771\b',
     message: 'DIN 6771 (Schriftfelder) ist zurückgezogen – ISO 7200 verwenden'}
  - {pattern: 'DIN\s*406[-\s]?1[01]?\b',
     message: 'DIN 406 (Maßeintragung) ist zurückgezogen – ISO 129-1 verwenden'}
  - {pattern: '\bDIN\s*15\b(?!\d)',
     message: 'DIN 15 (Linien) ist zurückgezogen – ISO 128 verwenden'}
  # --- Schweißen ----------------------------------------------------------
  - {pattern: 'DIN\s*8570\b',
     message: 'DIN 8570 wurde durch ISO 13920 ersetzt (Allgemeintoleranzen Schweißkonstruktionen)'}
  - {pattern: 'DIN\s*8551\b',
     message: 'DIN 8551 (Schweißnahtvorbereitung) ist zurückgezogen – ISO 9692 verwenden'}
  - {pattern: 'DIN\s*8563\b',
     message: 'DIN 8563 (Schweißnahtgüte) ist zurückgezogen – ISO 5817 verwenden'}
  # --- Guss ---------------------------------------------------------------
  - {pattern: 'DIN\s*1680\b',
     message: 'DIN 1680 (Gussrohteile Allgemeintoleranzen) ist zurückgezogen – ISO 8062 verwenden'}
  - {pattern: 'DIN\s*1683\b|DIN\s*1684\b|DIN\s*1685\b|DIN\s*1686\b|DIN\s*1687\b',
     message: 'DIN 1683ff (Gusstoleranzen) sind zurückgezogen – ISO 8062-3 verwenden'}
  - {pattern: 'ISO\s*8062\s*:\s*1994',
     message: 'ISO 8062:1994 ist ersetzt – aktuelle Reihe ISO 8062-3 zitieren'}
  # --- Gewinde / Verbindungselemente --------------------------------------
  - {pattern: 'DIN\s*13\s*T(?:eil)?\s*\d',
     message: 'DIN 13 Teilausgaben veraltet – aktuelle DIN 13-Reihe/ISO 261 prüfen'}
  - {pattern: '\bDIN\s*931\b|\bDIN\s*933\b',
     message: 'DIN 931/933 sind durch ISO 4014/4017 ersetzt (zulässig, aber ISO bevorzugen)'}
  - {pattern: '\bDIN\s*912\b',
     message: 'DIN 912 ist durch ISO 4762 ersetzt (zulässig, aber ISO bevorzugen)'}
""",
    "profiles.yaml": r"""# Regelprofile je Materialgruppe.
#
# Jede Regel: enabled + severity (info|warning|error|blocker) + optionale Parameter.
# Profile können mit `inherit` von anderen erben und einzelne Regeln überschreiben.
# Prüf-Philosophie: Was auf der Zeichnung nicht sicher entscheidbar ist, wird als
# "nicht nachweisbar" (warning) gemeldet, nicht fälschlich als harter Fehler.

profiles:
  default:
    # Toleranzband für den Geometrieabgleich STEP vs. Zeichnungsmaße.
    # rel: relative Abweichung, abs: absolute Abweichung in mm (das Größere zählt).
    step_tolerance: {rel: 0.05, abs: 2.0}
    params:
      # Maximal plausibles Einzelmaß in mm (größere Zahlen sind keine Maße).
      max_plausible_dim: 6000
      # Höchstzahl markierter Sprach-Findings im Bild (Rest wird aggregiert).
      max_language_markers: 12
      # Masseabgleich Zeichnung vs. Modell (Prozent Abweichung).
      mass_warn_pct: 15
      mass_error_pct: 40
      # Durchmessertoleranz beim Bohrbildabgleich (mm).
      hole_dia_tol: 0.6
      thread_core_tol: 0.8
      unit_ratio_tol: 0.06       # Toleranz beim Zoll/mm-Verhältnis
      scale_tol: 0.15            # Ansicht vs. Maßtext (Maßstabsprüfung)
      view_model_tol: 0.2        # Ansicht vs. Modell-Bounding-Box
      hardness_reserve_hrc: 2    # Zuschlag auf die Werkstoff-Härtegrenze
      # Bemaßung / Fertigung
      chain_epsilon: 0.05        # Toleranz beim Maßketten-Summenvergleich (mm)
      chain_line_tol: 8.0        # max. Versatz quer zur Maßlinie (PDF-Punkte)
      tight_tol_mm: 0.01         # ab hier gilt eine Toleranz als sehr eng
      tight_tol_it: 5            # bzw. ab diesem IT-Grad
      max_tight_tol_markers: 5
      deep_hole_ratio: 5.0       # Tiefe/Durchmesser
      fine_ra_limit: 0.4         # Ra darunter braucht Feinbearbeitung
    rules:
      # --- Schriftfeld / Title Block (ISO 7200) --------------------------------
      TB.DRAWNO:    {enabled: true, severity: error,
                     keywords: ["Zeichnungsnummer", "Zeichn.-Nr", "Drawing no", "Drawing number", "Document no", "Dokumentennr", "DWG NO", "DWG. NO"]}
      TB.MATERIAL:  {enabled: true, severity: error,
                     keywords: ["Werkstoff", "Material"]}
      TB.SCALE:     {enabled: true, severity: error,
                     keywords: ["Maßstab", "Scale"]}
      TB.WEIGHT:    {enabled: true, severity: warning,
                     keywords: ["Gewicht", "Weight", "Mass"]}
      TB.REVISION:  {enabled: true, severity: warning,
                     keywords: ["Änderung", "Revision", "Rev.", "Index", "Issue"]}
      TB.APPROVAL:  {enabled: true, severity: warning,
                     keywords: ["Freigabe", "Freigegeben", "Approved", "Released", "Geprüft", "Checked"]}
      # --- Toleranzen und GPS --------------------------------------------------
      GT.GENERAL_TOL: {enabled: true, severity: error}    # ISO 2768 / ISO 22081
      GT.PRINCIPLE:   {enabled: true, severity: warning}  # ISO 8015 / Tolerierungsgrundsatz
      GPS.DATUM:      {enabled: true, severity: error}    # Lagetoleranz ohne Bezug
      GPS.FORM_WITH_DATUM:   {enabled: true, severity: error}   # Formtoleranz MIT Bezug (Widerspruch)
      GPS.DEPRECATED_SYMBOL: {enabled: true, severity: warning} # ◎/⌯ (ASME 2018 gestrichen)
      GPS.ENVELOPE:        {enabled: true, severity: warning}  # Passung ohne Hüllbedingung Ⓔ
      GPS.DATUM_UNDEFINED: {enabled: true, severity: error}    # Bezug referenziert, nicht definiert
      GPS.DATUM_UNUSED:    {enabled: true, severity: warning}  # Bezug definiert, nie verwendet
      GPS.POSITION_NO_TED: {enabled: true, severity: warning}  # Position ohne theoretisch genaue Maße
      GPS.MOD_ON_FORM:     {enabled: true, severity: error}    # Ⓜ/Ⓛ an Formtoleranz
      GPS.ZONE_NO_DATUM:   {enabled: true, severity: error}    # ⌀-Toleranzzone ohne Bezug
      DOC.GDT_GRAPHIC:     {enabled: true, severity: info}     # GD&T nur als Grafik lesbar
      # --- Bemaßung und Fertigungsgerechtigkeit -------------------------------
      DIM.CHAIN:           {enabled: true, severity: warning}  # geschlossene Maßkette
      MFG.TIGHT_TOL:       {enabled: true, severity: warning}  # Kostentreiber enge Toleranz
      MFG.DEEP_HOLE:       {enabled: true, severity: warning}  # Tiefe/Durchmesser > 5
      MFG.SHARP_CORNER:    {enabled: true, severity: warning}  # R0 / scharfe Innenecke
      SURF.UNREALISTIC:       {enabled: true, severity: error}   # Ra feiner als Verfahren liefert
      SURF.UNREALISTIC_MINOR: {enabled: true, severity: warning} # sehr feine Ra ohne Verfahren
      # --- Oberflächen und Kanten ---------------------------------------------
      SURF.ROUGHNESS: {enabled: true, severity: warning}  # Ra/Rz bzw. ISO 21920/1302
      SURF.EDGES:     {enabled: true, severity: warning}  # ISO 13715
      # --- Darstellung ---------------------------------------------------------
      VIEW.PROJECTION: {enabled: true, severity: warning} # Projektionsmethode nachweisbar?
      VIEW.UNIT:       {enabled: true, severity: warning} # Einheit mm deklariert
      # --- Sprache (internationaler Einkauf) ----------------------------------
      LANG.GERMAN:  {enabled: true, severity: error}
      # --- Kontextregeln Schweißen / Guss -------------------------------------
      WELD.QUALITY: {enabled: true, severity: error}      # Schweißkontext ohne ISO 5817
      CAST.TOL:     {enabled: true, severity: error}      # Gusskontext ohne ISO 8062
      # --- Werkstoff und fachliche Widersprüche -------------------------------
      MAT.MISSING:          {enabled: true, severity: error}   # kein Werkstoff angegeben
      MAT.UNKNOWN:          {enabled: true, severity: warning} # Label da, Bezeichnung nicht erkannt
      MAT.WELD_CONFLICT:    {enabled: true, severity: error}   # nicht schweißgeeignet + Schweißangaben
      MAT.WELD_LIMITED:     {enabled: true, severity: warning} # nur bedingt schweißgeeignet
      MAT.HT_CONFLICT:      {enabled: true, severity: error}   # Wärmebehandlung passt nicht zum Werkstoff
      MAT.COATING_CONFLICT: {enabled: true, severity: error}   # Verzinken/Eloxieren fachlich unsinnig
      MAT.CAST_CONFLICT:    {enabled: true, severity: warning} # Gusskontext ohne Gusswerkstoff
      MAT.ANODIZE_ALLOY:    {enabled: true, severity: error}   # Legierung zum Eloxieren ungeeignet
      MAT.ANODIZE_LIMITED:  {enabled: true, severity: warning} # nur bedingt eloxierbar
      PROC.STUD_ON_ZINC:    {enabled: true, severity: error}   # Schweißbolzen auf verzinktem Teil
      PROC.WELD_ZINC_ORDER: {enabled: true, severity: warning} # Reihenfolge Schweißen/Verzinken fehlt
      COAT.FIT:             {enabled: true, severity: warning} # Beschichtung + Passung/Gewinde ohne Freihaltevermerk
      WELD.MIXED:           {enabled: true, severity: error}   # Alu + Stahl geschweißt
      WELD.MIXED_FILLER:    {enabled: true, severity: warning} # Schwarz-Weiß ohne 309L-Angabe
      NORM.WELD_GENTOL:     {enabled: true, severity: warning} # Schweißteil nur mit ISO 2768 (13920 fehlt)
      THRD.FIT_CLASS:       {enabled: true, severity: error}   # "M12 H7" statt 6H/6g
      NORM.MATERIAL_MISMATCH: {enabled: true, severity: error} # z. B. ISO 5817 bei Aluminium
      NORM.OBSOLETE:        {enabled: true, severity: warning} # zurückgezogene/ersetzte Norm
      DOC.BALLOONS:         {enabled: true, severity: warning} # Stückliste ohne Positionsballone
      # --- Verfahrensspezifische Vollständigkeit ------------------------------
      WELD.NO_SIZE:    {enabled: true, severity: error}    # Schweißnaht ohne a-/z-Maß
      WELD.AZ_MIXED:   {enabled: true, severity: warning}  # a- und z-Maße gemischt
      WELD.NO_PREP:    {enabled: true, severity: warning}  # Stumpfnaht ohne ISO 9692
      CAST.NO_DRAFT:   {enabled: true, severity: warning}  # Guss ohne Formschrägen
      CAST.NO_RMA:     {enabled: true, severity: warning}  # Guss ohne Bearbeitungszugabe
      SHEET.NO_THICK:  {enabled: true, severity: error}    # Blechteil ohne Blechdicke
      SHEET.NO_RADIUS: {enabled: true, severity: warning}  # Abkantung ohne Biegeradius
      HT.NO_HARDNESS:  {enabled: true, severity: warning}  # Wärmebehandlung ohne Härtewert
      HT.NO_DEPTH:     {enabled: true, severity: warning}  # Randschichthärten ohne Eht/CHD
      HT.HARDNESS_LIMIT: {enabled: true, severity: error}  # Härte über Werkstoffgrenze
      COAT.EMBRITTLEMENT: {enabled: true, severity: error}  # galvanisch auf hochfest ohne Entsprödung
      # --- Bemaßungswidersprüche ------------------------------------------------
      DIM.TOL_ORDER:   {enabled: true, severity: error}    # Grenzabmaße vertauscht
      DIM.BASIC_TOL:   {enabled: true, severity: error}    # TED-Maß zusätzlich toleriert
      SURF.TOL_MISMATCH: {enabled: true, severity: warning, max_ratio: 0.5}
      THRD.DEPTH:      {enabled: true, severity: error}    # Gewinde tiefer als die Bohrung
      THRD.SHORT:      {enabled: true, severity: warning}  # Einschraubtiefe unter 1xD
      # --- Masse-Plausibilität (ohne STEP prüfbar) ------------------------------
      MASS.IMPOSSIBLE: {enabled: true, severity: error}    # schwerer als der Hüllquader
      MASS.TOO_LIGHT:  {enabled: true, severity: warning}  # Füllgrad unter 1 %
      MASS.DENSITY_HINT: {enabled: true, severity: warning} # Gewicht passt zu anderem Werkstoff
      # --- Dokumenten-Formalien -------------------------------------------------
      DOC.SHEET_COUNT: {enabled: true, severity: error}    # Blatt 1 von 3, geliefert 1
      DOC.ANNOTATIONS: {enabled: true, severity: warning}  # nachträgliche PDF-Markierungen
      DOC.DATE_FUTURE: {enabled: true, severity: warning}  # Datum in der Zukunft
      DOC.DECIMAL_MIXED: {enabled: true, severity: warning, min_count: 3}
      # --- Internationale Beschaffung -------------------------------------------
      PUR.VAGUE_SPEC:   {enabled: true, severity: warning, max_findings: 4}
      PUR.INTERNAL_NORM: {enabled: true, severity: warning}
      PUR.STOCK_SIZE:   {enabled: true, severity: info}
      # --- Konsistenz ----------------------------------------------------------
      CONS.MATNO:   {enabled: true, severity: warning}    # Materialnummer auf Zeichnung
      # --- Paket / Geometrie ---------------------------------------------------
      DOC.NO_PDF:     {enabled: true, severity: blocker}
      DOC.MULTI_PDF:  {enabled: true, severity: info}
      DOC.NO_STEP:    {enabled: true, severity: info}
      DOC.OCR:        {enabled: true, severity: warning}
      DOC.NO_TEXT:    {enabled: true, severity: warning}
      GEO.MISMATCH:   {enabled: true, severity: blocker}
      GEO.UNCERTAIN:  {enabled: true, severity: warning}
      GEO.NO_DIMS:    {enabled: true, severity: warning}
      # Vertiefte Geometrie: Masse, Bohrbild, Gewinde
      GEO.MASS:        {enabled: true, severity: error}    # Gewicht vs. Volumen×Dichte
      GEO.MASS_MINOR:  {enabled: true, severity: warning}  # moderate Massenabweichung
      GEO.HOLE_COUNT:  {enabled: true, severity: error}    # 4×⌀18 fehlt im Modell
      GEO.HOLE_COUNT_MINOR: {enabled: true, severity: warning}
      GEO.THREAD:      {enabled: true, severity: warning}  # Gewinde ohne Kernloch
      GEO.UNIT_MISMATCH:   {enabled: true, severity: error}   # Zoll/mm verwechselt
      GEO.ASSEMBLY:        {enabled: true, severity: error}   # Baugruppe statt Einzelteil
      GEO.ASSEMBLY_MINOR:  {enabled: true, severity: warning}
      GEO.NOT_FUSED:       {enabled: true, severity: info}     # Körper nicht verschmolzen
      # Spiegelprüfung: falsche Hand gespeichert (nur über die Kontur
      # erkennbar – Hüllmaße, Masse und Bohrbild sind identisch).
      GEO.MIRROR:          {enabled: true, severity: error, min_score: 0.5,
                            min_abstand: 0.15}
      # Maßstabsbasierte Prüfungen: standardmäßig AUS.
      # Viele CAD-Systeme führen im Schriftfeld den Blattmaßstab, einzelne
      # Ansichten haben aber eigene Maßstäbe (Detail-/Schnittansichten).
      # Wo die Zeichnungsnorm einen einheitlichen Maßstab vorschreibt, sind
      # beide Regeln wertvoll – dann hier einschalten. Die gemessene
      # Ansichtsgröße erscheint unabhängig davon in den Vergleichswerten.
      GEO.VIEW_SIZE:       {enabled: false, severity: warning} # gemessene Ansicht vs. Modell
      SCALE.MISMATCH:      {enabled: false, severity: warning} # Zeichnung nicht maßstäblich
      # Ausbaustufe: Konturprojektion (STEP-Silhouetten vs. PDF-Ansichten).
      # Schärft das Maß-Urteil (bestätigt "unsicher" bzw. stuft "passt" bei
      # klarem Widerspruch herab). Bei Bedarf hier abschaltbar.
      GEO.CONTOUR:    {enabled: true, severity: warning}

  # Gussteile: Rohteil vs. Fertigteil-STEP weicht systematisch ab (Zugaben,
  # Formschrägen) -> großzügigeres Toleranzband, Abweichung nur "warning".
  guss:
    inherit: default
    step_tolerance: {rel: 0.12, abs: 6.0}
    params:
      mass_warn_pct: 25
      mass_error_pct: 60
    rules:
      GEO.MISMATCH: {enabled: true, severity: warning}
      CAST.TOL:     {enabled: true, severity: error}

  # Schweißbaugruppen: Verzug/Nahtaufbau -> ebenfalls großzügiger.
  schweiss:
    inherit: default
    step_tolerance: {rel: 0.08, abs: 4.0}
    params:
      mass_warn_pct: 20
      mass_error_pct: 50
    rules:
      GEO.MISMATCH: {enabled: true, severity: warning}
      WELD.QUALITY: {enabled: true, severity: error}
""",
}


# ========================================================================
# kern
# ========================================================================
# Kernbausteine: Datenmodelle, Paketzugriff, Laufzustand, Haushalt.
#
# Vier kleine Bausteine, die alles andere benutzt - deshalb liegen sie in
# einem Modul: was ein Finding ist, wie ein YMATDOCS-Paket ausgepackt wird,
# wo ein unterbrochener Lauf weitermacht, und wie man Speicher und Platte
# wieder freibekommt.
# ======================================================================
# models
# ======================================================================
# Zentrale Datenmodelle des Drawing Checkers.



import enum
import time
from dataclasses import dataclass, field
from pathlib import Path


class Severity(enum.IntEnum):
    """Schwere eines Findings. Reihenfolge = Sortierung (schwerstes zuerst)."""

    INFO = 0      # Hinweis, keine Beanstandung (z. B. "kein STEP vorhanden")
    WARNING = 1   # "nicht nachweisbar" / Plausibilität, manuell nachsehen
    ERROR = 2     # Klare Beanstandung (fehlende Pflichtangabe, deutsche Beschriftung)
    BLOCKER = 3   # K.O.: Geometrie passt nicht / falsche Zeichnung im Paket


SEVERITY_LABEL = {
    Severity.INFO: "Hinweis",
    Severity.WARNING: "Prüfen",
    Severity.ERROR: "Fehler",
    Severity.BLOCKER: "K.O.",
}


@dataclass
class BBox:
    """Achsparalleles Rechteck in PDF-Punkten (Ursprung oben links, PyMuPDF)."""

    x0: float
    y0: float
    x1: float
    y1: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)


@dataclass
class Finding:
    """Ein Prüfergebnis eines Checks.

    code: stabiler Regelcode (z. B. "TB.MATERIAL"), erscheint in Excel und Legende.
    bbox: Position auf der Zeichnung (PDF-Koordinaten); None = nur Legendeneintrag.
    page: 0-basierte PDF-Seite, auf die sich bbox bezieht.
    """

    code: str
    severity: Severity
    text: str
    bbox: BBox | None = None
    page: int = 0
    detail: str = ""


class JobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"                  # geprüft, keine Findings >= WARNING
    FINDINGS = "findings"      # geprüft, Findings vorhanden
    FAILED = "failed"          # Prüfung technisch fehlgeschlagen (nach Retries)
    SKIPPED = "skipped"        # ungültige Materialnummer o. ä.


@dataclass
class PackageContent:
    """Klassifizierter Inhalt eines YMATDOCS-ZIP-Pakets."""

    zip_path: Path | None = None
    work_dir: Path | None = None
    pdfs: list[Path] = field(default_factory=list)
    steps: list[Path] = field(default_factory=list)
    ignored: list[Path] = field(default_factory=list)

    @property
    def drawing_pdf(self) -> Path | None:
        """Das als Zeichnung ausgewählte PDF (Heuristik in core.package)."""
        return self.pdfs[0] if self.pdfs else None

    @property
    def step_file(self) -> Path | None:
        return self.steps[0] if self.steps else None


@dataclass
class MaterialResult:
    """Gesamtergebnis für eine Materialnummer (eine Excel-Zeile)."""

    material: str
    row: int                                   # 1-basierte Excel-Zeile
    status: JobStatus = JobStatus.PENDING
    findings: list[Finding] = field(default_factory=list)
    screenshot: Path | None = None             # annotiertes Zeichnungsbild
    error: str = ""                            # technischer Fehler bei FAILED
    step_summary: str = ""                     # Vergleichswerte STEP vs. Zeichnung
    duration_s: float = 0.0
    ocr_used: bool = False
    started_at: float = field(default_factory=time.time)
    # --- Prüfdokumentation (Pflichtspalten der Ergebnis-Excel) -------------
    checked_at: str = field(
        default_factory=lambda: time.strftime("%d.%m.%Y %H:%M"))
    drawing_rev_date: str = ""          # spätestes Datum auf der Zeichnung
    processes: list[str] = field(default_factory=list)  # Fertigungsverfahren

    @property
    def worst_severity(self) -> Severity | None:
        return max((f.severity for f in self.findings), default=None)

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (-int(f.severity), f.code))


@dataclass
class RunConfig:
    """Konfiguration eines Prüflaufs (aus GUI + config.yaml zusammengesetzt)."""

    excel_path: Path
    sheet_name: str
    material_column: str            # Spaltenbuchstabe, z. B. "C"
    header_row: int                 # 1-basierte Zeile der Überschriften
    output_dir: Path
    material_group: str = "default" # wählt Regel-/Toleranzprofil
    sap_connection: str = "P11"
    mock_source: Path | None = None # gesetzt => MockSapAdapter statt echtem SAP
    sap_flow: Path | None = None    # importierter .vbs-Ablauf (sonst Suchpfade)
    # Dauerlauf-Haushalt: entpackte Pakete nach der Prüfung löschen und
    # anhalten, bevor die Platte voll ist.
    keep_packages: bool = False     # True = Pakete zur Fehlersuche behalten
    min_free_mb: int = 500          # Sicherheitsreserve auf dem Laufwerk
    # Blockweise Abarbeitung: nach je `batch_size` Materialnummern wird ein
    # Zwischenstand gesichert (Excel, Zustand, Bericht), der Speicher
    # freigegeben und die SAP-Session aufgeräumt. 0 = alles am Stück.
    batch_size: int = 25
    batch_pause_s: float = 0.0      # optionale Atempause zwischen Blöcken
    max_sap_sessions: int = 5       # Obergrenze offener SAP-Fenster


# ======================================================================
# package
# ======================================================================
# Entpacken und Klassifizieren der YMATDOCS-ZIP-Pakete.
#
# YMATDOCS liefert je Materialnummer ein ZIP mit mindestens einem PDF
# (der Zeichnung), manchmal STEP-Dateien und manchmal nativen CAD-Daten,
# die ignoriert werden.



import logging
import re
import shutil
import zipfile
from pathlib import Path



PDF_EXT = {".pdf"}
STEP_EXT = {".stp", ".step", ".p21"}
# Native CAD- und Begleitformate, die bewusst ignoriert werden.
IGNORED_EXT = {
    ".catpart", ".catproduct", ".catdrawing", ".cgr",
    ".prt", ".asm", ".drw", ".sldprt", ".sldasm", ".slddrw",
    ".dwg", ".dxf", ".jt", ".tif", ".tiff", ".xml", ".txt", ".log",
}


class PackageError(Exception):
    """ZIP fehlt, ist leer oder nicht lesbar."""


def extract_package(zip_path: Path, work_dir: Path, material: str) -> PackageContent:
    """Entpackt das ZIP nach work_dir/<material>/ und klassifiziert den Inhalt."""
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise PackageError(f"ZIP-Paket fehlt oder ist leer: {zip_path}")

    target = work_dir / _safe_name(material)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Zip-Slip-Schutz: nur flache, bereinigte Dateinamen zulassen.
                name = Path(info.filename).name
                if not name or name.startswith("."):
                    continue
                dest = target / name
                with zf.open(info) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    except zipfile.BadZipFile as exc:
        raise PackageError(f"ZIP-Paket nicht lesbar: {zip_path} ({exc})") from exc

    content = classify_files(list(target.iterdir()), material)
    content.zip_path = zip_path
    content.work_dir = target
    log.info(
        "Paket %s: %d PDF, %d STEP, %d ignoriert",
        material, len(content.pdfs), len(content.steps), len(content.ignored),
    )
    return content


def classify_files(files: list[Path], material: str) -> PackageContent:
    content = PackageContent()
    for f in sorted(files):
        ext = f.suffix.lower()
        if ext in PDF_EXT:
            content.pdfs.append(f)
        elif ext in STEP_EXT:
            content.steps.append(f)
        else:
            content.ignored.append(f)

    # Bei mehreren PDFs: das wahrscheinlichste Zeichnungs-PDF nach vorn sortieren.
    if len(content.pdfs) > 1:
        content.pdfs.sort(key=lambda p: _drawing_score(p, material), reverse=True)
    return content


def _drawing_score(pdf: Path, material: str) -> tuple[int, int]:
    """Heuristik: Materialnummer im Dateinamen schlägt alles, dann Dateigröße."""
    stem = pdf.stem.lower()
    digits = re.sub(r"\D", "", material)
    hit = 1 if (material.lower() in stem or (digits and digits in stem)) else 0
    return (hit, pdf.stat().st_size)


def _safe_name(material: str) -> str:
    return re.sub(r"[^\w.-]", "_", material.strip()) or "unbenannt"


# ======================================================================
# state
# ======================================================================
# Persistenter Lauf-Zustand: macht jeden Lauf nach Absturz fortsetzbar.
#
# Nach jeder abgeschlossenen Materialnummer wird der Zustand atomar auf Platte
# geschrieben. "Fortsetzen" in der GUI lädt den Zustand und überspringt alles,
# was bereits einen Endstatus hat.



import json
import logging
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path



STATE_NAME = "lauf_zustand.json"


def finde_fortsetzbaren_lauf(config: RunConfig) -> tuple[Path, int, int] | None:
    """Sucht einen unfertigen Lauf, der zu DIESER Excel-Auswahl gehört.

    Früher wurde beim Fortsetzen einfach der neueste Lauf-Ordner genommen –
    das konnte den Lauf einer ganz anderen Materialgruppe fortsetzen.
    Verglichen werden deshalb Datei, Blatt und Spalte.

    Rückgabe: (Ordner, bereits geprüft, insgesamt bekannt) oder None.
    """
    basis = config.output_dir
    if not basis.is_dir():
        return None
    for ordner in sorted((p for p in basis.glob("lauf_*") if p.is_dir()),
                         reverse=True):
        try:
            data = json.loads((ordner / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cfg = data.get("config", {})
        if (Path(cfg.get("excel_path", "")) != config.excel_path
                or cfg.get("sheet_name") != config.sheet_name
                or cfg.get("material_column") != config.material_column):
            continue
        fertig = sum(1 for r in data.get("results", [])
                     if r.get("status") in ("ok", "findings", "skipped"))
        if fertig:
            return (ordner, fertig, len(data.get("results", [])))
    return None


class RunState:
    def __init__(self, config: RunConfig, run_dir: Path):
        self.config = config
        self.run_dir = run_dir
        self.results: dict[str, MaterialResult] = {}  # key: f"{row}:{material}"
        self.started = time.time()

    # ---------------------------------------------------------------- Zugriff
    @staticmethod
    def key(result: MaterialResult) -> str:
        return f"{result.row}:{result.material}"

    def is_done(self, row: int, material: str) -> bool:
        r = self.results.get(f"{row}:{material}")
        return r is not None and r.status in (
            JobStatus.OK, JobStatus.FINDINGS, JobStatus.SKIPPED
        )

    def record(self, result: MaterialResult) -> None:
        self.results[self.key(result)] = result
        self.save()

    # ------------------------------------------------------------ Persistenz
    @property
    def path(self) -> Path:
        return self.run_dir / STATE_NAME

    def save(self) -> None:
        data = {
            "version": 1,
            "started": self.started,
            "config": {
                "excel_path": str(self.config.excel_path),
                "sheet_name": self.config.sheet_name,
                "material_column": self.config.material_column,
                "header_row": self.config.header_row,
                "material_group": self.config.material_group,
                "sap_connection": self.config.sap_connection,
            },
            "results": [self._result_to_json(r) for r in self.results.values()],
        }
        # Atomar schreiben, damit ein Absturz mitten im Schreiben den
        # Zustand nicht zerstört.
        fd, tmp = tempfile.mkstemp(dir=self.run_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    @staticmethod
    def _result_to_json(r: MaterialResult) -> dict:
        d = asdict(r)
        d["status"] = r.status.value
        d["screenshot"] = str(r.screenshot) if r.screenshot else None
        for f, fd_ in zip(r.findings, d["findings"]):
            fd_["severity"] = int(f.severity)
        return d

    @classmethod
    def load(cls, config: RunConfig, run_dir: Path) -> "RunState":
        """Lädt einen früheren Zustand; fehlende/kaputte Datei => leerer Zustand."""
        state = cls(config, run_dir)
        try:
            data = json.loads((run_dir / STATE_NAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return state
        pass  # (im selben Modul)

        state.started = data.get("started", state.started)
        for rd in data.get("results", []):
            findings = [
                Finding(
                    code=f["code"],
                    severity=Severity(f["severity"]),
                    text=f["text"],
                    bbox=BBox(**f["bbox"]) if f.get("bbox") else None,
                    page=f.get("page", 0),
                    detail=f.get("detail", ""),
                )
                for f in rd.get("findings", [])
            ]
            result = MaterialResult(
                material=rd["material"],
                row=rd["row"],
                status=JobStatus(rd["status"]),
                findings=findings,
                screenshot=Path(rd["screenshot"]) if rd.get("screenshot") else None,
                error=rd.get("error", ""),
                step_summary=rd.get("step_summary", ""),
                duration_s=rd.get("duration_s", 0.0),
                ocr_used=rd.get("ocr_used", False),
                checked_at=rd.get("checked_at", ""),
                drawing_rev_date=rd.get("drawing_rev_date", ""),
                processes=list(rd.get("processes", [])),
            )
            state.results[cls.key(result)] = result
        log.info("Lauf-Zustand geladen: %d Ergebnisse", len(state.results))
        return state


# ======================================================================
# housekeeping
# ======================================================================
# Platten- und Aufräumverwaltung für lange Prüfläufe.
#
# Ein Lauf über eine ganze Materialgruppe holt hunderte ZIP-Pakete und
# entpackt sie. Ohne Aufräumen wächst der Ergebnisordner um mehrere
# Gigabyte, und der Lauf stirbt mitten in der Nacht an einer vollen Platte –
# mit einem Traceback, den niemand deuten kann.
#
# Deshalb:
#   * Nach jeder Materialnummer wird das entpackte Paket (und auf Wunsch das
#     ZIP) gelöscht. Gebraucht wird davon nichts mehr: annotiertes Bild,
#     Findings und Bericht liegen im Ergebnisordner.
#   * Vor jeder Materialnummer wird der freie Platz geprüft. Wird es eng,
#     räumt der Lauf zuerst selbst auf; hilft das nicht, hält er GEORDNET an,
#     statt unkontrolliert abzustürzen – das Ergebnis bis dahin bleibt
#     verwertbar und der Lauf ist fortsetzbar.



import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MIN_FREE_MB = 500


class DiskFull(Exception):
    """Zu wenig Platz, um den Lauf sinnvoll fortzusetzen."""


def free_mb(path: Path) -> float:
    """Freier Platz auf dem Laufwerk von `path` in MB (-1 = unbekannt)."""
    try:
        return shutil.disk_usage(path).free / (1024 * 1024)
    except OSError:
        return -1.0


def dir_size_mb(path: Path) -> float:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    return total / (1024 * 1024)


def cleanup_package(work_dir: Path | None, zip_path: Path | None,
                    keep: bool = False) -> float:
    """Entpackten Ordner und ZIP einer Materialnummer entfernen.

    Liefert die freigegebene Größe in MB. Mit `keep=True` bleibt alles
    liegen (Fehlersuche an einzelnen Paketen).
    """
    if keep:
        return 0.0
    freed = 0.0
    for target in (work_dir, zip_path):
        if target is None or not target.exists():
            continue
        try:
            if target.is_dir():
                freed += dir_size_mb(target)
                shutil.rmtree(target, ignore_errors=True)
            else:
                freed += target.stat().st_size / (1024 * 1024)
                target.unlink()
        except OSError as exc:
            log.warning("Aufräumen von %s fehlgeschlagen: %s", target, exc)
    return freed


def sweep_packages(package_dir: Path, keep_newest: int = 0) -> float:
    """Notaufräumen: alle (bis auf die neuesten) Pakete löschen."""
    if not package_dir.is_dir():
        return 0.0
    entries = sorted(package_dir.iterdir(),
                     key=lambda p: p.stat().st_mtime if p.exists() else 0,
                     reverse=True)
    freed = 0.0
    for entry in entries[keep_newest:]:
        freed += cleanup_package(entry if entry.is_dir() else None,
                                 None if entry.is_dir() else entry)
    return freed


@dataclass
class DiskGuard:
    """Wacht über den freien Platz während des Laufs."""

    package_dir: Path
    min_free_mb: float = DEFAULT_MIN_FREE_MB

    def check(self) -> str:
        """Vor jeder Materialnummer aufrufen.

        Liefert einen Hinweistext (leer = alles gut) oder wirft DiskFull,
        wenn auch nach dem Aufräumen zu wenig Platz bleibt.
        """
        free = free_mb(self.package_dir)
        if free < 0 or free >= self.min_free_mb:
            return ""
        freed = sweep_packages(self.package_dir)
        free = free_mb(self.package_dir)
        if free >= self.min_free_mb:
            return (f"Wenig Speicherplatz – {freed:.0f} MB Pakete "
                    f"aufgeräumt, jetzt {free:.0f} MB frei")
        raise DiskFull(
            f"Nur noch {free:.0f} MB frei (nötig sind {self.min_free_mb:.0f} "
            f"MB). Der Lauf hält an; bereits geprüfte Zeilen sind gesichert. "
            f"Platz schaffen und mit „Fortsetzen“ weiterlaufen lassen.")


def release_memory() -> None:
    """Speicher einsammeln und ans Betriebssystem zurückgeben.

    Beim Rendern und bei der OCR entstehen Puffer von über 100 MB je Seite.
    Python gibt sie frei, die C-Speicherverwaltung von Linux (glibc) behält
    sie aber im Prozess – über hunderte Materialnummern wächst der Prozess
    dadurch um Gigabyte (gemessen mit `python -m tools.messen langlauf`).
    `malloc_trim` gibt sie wirklich zurück. Unter Windows regelt das die
    Heap-Verwaltung selbst; dort ist der Aufruf ein wirkungsloser No-op.
    """
    import gc

    gc.collect()
    # PyMuPDF hält einen internen Zwischenspeicher (Schriften, Bilder,
    # gerenderte Objekte) über Dokumentgrenzen hinweg. Über hunderte
    # Zeichnungen sind das Gigabyte – messbar mit tools/messen.py langlauf.
    try:
        import pymupdf

        pymupdf.TOOLS.store_shrink(100)
    except Exception:      # pragma: no cover - andere PyMuPDF-Fassung
        log.debug("PyMuPDF-Zwischenspeicher nicht leerbar", exc_info=True)
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:      # pragma: no cover - z. B. musl statt glibc
        log.debug("malloc_trim nicht verfügbar", exc_info=True)


# ========================================================================
# zeichnung
# ========================================================================
# Die Zeichnung lesen: PDF, Metadaten, Masse, Form- und Lagetoleranzen.
#
# Alles, was aus der PDF Rohdaten macht - noch ohne jede Bewertung. Die
# Bewertung passiert in den pruef_*-Modulen.
# ======================================================================
# pdfdoc
# ======================================================================
# Zugriff auf das Zeichnungs-PDF: Textlayer, Vektoren, Rendering.
#
# Alle Koordinaten sind PDF-Punkte im PyMuPDF-Koordinatensystem
# (Ursprung oben links). Die Annotation rechnet später mit demselben
# Rendering-Zoom, daher bleiben Findings lagerichtig.



import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf



RENDER_DPI = 200
# Ab so vielen Zeichen gilt eine Seite als „hat Textlayer". Darunter wird
# sie als Scan behandelt und per OCR nachgezogen.
MIN_PAGE_CHARS = 20


@dataclass
class TextBlock:
    """Zusammenhängender Textblock mit Position."""

    text: str
    bbox: BBox
    page: int


@dataclass
class Word:
    """Ein Wort mit Fundstelle.

    conf ist die OCR-Konfidenz in Prozent; Wörter aus dem Textlayer sind
    per Definition sicher (100). Die Maßextraktion nutzt den Wert, um
    unsichere OCR-Schnipsel nicht als Maß zu übernehmen.
    """

    text: str
    bbox: BBox
    page: int
    conf: float = 100.0


class DrawingPdf:
    """Ein geöffnetes Zeichnungs-PDF mit extrahiertem Text."""

    def __init__(self, path: Path):
        self.path = path
        self.doc = pymupdf.open(path)
        self.ocr_used = False
        self.ocr_pages: list[int] = []      # 0-basierte Seiten aus OCR
        self.ocr_conf: float = 0.0          # mittlere Konfidenz in Prozent
        self._words: list[Word] | None = None
        self._blocks: list[TextBlock] | None = None

    def close(self) -> None:
        self.doc.close()

    def __enter__(self) -> "DrawingPdf":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ Text
    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def has_text_layer(self, min_chars: int = 40) -> bool:
        total = sum(len(page.get_text("text").strip()) for page in self.doc)
        return total >= min_chars

    def words(self) -> list[Word]:
        """Alle Wörter mit Bounding-Box; nutzt OCR-Fallback bei Bedarf."""
        if self._words is None:
            self._extract()
        return self._words or []

    def blocks(self) -> list[TextBlock]:
        """Textblöcke (für Sprach-Check und Schriftfeld-Analyse)."""
        if self._blocks is None:
            self._extract()
        return self._blocks or []

    def ocr_note(self) -> str:
        """Kurzbeschreibung der OCR-Güte für Bericht und Finding."""
        if not self.ocr_used:
            return ""
        seiten = ", ".join(str(p + 1) for p in self.ocr_pages)
        anzahl = sum(1 for w in self.words() if w.conf < 100.0)
        return (f"OCR auf Seite {seiten}: {anzahl} Wörter, mittlere "
                f"Erkennungsgüte {self.ocr_conf:.0f} %")

    def full_text(self) -> str:
        return "\n".join(b.text for b in self.blocks())

    def _extract(self) -> None:
        """Text je Seite holen; Seiten ohne Textlayer per OCR nachziehen.

        Gemischte Dokumente sind der Normalfall aus Archiven: Blatt 1 ist
        ein Scan, Blatt 2 stammt aus dem CAD – oder das Schriftfeld ist
        Text und die Zeichnung ein eingebettetes Rasterbild. Deshalb wird
        seitenweise entschieden und beides zusammengeführt, statt das
        ganze Dokument als „mit" oder „ohne" Textlayer zu behandeln.
        """
        self._words, self._blocks = [], []
        scanned: list[int] = []
        for pno, page in enumerate(self.doc):
            text = page.get_text("text").strip()
            if len(text) >= MIN_PAGE_CHARS:
                self._read_page_text(pno, page)
            else:
                scanned.append(pno)

        if not scanned:
            return
        pass  # (Import entfaellt - alles ein Modul)

        if self._words:
            log.warning("%s: Seite(n) %s ohne Textlayer – OCR nur dafür",
                        self.path.name,
                        ", ".join(str(p + 1) for p in scanned))
        else:
            log.warning("%s: kein Textlayer, versuche OCR", self.path.name)
        words = ocr_words(self.doc, pages=scanned)
        if words is None:
            log.error("%s: kein Textlayer und kein OCR verfügbar",
                      self.path.name)
            return
        self.ocr_used = True
        self.ocr_pages = scanned
        if words:
            self.ocr_conf = sum(w.conf for w in words) / len(words)
        self._words.extend(words)
        self._blocks.extend(_words_to_blocks(words))

    def _read_page_text(self, pno: int, page) -> None:
        for x0, y0, x1, y1, wtext, *_ in page.get_text("words"):
            self._words.append(Word(wtext, BBox(x0, y0, x1, y1), pno))
        for x0, y0, x1, y1, btext, _bno, btype in page.get_text("blocks"):
            if btype == 0 and btext.strip():
                self._blocks.append(
                    TextBlock(btext.strip(), BBox(x0, y0, x1, y1), pno))

    # ------------------------------------------------------------- Rendering
    def render_page(self, page: int = 0, dpi: int = RENDER_DPI) -> "pymupdf.Pixmap":
        return self.doc[page].get_pixmap(dpi=dpi)

    def page_size(self, page: int = 0) -> tuple[float, float]:
        r = self.doc[page].rect
        return (r.width, r.height)

    # ---------------------------------------------------------------- Suchen
    def search(self, needle: str, page: int | None = None) -> list[tuple[int, BBox]]:
        """Case-insensitive Volltextsuche, liefert (Seite, BBox) je Treffer."""
        hits: list[tuple[int, BBox]] = []
        pages = range(self.page_count) if page is None else [page]
        for pno in pages:
            for rect in self.doc[pno].search_for(needle):
                hits.append((pno, BBox(rect.x0, rect.y0, rect.x1, rect.y1)))
        return hits


def _words_to_blocks(words: list[Word], line_tol: float = 6.0) -> list[TextBlock]:
    """Gruppiert OCR-Wörter zeilenweise zu Blöcken (grobe Näherung)."""
    blocks: list[TextBlock] = []
    by_page: dict[int, list[Word]] = {}
    for w in words:
        by_page.setdefault(w.page, []).append(w)
    for pno, ws in by_page.items():
        ws.sort(key=lambda w: (round(w.bbox.y0 / line_tol), w.bbox.x0))
        line: list[Word] = []
        for w in ws:
            if line and abs(w.bbox.y0 - line[-1].bbox.y0) > line_tol:
                blocks.append(_merge_line(line, pno))
                line = []
            line.append(w)
        if line:
            blocks.append(_merge_line(line, pno))
    return blocks


def _merge_line(line: list[Word], pno: int) -> TextBlock:
    text = " ".join(w.text for w in line)
    bbox = BBox(
        min(w.bbox.x0 for w in line),
        min(w.bbox.y0 for w in line),
        max(w.bbox.x1 for w in line),
        max(w.bbox.y1 for w in line),
    )
    return TextBlock(text, bbox, pno)


# ======================================================================
# metadata
# ======================================================================
# Metadaten aus der Zeichnung: letztes Änderungsdatum.
#
# Strategie: Alle Datumsangaben im Textlayer einsammeln (deutsche, ISO- und
# US-Schreibweise) und das SPÄTESTE nehmen – das ist auf Fertigungszeichnungen
# praktisch immer der jüngste Eintrag der Änderungstabelle bzw. das
# Freigabedatum. Fallback: Änderungsdatum aus den PDF-Metadaten.



import datetime as dt
import logging
import re


RE_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")        # 12.01.2026
RE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")                # 2026-01-12
RE_US = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")           # 5/23/2021
RE_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})(\d{2})")

MIN_YEAR, MAX_YEAR = 1970, 2100


def _mk(year: int, month: int, day: int) -> dt.date | None:
    if year < 100:
        year += 2000 if year < 70 else 1900
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def _candidates(text: str):
    for d, m, y in RE_DMY.findall(text):
        date = _mk(int(y), int(m), int(d))
        if date:
            yield date
    for y, m, d in RE_ISO.findall(text):
        date = _mk(int(y), int(m), int(d))
        if date:
            yield date
    for a, b, y in RE_US.findall(text):
        a, b = int(a), int(b)
        # US-Schreibweise ist Monat/Tag; wenn das unmöglich ist, Tag/Monat.
        date = _mk(int(y), a, b) if a <= 12 else None
        if date is None and b <= 12:
            date = _mk(int(y), b, a)
        if date:
            yield date


def extract_revision_date(pdf) -> str:
    """Spätestes Datum auf der Zeichnung als ISO-String; '' wenn keins.

    pdf: DrawingPdf. Nutzt den Textlayer; Fallback sind die PDF-Metadaten
    (ModDate/CreationDate), dann mit Kennzeichnung "(PDF-Metadatum)".
    """
    dates = list(_candidates(pdf.full_text()))
    if dates:
        return max(dates).isoformat()

    meta = pdf.doc.metadata or {}
    for key in ("modDate", "creationDate"):
        m = RE_PDF_DATE.search(meta.get(key) or "")
        if m:
            date = _mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if date:
                return f"{date.isoformat()} (PDF-Metadatum)"
    return ""


# --------------------------------------------------------------------------
# Gewichtsangabe aus dem Schriftfeld
# --------------------------------------------------------------------------
RE_WEIGHT = re.compile(
    r"(\d{1,6}(?:[.,]\d{1,3})?)\s*(kg|g|t)\b(?!\w)", re.IGNORECASE)
# Zeilen, in denen eine Masseangabe erwartet wird (verhindert Treffer auf
# Werkstoffnamen o. Ä.).
RE_WEIGHT_LABEL = re.compile(
    r"gewicht|masse\b|weight|mass\b", re.IGNORECASE)
_TO_KG = {"kg": 1.0, "g": 0.001, "t": 1000.0}


# Rohteil-/Fertigteilgewicht unterscheiden: verglichen wird mit dem
# FERTIGGEWICHT, weil das STEP-Modell das fertige Teil beschreibt.
RE_ROUGH_WEIGHT = re.compile(
    r"rohteil|rohgewicht|rohmasse|brutto|gross\s*(?:weight|mass)|raw",
    re.IGNORECASE)


def extract_weight_kg(pdf) -> float | None:
    """Masseangabe der Zeichnung in kg; None wenn keine gefunden.

    Reihenfolge der Bevorzugung:
      1. Angaben in Textblöcken mit Gewichts-Label (Schriftfeld), die NICHT
         als Rohteil-/Bruttogewicht gekennzeichnet sind – das ist das
         Fertiggewicht und damit der richtige Vergleichswert zum Modell.
      2. Sonstige beschriftete Angaben (auch Rohgewicht).
      3. Freistehende Einheiten-Angaben im Text.
    """
    finished: list[float] = []
    labelled: list[float] = []
    loose: list[float] = []
    for block in pdf.blocks():
        has_label = bool(RE_WEIGHT_LABEL.search(block.text))
        is_rough = bool(RE_ROUGH_WEIGHT.search(block.text))
        for value, unit in RE_WEIGHT.findall(block.text):
            kg = _to_kg(value, unit)
            if kg is None:
                continue
            if has_label and not is_rough:
                finished.append(kg)
            elif has_label:
                labelled.append(kg)
            else:
                loose.append(kg)
    for pool in (finished, labelled, loose):
        if pool:
            return max(pool)
    return None


def _to_kg(value: str, unit: str) -> float | None:
    try:
        v = float(value.replace(",", "."))
    except ValueError:
        return None
    kg = v * _TO_KG[unit.lower()]
    # Plausibilitätsfenster: 1 g bis 50 t
    return kg if 0.001 <= kg <= 50000 else None


# --------------------------------------------------------------------------
# Maßstab aus dem Schriftfeld
# --------------------------------------------------------------------------
_SC_NUM = r"(\d{1,3}(?:[.,]\d{1,2})?)"
RE_SCALE = re.compile(
    rf"(?:ma[ßs]stab|scale)\s*:?\s*{_SC_NUM}\s*[:/]\s*{_SC_NUM}",
    re.IGNORECASE)
_PT_PER_MM = 72.0 / 25.4


# Normübliche Maßstäbe nach ISO 5455 (plus die gängigen Zwischenwerte).
COMMON_SCALES = {
    0.02, 0.05, 0.1, 0.2, 0.5,          # Vergrößerungen 50:1 … 2:1
    1.0,
    2.0, 2.5, 4.0, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0,
}


def extract_scale(pdf) -> float | None:
    """Maßstab als Faktor Bauteil/Zeichnung.

    „1:2" (verkleinert) -> 2.0, „2:1" (vergrößert) -> 0.5, „1:1" -> 1.0.
    Ausgewertet wird nur die BESCHRIFTETE Angabe („Maßstab 1:2", „SCALE 1:2")
    und nur, wenn sie einem normüblichen Maßstab entspricht – freistehende
    „x:y"-Muster auf einer Zeichnung sind häufiger Blatt-, Zeit- oder
    Verhältnisangaben als Maßstäbe.
    """
    for a, b in RE_SCALE.findall(pdf.full_text()):
        try:
            num = float(a.replace(",", "."))
            den = float(b.replace(",", "."))
        except ValueError:
            continue
        if num <= 0 or den <= 0:
            continue
        factor = den / num
        if any(abs(factor - c) < 0.01 for c in COMMON_SCALES):
            return factor
    return None


def mm_per_point(scale_factor: float) -> float:
    """Bauteil-Millimeter je PDF-Punkt bei gegebenem Maßstab."""
    return scale_factor / _PT_PER_MM


# ======================================================================
# dimensions
# ======================================================================
# Extraktion von Maßangaben aus dem Zeichnungs-PDF.
#
# Grundlage für den Geometrieabgleich gegen STEP und für die Bemaßungs-/
# Fertigungsregeln. Die Extraktion ist bewusst konservativ – lieber ein Maß
# übersehen als eine Normbezeichnung ("ISO 2768") als 2768-mm-Maß
# fehlinterpretieren.
#
# Erfasst je Maß:
#   * Nennwert und Art (linear, Durchmesser, Radius, Gewinde)
#   * Wiederholfaktor ("4×⌀18" -> count=4)
#   * Toleranz (±0,1 -> tol_plus/tol_minus; Grenzabmaße +0,2/-0,1)
#   * ISO-Passung ("40H7" -> fit="H7") inkl. IT-Grad
#   * theoretisch genaues Maß (eingerahmt, ISO 1101) -> is_basic



import os
import re
from dataclasses import dataclass
from enum import Enum



class DimKind(Enum):
    LINEAR = "linear"
    DIAMETER = "diameter"
    RADIUS = "radius"
    THREAD = "thread"


@dataclass
class DimValue:
    value: float                 # Nennmaß in mm
    kind: DimKind
    raw: str                     # Originaltext
    bbox: BBox
    page: int
    count: int = 1               # Wiederholfaktor ("4×⌀18")
    tol_plus: float | None = None
    tol_minus: float | None = None
    fit: str = ""                # ISO-Passung, z. B. "H7"
    is_basic: bool = False       # theoretisch genaues Maß (eingerahmt)
    depth: float | None = None   # Bohrtiefe ("⌀8 ↧25" / "⌀8 T25")

    @property
    def tolerance_span(self) -> float | None:
        """Toleranzbreite in mm (aus ± bzw. Grenzabmaßen oder ISO-Passung)."""
        if self.tol_plus is not None or self.tol_minus is not None:
            hi = self.tol_plus if self.tol_plus is not None else 0.0
            lo = self.tol_minus if self.tol_minus is not None else 0.0
            return abs(hi - lo)
        if self.fit:
            return it_grade_span(self.fit, self.value)
        return None

    @property
    def it_grade(self) -> int | None:
        m = re.search(r"(\d{1,2})$", self.fit)
        return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# ISO-286 Grundtoleranzgrade (Auszug): Toleranzbreite in µm je Nennmaßbereich.
# Reicht für die Bewertung "wie eng ist diese Toleranz" völlig aus.
# --------------------------------------------------------------------------
_IT_RANGES = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]
_IT_TABLE_UM = {
    #    ≤3   ≤6  ≤10  ≤18  ≤30  ≤50  ≤80 ≤120 ≤180 ≤250 ≤315 ≤400 ≤500
    1: [0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8],
    2: [1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10],
    3: [2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15],
    4: [3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20],
    5: [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6: [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7: [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8: [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9: [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
    12: [100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630],
    13: [140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970],
}


def it_grade_span(fit: str, nominal: float) -> float | None:
    """Toleranzbreite einer ISO-Passung in mm (None wenn unbekannt)."""
    m = re.search(r"(\d{1,2})$", fit or "")
    if not m:
        return None
    grade = int(m.group(1))
    row = _IT_TABLE_UM.get(grade)
    if row is None or nominal <= 0:
        return None
    idx = next((i for i, upper in enumerate(_IT_RANGES) if nominal <= upper),
               len(_IT_RANGES) - 1)
    return row[min(idx, len(row) - 1)] / 1000.0


# --------------------------------------------------------------------------
# Regex-Bausteine
# --------------------------------------------------------------------------
NUM = r"(\d{1,4}(?:[.,]\d{1,3})?)"
DIA = r"[⌀Øø∅]"
# Wiederholfaktor: "4x", "4×", "4 X"
MULT = r"(?:(\d{1,3})\s*[xX×]\s*)?"
# ISO-Passung: gültige Toleranzlagen nach ISO 286 (einbuchstabig oder
# die zweibuchstabigen Sonderlagen), z. B. H7, h6, js9, JS13, k6.
FIT_LETTERS = r"(?:JS|js|CD|cd|EF|ef|FG|fg|Z[ABC]|z[abc]|[A-Za-z])"
FIT = rf"(?:\s*({FIT_LETTERS}\d{{1,2}}))?"
# Symmetrische Toleranz: ±0,1
TOL_SYM = r"(?:\s*±\s*(\d+(?:[.,]\d+)?))?"
# Grenzabmaße: +0,2 -0,1  (auch mit Leerzeichen/Zeilenumbruch dazwischen)
TOL_LIM = r"(?:\s*\+\s*(\d+(?:[.,]\d+)?)\s*[-−]\s*(\d+(?:[.,]\d+)?))?"

RE_DIAMETER = re.compile(rf"{MULT}{DIA}\s*{NUM}{FIT}{TOL_SYM}")
RE_RADIUS = re.compile(rf"\bR\s*{NUM}\b")
RE_THREAD = re.compile(
    rf"(?:(\d{{1,3}})\s*[xX×]\s*M|\bM)\s*{NUM}"
    rf"(?:\s*[xX×]\s*(\d+(?:[.,]\d+)?))?\b")
RE_LINEAR = re.compile(rf"^{NUM}{FIT}{TOL_SYM}$")
RE_LIMITS = re.compile(rf"^{NUM}\s*\+\s*(\d+(?:[.,]\d+)?)\s*[-−]\s*"
                       rf"(\d+(?:[.,]\d+)?)$")
# Theoretisch genaues Maß (TED): eingerahmt, im Textlayer meist als
# "[50]" oder mit Rahmen-Unicode. Wir erkennen die Klammerformen.
RE_BASIC = re.compile(rf"^[\[⟦(]\s*{NUM}\s*[\]⟧)]$")
# Allein stehende Passung ("H7") bzw. Toleranz ("±0,1") als Folgewort.
RE_FIT_ONLY = re.compile(rf"^({FIT_LETTERS}\d{{1,2}})$")
RE_TOL_ONLY = re.compile(r"^±\s*(\d+(?:[.,]\d+)?)$")
# Bohrtiefe: "↧25", "T25", "tief 25"
RE_DEPTH = re.compile(r"(?:↧|\bT(?=\d)|\btief\s*|\bdeep\s*)\s*(\d{1,4}"
                      r"(?:[.,]\d{1,2})?)", re.IGNORECASE)

# Kontexte, in denen Zahlen KEINE Maße sind.
NORM_WORDS = {"iso", "din", "en", "vdi", "asme", "ansi", "nf", "bs", "sep",
              "vdg", "awt", "aws", "sae", "astm", "ral"}
UNIT_NOT_MM = re.compile(r"(kg|g\b|°|grad|deg|%|:|/|µm|hrc|hv|hb)",
                         re.IGNORECASE)
# Wörter, nach denen eine Zahl keine Länge ist (Gewicht, Stückzahl, Härte).
NON_DIM_PREV = {"gewicht", "masse", "weight", "mass", "gew", "menge",
                "stück", "stk", "anzahl", "qty", "pos", "position",
                "härte", "hardness", "index", "rev", "revision", "blatt",
                "sheet", "seite", "page", "zone", "auftrag", "order"}
# Einheiten, die als eigenes Folgewort stehen und ein Längenmaß ausschließen.
RE_UNIT_AFTER = re.compile(
    r"^(kg|kgs|g|t|lb|lbs|°|grad|deg|%|µm|um|hrc|hv|hb|n/mm|mpa|bar|nm|min|"
    r"stk|stück|pcs|pc)\b", re.IGNORECASE)
# Ein Token wie "1:2" ist ein Massstab, kein Mass. Der Name ist bewusst
# ein anderer als der von RE_SCALE oben: der sucht die Massstabsangabe
# im Schriftfeld, dieser wehrt ein Token in der Massextraktion ab.
RE_SCALE_TOKEN = re.compile(r"^\d+\s*:\s*\d+$")
RE_LONG_ID = re.compile(r"^\d{6,}$")
RE_YEAR = re.compile(r"^(19|20)\d{2}$")


def parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _num_or_none(s) -> float | None:
    return parse_number(s) if s else None


# Mindestkonfidenz für Maße aus OCR. Kurze Zahlenschnipsel ("2", "13")
# sind die häufigste OCR-Halluzination und würden als Maß den
# Geometrieabgleich verfälschen – deshalb für sie eine höhere Schwelle.
OCR_DIM_MIN_CONF = float(os.environ.get("DRAWING_CHECKER_OCR_DIM_CONF", 70))
OCR_SHORT_MIN_CONF = float(os.environ.get("DRAWING_CHECKER_OCR_SHORT_CONF", 85))


def extract_dimensions(pdf: DrawingPdf, max_plausible: float = 6000.0
                       ) -> list[DimValue]:
    """Extrahiert alle Maßkandidaten aus den Wörtern des PDFs.

    Bei OCR-Text werden unsichere Funde verworfen (siehe Word.conf) –
    lieber ein Maß weniger als ein erfundenes.
    """
    words = pdf.words()
    dims: list[DimValue] = []
    for i, w in enumerate(words):
        if not _confident_enough(w):
            continue
        prev = words[i - 1].text.lower().rstrip(".:") if i > 0 else ""
        # Nachbarwörter für Kontextangaben (Tiefe, Grenzabmaße, Faktor)
        nxt = " ".join(x.text for x in words[i + 1:i + 3])
        for d in _parse_word(w, prev_word=prev, next_text=nxt):
            if 0.05 <= d.value <= max_plausible:
                dims.append(d)
    return dims


def _confident_enough(w: Word) -> bool:
    conf = getattr(w, "conf", 100.0)
    if conf >= 100.0:
        return True
    limit = (OCR_SHORT_MIN_CONF if len(w.text.strip()) <= 2
             else OCR_DIM_MIN_CONF)
    return conf >= limit


def _parse_word(w: Word, prev_word: str, next_text: str = "") -> list[DimValue]:
    t = w.text.strip()
    out: list[DimValue] = []

    def mk(value, kind, **kw) -> DimValue:
        d = DimValue(value=value, kind=kind, raw=t, bbox=w.bbox, page=w.page,
                     **kw)
        # Tiefe steht oft im Folgewort ("⌀8", "↧25")
        dm = RE_DEPTH.search(next_text)
        if dm and kind in (DimKind.DIAMETER, DimKind.THREAD):
            d.depth = parse_number(dm.group(1))
        # Passung und Toleranz stehen häufig als eigenes Token dahinter
        # ("⌀20" "H7" bzw. "40" "±0,1") – CAD-Systeme trennen sie oft.
        if kind in (DimKind.DIAMETER, DimKind.LINEAR):
            head = next_text.split()[:1]
            if head and not d.fit:
                fm = RE_FIT_ONLY.match(head[0])
                if fm:
                    d.fit = fm.group(1)
                    d.raw = f"{t} {head[0]}"
            if head and d.tol_plus is None:
                tm = RE_TOL_ONLY.match(head[0])
                if tm:
                    v = parse_number(tm.group(1))
                    d.tol_plus, d.tol_minus = v, -v
                    d.raw = f"{t} {head[0]}"
        return d

    # --- Durchmesser (inkl. Anzahl und Passung) ---------------------------
    for m in RE_DIAMETER.finditer(t):
        count, value, fit, tol = m.group(1), m.group(2), m.group(3), m.group(4)
        tol_v = _num_or_none(tol)
        out.append(mk(parse_number(value), DimKind.DIAMETER,
                      count=int(count) if count else 1,
                      fit=fit or "",
                      tol_plus=tol_v, tol_minus=-tol_v if tol_v else None))
    # --- Gewinde ----------------------------------------------------------
    for m in RE_THREAD.finditer(t):
        count, value = m.group(1), m.group(2)
        out.append(mk(parse_number(value), DimKind.THREAD,
                      count=int(count) if count else 1))
    if out:
        return out

    m = RE_RADIUS.search(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.RADIUS)]

    # --- Lineare Maße: nur wenn das ganze Token wie ein Maß aussieht ------
    if prev_word in NORM_WORDS or prev_word in NON_DIM_PREV:
        return []
    # „4200" gefolgt von „kg" ist ein Gewicht, keine Länge. CAD-Systeme
    # trennen Zahl und Einheit häufig in zwei Wörter.
    first_next = next_text.split()[:1]
    if first_next and RE_UNIT_AFTER.match(first_next[0]):
        return []
    if (UNIT_NOT_MM.search(t) or RE_SCALE_TOKEN.match(t) or RE_LONG_ID.match(t)
            or RE_YEAR.match(t)):
        return []

    m = RE_BASIC.match(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.LINEAR, is_basic=True)]

    m = RE_LIMITS.match(t)
    if m:
        return [mk(parse_number(m.group(1)), DimKind.LINEAR,
                   tol_plus=parse_number(m.group(2)),
                   tol_minus=-parse_number(m.group(3)))]

    m = RE_LINEAR.match(t)
    if m:
        value, fit, tol = m.group(1), m.group(2), m.group(3)
        tol_v = _num_or_none(tol)
        return [mk(parse_number(value), DimKind.LINEAR, fit=fit or "",
                   tol_plus=tol_v, tol_minus=-tol_v if tol_v else None)]
    return []


def estimate_envelope(dims: list[DimValue], top_n: int = 6) -> list[float]:
    """Schätzt die Hüllmaß-Kandidaten der Zeichnung.

    Liefert die größten `top_n` voneinander verschiedenen Werte aus linearen
    Maßen und Durchmessern, absteigend sortiert. Die größten konsistenten
    Maße dominieren erfahrungsgemäß die Außenkontur.
    """
    candidates = sorted(
        {round(d.value, 2) for d in dims
         if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)},
        reverse=True,
    )
    return candidates[:top_n]


def hole_pattern(dims: list[DimValue]) -> dict[float, int]:
    """Bohrbild aus der Zeichnung: {Durchmesser: Anzahl}.

    Mehrfachnennungen desselben Durchmessers werden aufsummiert
    ("4×⌀18" und später nochmal "2×⌀18" ergibt 6).
    """
    pattern: dict[float, int] = {}
    for d in dims:
        if d.kind is DimKind.DIAMETER:
            key = round(d.value, 2)
            pattern[key] = pattern.get(key, 0) + d.count
    return pattern


# ======================================================================
# fcf
# ======================================================================
# Erkennung von Toleranzrahmen (Feature Control Frames) als Vektorgrafik.
#
# Hintergrund: CAD-Systeme zeichnen Toleranzrahmen samt GD&T-Symbol meist als
# Grafik. Im PDF-Textlayer stehen dann nur Toleranzwert und Bezugsbuchstaben –
# das Symbol fehlt. Symbolbasierte Regeln wären damit auf realen Zeichnungen
# blind.
#
# Dieses Modul findet die Rahmen über ihre Geometrie (flaches Rechteck aus
# Linien, Text darin) und liest Wert und Bezüge aus. Das Symbol selbst bleibt
# unbekannt – dafür meldet der Checker einen Sichtprüfungs-Hinweis.



import re
from dataclasses import dataclass, field


# Geometrie eines Toleranzrahmens (PDF-Punkte).
MIN_H, MAX_H = 5.0, 24.0
MIN_W, MAX_W = 14.0, 300.0
MIN_RATIO = 1.4

RE_VALUE = re.compile(r"^[⌀Øø]?\s*\d+(?:[.,]\d+)?$")
RE_DATUM_LETTER = re.compile(r"^[A-Z](?:[ⓂⓁ])?$")
RE_MODIFIER = re.compile(r"[ⓂⓁⒺⓅ]")


@dataclass
class FeatureFrame:
    """Ein erkannter Toleranzrahmen."""

    bbox: BBox
    page: int
    texts: list[str] = field(default_factory=list)
    value: float | None = None
    diameter_zone: bool = False       # ⌀-Toleranzzone
    datums: list[str] = field(default_factory=list)
    symbol: str = ""                  # nur gesetzt, wenn im Textlayer
    chambers: int = 0

    @property
    def has_datums(self) -> bool:
        return bool(self.datums)

    @property
    def raw(self) -> str:
        return " ".join(self.texts)


def find_feature_frames(pdf, max_pages: int = 3) -> list[FeatureFrame]:
    """Sucht Toleranzrahmen auf den ersten Seiten des Dokuments."""
    frames: list[FeatureFrame] = []
    for pno in range(min(pdf.page_count, max_pages)):
        page = pdf.doc[pno]
        words = page.get_text("words")
        for path in page.get_drawings():
            rect = path.get("rect")
            if rect is None:
                continue
            h, w = rect.height, rect.width
            if not (MIN_H <= h <= MAX_H and MIN_W <= w <= MAX_W):
                continue
            if w / max(h, 0.1) < MIN_RATIO:
                continue
            inside = [
                wd for wd in words
                if rect.x0 - 1 <= (wd[0] + wd[2]) / 2 <= rect.x1 + 1
                and rect.y0 - 1 <= (wd[1] + wd[3]) / 2 <= rect.y1 + 1
            ]
            if not inside:
                continue
            texts = [wd[4].strip() for wd in sorted(inside, key=lambda x: x[0])]
            if not any(any(c.isdigit() for c in t) for t in texts):
                continue
            frame = _parse_frame(texts, rect, pno, len(path["items"]))
            if frame is not None:
                frames.append(frame)
    return _dedupe(frames)


def _parse_frame(texts: list[str], rect, pno: int,
                 n_items: int) -> FeatureFrame | None:
    """Wandelt die Textfragmente eines Rahmens in Wert + Bezüge um."""
    value: float | None = None
    diameter = False
    datums: list[str] = []
    symbol = ""
    for t in texts:
        clean = t.strip()
        if not clean:
            continue
        if RE_VALUE.match(clean):
            if value is None:
                diameter = clean[0] in "⌀Øø"
                try:
                    value = float(re.sub(r"[^\d.,]", "", clean)
                                  .replace(",", "."))
                except ValueError:
                    pass
            continue
        if RE_DATUM_LETTER.match(clean):
            letter = clean[0]
            if letter not in datums:
                datums.append(letter)
            continue
        # GD&T-Symbol im Textlayer (selten, aber möglich)
        for ch in clean:
            if ch in "⌖⏥⏤○⌭∥⊥∠↗⌰◎⌯⌓⌔":
                symbol = ch
    if value is None:
        return None
    return FeatureFrame(
        bbox=BBox(rect.x0, rect.y0, rect.x1, rect.y1), page=pno,
        texts=texts, value=value, diameter_zone=diameter, datums=datums,
        symbol=symbol, chambers=max(1, n_items - 3),
    )


def _contains(outer: FeatureFrame, inner: FeatureFrame,
              slack: float = 2.0) -> bool:
    a, b = outer.bbox, inner.bbox
    return (outer.page == inner.page
            and a.x0 - slack <= b.x0 and a.y0 - slack <= b.y0
            and a.x1 + slack >= b.x1 and a.y1 + slack >= b.y1)


def _dedupe(frames: list[FeatureFrame]) -> list[FeatureFrame]:
    """Entfernt Mehrfachtreffer und Teilkammern desselben Rahmens.

    CAD-Exporte zeichnen Toleranzrahmen als mehrere Pfade: den ganzen
    Rahmen und einzelne Kammern. Der umfassendste Rahmen enthält alle
    Angaben (Wert plus Bezüge) und gewinnt.
    """
    # Größte zuerst – kleinere, enthaltene Rahmen fallen dann weg.
    ordered = sorted(
        frames, key=lambda f: (f.bbox.x1 - f.bbox.x0) * (f.bbox.y1 - f.bbox.y0),
        reverse=True)
    out: list[FeatureFrame] = []
    for f in ordered:
        if any(_contains(g, f) for g in out):
            continue
        out.append(f)
    return sorted(out, key=lambda f: (f.page, f.bbox.y0, f.bbox.x0))


# ========================================================================
# regeln
# ========================================================================
# Regelwerk: Kontext, Registrierung, Profile und die Pflege der YAMLs.
#
# Hier steht die Mechanik (was ein Finding ist, welches Profil welche Regel
# scharf schaltet) - das Fachwissen selbst liegt in rules/*.yaml.
# ======================================================================
# base
# ======================================================================
# Check-Basis: Regelprofile (YAML) und gemeinsamer Kontext für alle Checks.



import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml



def _eingebaute_regeln_auspacken() -> Path:
    """Die eingebetteten YAMLs als Dateien - dort, wo der Lader sie erwartet.

    Landet in einem Cache-Ordner je Inhaltsstand (Hash), damit eine neue
    Programmfassung nie alte Regeln vorfindet.
    """
    import hashlib
    import tempfile

    stand = hashlib.sha256(
        "".join(f"{n}\n{EINGEBAUTE_REGELN[n]}" for n in sorted(EINGEBAUTE_REGELN))
        .encode("utf-8")).hexdigest()[:12]
    ordner = Path(tempfile.gettempdir()) / f"drawing_checker_regeln_{stand}"
    if not (ordner / ".fertig").exists():
        ordner.mkdir(parents=True, exist_ok=True)
        for dateiname, inhalt in EINGEBAUTE_REGELN.items():
            (ordner / dateiname).write_text(inhalt, encoding="utf-8")
        (ordner / ".fertig").write_text("ok", encoding="ascii")
    return ordner


def export_rules(ziel: Path) -> list[Path]:
    """Schreibt die eingebauten Wissenspakete zum Bearbeiten nach `ziel`.

    Vorhandene Dateien werden nicht ueberschrieben - wer dort schon
    gepflegt hat, verliert nichts.
    """
    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for dateiname, inhalt in EINGEBAUTE_REGELN.items():
        pfad = ziel / dateiname
        if not pfad.exists():
            pfad.write_text(inhalt, encoding="utf-8")
            geschrieben.append(pfad)
    return geschrieben


RULES_DIR = _eingebaute_regeln_auspacken()


def rules_dirs() -> list[Path]:
    """Alle Regelordner in Ladereihenfolge (spätere überschreiben frühere).

    1. Mitgelieferte Pakete im Programm (RULES_DIR).
    2. Ordner aus der Umgebungsvariablen DRAWING_CHECKER_RULES.
    3. Ordner `regeln/` neben der ausführbaren Datei (PyInstaller-.exe)
       bzw. im Arbeitsverzeichnis – dort pflegen Anwender ihre YAMLs
       manuell nach, ohne das Programm anzufassen.
    """
    import sys

    dirs = [RULES_DIR]
    env = os.environ.get("DRAWING_CHECKER_RULES")
    if env:
        dirs.append(Path(env))
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent / "regeln")
    dirs.append(Path.cwd() / "regeln")
    seen: set[Path] = set()
    out = []
    for d in dirs:
        if d.is_dir() and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def rules_files(pattern: str) -> list[Path]:
    """Alle Wissenspaket-Dateien zu einem Muster über alle Regelordner."""
    files: list[Path] = []
    for d in rules_dirs():
        files.extend(sorted(d.glob(pattern)))
    return files

# Befunde, die nicht vom erkannten Text abhängen und deshalb auch bei
# OCR-Grundlage ihre volle Härte behalten.
OCR_INDEPENDENT = {"DOC.NO_PDF", "DOC.NO_TEXT", "DOC.OCR", "GEO.UNIT_MISMATCH",
                   "GEO.ASSEMBLY"}

SEVERITY_BY_NAME = {
    "info": Severity.INFO,
    "warning": Severity.WARNING,
    "error": Severity.ERROR,
    "blocker": Severity.BLOCKER,
}


@dataclass
class RuleProfile:
    """Aufgelöstes Regelprofil einer Materialgruppe."""

    name: str
    rules: dict[str, dict] = field(default_factory=dict)
    step_tolerance: dict = field(default_factory=lambda: {"rel": 0.05, "abs": 2.0})
    params: dict = field(default_factory=dict)

    def enabled(self, code: str) -> bool:
        return bool(self.rules.get(code, {}).get("enabled", False))

    def severity(self, code: str, default: Severity = Severity.ERROR) -> Severity:
        name = self.rules.get(code, {}).get("severity")
        return SEVERITY_BY_NAME.get(str(name).lower(), default) if name else default

    def rule_param(self, code: str, key: str, default=None):
        return self.rules.get(code, {}).get(key, default)


def load_profiles_data(rules_file: Path | None = None) -> dict:
    """Sammelt alle profiles*.yaml über alle Regelordner (deep-merged).

    Externe Ordner (regeln/ neben der .exe, DRAWING_CHECKER_RULES) können
    damit einzelne Regeln/Severities überschreiben oder eigene Profile
    ergänzen, ohne die mitgelieferte Datei anzufassen.
    """
    if rules_file is not None:
        data = yaml.safe_load(rules_file.read_text(encoding="utf-8")) or {}
        return data.get("profiles", {})
    merged: dict = {}
    for f in rules_files("profiles*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            log.error("Profildatei %s nicht lesbar: %s", f, exc)
            continue
        merged = _deep_merge(merged, data.get("profiles", {}))
    return merged


def load_profile(material_group: str, rules_file: Path | None = None) -> RuleProfile:
    """Lädt ein Profil inkl. `inherit`-Auflösung aus den profiles*.yaml."""
    profiles = load_profiles_data(rules_file)
    if material_group not in profiles:
        log.warning("Profil %r unbekannt, nutze 'default'", material_group)
        material_group = "default"

    merged: dict = {}
    chain: list[str] = []
    name: str | None = material_group
    while name:
        if name in chain:
            raise ValueError(f"Zyklische inherit-Kette in Profilen: {chain + [name]}")
        chain.append(name)
        name = profiles.get(name, {}).get("inherit")
    for pname in reversed(chain):
        merged = _deep_merge(merged, profiles.get(pname, {}))
    merged.pop("inherit", None)

    return RuleProfile(
        name=material_group,
        rules=merged.get("rules", {}),
        step_tolerance=merged.get("step_tolerance", {"rel": 0.05, "abs": 2.0}),
        params=merged.get("params", {}),
    )


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class CheckContext:
    """Alles, was ein Check über den aktuellen Prüfling wissen darf."""

    material: str
    pdf: DrawingPdf
    package: PackageContent
    profile: RuleProfile
    findings: list[Finding] = field(default_factory=list)
    _frames: list | None = field(default=None, repr=False)

    @property
    def feature_frames(self) -> list:
        """Grafisch erkannte Toleranzrahmen (einmalig ermittelt)."""
        if self._frames is None:
            pass  # (Import entfaellt - alles ein Modul)
            try:
                self._frames = find_feature_frames(self.pdf)
            except Exception:  # Stub-PDFs in Tests haben kein doc
                self._frames = []
        return self._frames

    def add(self, code: str, text: str, *, severity: Severity | None = None,
            bbox=None, page: int = 0, detail: str = "") -> None:
        """Finding aufnehmen; bei OCR-Grundlage wird die Härte gedeckelt.

        Beruht der Text auf OCR, ist jede Aussage „Angabe fehlt" nur so
        sicher wie die Erkennung. Solche Befunde werden deshalb auf
        „Prüfen" heruntergestuft – ausgenommen Befunde, die gar nicht vom
        Text abhängen (fehlendes PDF im Paket).
        """
        sev = severity if severity is not None else self.profile.severity(code)
        if (sev >= Severity.ERROR and code not in OCR_INDEPENDENT
                and getattr(self.pdf, "ocr_used", False)):
            sev = Severity.WARNING
            detail = (detail + " " if detail else "") + (
                "Herabgestuft: die Zeichnung wurde per OCR gelesen, ein "
                "Erkennungsfehler ist nicht auszuschließen – am Original "
                "prüfen.")
        self.findings.append(
            Finding(code=code, severity=sev, text=text, bbox=bbox, page=page, detail=detail)
        )


# ======================================================================
# rules_check
# ======================================================================
# Validierung der handgepflegten Wissenspakete (YAML).
#
# Für Anwender, die rules-Dateien manuell nachpflegen:
#
#     drawing-checker --check-rules
#
# prüft alle Regelordner (mitgeliefert + externe `regeln/`-Ordner) und meldet
# Fehler in Klartext mit Datei und Eintrag – bevor ein Prüflauf damit startet.
# Die GUI führt dieselbe Prüfung beim Start aus und zeigt Probleme als Warnung.



import re
from dataclasses import dataclass
from pathlib import Path

import yaml


VALID_CATEGORIES = {
    "baustahl", "verguetung", "einsatz", "automaten", "nirosta",
    "nirosta_auto", "guss", "stahlguss", "alu", "kupfer", "titan",
    "magnesium", "kunststoff", "verbund",
}
VALID_WELDABLE = {"ja", "bedingt", "nein"}
VALID_HARDENABLE = {"qt", "case", "nitr"}


@dataclass
class Issue:
    file: str
    where: str
    problem: str

    def __str__(self) -> str:
        return f"[{self.file}] {self.where}: {self.problem}"


def validate_rules() -> tuple[list[Issue], dict[str, int]]:
    """Prüft alle Wissenspakete; liefert (Probleme, Statistik)."""
    issues: list[Issue] = []
    stats = {"materialien": 0, "normen": 0, "profile": 0, "beschaffung": 0,
             "halbzeuge": 0, "ordner": len(rules_dirs())}

    # ---------------------------------------------------------- materials
    seen_names: set[str] = set()
    for f in rules_files("materials*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        entries = data.get("materials")
        if entries is None:
            issues.append(Issue(f.name, "Datei",
                                "Schlüssel 'materials:' fehlt auf oberster Ebene"))
            continue
        for i, e in enumerate(entries, start=1):
            where = f"Eintrag {i} ({e.get('name', '?') if isinstance(e, dict) else e!r})"
            if not isinstance(e, dict):
                issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                continue
            for key in ("name", "patterns", "category"):
                if key not in e:
                    issues.append(Issue(f.name, where, f"Pflichtfeld '{key}' fehlt"))
            name = e.get("name")
            if name in seen_names:
                issues.append(Issue(f.name, where,
                                    f"Werkstoffname doppelt: {name!r}"))
            elif name:
                seen_names.add(name)
            if e.get("category") and e["category"] not in VALID_CATEGORIES:
                issues.append(Issue(
                    f.name, where,
                    f"unbekannte category {e['category']!r} "
                    f"(erlaubt: {', '.join(sorted(VALID_CATEGORIES))})"))
            if e.get("weldable") and str(e["weldable"]) not in VALID_WELDABLE:
                issues.append(Issue(f.name, where,
                                    f"weldable muss ja/bedingt/nein sein, "
                                    f"nicht {e['weldable']!r}"))
            for h in e.get("hardenable", []) or []:
                if h not in VALID_HARDENABLE:
                    issues.append(Issue(f.name, where,
                                        f"unbekanntes hardenable-Verfahren {h!r} "
                                        f"(erlaubt: qt, case, nitr)"))
            for pat in e.get("patterns", []) or []:
                perr = _check_regex(pat)
                if perr:
                    issues.append(Issue(f.name, where, perr))
            stats["materialien"] += 1

    # -------------------------------------------------------------- norms
    for f in rules_files("norms*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        entries = data.get("obsolete")
        if entries is None:
            issues.append(Issue(f.name, "Datei",
                                "Schlüssel 'obsolete:' fehlt auf oberster Ebene"))
            continue
        for i, e in enumerate(entries, start=1):
            where = f"Eintrag {i}"
            if not isinstance(e, dict):
                issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                continue
            if "pattern" not in e or "message" not in e:
                issues.append(Issue(f.name, where,
                                    "Felder 'pattern' und 'message' sind Pflicht"))
                continue
            perr = _check_regex(e["pattern"])
            if perr:
                issues.append(Issue(f.name, where, perr))
            stats["normen"] += 1

    # ------------------------------------------------------- beschaffung
    for f in rules_files("beschaffung*.yaml"):
        data, err = _load_yaml(f)
        if err:
            issues.append(Issue(f.name, "Datei", err))
            continue
        for key in ("vage", "hausnormen"):
            for i, e in enumerate(data.get(key) or [], start=1):
                where = f"{key}, Eintrag {i}"
                if not isinstance(e, dict):
                    issues.append(Issue(f.name, where, "Eintrag ist kein Mapping"))
                    continue
                if "pattern" not in e or "message" not in e:
                    issues.append(Issue(
                        f.name, where,
                        "Felder 'pattern' und 'message' sind Pflicht"))
                    continue
                perr = _check_regex(e["pattern"])
                if perr:
                    issues.append(Issue(f.name, where, perr))
                stats["beschaffung"] += 1
        for key, values in (data.get("halbzeuge") or {}).items():
            if not isinstance(values, list) or not values:
                issues.append(Issue(f.name, f"halbzeuge/{key}",
                                    "Liste von Zahlen erwartet"))
                continue
            for v in values:
                if not isinstance(v, (int, float)) or v <= 0:
                    issues.append(Issue(f.name, f"halbzeuge/{key}",
                                        f"ungültiges Maß {v!r}"))
            stats["halbzeuge"] += len(values)

    # ------------------------------------------------------------ profiles
    try:
        profiles = load_profiles_data()
        stats["profile"] = len(profiles)
        for pname in profiles:
            try:
                pass  # (im selben Modul)

                prof = load_profile(pname)
            except ValueError as exc:  # zyklisches inherit
                issues.append(Issue("profiles*.yaml", f"Profil {pname!r}", str(exc)))
                continue
            for code, rule in prof.rules.items():
                sev = rule.get("severity")
                if sev and str(sev).lower() not in SEVERITY_BY_NAME:
                    issues.append(Issue(
                        "profiles*.yaml", f"Profil {pname!r}, Regel {code}",
                        f"unbekannte severity {sev!r} "
                        f"(erlaubt: {', '.join(SEVERITY_BY_NAME)})"))
    except yaml.YAMLError as exc:
        issues.append(Issue("profiles*.yaml", "Datei", f"YAML-Fehler: {exc}"))

    return issues, stats


def _load_yaml(f: Path) -> tuple[dict, str]:
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"nicht lesbar: {exc}"
    if data is None:
        return {}, ""
    if not isinstance(data, dict):
        return {}, "oberste Ebene muss ein Mapping sein"
    return data, ""


def _check_regex(pattern) -> str:
    if not isinstance(pattern, str) or not pattern.strip():
        return f"pattern ist leer oder kein Text: {pattern!r}"
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"ungültiges Regex-Muster {pattern!r}: {exc}"
    return ""


def format_report(issues: list[Issue], stats: dict[str, int]) -> str:
    lines = [
        "Regelordner: " + ", ".join(str(d) for d in rules_dirs()),
        f"Geladen: {stats['materialien']} Werkstoffe, {stats['normen']} "
        f"Normeinträge, {stats['beschaffung']} Beschaffungsregeln, "
        f"{stats['halbzeuge']} Halbzeugmaße, {stats['profile']} Profile",
    ]
    if issues:
        lines.append(f"\n{len(issues)} Problem(e) gefunden:")
        lines += [f"  - {i}" for i in issues]
        lines.append("\nBitte korrigieren – fehlerhafte Einträge werden beim "
                     "Prüflauf ignoriert.")
    else:
        lines.append("Alle Wissenspakete sind in Ordnung.")
    return "\n".join(lines)


# ========================================================================
# pruef_werkstoff
# ========================================================================
# Pruefungen zu Werkstoff, Fertigungsverfahren, Masse und Beschaffung.
#
# Was aus dem Werkstoff folgt (Verfahren, Oberflaechenbehandlung, Dichte
# und damit das Gewicht) und was der internationale Einkauf braucht
# (eindeutige Normen statt Hausnormen, Halbzeugmasse).
# ======================================================================
# materials
# ======================================================================
# Werkstofferkennung und fachliche Widerspruchsprüfung.
#
# Zwei Aufgaben:
#   1. Ist überhaupt ein Werkstoff angegeben (erkennbare Bezeichnung, nicht nur
#      das Schriftfeld-Label)?
#   2. Passen Freitexte/Symbolik/Normbezüge fachlich zum Werkstoff?
#      Beispiele: 1.4305 (Automatenstahl, nicht schweißgeeignet) + Schweißnaht;
#      nichtrostender Stahl + "feuerverzinkt"; Baustahl S235 + "vergütet";
#      Aluminium + ISO 5817 (gilt für Stahl, für Alu: ISO 10042).
#
# Die Werkstoffdatenbank ist bewusst kompakt und konservativ: nur eindeutige
# Fälle führen zu einem Fehler, Unsicheres wird als "Prüfen" (warning) gemeldet.



import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml



# --------------------------------------------------------------------------
# Werkstoffdatenbank
# --------------------------------------------------------------------------
# weldable: "ja" | "bedingt" | "nein"
# hardenable: Verfahren, die fachlich sinnvoll sind
#   qt = vergüten/härten, case = einsatzhärten, nitr = nitrieren
# zinc: Feuer-/galvanisch verzinken sinnvoll, anodize: eloxieren sinnvoll


@dataclass
class Material:
    name: str                       # Anzeigename
    patterns: list[str]             # Regex-Alternativen (Nummer + Kurzname)
    category: str                   # baustahl|verguetung|einsatz|automaten|
                                    # nirosta|nirosta_auto|guss|alu|kupfer|kunststoff
    weldable: str = "ja"
    hardenable: set[str] = field(default_factory=set)
    zinc: bool = False
    anodize: bool = False
    # Eloxier-Eignung von Alu-Legierungen: "" (gut) | "bedingt" | "schlecht".
    # Praxisfall: falsche Legierung fürs Eloxieren gewählt (Si-/Cu-haltig).
    anodize_quality: str = ""
    castable: bool = False
    density: float | None = None   # g/cm³ – für den Masseabgleich
    max_hrc: float | None = None   # erreichbare Oberflächenhärte (HRC)
    note: str = ""


def _load_materials() -> list[Material]:
    """Lädt alle materials*.yaml aus dem rules-Ordner (Wissenspakete)."""
    out: list[Material] = []
    for f in rules_files("materials*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for e in data.get("materials", []):
            try:
                patterns = [str(p) for p in e["patterns"]]
                for pat in patterns:
                    re.compile(pat)  # Tippfehler sofort erkennen
                out.append(Material(
                    name=e["name"], patterns=patterns,
                    category=e["category"], weldable=e.get("weldable", "ja"),
                    hardenable=set(e.get("hardenable", [])),
                    zinc=bool(e.get("zinc", False)),
                    anodize=bool(e.get("anodize", False)),
                    anodize_quality=str(e.get("anodize_quality", "") or ""),
                    castable=bool(e.get("castable", False)),
                    density=(float(e["density"]) if e.get("density") else None),
                    max_hrc=(float(e["max_hrc"]) if e.get("max_hrc") else None),
                    note=e.get("note", ""),
                ))
            except (KeyError, TypeError, re.error) as exc:
                # Fehlerhafte Einträge überspringen statt Lauf abbrechen –
                # `drawing-checker --check-rules` zeigt sie dem Pfleger an.
                log.error("Werkstoffeintrag in %s fehlerhaft (%s): %r",
                          f.name, exc, e)
    return out


MATERIALS: list[Material] = _load_materials()

METAL_HT = {"baustahl", "verguetung", "einsatz", "automaten", "nirosta",
            "nirosta_auto"}


@dataclass
class MaterialHit:
    material: Material
    matched: str
    bbox: object
    page: int


def find_materials(ctx: CheckContext) -> list[MaterialHit]:
    """Erkennt alle Werkstoffbezeichnungen mit Fundstelle."""
    hits: list[MaterialHit] = []
    seen: set[str] = set()
    for block in ctx.pdf.blocks():
        for mat in MATERIALS:
            for pat in mat.patterns:
                m = re.search(pat, block.text, re.IGNORECASE)
                if m and mat.name not in seen:
                    seen.add(mat.name)
                    hits.append(MaterialHit(mat, m.group(0), block.bbox,
                                            block.page))
                    break
    return hits


# --------------------------------------------------------------------------
# Kontextsignale in Freitext / Symbolik
# --------------------------------------------------------------------------
RE_WELD = re.compile(
    r"schwei[ßs]|weld|\bwps\b|naht|fillet\s+weld|\bseam\b|ISO\s*2553"
    r"|ISO\s*5817|ISO\s*10042|EN\s*1090|\ba\s?[2-9]\s*[▲△]", re.IGNORECASE)
RE_HT_QT = re.compile(
    r"vergüte|härten|gehärtet|induktivgehärtet|randschichtgehärtet|\+QT\b"
    r"|quench|hardened|tempered|\bHRC\s*\d{2}", re.IGNORECASE)
RE_HT_CASE = re.compile(
    r"einsatzgehärtet|einsatzhärten|aufgekohlt|carburi[sz]ed|case[-\s]harden"
    r"|\bEht\b|\bCHD\b", re.IGNORECASE)
RE_HT_NITR = re.compile(r"nitrier|nitrid(?:ed|ing)|plasmanitrier|\bNHD\b",
                        re.IGNORECASE)
RE_ZINC = re.compile(
    r"feuerverzink|verzink|zinc[-\s]?(?:plated|coated)|galvani[sz]ed"
    r"|hot[-\s]?dip|zn\s*\d+\b|ISO\s*1461|ISO\s*2081", re.IGNORECASE)
RE_ANODIZE = re.compile(r"eloxier|anodi[sz]|anodisiert", re.IGNORECASE)
RE_ANODIZE_DECOR = re.compile(
    r"eloxier|anodi[sz](?:ed|ation|ing)?\s*(?:type\s*ii\b|farb|schwarz|black"
    r"|natur|clear|dekorativ|decorative)?", re.IGNORECASE)
RE_STUD_WELD = re.compile(
    r"schwei[ßs]bolzen|bolzenschwei[ßs]|stud\s*weld(?:ing|s|ed)?"
    r"|weld(?:ing|ed)?\s*studs?|ISO\s*13918|ISO\s*14555", re.IGNORECASE)
# Reihenfolge-Hinweise, die den Konflikt Schweißen/Verzinken auflösen.
RE_ZINC_SEQUENCE = re.compile(
    r"vor\s+dem\s+(?:feuer)?verzinken|nach\s+dem\s+schwei[ßs]en.{0,30}?verzink"
    r"|erst\s+schwei[ßs]en|geschwei[ßs]t\s*,?\s*(?:dann|danach).{0,20}?verzink"
    r"|weld(?:ed)?\s+(?:before|prior\s+to)\s+galvaniz|galvanized?\s+after\s+weld",
    re.IGNORECASE)
RE_BLACKEN = re.compile(r"brüniert?|black\s*oxid[ei]|schwarzoxid", re.IGNORECASE)
# Passungen (40H7, ⌀22 h6, js9 …) und metrische Gewinde – für den
# Schichtdicken-Check bei Verzinken/Eloxieren.
RE_FIT_TOKEN = re.compile(
    r"[⌀Øø]?\s*\d{1,3}\s*(?:H|h|G|g|F|f|K|k|M(?=\d)|m(?=\d)|N|n|P|p|R|r|S|s"
    r"|JS|js)\d{1,2}\b")
RE_METRIC_THREAD = re.compile(r"\bM\s*\d{1,3}(?:\s*[xX×]\s*\d+(?:[.,]\d+)?)?\b")
RE_COAT_EXCLUDE = re.compile(
    r"freihalten|freigehalten|abdecken|abgedeckt|abkleben|maskier"
    r"|nachschneiden|nacharbeiten|nachreiben|nach\s+dem\s+(?:verzinken"
    r"|eloxieren|beschichten)|masked?|plugged|after\s+(?:coating|galvanizing"
    r"|anodizing)|re-?tap", re.IGNORECASE)
RE_FILLER_309 = re.compile(r"\b309L?\b|\b1\.4332\b|ER\s*309", re.IGNORECASE)
RE_ISO5817_NENNUNG = re.compile(r"ISO\s*5817", re.IGNORECASE)
RE_ISO10042 = re.compile(r"ISO\s*10042", re.IGNORECASE)
RE_CAST = re.compile(r"\bguss|gussteil|casting|\bcast\b|rohteil|formschräge"
                     r"|draft\s+angle|ISO\s*8062|DCTG|GCTG", re.IGNORECASE)


def _find_context(ctx: CheckContext, regex: re.Pattern):
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m.group(0), block.bbox, block.page
    return None


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def check_material_present(ctx: CheckContext, hits: list[MaterialHit]) -> None:
    """MAT.MISSING: Werkstoff muss irgendwo als Bezeichnung erkennbar sein."""
    if not ctx.profile.enabled("MAT.MISSING"):
        return
    if hits:
        return
    label_kws = ctx.profile.rule_param("TB.MATERIAL", "keywords",
                                       ["Werkstoff", "Material"])
    text = ctx.pdf.full_text().lower()
    has_label = any(k.lower() in text for k in label_kws)
    if has_label:
        ctx.add("MAT.MISSING",
                "Werkstoffbezeichnung nicht erkannt (Schriftfeld-Label vorhanden, "
                "aber keine bekannte Bezeichnung gefunden)",
                severity=ctx.profile.severity("MAT.UNKNOWN"),
                detail="Entweder exotischer Werkstoff (Datenbank erweitern) "
                       "oder Angabe fehlt/ist unvollständig.")
    else:
        ctx.add("MAT.MISSING",
                "Kein Werkstoff auf der Zeichnung angegeben",
                detail="Weder Werkstoff-Feld noch erkennbare "
                       "Werkstoffbezeichnung gefunden.")


# Gattungsbegriffe für eloxierfähige Werkstoffe (ohne Legierungsangabe).
RE_ALU_TEXT = re.compile(r"alumin(?:i)?um|\baluminium\b|\btitan(?:ium)?\b",
                         re.IGNORECASE)


def check_material_conflicts(ctx: CheckContext, hits: list[MaterialHit]) -> None:
    """Fachliche Widersprüche zwischen Werkstoff und Freitext/Symbolik."""
    if not hits:
        return
    primary = hits[0].material
    all_mats = [h.material for h in hits]

    # --- Schweißen ---------------------------------------------------------
    weld = _find_context(ctx, RE_WELD)
    if weld and ctx.profile.enabled("MAT.WELD_CONFLICT"):
        snippet, bbox, page = weld
        if primary.weldable == "nein":
            ctx.add("MAT.WELD_CONFLICT",
                    f"Widerspruch: Werkstoff {primary.name} ist nicht "
                    f"schweißgeeignet, Zeichnung enthält aber Schweißangaben "
                    f"(„{snippet}“)",
                    bbox=bbox, page=page, detail=primary.note)
        elif primary.weldable == "bedingt":
            ctx.add("MAT.WELD_CONFLICT",
                    f"Werkstoff {primary.name} nur bedingt schweißgeeignet – "
                    f"Schweißangaben prüfen (Vorwärmung/Verfahren spezifiziert?)",
                    severity=ctx.profile.severity("MAT.WELD_LIMITED"),
                    bbox=bbox, page=page, detail=primary.note)

    # --- Wärmebehandlung ---------------------------------------------------
    if ctx.profile.enabled("MAT.HT_CONFLICT"):
        for regex, verfahren, needed in (
            (RE_HT_QT, "Härten/Vergüten", "qt"),
            (RE_HT_CASE, "Einsatzhärten", "case"),
            (RE_HT_NITR, "Nitrieren", "nitr"),
        ):
            hit = _find_context(ctx, regex)
            if not hit:
                continue
            snippet, bbox, page = hit
            if primary.category not in METAL_HT:
                ctx.add("MAT.HT_CONFLICT",
                        f"Widerspruch: {verfahren} („{snippet}“) ist für "
                        f"{primary.name} nicht anwendbar",
                        bbox=bbox, page=page)
            elif needed not in primary.hardenable:
                ctx.add("MAT.HT_CONFLICT",
                        f"Widerspruch: {verfahren} („{snippet}“) passt nicht zu "
                        f"{primary.name} (Werkstoff dafür nicht vorgesehen)",
                        bbox=bbox, page=page,
                        detail="Kohlenstoffgehalt/Legierung prüfen – ggf. "
                               "falscher Werkstoff oder falsche Angabe.")

    # --- Beschichtung ------------------------------------------------------
    if ctx.profile.enabled("MAT.COATING_CONFLICT"):
        zinc = _find_context(ctx, RE_ZINC)
        if zinc and primary.category in ("nirosta", "nirosta_auto", "alu",
                                         "kupfer", "kunststoff", "verbund"):
            snippet, bbox, page = zinc
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Verzinkung („{snippet}“) auf {primary.name} "
                    f"ist fachlich unsinnig",
                    bbox=bbox, page=page)
        anod = _find_context(ctx, RE_ANODIZE)
        # Auf Zeichnungen mit mehreren Werkstoffen (Baugruppen, Einsätze)
        # gehört das Eloxieren oft zu einem anderen Teil als dem
        # Hauptwerkstoff – dann ist es kein Widerspruch.
        # Auch die bloße Nennung („Aluminum insert") zählt hier als Beleg –
        # für den Widerspruch genügt sie, für MAT.MISSING nicht (eine
        # Gattung ohne Legierung ist keine beschaffbare Angabe).
        eloxierbar = (any(h.material.category in ("alu", "titan") for h in hits)
                      or bool(RE_ALU_TEXT.search(ctx.pdf.full_text())))
        if anod and not eloxierbar and primary.category not in ("alu", "titan"):
            snippet, bbox, page = anod
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Eloxieren („{snippet}“) ist nur für "
                    f"Aluminium möglich, Werkstoff ist {primary.name}",
                    bbox=bbox, page=page)
        blacken = _find_context(ctx, RE_BLACKEN)
        if blacken and primary.category not in (
                "baustahl", "verguetung", "einsatz", "automaten", "stahlguss",
                "guss"):
            snippet, bbox, page = blacken
            ctx.add("MAT.COATING_CONFLICT",
                    f"Widerspruch: Brünieren („{snippet}“) funktioniert nur "
                    f"auf Stahl/Eisenwerkstoffen, Werkstoff ist {primary.name}",
                    bbox=bbox, page=page)

    # --- Eloxier-Eignung der Alu-Legierung (Praxisfall: falsche Legierung) --
    if ctx.profile.enabled("MAT.ANODIZE_ALLOY") and primary.category == "alu":
        anod = _find_context(ctx, RE_ANODIZE)
        if anod and primary.anodize_quality in ("schlecht", "bedingt"):
            snippet, bbox, page = anod
            if primary.anodize_quality == "schlecht":
                ctx.add("MAT.ANODIZE_ALLOY",
                        f"Legierung {primary.name} ist zum Eloxieren ungeeignet "
                        f"(„{snippet}“)",
                        bbox=bbox, page=page, detail=primary.note)
            else:
                ctx.add("MAT.ANODIZE_ALLOY",
                        f"Legierung {primary.name} nur bedingt eloxierbar – "
                        f"Anforderung an die Eloxalschicht klären",
                        severity=ctx.profile.severity("MAT.ANODIZE_LIMITED"),
                        bbox=bbox, page=page, detail=primary.note)

    # --- Schweißbolzen / Reihenfolge Schweißen–Verzinken --------------------
    zinc_ctx = _find_context(ctx, RE_ZINC)
    stud = _find_context(ctx, RE_STUD_WELD)
    if ctx.profile.enabled("PROC.STUD_ON_ZINC") and stud and zinc_ctx:
        snippet, bbox, page = stud
        ctx.add("PROC.STUD_ON_ZINC",
                f"Bolzenschweißen („{snippet}“) auf feuerverzinktem Teil – "
                f"Zinkschicht verhindert prozesssichere Bolzenschweißung",
                bbox=bbox, page=page,
                detail="Bolzen vor dem Verzinken schweißen oder Schweißfläche "
                       "beim Verzinken abdecken – Reihenfolge auf der Zeichnung "
                       "eindeutig vorgeben.")
    elif (ctx.profile.enabled("PROC.WELD_ZINC_ORDER") and zinc_ctx
          and _find_context(ctx, RE_WELD)
          and not _find_context(ctx, RE_ZINC_SEQUENCE)):
        snippet, bbox, page = zinc_ctx
        ctx.add("PROC.WELD_ZINC_ORDER",
                "Schweißen und Verzinken auf derselben Zeichnung, aber keine "
                "Reihenfolge angegeben",
                bbox=bbox, page=page,
                detail="Üblich: erst schweißen, dann feuerverzinken. Ohne "
                       "Angabe drohen Schweißen auf Zinkschicht (Poren, "
                       "Zinkdämpfe) oder unverzinkte Nahtzonen.")

    # --- Schichtdicke vs. Passung/Gewinde (Verzinken/Eloxieren) -------------
    if ctx.profile.enabled("COAT.FIT"):
        coating = zinc_ctx or _find_context(ctx, RE_ANODIZE)
        if coating and not _find_context(ctx, RE_COAT_EXCLUDE):
            fit = _find_context(ctx, RE_FIT_TOKEN)
            thread = _find_context(ctx, RE_METRIC_THREAD)
            target = fit or thread
            if target:
                what = "Passung" if fit else "Gewinde"
                snippet, bbox, page = target
                ctx.add("COAT.FIT",
                        f"Beschichtung ({coating[0]}) und {what} "
                        f"(„{snippet}“) ohne Freihalte-/Nacharbeitsvermerk",
                        bbox=bbox, page=page,
                        detail="Zink-/Eloxalschicht verändert das Maß "
                               "(Feuerverzinkung 50–150 µm). Passflächen/"
                               "Gewinde freihalten, abdecken oder Nacharbeit "
                               "(nachschneiden/reiben) vorgeben.")

    # --- Mischverbindungen beim Schweißen -----------------------------------
    if weld:
        cats = {m.category for m in all_mats}
        steel_cats = cats & {"baustahl", "verguetung", "einsatz", "automaten",
                             "stahlguss"}
        snippet, bbox, page = weld
        if ctx.profile.enabled("WELD.MIXED") and "alu" in cats and steel_cats:
            ctx.add("WELD.MIXED",
                    "Widerspruch: Aluminium und Stahl auf einer "
                    "Schweißzeichnung – schmelzschweißen ist nicht möglich",
                    bbox=bbox, page=page,
                    detail="Mischverbindung Al/Fe nur über Sonderverfahren "
                           "(Reib-/Explosionsschweißen) oder mechanisch fügen.")
        elif (ctx.profile.enabled("WELD.MIXED_FILLER")
              and steel_cats and cats & {"nirosta", "nirosta_auto"}
              and not _find_context(ctx, RE_FILLER_309)):
            ctx.add("WELD.MIXED_FILLER",
                    "Schwarz-Weiß-Verbindung (Edelstahl + un-/niedriglegierter "
                    "Stahl) ohne Zusatzwerkstoff-Angabe",
                    bbox=bbox, page=page,
                    detail="Für Mischverbindungen Zusatzwerkstoff vorgeben "
                           "(üblich 309L / 1.4332), sonst Aufmischungsrisse.")

    # --- Guss --------------------------------------------------------------
    if ctx.profile.enabled("MAT.CAST_CONFLICT"):
        cast = _find_context(ctx, RE_CAST)
        if cast and not any(m.castable for m in all_mats):
            snippet, bbox, page = cast
            ctx.add("MAT.CAST_CONFLICT",
                    f"Gusskontext („{snippet}“), aber {primary.name} ist kein "
                    f"Gusswerkstoff – Werkstoff- oder Textangabe prüfen",
                    bbox=bbox, page=page)

    # --- Normbezug passt zum Werkstoff ------------------------------------
    if ctx.profile.enabled("NORM.MATERIAL_MISMATCH"):
        if primary.category == "alu":
            hit = _find_context(ctx, RE_ISO5817_NENNUNG)
            if hit:
                snippet, bbox, page = hit
                ctx.add("NORM.MATERIAL_MISMATCH",
                        "ISO 5817 gilt für Stahl – für Aluminium ist "
                        "ISO 10042 anzugeben",
                        bbox=bbox, page=page)
        elif primary.category not in ("alu",):
            hit = _find_context(ctx, RE_ISO10042)
            if hit and primary.category != "alu":
                snippet, bbox, page = hit
                ctx.add("NORM.MATERIAL_MISMATCH",
                        f"ISO 10042 gilt für Aluminium – Werkstoff ist aber "
                        f"{primary.name} (Stahl: ISO 5817)",
                        bbox=bbox, page=page)


# --------------------------------------------------------------------------
# Normen-Katalog: zurückgezogene/ersetzte Normen
# --------------------------------------------------------------------------
def _load_obsolete_norms() -> list[tuple[re.Pattern, str]]:
    """Lädt alle norms*.yaml aus dem rules-Ordner (Wissenspakete)."""
    out: list[tuple[re.Pattern, str]] = []
    for f in rules_files("norms*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for e in data.get("obsolete", []):
            try:
                out.append((re.compile(e["pattern"], re.IGNORECASE),
                            e["message"]))
            except (KeyError, re.error) as exc:
                log.error("Normeintrag in %s fehlerhaft (%s): %r",
                          f.name, exc, e)
    return out


OBSOLETE_NORMS: list[tuple[re.Pattern, str]] = _load_obsolete_norms()


def check_obsolete_norms(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("NORM.OBSOLETE"):
        return
    for block in ctx.pdf.blocks():
        for regex, message in OBSOLETE_NORMS:
            if regex.search(block.text):
                ctx.add("NORM.OBSOLETE",
                        f"Veralteter Normbezug: {message}",
                        bbox=block.bbox, page=block.page)


def run_material_checks(ctx: CheckContext) -> None:
    hits = find_materials(ctx)
    check_material_present(ctx, hits)
    check_material_conflicts(ctx, hits)
    check_obsolete_norms(ctx)


# ======================================================================
# process_checks
# ======================================================================
# Verfahrensspezifische Vollständigkeitsprüfungen.
#
# Prüft je erkanntem Fertigungsverfahren, ob die dafür zwingenden Angaben auf
# der Zeichnung stehen. Grundlage: Fertigungs- und Schweißpraxis (ISO 2553,
# ISO 9692, VDG-Merkblatt K 200, Blech-Konstruktionsrichtlinien).
#
#   WELD.NO_SIZE      Schweißsymbolik ohne Nahtdicke (a-/z-Maß)
#   WELD.AZ_MIXED     a- und z-Maße gemischt – teuerster Lesefehler der Praxis
#   WELD.NO_PREP      Stumpfnaht ohne Angabe der Nahtvorbereitung (ISO 9692)
#   CAST.NO_DRAFT     Gussteil ohne Formschrägen-Angabe (ISO 10135/DIN EN 12890)
#   CAST.NO_RMA       Gussteil mit Bearbeitung, aber ohne Bearbeitungszugabe
#   SHEET.NO_THICK    Blech-/Biegeteil ohne Blechdickenangabe
#   SHEET.NO_RADIUS   Abkantung ohne Biegeradius
#   HT.NO_HARDNESS    Wärmebehandlung ohne Härtewert (DIN 6773)
#   HT.NO_DEPTH       Randschichthärten ohne Einhärtetiefe (Eht/CHD/NHD)
#   HT.HARDNESS_LIMIT Härteforderung über dem, was der Werkstoff hergibt



import re


# --- Schweißen ------------------------------------------------------------
# a-Maß (Nahtdicke) und z-Maß (Schenkellänge) einer Kehlnaht.
RE_WELD_A = re.compile(r"(?<![A-Za-z0-9])a\s?(\d{1,2}(?:[.,]\d)?)\b")
RE_WELD_Z = re.compile(r"(?<![A-Za-z0-9])z\s?(\d{1,2}(?:[.,]\d)?)\b")
# "fillet" heißt auf englischen Zeichnungen meist Eckenradius, nicht
# Kehlnaht – allein ist es kein Schweißbeleg (Kalibriersatz: 21 Fehlalarme).
RE_WELD_CONTEXT = re.compile(
    r"schwei[ßs]|\bweld|\bnaht\b|kehlnaht|fillet\s*weld|weld\s*seam"
    r"|ISO\s*2553|ISO\s*5817",
    re.IGNORECASE)
RE_BUTT_WELD = re.compile(
    r"stumpfnaht|stumpfsto[ßs]|\bV-?naht\b|\bY-?naht\b|\bU-?naht\b"
    r"|\bHV-?naht\b|\bDV-?naht\b|butt\s*weld|groove\s*weld|full\s*pen",
    re.IGNORECASE)
RE_WELD_PREP = re.compile(
    r"ISO\s*9692|nahtvorbereitung|fugenform|wurzel(?:öffnung|spalt)"
    r"|öffnungswinkel|steghöhe|joint\s*preparation|root\s*(?:gap|face)",
    re.IGNORECASE)

# --- Guss -----------------------------------------------------------------
RE_CAST_CONTEXT = re.compile(
    r"\bguss(?:teil|rohteil|stück)?\b|casting|EN[-\s]?GJ|rohteil|sandguss"
    r"|druckguss|kokillenguss", re.IGNORECASE)
RE_DRAFT = re.compile(
    r"formschräge|aushebeschräge|draft\s*angle|entformungsschräge"
    r"|ISO\s*10135|DIN\s*EN\s*12890|\b\d{1,2}\s*°\s*(?:formschräge|draft)",
    re.IGNORECASE)
RE_RMA = re.compile(
    r"bearbeitungszugabe|aufma[ßs]|\bRMA\b|machining\s*allowance"
    r"|zugabe\s*\d|ISO\s*8062-?3", re.IGNORECASE)
RE_MACHINED_SURFACE = re.compile(
    r"bearbeitet|gefräst|gedreht|geschliffen|machined|spanend|\bRa\s*\d"
    r"|\bH[789]\b|\bh[6789]\b", re.IGNORECASE)

# --- Blech ----------------------------------------------------------------
RE_SHEET_CONTEXT = re.compile(
    r"\bblech\b|abgekantet|gekantet|abkanten|kantung|biegeteil|sheet\s*metal"
    r"|laserzuschnitt|lasergeschnitten|\bbend(?:ing)?\b|abwicklung",
    re.IGNORECASE)
RE_SHEET_THICK = re.compile(
    r"blechdicke|blechstärke|materialstärke|\bdicke\s*\d|\bt\s*=\s*\d"
    r"|sheet\s*thickness|thickness\s*\d|\bs\s*=\s*\d", re.IGNORECASE)
RE_BEND_RADIUS = re.compile(
    r"biegeradius|innenradius|\bri\s*=|bend\s*radius|inner\s*radius"
    r"|biegeradien", re.IGNORECASE)
RE_BEND_PRESENT = re.compile(
    r"abgekantet|gekantet|abkanten|kantung|biegeteil|biegewinkel"
    r"|\bbend(?:ing|s)?\b|abwicklung", re.IGNORECASE)




def check_weld_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_WELD_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    text = ctx.pdf.full_text()
    a_sizes = RE_WELD_A.findall(text)
    z_sizes = RE_WELD_Z.findall(text)

    if ctx.profile.enabled("WELD.NO_SIZE") and not a_sizes and not z_sizes:
        ctx.add("WELD.NO_SIZE",
                "Schweißangaben ohne Nahtdicke (a-Maß bzw. z-Maß)",
                bbox=bbox, page=page,
                detail="Ohne Nahtdicke ist die Verbindung nicht bemessen – "
                       "a (Nahtdicke) oder z (Schenkellänge) nach ISO 2553 "
                       "angeben.")
    elif ctx.profile.enabled("WELD.AZ_MIXED") and a_sizes and z_sizes:
        ctx.add("WELD.AZ_MIXED",
                f"a- und z-Maße gemischt verwendet (a: {', '.join(a_sizes[:3])}"
                f" / z: {', '.join(z_sizes[:3])})",
                bbox=bbox, page=page,
                detail="a-Maß (Nahtdicke) und z-Maß (Schenkellänge) "
                       "unterscheiden sich um Faktor √2 (~29 %). Gemischte "
                       "Angaben auf einer Zeichnung führen regelmäßig zu "
                       "unterdimensionierten Nähten – einheitlich bemaßen.")

    if ctx.profile.enabled("WELD.NO_PREP"):
        butt = _find(ctx, RE_BUTT_WELD)
        if butt and not _find(ctx, RE_WELD_PREP):
            _bm, bbbox, bpage = butt
            ctx.add("WELD.NO_PREP",
                    "Stumpf-/Fugennaht ohne Angabe der Nahtvorbereitung",
                    bbox=bbbox, page=bpage,
                    detail="Fugenform, Öffnungswinkel und Wurzelspalt nach "
                           "ISO 9692 angeben – sonst entscheidet der "
                           "Lieferant über die Nahtqualität.")


def check_cast_details(ctx: CheckContext) -> None:
    hit = _find(ctx, RE_CAST_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("CAST.NO_DRAFT") and not _find(ctx, RE_DRAFT):
        ctx.add("CAST.NO_DRAFT",
                "Gussteil ohne Angabe von Formschrägen",
                bbox=bbox, page=page,
                detail="Formschrägen sind in Winkelgraden anzugeben "
                       "(DIN EN 12890 / ISO 10135); ohne Angabe legt sie die "
                       "Gießerei fest – mit Folgen für Maße und Gewicht.")
    if (ctx.profile.enabled("CAST.NO_RMA")
            and _find(ctx, RE_MACHINED_SURFACE) and not _find(ctx, RE_RMA)):
        ctx.add("CAST.NO_RMA",
                "Gussteil mit bearbeiteten Flächen, aber ohne "
                "Bearbeitungszugabe (RMA)",
                bbox=bbox, page=page,
                detail="Bearbeitungszugabe nach ISO 8062-3 angeben, sonst ist "
                       "unklar, ob das Rohteil genug Material für die "
                       "Bearbeitung hat.")


def check_sheet_details(ctx: CheckContext, dims: list[DimValue]) -> None:
    hit = _find(ctx, RE_SHEET_CONTEXT)
    if not hit:
        return
    _m, bbox, page = hit
    if ctx.profile.enabled("SHEET.NO_THICK") and not _find(ctx, RE_SHEET_THICK):
        ctx.add("SHEET.NO_THICK",
                "Blech-/Biegeteil ohne ausgewiesene Blechdicke",
                bbox=bbox, page=page,
                detail="Blechdicke explizit angeben (z. B. „Blechdicke 3 mm“ "
                       "oder t = 3) – aus der Ansicht allein ist sie für den "
                       "Zuschnitt nicht eindeutig.")
    if ctx.profile.enabled("SHEET.NO_RADIUS"):
        bend = _find(ctx, RE_BEND_PRESENT)
        has_radius = bool(_find(ctx, RE_BEND_RADIUS)
                          or [d for d in dims if d.kind is DimKind.RADIUS])
        if bend and not has_radius:
            _bm, bbbox, bpage = bend
            ctx.add("SHEET.NO_RADIUS",
                    "Abkantung ohne Angabe des Biegeradius",
                    bbox=bbbox, page=bpage,
                    detail="Innenradius angeben (Faustregel ri ≥ Blechdicke). "
                           "Ohne Angabe wählt der Fertiger das Werkzeug – "
                           "Abwicklung und Endmaße ändern sich dadurch.")


def run_process_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_weld_details(ctx)
    check_cast_details(ctx)
    check_sheet_details(ctx, dims)
    check_heat_treatment(ctx)
    check_hydrogen_embrittlement(ctx)


# --- Wasserstoffversprödung (EN ISO 4042 / EN ISO 9588) -------------------
# Galvanische (elektrolytische) Beschichtungen setzen Wasserstoff frei.
RE_GALVANIC = re.compile(
    r"galvanisch\s*(?:verzinkt|vernickelt|verchromt)?|elektrolytisch"
    r"|Zn/?Ni|zink[-\s]?nickel|vercadmiert|Cd\s*besch"
    r"|electroplat|zinc\s*plated|ISO\s*4042|ISO\s*2081|ISO\s*19598",
    re.IGNORECASE)
# Hinweis auf die vorgeschriebene Entsprödung.
RE_DEEMBRITTLE = re.compile(
    r"entspröd|wasserstoffarm|wasserstoffvers|entsprödungsglüh|tempern"
    r"|bak(?:e|ing|en)|hydrogen\s*(?:relief|embrittle)|ISO\s*9588"
    r"|ISO\s*15330", re.IGNORECASE)
# Festigkeitsklassen und Härten, ab denen entsprödet werden muss.
RE_HIGH_STRENGTH_CLASS = re.compile(
    r"(?:10\.9|12\.9|14\.9)|festigkeitsklasse\s*(?:10|12|14)",
    re.IGNORECASE)


def check_hydrogen_embrittlement(ctx: CheckContext) -> None:
    """Galvanische Beschichtung auf hochfestem Stahl ohne Entsprödung.

    Nach EN ISO 4042 müssen Teile mit einer Zugfestigkeit ab 1000 MPa
    (bzw. Härte ab 320 HV / 32 HRC) und Festigkeitsklassen ab 10.9 nach dem
    galvanischen Beschichten wasserstoffarm geglüht werden – sonst brechen
    sie verzögert und ohne Vorankündigung. Auf Zeichnungen fehlt die
    Forderung regelmäßig, weil sie als „Sache des Beschichters" gilt.
    """
    if not ctx.profile.enabled("COAT.EMBRITTLEMENT"):
        return
    hit = _find(ctx, RE_GALVANIC)
    if hit is None or _find(ctx, RE_DEEMBRITTLE):
        return
    _m, bbox, page = hit
    reason = _high_strength_reason(ctx)
    if not reason:
        return
    ctx.add("COAT.EMBRITTLEMENT",
            f"Galvanische Beschichtung an hochfestem Bauteil ({reason}) ohne "
            f"geforderte Entsprödung",
            bbox=bbox, page=page,
            detail="EN ISO 4042 verlangt ab 1000 MPa bzw. 320 HV eine "
                   "Wasserstoffarmglühung (typisch 190–230 °C, ≥ 4 h, "
                   "innerhalb von 4 h nach dem Beschichten); die Wirksamkeit "
                   "wird nach EN ISO 15330 nachgewiesen. Ohne diese Angabe "
                   "drohen verzögerte Sprödbrüche. Alternativ mechanisch "
                   "beschichten oder eine Zinklamellenbeschichtung "
                   "(ISO 10683) vorschreiben.")


def _high_strength_reason(ctx: CheckContext) -> str:
    """Begründung, warum das Teil als hochfest gilt ("" = ist es nicht)."""
    text = ctx.pdf.full_text()
    m = RE_HIGH_STRENGTH_CLASS.search(text)
    if m:
        return f"Festigkeitsklasse {m.group(0)}"
    for m in RE_HARDNESS_HRC.finditer(text):
        try:
            if float(m.group(1).replace(",", ".")) >= 32:
                return f"{m.group(0).strip()}"
        except ValueError:
            continue
    for m in RE_HARDNESS_HV.finditer(text):
        try:
            if float(m.group(1)) >= 320:
                return f"{m.group(0).strip()}"
        except ValueError:
            continue
    for m in RE_STRENGTH.finditer(text):
        for group in m.groups():
            try:
                if group and float(str(group).replace(",", ".")) >= 1000:
                    return f"{m.group(0).strip()}"
            except ValueError:
                continue
    return ""


# --- Wärmebehandlung (DIN 6773) -------------------------------------------
RE_HARDNESS_HRC = re.compile(r"(\d{2}(?:[.,]\d)?)\s*[-–+±]?\s*(?:\d{1,2})?\s*HRC",
                             re.IGNORECASE)
RE_HARDNESS_HV = re.compile(r"(\d{3,4})\s*HV\s*\d*", re.IGNORECASE)
RE_HARDNESS_ANY = re.compile(r"\bHRC\b|\bHV\s*\d|\bHB\b|härte(?!n)|hardness",
                             re.IGNORECASE)
RE_CASE_DEPTH = re.compile(
    r"\bEht\b|\bCHD\b|\bNHD\b|\bSHD\b|einhärt(?:e|ungs)tiefe|nitrierhärtetiefe"
    r"|case\s*depth|einsatztiefe|\bRht\b", re.IGNORECASE)
RE_SURFACE_HT = re.compile(
    r"einsatzgehärtet|einsatzhärten|aufgekohlt|carburi[sz]|nitrier|nitrid"
    r"|randschichtgehärtet|induktivgehärtet|induction\s*harden|case\s*harden"
    r"|flammgehärtet", re.IGNORECASE)
# Genormter Lieferzustand im Werkstoffnamen (+QT, +N, +A …): Wärmebehandlung
# und Festigkeit sind damit normativ festgelegt (z. B. EN 10083) – eine
# separate Härteangabe ist dann NICHT erforderlich.
RE_DELIVERY_STATE = re.compile(
    r"\+\s*(?:QT|AT|NT|AR|N|A|C|M|P|SR|U)\b")
RE_STRENGTH = re.compile(
    r"\b\d{3,4}\s*(?:N/mm²|N/mm2|MPa)\b|\bRm\s*[≥>=]|\bRe(?:H|L)?\s*[≥>=]",
    re.IGNORECASE)
RE_HT_PROCESS = re.compile(
    r"gehärtet|härten|vergütet|vergüten|hardened|quenched|tempered"
    r"|einsatzgehärtet|nitriert", re.IGNORECASE)


def check_heat_treatment(ctx: CheckContext) -> None:
    """Härteangaben auf Vollständigkeit und Plausibilität prüfen (DIN 6773)."""
    pass  # (im selben Modul)

    ht = _find(ctx, RE_HT_PROCESS)
    if not ht:
        return
    _m, bbox, page = ht
    text = ctx.pdf.full_text()

    # 1) Härteverfahren ohne Härtewert
    if (ctx.profile.enabled("HT.NO_HARDNESS")
            and not RE_HARDNESS_ANY.search(text)
            and not RE_DELIVERY_STATE.search(text)
            and not RE_STRENGTH.search(text)):
        ctx.add("HT.NO_HARDNESS",
                "Wärmebehandlung angegeben, aber kein Härtewert",
                bbox=bbox, page=page,
                detail="Nach DIN 6773 gehören Oberflächenhärte (HRC/HV) und "
                       "Toleranz zur Angabe – sonst ist das Ergebnis nicht "
                       "prüfbar.")

    # 2) Randschichtverfahren ohne Einhärtetiefe
    surface = _find(ctx, RE_SURFACE_HT)
    if (ctx.profile.enabled("HT.NO_DEPTH") and surface
            and not RE_CASE_DEPTH.search(text)):
        _sm, sbbox, spage = surface
        ctx.add("HT.NO_DEPTH",
                "Randschichthärten ohne Angabe der Einhärtetiefe",
                bbox=sbbox, page=spage,
                detail="Einhärtungstiefe (Eht/CHD bzw. NHD beim Nitrieren) "
                       "mit Grenzhärte angeben – ohne sie ist die Randschicht "
                       "nicht spezifiziert (DIN 6773 / ISO 15787).")

    # 3) Härtewert über dem, was der Werkstoff hergibt
    if not ctx.profile.enabled("HT.HARDNESS_LIMIT"):
        return
    hits = find_materials(ctx)
    material = next((h.material for h in hits if h.material.max_hrc), None)
    if material is None:
        return
    values = [float(v.replace(",", ".")) for v in RE_HARDNESS_HRC.findall(text)]
    if not values:
        return
    reserve = float(ctx.profile.params.get("hardness_reserve_hrc", 2))
    highest = max(values)
    if highest > material.max_hrc + reserve:
        ctx.add("HT.HARDNESS_LIMIT",
                f"Härteforderung {highest:g} HRC über dem für {material.name} "
                f"erreichbaren Wert (ca. {material.max_hrc:g} HRC)",
                bbox=bbox, page=page,
                detail="Entweder ist der Werkstoff für die geforderte Härte "
                       "ungeeignet oder die Härteangabe ist zu hoch – "
                       "Werkstoff oder Anforderung anpassen.")


# ======================================================================
# mass_checks
# ======================================================================
# Plausibilitätsprüfung der Gewichtsangabe – auch ohne STEP-Datei.
#
# Der Masseabgleich gegen das STEP-Modell (`geometry_checks.check_mass`) ist
# die schärfste Prüfung, setzt aber ein STEP voraus. Weil ein großer Teil der
# Pakete nur ein PDF enthält, prüft dieses Modul die Gewichtsangabe allein
# gegen die Zeichnung:
#
#   MASS.IMPOSSIBLE  Das Teil wäre schwerer als ein VOLLER Quader seiner
#                    Hüllmaße. Physikalisch unmöglich – klassische Ursachen:
#                    Einheit vertauscht (g/kg), Komma verrutscht, Gewicht aus
#                    einer anderen Variante übernommen, falscher Werkstoff.
#   MASS.TOO_LIGHT   Das Teil wäre fast nur Luft (Füllgrad < 1 %). Bei Blech-
#                    und Schweißkonstruktionen möglich, sonst verdächtig.
#   MASS.DENSITY_HINT Die Gewichtsangabe passt rechnerisch zu einem ANDEREN
#                    Werkstoff als dem angegebenen (Volumen aus dem STEP).
#                    Findet den häufigsten Fall „Schriftfeld kopiert".
#
# Grundgedanke der Unmöglichkeitsprüfung:
#
#     m = ρ · V_Teil   und   V_Teil ≤ V_Hüllquader
#     =>  ρ_rechnerisch = m / V_Hüllquader ≤ ρ_Werkstoff
#
# Weil die Hüllmaße aus den größten Zeichnungsmaßen geschätzt werden, ist der
# Quader in aller Regel zu GROSS – das Urteil „unmöglich" ist damit auf der
# sicheren Seite. Zusätzlich wird erst ab einem deutlichen Faktor gemeldet.



import logging



# Verhältnis rechnerische Dichte / Werkstoffdichte, ab dem gemeldet wird.
DEFAULT_IMPOSSIBLE_FACTOR = 1.3     # 30 % Reserve für grobe Hüllmaßschätzung
DEFAULT_MIN_FILL = 0.01             # Füllgrad, unter dem es verdächtig wird
# Typische Zahlendreher: Faktor zwischen Angabe und Rechnung.
UNIT_FACTORS = {1000.0: "g statt kg", 100.0: "Komma zwei Stellen verrutscht",
                10.0: "Komma eine Stelle verrutscht"}


def check_mass_plausibility(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gewichtsangabe gegen die Hüllmaße der Zeichnung prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte ("" wenn nicht prüfbar).
    """
    if not (ctx.profile.enabled("MASS.IMPOSSIBLE")
            or ctx.profile.enabled("MASS.TOO_LIGHT")):
        return ""
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return ""
    density = _declared_density(ctx)
    if density is None:
        return ""
    box_cm3 = _envelope_volume_cm3(dims)
    if box_cm3 is None:
        return ""

    max_kg = box_cm3 * density / 1000.0        # g/cm³ · cm³ = g -> kg
    fill = drawing_kg / max_kg if max_kg else 0.0
    summary = (f"Masse-Plausibilität: {drawing_kg:.2f} kg, Hüllquader "
               f"{box_cm3:.0f} cm³ → Füllgrad {fill * 100:.0f} %")

    factor = float(ctx.profile.params.get("mass_impossible_factor",
                                          DEFAULT_IMPOSSIBLE_FACTOR))
    if fill > factor and ctx.profile.enabled("MASS.IMPOSSIBLE"):
        ctx.add("MASS.IMPOSSIBLE",
                f"Gewichtsangabe unmöglich: {drawing_kg:.2f} kg bei Hüllmaßen "
                f"{_envelope_text(dims)} – ein VOLLER Block aus diesem "
                f"Werkstoff wöge nur {max_kg:.2f} kg",
                detail=_explain(drawing_kg, max_kg, density, box_cm3))
    elif (fill < float(ctx.profile.params.get("mass_min_fill", DEFAULT_MIN_FILL))
          and ctx.profile.enabled("MASS.TOO_LIGHT")):
        ctx.add("MASS.TOO_LIGHT",
                f"Gewichtsangabe sehr klein: {drawing_kg:.3f} kg entspricht "
                f"{fill * 100:.1f} % des Hüllquaders ({max_kg:.1f} kg voll)",
                severity=ctx.profile.severity("MASS.TOO_LIGHT",
                                              Severity.WARNING),
                detail="Bei dünnen Blechen und Schweißrahmen möglich. Sonst "
                       "prüfen, ob die Einheit stimmt (g statt kg) oder das "
                       "Gewicht von einer kleineren Variante stammt.")
    return summary


def check_density_hint(ctx: CheckContext, model_volume_mm3: float) -> None:
    """Passt die Gewichtsangabe rechnerisch zu einem anderen Werkstoff?

    Wird nur mit STEP aufgerufen (exaktes Volumen). Der Hinweis ist die
    Diagnose zur Massenabweichung: „Angabe passt zu Stahl, angegeben ist
    Aluminium" – der Klassiker beim kopierten Schriftfeld.
    """
    if not ctx.profile.enabled("MASS.DENSITY_HINT") or model_volume_mm3 <= 0:
        return
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return
    declared = _declared_material(ctx)
    if declared is None or not declared.density:
        return
    volume_cm3 = model_volume_mm3 / 1000.0
    implied = drawing_kg * 1000.0 / volume_cm3      # g/cm³
    if abs(implied - declared.density) / declared.density <= 0.10:
        return                                      # passt zum Werkstoff

    match = _closest_material(implied, exclude=declared.name)
    if match is None:
        return
    ctx.add("MASS.DENSITY_HINT",
            f"Gewichtsangabe passt nicht zu {declared.name}: rechnerisch "
            f"{implied:.1f} g/cm³ – das entspricht {match.name} "
            f"({match.density} g/cm³)",
            detail=f"{drawing_kg:.2f} kg auf {volume_cm3:.0f} cm³ "
                   f"Modellvolumen. Häufige Ursache: Schriftfeld aus einer "
                   f"anderen Zeichnung übernommen, Werkstoff geändert ohne "
                   f"das Gewicht neu zu rechnen, oder falsche Variante im "
                   f"STEP. Erwartet für {declared.name}: "
                   f"{volume_cm3 * declared.density / 1000:.2f} kg.")


# ---------------------------------------------------------------- Intern
def _declared_material(ctx: CheckContext):
    hits = [h.material for h in find_materials(ctx) if h.material.density]
    return hits[0] if hits else None


def _declared_density(ctx: CheckContext) -> float | None:
    mat = _declared_material(ctx)
    return mat.density if mat else None


def _envelope_volume_cm3(dims: list[DimValue]) -> float | None:
    """Volumen des geschätzten Hüllquaders in cm³.

    Genutzt werden die drei größten unterschiedlichen Maße. Fehlt eine
    dritte Kante (typisch bei Wellen: nur Länge und Durchmesser bemaßt),
    wird die zweitgrößte doppelt verwendet – der Quader bleibt damit eine
    Obergrenze für das tatsächliche Bauteilvolumen.
    """
    env = estimate_envelope(dims, top_n=3)
    if len(env) < 2:
        return None
    a, b = env[0], env[1]
    c = env[2] if len(env) >= 3 else b
    volume = a * b * c / 1000.0
    return volume if volume > 0 else None


def _envelope_text(dims: list[DimValue]) -> str:
    env = estimate_envelope(dims, top_n=3)
    return "×".join(f"{v:g}" for v in env) + " mm"


def _explain(drawing_kg: float, max_kg: float, density: float,
             box_cm3: float) -> str:
    ratio = drawing_kg / max_kg if max_kg else 0.0
    hint = ""
    for factor, text in UNIT_FACTORS.items():
        if abs(ratio - factor) / factor < 0.35:
            hint = f" Der Faktor ≈ {factor:g} deutet auf {text} hin."
            break
    return (f"Hüllquader {box_cm3:.0f} cm³ × {density} g/cm³ = {max_kg:.2f} kg "
            f"als absolute Obergrenze; angegeben sind {drawing_kg:.2f} kg "
            f"({ratio:.1f}-faches).{hint} Die Hüllmaße stammen aus den "
            f"größten Zeichnungsmaßen und sind eher zu groß geschätzt – die "
            f"Angabe ist damit sicher zu hoch.")


def _closest_material(implied: float, exclude: str):
    """Werkstoff, dessen Dichte am besten zur Rechnung passt (±8 %)."""
    best = None
    best_dev = 0.08
    for mat in MATERIALS:
        if not mat.density or mat.name == exclude:
            continue
        dev = abs(mat.density - implied) / mat.density
        if dev < best_dev:
            best, best_dev = mat, dev
    return best


# ======================================================================
# purchasing_checks
# ======================================================================
# Prüfung aus Sicht des internationalen Einkaufs.
#
# Die Zeichnung muss für einen Lieferanten ausreichen, der weder im Haus
# sitzt noch die Historie des Teils kennt. Geprüft wird deshalb nicht nur die
# technische Richtigkeit, sondern die Anfragereife:
#
#   PUR.VAGUE_SPEC   Formulierungen ohne prüfbaren Inhalt („ca. 20", „nach
#                    Absprache", „sauber entgraten", „TBD"). Sie erzeugen
#                    Rückfragen, Nachträge und Streit bei der Abnahme.
#   PUR.INTERNAL_NORM Verweis auf Werk-/Konzernnormen, die ein externer
#                    Lieferant nicht beziehen kann. Sie müssen der Anfrage
#                    als Dokument beiliegen.
#   PUR.STOCK_SIZE   Blechdicke oder Rundmaterial außerhalb der gängigen
#                    Vorzugsmaße. Das Teil muss dann aus dem nächstgrößeren
#                    Halbzeug herausgearbeitet werden – teurer, längere
#                    Lieferzeit, oft ohne konstruktiven Grund.
#
# Das Wissen steht in `rules/beschaffung*.yaml` und ist ohne Codeänderung
# erweiterbar.



import logging
import re

import yaml




def _load_knowledge() -> dict:
    """Alle beschaffung*.yaml einsammeln (mitgeliefert + externe Ordner)."""
    vage: list[tuple[re.Pattern, str]] = []
    hausnormen: list[tuple[re.Pattern, str]] = []
    halbzeuge: dict[str, list[float]] = {}
    for f in rules_files("beschaffung*.yaml"):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            log.error("Beschaffungs-Wissenspaket %s nicht lesbar: %s", f, exc)
            continue
        for key, target in (("vage", vage), ("hausnormen", hausnormen)):
            for entry in data.get(key, []) or []:
                try:
                    target.append((re.compile(entry["pattern"], re.IGNORECASE),
                                   entry["message"]))
                except (KeyError, TypeError, re.error) as exc:
                    log.error("Eintrag in %s (%s) fehlerhaft: %s", f, key, exc)
        for key, values in (data.get("halbzeuge") or {}).items():
            try:
                halbzeuge.setdefault(key, []).extend(float(v) for v in values)
            except (TypeError, ValueError):
                log.error("Halbzeugliste %r in %s fehlerhaft", key, f)
    return {"vage": vage, "hausnormen": hausnormen, "halbzeuge": halbzeuge}


KNOWLEDGE = _load_knowledge()

RE_SHEET_THICK_VALUE = re.compile(
    r"(?:blechdicke|blechstärke|materialstärke|sheet\s*thickness"
    r"|thickness|dicke|\bt|\bs)\s*[:=]?\s*(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:mm)?",
    re.IGNORECASE)
RE_ROUND_STOCK = re.compile(
    r"(?:rundstahl|rundmaterial|blankstahl|round\s*bar|stangenmaterial)"
    r"[^\n]{0,20}?(\d{1,3}(?:[.,]\d{1,2})?)", re.IGNORECASE)


def run_purchasing_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_vague_specs(ctx)
    check_internal_norms(ctx)
    check_stock_sizes(ctx, dims)


def check_vague_specs(ctx: CheckContext) -> None:
    """Unbestimmte Formulierungen melden – je Muster höchstens einmal."""
    if not ctx.profile.enabled("PUR.VAGUE_SPEC"):
        return
    limit = int(ctx.profile.rule_param("PUR.VAGUE_SPEC", "max_findings", 4))
    shown = 0
    for regex, message in KNOWLEDGE["vage"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        shown += 1
        if shown > limit:
            continue
        ctx.add("PUR.VAGUE_SPEC",
                f"Unbestimmte Angabe „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Aus Sicht eines auswärtigen Lieferanten nicht "
                       "kalkulierbar und bei der Abnahme nicht prüfbar. "
                       "Anforderung mit Zahlenwert oder Norm angeben.")
    if shown > limit:
        ctx.add("PUR.VAGUE_SPEC",
                f"… und {shown - limit} weitere unbestimmte Angaben",
                detail="Vollständige Liste im Regelkatalog "
                       "(rules/beschaffung.yaml).")


def check_internal_norms(ctx: CheckContext) -> None:
    """Verweise auf nicht öffentlich beziehbare Normen melden."""
    if not ctx.profile.enabled("PUR.INTERNAL_NORM"):
        return
    seen: set[str] = set()
    for regex, message in KNOWLEDGE["hausnormen"]:
        hit = _first_hit(ctx, regex)
        if hit is None:
            continue
        matched, bbox, page = hit
        key = matched.strip().upper()
        if key in seen:
            continue
        seen.add(key)
        ctx.add("PUR.INTERNAL_NORM",
                f"Verweis auf interne Norm „{matched.strip()}“: {message}",
                bbox=bbox, page=page,
                detail="Der Anfrage beilegen oder durch eine öffentliche "
                       "Norm ersetzen – sonst liefert jeder Lieferant nach "
                       "eigener Auslegung.")


def check_stock_sizes(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Blechdicke/Rundmaterial gegen die Vorzugsmaße prüfen."""
    if not ctx.profile.enabled("PUR.STOCK_SIZE"):
        return
    sheet = KNOWLEDGE["halbzeuge"].get("blech") or []
    if not sheet:
        return
    text = ctx.pdf.full_text()
    for m in RE_SHEET_THICK_VALUE.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 0.3 <= value <= 120:
            continue
        if _matches_stock(value, sheet):
            continue
        nearest = min(sheet, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Blechdicke {value:g} mm ist kein Vorzugsmaß "
                f"(nächstes Lagermaß {nearest:g} mm)",
                detail="Ein Sondermaß bedeutet Mindestabnahmemengen, längere "
                       "Lieferzeit oder Herausarbeiten aus dickerem Material. "
                       "Wenn es keinen funktionalen Grund gibt: auf das "
                       "Lagermaß gehen. Vorzugsmaße pflegbar in "
                       "rules/beschaffung.yaml.")
        break       # eine Blechmeldung je Zeichnung genügt

    _check_round_stock(ctx, text)


def _check_round_stock(ctx: CheckContext, text: str) -> None:
    """Ausdrücklich genanntes Rundmaterial gegen die Lagerdurchmesser prüfen.

    Bewusst nur bei ausgeschriebenem Halbzeug („Rundstahl ⌀37") – jeder
    beliebige Durchmesser auf der Zeichnung wäre ein Maß am Fertigteil und
    sagt nichts über das Halbzeug aus.
    """
    series = KNOWLEDGE["halbzeuge"].get("rund") or []
    if not series:
        return
    for m in RE_ROUND_STOCK.finditer(text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if not 3 <= value <= 300 or _matches_stock(value, series, tol=0.2):
            continue
        nearest = min(series, key=lambda s: abs(s - value))
        ctx.add("PUR.STOCK_SIZE",
                f"Rundmaterial ⌀{value:g} mm ist kein Lagermaß "
                f"(nächstes {nearest:g} mm)",
                detail="Sonderdurchmesser müssen aus dem nächstgrößeren "
                       "Stangenmaterial gedreht werden – mehr Zerspanung, "
                       "höherer Preis, längere Beschaffung.")
        return


def _matches_stock(value: float, series: list[float],
                   tol: float = 0.05) -> bool:
    return any(abs(value - s) <= tol for s in series)


def _first_hit(ctx: CheckContext, regex: re.Pattern):
    """Erster Treffer mit Fundstelle (für die Markierung im Bild)."""
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m.group(0), block.bbox, block.page
    return None


# ========================================================================
# pruef_zeichnung
# ========================================================================
# Pruefungen an der Zeichnung selbst: Vollstaendigkeit, Sprache, Massstab.
#
# Titelblock, Schriftfeld, Allgemeintoleranz, Oberflaechenangaben, Sprache
# (international beschaffbar?), Massstab gegen die tatsaechliche Geometrie
# und die erkannten Fertigungsverfahren.
# ======================================================================
# drawing_checks
# ======================================================================
# Fachliche Zeichnungs-Checks nach allgemeinen Normen (Sicht: internationaler Einkauf).
#
# Regelgruppen (Codes siehe rules/profiles.yaml):
#   TB.*   Schriftfeld (ISO 7200)
#   GT.*   Allgemeintoleranzen / Tolerierungsgrundsatz (ISO 2768, ISO 22081, ISO 8015)
#   GPS.*  Form- und Lagetolerierung (ISO 1101)
#   SURF.* Oberflächen und Kanten (ISO 21920 / ISO 1302, ISO 13715)
#   VIEW.* Darstellung (Projektionsmethode, Einheit)
#   WELD.* / CAST.*  Kontextregeln für Schweiß- und Gussteile (ISO 2553/5817, ISO 8062)
#   CONS.* Konsistenz zur Anfrage (Materialnummer)
#
# Prinzip: Regeln, die auf der Zeichnung nicht sicher entscheidbar sind, melden
# "nicht nachweisbar" (Severity aus dem Profil, i. d. R. warning) statt hart "fehlt".



import re


# ---------------------------------------------------------------- Normmuster
RE_ISO2768 = re.compile(r"ISO\s*2768\s*[-–]?\s*([a-zA-Z]{1,2})?", re.IGNORECASE)
RE_ISO22081 = re.compile(r"ISO\s*22081", re.IGNORECASE)
RE_ISO8015 = re.compile(r"ISO\s*8015", re.IGNORECASE)
RE_ISO13715 = re.compile(r"ISO\s*13715", re.IGNORECASE)
RE_SURF_NORM = re.compile(r"ISO\s*(21920|1302)", re.IGNORECASE)
RE_ROUGHNESS = re.compile(r"\bR[az]\s*\d+(?:[.,]\d+)?", re.IGNORECASE)
RE_ISO5817 = re.compile(r"ISO\s*5817\s*[-–]?\s*([BCD])?", re.IGNORECASE)
RE_ISO2553 = re.compile(r"ISO\s*2553", re.IGNORECASE)
RE_ISO8062 = re.compile(r"ISO\s*8062(?:\s*[-–]?\s*3)?", re.IGNORECASE)
RE_DCTG = re.compile(r"\b[DG]CTG?\s*\d{1,2}\b", re.IGNORECASE)
RE_CT_GRADE = re.compile(r"\bCT\s*\d{1,2}\b")
RE_PROJECTION = re.compile(
    r"(first\s+angle|third\s+angle|1st\s+angle|3rd\s+angle|projektionsmethode\s*[13]?"
    r"|projection\s+method)", re.IGNORECASE)
RE_UNIT_MM = re.compile(r"(dimensions?\s+(?:are\s+)?in\s+mm|maße\s+in\s+mm"
                        r"|angaben\s+in\s+mm|unit\s*s?\s*:?\s*(?:mm|inch)"
                        r"|\bin\s+millimet|dimensions?\s+(?:are\s+)?in\s+inch)",
                        re.IGNORECASE)
# ASME-Welt: Toleranzblock im Schriftfeld + Y14.5 als Tolerierungsgrundsatz.
RE_ASME_Y145 = re.compile(r"ASME\s*Y\s*14\.5", re.IGNORECASE)
# Allgemeintoleranz ohne Normbezug: ASME-Toleranzblock oder Freitext.
# „+/-" ist die ASCII-Schreibweise von ±; ohne sie meldete der Checker an
# 31 echten Zeichnungen des Kalibriersatzes fälschlich „keine
# Allgemeintoleranz" (z. B. „Tolerance unless otherwise noted: +/- 0.25mm").
_PM = r"(?:±|\+/-|\+-)"
RE_ASME_TOLBLOCK = re.compile(
    rf"TOLERANCES?\s*[:\s].{{0,200}}?(?:DECIMAL|{_PM}|ANGULAR)"
    rf"|TOLERANCES?\s+WITHIN\s*{_PM}?\s*\d"     # "TOLERANCES WITHIN 0.1"
    rf"|TOLERANCE[^.\n]{{0,60}}(?:unless|otherwise|noted|specified)"
    rf"[^.\n]{{0,40}}{_PM}?\s*\d"                # "Tolerance unless ...: +/- 0,25"
    rf"|(?:allgemein|frei|unbemaßt)\w*toleranz\w*[^.\n]{{0,40}}{_PM}?\s*\d"
    rf"|(?:alle|all)\s+(?:maße|dimensions)[^.\n]{{0,30}}{_PM}\s*\d"
    rf"|\.X{{1,3}}\s*(?:{_PM}|=)"                 # Toleranzzeilen .X± / .XX±
    rf"|X\.X{{1,3}}\s*(?:{_PM}|=)",
    re.IGNORECASE | re.DOTALL)
# Kantenzustand als Freitext (statt ISO 13715).
RE_EDGE_TEXT = re.compile(
    r"(break\s+all\s+(?:sharp\s+)?edges|remove\s+all\s+burrs"
    r"|burrs?\s+and\s+sharp\s+edges|deburr|kanten\s+gebrochen"
    r"|kanten\s+entgratet|gratfrei|scharfe\s+kanten\s+(?:brechen|gebrochen))",
    re.IGNORECASE)
# Oberflächenangabe als Freitext.
RE_SURF_TEXT = re.compile(
    r"(surface\s+(?:roughness|finish)|finish\s+all\s+faces"
    r"|\d+\s*µ?in\b|microinch|\bRMS\b)", re.IGNORECASE)
# GD&T-Symbole (Unicode) – Positions-/Form-/Lauf-Toleranzen.
GDT_POSITIONAL = "⌖◎⌯∥⊥∠↗⌰"      # brauchen einen Bezug
GDT_FORM = "⏤⏥○⌭⌒"               # Formtoleranzen: dürfen KEINEN Bezug haben
GDT_ANY = GDT_POSITIONAL + GDT_FORM
# Widersprüchliche GD&T: Formtoleranz (Ebenheit/Geradheit/Rundheit/…)
# mit Bezugsbuchstaben dahinter.
RE_FORM_WITH_DATUM = re.compile(
    rf"[{GDT_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?\s+[A-Z](?:[-|][A-Z])?\b")
# In ASME Y14.5-2018 gestrichene, messtechnisch problematische Symbole.
RE_DEPRECATED_GDT = re.compile(r"[◎⌯]")
# Stückliste / Positionsballone
RE_BOM_HEADER = re.compile(
    r"stückliste|parts?\s*list|bill\s+of\s+materials?"
    r"|\b(?:pos\.?|item)\b.{0,60}?\b(?:qty|quantity|stück|menge|anzahl)\b"
    r"|\b(?:qty|quantity)\b.{0,60}?\b(?:pos\.?|item)\b",
    re.IGNORECASE | re.DOTALL)
RE_BALLOON_NUM = re.compile(r"^\d{1,2}$")
RE_DATUM = re.compile(r"^[A-Z]$|^\[?[A-Z](?:[-|][A-Z])?\]?$")

# Schweißkontext: NUR eindeutige Belege. Früher stand hier auch ein
# freies "a\d+" für das a-Maß – das traf jede Zeichnungsnummer mit "A01"
# und machte aus 21 gefrästen Teilen des Kalibriersatzes Schweißteile.
# Das a-/z-Maß zählt jetzt nur mit Nahtsymbol (▲/△) davor oder dahinter.
WELD_CONTEXT = re.compile(
    r"schwei[ßs]|\bweld|\bwps\b|\bnaht\b|kehlnaht|stumpfnaht"
    r"|fillet\s*weld|weld\s*seam|ISO\s*2553|ISO\s*5817"
    r"|[▲△]\s*[az]\s?\d|(?<![A-Za-z0-9])[az]\s?\d{1,2}\s*[▲△]",
    re.IGNORECASE)
CAST_CONTEXT = re.compile(r"\bguss|gussteil|casting|\bcast\b|EN[-\s]?GJ[SLMV]"
                          r"|\bGG[-\s]?\d\d|\bGGG[-\s]?\d\d|rohteil|formschräge"
                          r"|draft\s+angle", re.IGNORECASE)


def _find(ctx: CheckContext, regex: re.Pattern) -> tuple[re.Match, BBox | None, int] | None:
    """Erster Regex-Treffer über alle Textblöcke, mit Blockposition."""
    for block in ctx.pdf.blocks():
        m = regex.search(block.text)
        if m:
            return m, block.bbox, block.page
    return None

def _has_keyword(ctx: CheckContext, keywords: list[str]) -> bool:
    # Whitespace normalisieren: CAD-Textlayer brechen Labels oft mitten im
    # Wortpaar um ("DWG.\nNO.").
    text = " ".join(ctx.pdf.full_text().lower().split())
    return any(" ".join(k.lower().split()) in text for k in keywords)


# ------------------------------------------------------------ Schriftfeld
TB_RULES = ["TB.DRAWNO", "TB.MATERIAL", "TB.SCALE", "TB.WEIGHT",
            "TB.REVISION", "TB.APPROVAL"]
TB_LABEL = {
    "TB.DRAWNO": "Zeichnungsnummer",
    "TB.MATERIAL": "Werkstoffangabe",
    "TB.SCALE": "Maßstab",
    "TB.WEIGHT": "Gewichtsangabe",
    "TB.REVISION": "Änderungsindex/Revision",
    "TB.APPROVAL": "Prüf-/Freigabevermerk",
}


def check_title_block(ctx: CheckContext) -> None:
    for code in TB_RULES:
        if not ctx.profile.enabled(code):
            continue
        keywords = ctx.profile.rule_param(code, "keywords", [])
        if not _has_keyword(ctx, keywords):
            ctx.add(code,
                    f"Schriftfeld: {TB_LABEL[code]} nicht nachweisbar (ISO 7200)",
                    detail="Gesucht wurde nach: " + ", ".join(keywords))


# ------------------------------------------------------------- Toleranzen
def check_general_tolerances(ctx: CheckContext) -> None:
    if ctx.profile.enabled("GT.GENERAL_TOL"):
        hit2768 = _find(ctx, RE_ISO2768)
        hit22081 = _find(ctx, RE_ISO22081)
        asme_block = RE_ASME_TOLBLOCK.search(ctx.pdf.full_text())
        if not hit2768 and not hit22081 and not asme_block:
            ctx.add("GT.GENERAL_TOL",
                    "Keine Allgemeintoleranzangabe gefunden (ISO 2768/ISO 22081 "
                    "bzw. ASME-Toleranzblock)",
                    detail="Ohne Allgemeintoleranzen sind unbemaßte Toleranzen "
                           "für den Lieferanten nicht definiert.")
        elif hit2768 and not hit2768[0].group(1):
            m, bbox, page = hit2768
            ctx.add("GT.GENERAL_TOL",
                    "ISO 2768 ohne Toleranzklasse angegeben (z. B. „ISO 2768-mK“)",
                    severity=ctx.profile.severity("GT.GENERAL_TOL"),
                    bbox=bbox, page=page)
    if (ctx.profile.enabled("GT.PRINCIPLE")
            and not _find(ctx, RE_ISO8015) and not _find(ctx, RE_ASME_Y145)):
        ctx.add("GT.PRINCIPLE",
                "Tolerierungsgrundsatz nicht nachweisbar (ISO 8015 bzw. "
                "ASME Y14.5)",
                detail="International uneinheitliche Default-Auslegung "
                       "(ISO vs. ASME) – Angabe empfohlen.")


def check_gps_datums(ctx: CheckContext) -> None:
    """Lagetoleranz-Symbole vorhanden, aber keine Bezugsbuchstaben erkennbar."""
    if not ctx.profile.enabled("GPS.DATUM"):
        return
    text = ctx.pdf.full_text()
    used_positional = [c for c in GDT_POSITIONAL if c in text]
    if not used_positional:
        return
    words = {w.text.strip() for w in ctx.pdf.words()}
    has_datum = any(RE_DATUM.match(w) for w in words if 1 <= len(w) <= 5)
    if not has_datum:
        ctx.add("GPS.DATUM",
                "Lagetoleranzen verwendet, aber kein Bezug (Datum) erkennbar (ISO 1101)",
                detail=f"Gefundene Symbole: {' '.join(used_positional)}")


def check_gdt_contradictions(ctx: CheckContext) -> None:
    """Widersprüchliche bzw. problematische GD&T-Angaben."""
    if ctx.profile.enabled("GPS.FORM_WITH_DATUM"):
        hit = _find(ctx, RE_FORM_WITH_DATUM)
        if hit:
            m, bbox, page = hit
            ctx.add("GPS.FORM_WITH_DATUM",
                    f"Widersprüchliche GD&T: Formtoleranz mit Bezug angegeben "
                    f"(„{m.group(0)}“)",
                    bbox=bbox, page=page,
                    detail="Form (Ebenheit/Geradheit/Rundheit/Zylindrizität) "
                           "ist bezugsunabhängig definiert (ISO 1101) – Bezug "
                           "streichen oder Lage-/Lauftoleranz verwenden.")
    if ctx.profile.enabled("GPS.DEPRECATED_SYMBOL"):
        hit = _find(ctx, RE_DEPRECATED_GDT)
        if hit:
            m, bbox, page = hit
            name = ("Koaxialität/Konzentrizität" if m.group(0) == "◎"
                    else "Symmetrie")
            ctx.add("GPS.DEPRECATED_SYMBOL",
                    f"GD&T-Symbol {m.group(0)} ({name}) verwendet – in "
                    f"ASME Y14.5-2018 gestrichen und messtechnisch problematisch",
                    bbox=bbox, page=page,
                    detail="Für internationale Lieferanten Position bzw. "
                           "Lauf bevorzugen (eindeutig messbar).")


# ------------------------------------------------------ Positionsballone
def check_balloons(ctx: CheckContext) -> None:
    """Stückliste vorhanden, aber keine Positionsballone in der Darstellung.

    Heuristik: Positionsnummern (1, 2, …) müssen als freistehende kurze
    Zahlen AUSSERHALB des Stücklisten-Bereichs auftauchen. Konservativ als
    "Prüfen" gemeldet – Ballon-Grafiken selbst sind nicht auswertbar.
    """
    if not ctx.profile.enabled("DOC.BALLOONS"):
        return
    bom_blocks = [b for b in ctx.pdf.blocks() if RE_BOM_HEADER.search(b.text)]
    if not bom_blocks:
        return
    # Ausschlusszone: x-Spannweite der Stücklisten-Blöcke (Tabellenspalten
    # liegen darüber/darunter in derselben Spur).
    x_ranges = [(b.bbox.x0 - 10, b.bbox.x1 + 10) for b in bom_blocks]
    pages = {b.page for b in bom_blocks}

    def in_bom_column(w) -> bool:
        cx = (w.bbox.x0 + w.bbox.x1) / 2
        return w.page in pages and any(x0 <= cx <= x1 for x0, x1 in x_ranges)

    outside = {w.text.strip() for w in ctx.pdf.words()
               if RE_BALLOON_NUM.match(w.text.strip()) and not in_bom_column(w)}
    missing = [n for n in ("1", "2") if n not in outside]
    if missing:
        b = bom_blocks[0]
        ctx.add("DOC.BALLOONS",
                "Stückliste vorhanden, aber Positionsballone in der "
                "Darstellung nicht erkennbar",
                bbox=b.bbox, page=b.page,
                detail=f"Positionsnummer(n) {', '.join(missing)} wurden "
                       "außerhalb der Stückliste nicht gefunden – ohne Ballone "
                       "ist die Zuordnung Teil ↔ Position nicht eindeutig.")


# ------------------------------------------------------------ Oberflächen
def check_surfaces(ctx: CheckContext) -> None:
    if ctx.profile.enabled("SURF.ROUGHNESS"):
        if (not _find(ctx, RE_ROUGHNESS) and not _find(ctx, RE_SURF_NORM)
                and not _find(ctx, RE_SURF_TEXT)):
            ctx.add("SURF.ROUGHNESS",
                    "Keine Oberflächenangabe nachweisbar (Ra/Rz, ISO 21920/1302 "
                    "oder Freitext)",
                    detail="Mindestens eine Sammelangabe wird erwartet.")
    if (ctx.profile.enabled("SURF.EDGES") and not _find(ctx, RE_ISO13715)
            and not _find(ctx, RE_EDGE_TEXT)):
        ctx.add("SURF.EDGES",
                "Kein Kantenzustand nachweisbar (ISO 13715 oder Freitext "
                "„Kanten gebrochen/entgratet“)",
                detail="Werkstückkanten (Grat/Übergang) sind nicht definiert.")


# ------------------------------------------------------------- Darstellung
def check_view(ctx: CheckContext) -> None:
    if (ctx.profile.enabled("VIEW.PROJECTION") and not _find(ctx, RE_PROJECTION)
            and not _find(ctx, RE_ASME_Y145)):  # ASME => 3. Winkel per Default
        ctx.add("VIEW.PROJECTION",
                "Projektionsmethode nicht nachweisbar (Symbol/Text 1./3. Winkel)",
                detail="Für internationale Lieferanten kritisch (ISO- vs. "
                       "US-Projektion). Symbol ist ggf. nur grafisch vorhanden "
                       "– bitte Sichtprüfung.")
    if ctx.profile.enabled("VIEW.UNIT") and not _find(ctx, RE_UNIT_MM):
        ctx.add("VIEW.UNIT",
                "Einheit nicht deklariert (z. B. „Dimensions in mm“)")


# ------------------------------------------- Kontext: Schweißen und Guss
RE_ISO13920 = re.compile(r"ISO\s*13920", re.IGNORECASE)
# Gewinde fälschlich mit Passungs-Toleranzklasse ("M12 H7" statt 6H/6g).
RE_THREAD_WITH_FIT = re.compile(
    r"\bM\s*\d{1,3}(?:\s*[xX×]\s*\d+(?:[.,]\d+)?)?\s+[HhGgFf]\d{1,2}\b")


def check_thread_fit_class(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("THRD.FIT_CLASS"):
        return
    hit = _find(ctx, RE_THREAD_WITH_FIT)
    if hit:
        m, bbox, page = hit
        ctx.add("THRD.FIT_CLASS",
                f"Gewinde mit Passungs-Toleranzklasse bemaßt („{m.group(0)}“)",
                bbox=bbox, page=page,
                detail="Gewindetoleranzen heißen 6H/6g (ISO 965), "
                       "Bohrungs-/Wellenpassungen H7/h6 gelten nicht für "
                       "Gewinde – Angabe korrigieren.")


def check_welding(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("WELD.QUALITY"):
        return
    hit = _find(ctx, WELD_CONTEXT)
    if not hit:
        return
    # Schweißkonstruktion: ISO 2768 allein reicht nicht – Allgemeintoleranzen
    # für Schweißkonstruktionen sind ISO 13920.
    if (ctx.profile.enabled("NORM.WELD_GENTOL")
            and _find(ctx, RE_ISO2768) and not _find(ctx, RE_ISO13920)):
        ctx.add("NORM.WELD_GENTOL",
                "Schweißkonstruktion nur mit ISO 2768 – Allgemeintoleranzen "
                "für Schweißkonstruktionen (ISO 13920) fehlen",
                detail="ISO 2768 gilt für spanende Fertigung; für Längen-/"
                       "Winkelmaße und Form/Lage geschweißter Baugruppen "
                       "ISO 13920 (z. B. -BF) ergänzen.")
    q = _find(ctx, RE_ISO5817)
    if not q:
        _m, bbox, page = hit
        ctx.add("WELD.QUALITY",
                "Schweißteil ohne Schweißnahtgüte (ISO 5817 Bewertungsgruppe B/C/D)",
                bbox=bbox, page=page,
                detail="Zusätzlich prüfen: Symbolik nach ISO 2553 vollständig?")
    elif q and not q[0].group(1):
        _m, bbox, page = q
        ctx.add("WELD.QUALITY",
                "ISO 5817 ohne Bewertungsgruppe (B/C/D) angegeben",
                bbox=bbox, page=page)


def check_casting(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("CAST.TOL"):
        return
    hit = _find(ctx, CAST_CONTEXT)
    if not hit:
        return
    if not (_find(ctx, RE_ISO8062) or _find(ctx, RE_DCTG) or _find(ctx, RE_CT_GRADE)):
        _m, bbox, page = hit
        ctx.add("CAST.TOL",
                "Gussteil ohne Gusstoleranzangabe (ISO 8062, DCTG/GCTG bzw. CT)",
                bbox=bbox, page=page,
                detail="Auch Bearbeitungszugaben (RMA) prüfen.")


# -------------------------------------------------------------- Konsistenz
def check_consistency(ctx: CheckContext) -> None:
    if not ctx.profile.enabled("CONS.MATNO"):
        return
    material = ctx.material.strip()
    digits = re.sub(r"\D", "", material)
    text = ctx.pdf.full_text()
    found = material and material in text
    if not found and len(digits) >= 6:
        found = digits in re.sub(r"\D", "", text)
    if not found:
        ctx.add("CONS.MATNO",
                f"Materialnummer {material} auf der Zeichnung nicht gefunden",
                detail="Möglicherweise falsches Dokument im YMATDOCS-Paket "
                       "oder Nummer nur in SAP-Metadaten.")


ALL_CHECKS = [
    check_title_block,
    check_general_tolerances,
    check_gps_datums,
    check_gdt_contradictions,
    check_balloons,
    check_thread_fit_class,
    check_surfaces,
    check_view,
    check_welding,
    check_casting,
    check_consistency,
]


def run_drawing_checks(ctx: CheckContext) -> None:
    pass  # (Import entfaellt - alles ein Modul)

    for check in ALL_CHECKS:
        check(ctx)
    run_material_checks(ctx)


# ======================================================================
# processes
# ======================================================================
# Erkennung der nötigen Fertigungsverfahren aus dem Zeichnungstext.
#
# Für die Prüfdokumentation (Spalte "Fertigungsverfahren" in der Ergebnis-
# Excel). Nutzt dieselben Kontext-Regexe wie die Widerspruchsprüfung, damit
# Dokumentation und Checks nie auseinanderlaufen.



import re


RE_PAINT = re.compile(r"lackier|\bRAL\s*\d{4}\b|pulverbeschicht|powder\s*coat"
                      r"|\bKTL\b|paint(?:ed|ing)?\b", re.IGNORECASE)
RE_SHEET = re.compile(r"abgekantet|gekantet|abkanten|biegeradius|kantung"
                      r"|laserzuschnitt|lasergeschnitten|laser\s*cut"
                      r"|sheet\s*metal|\bbend(?:ing|s)?\b|blechdicke",
                      re.IGNORECASE)
RE_GRIND = re.compile(r"geschliffen|schleifen|\bgrinding\b|\bground\b(?!\s*(?:wire|terminal))",
                      re.IGNORECASE)
RE_MACHINING = re.compile(r"machined|spanend|gefräst|gedreht|milling|turning"
                          r"|gebohrt|reiben|geläppt|honen", re.IGNORECASE)

# (Label, Regex) – Reihenfolge = Ausgabereihenfolge in der Excel.
_PROCESS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Schweißen", WELD_CONTEXT),
    ("Bolzenschweißen", RE_STUD_WELD),
    ("Gießen", RE_CAST),
    ("Blechbearbeitung/Abkanten", RE_SHEET),
    ("Härten/Vergüten", RE_HT_QT),
    ("Einsatzhärten", RE_HT_CASE),
    ("Nitrieren", RE_HT_NITR),
    ("Schleifen", RE_GRIND),
    ("Verzinken", RE_ZINC),
    ("Eloxieren", RE_ANODIZE),
    ("Brünieren", RE_BLACKEN),
    ("Lackieren/Beschichten", RE_PAINT),
    ("Gewindefertigung", RE_METRIC_THREAD),
]


def detect_processes(pdf: DrawingPdf) -> list[str]:
    text = pdf.full_text()
    if not text.strip():
        return []
    found = [label for label, regex in _PROCESS_PATTERNS if regex.search(text)]

    # Spanende Bearbeitung: explizit genannt ODER über Oberflächen-/
    # Passungsangaben impliziert.
    if (RE_MACHINING.search(text) or RE_ROUGHNESS.search(text)
            or RE_FIT_TOKEN.search(text)):
        found.append("Spanende Bearbeitung")

    # Gusswerkstoff erkannt, aber kein expliziter Guss-Kontext im Text.
    if "Gießen" not in found:
        for mat in MATERIALS:
            if mat.castable and any(
                    re.search(p, text, re.IGNORECASE) for p in mat.patterns):
                found.insert(0, "Gießen")
                break
    return found


# ======================================================================
# language_check
# ======================================================================
# Sprach-Check: rein deutschsprachige Beschriftungen sind ein Finding.
#
# Hintergrund: Die Zeichnungen gehen an internationale Lieferanten – deutsche
# Anmerkungen sind dort nicht lesbar. Zweisprachige Beschriftung ist ok.
#
# Umsetzung ohne externe Modelle: Stoppwort-/Lexikon-Scoring je Textblock.
# Deterministisch, offline, und die Wortlisten sind auf technische
# Zeichnungssprache zugeschnitten.



import re


# Häufige deutsche Funktions- und Zeichnungswörter.
GERMAN_WORDS = {
    "und", "oder", "mit", "ohne", "nach", "vor", "bei", "der", "die", "das",
    "den", "dem", "des", "ein", "eine", "einer", "nicht", "alle", "sind",
    "ist", "wird", "werden", "muss", "müssen", "darf", "dürfen", "siehe",
    "für", "auf", "aus", "über", "unter", "zwischen", "sowie", "bzw",
    "kanten", "kante", "gebrochen", "entgratet", "entgraten", "gratfrei",
    "scharfkantig", "maße", "masse", "maß", "allgemeintoleranzen",
    "allgemeintoleranz", "werkstoff", "oberfläche", "oberflächen", "gewicht",
    "maßstab", "blatt", "änderung", "änderungen", "zeichnung", "benennung",
    "datum", "geprüft", "erstellt", "freigabe", "freigegeben", "bemerkung",
    "anmerkung", "hinweis", "ausführung", "beschichtung", "verzinkt",
    "lackiert", "geglüht", "gehärtet", "vergütet", "geschweißt", "schweißen",
    "schweißnaht", "schweißnähte", "nahtdicke", "ringsum", "umlaufend",
    "beidseitig", "allseitig", "gussteil", "rohteil", "fertigteil", "zugabe",
    "bearbeitungszugabe", "wärmebehandlung", "prüfung", "kennzeichnung",
    "teilenummer", "stückzahl", "halbzeug", "unbemaßt", "gelten", "gilt",
    "angaben", "toleranzen", "toleranz", "passung", "gewinde", "bohrung",
    "bohrungen", "senkung", "fase", "fasen", "radien", "innenliegend",
}
# Häufige englische Funktions- und Zeichnungswörter.
ENGLISH_WORDS = {
    "and", "or", "with", "without", "the", "all", "are", "is", "shall",
    "must", "may", "see", "for", "from", "not", "of", "to", "in", "on",
    "edges", "edge", "broken", "deburred", "burr", "free", "sharp",
    "dimensions", "dimension", "general", "tolerances", "tolerance",
    "material", "surface", "surfaces", "weight", "scale", "sheet",
    "revision", "drawing", "title", "date", "checked", "drawn", "approved",
    "released", "note", "notes", "remark", "finish", "coating", "galvanized",
    "painted", "hardened", "annealed", "welded", "welding", "weld", "seam",
    "around", "both", "sides", "casting", "cast", "raw", "machining",
    "allowance", "heat", "treatment", "unless", "otherwise", "specified",
    "apply", "applies", "marking", "part", "quantity", "thread", "hole",
    "holes", "chamfer", "radii", "internal", "number",
    "pressure", "test", "tolerancing", "per", "datum", "datums", "base",
    "face", "faces", "bearing", "bore", "bores", "key", "keyway", "seat",
    "seats", "detail", "centre", "center", "end", "ends", "machined",
    "paint", "quenched", "tempered", "hardness", "grade", "quality",
}
UMLAUT = re.compile(r"[äöüßÄÖÜ]")
WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{2,}")
# Tokens, die nie Sprachindiz sind (Normbezüge, Kürzel).
NEUTRAL = {"iso", "din", "en", "ra", "rz", "mm", "kg", "max", "min", "typ",
           "nr", "no", "pos", "st", "ca", "ø", "vgl", "asme", "gjs", "gjl"}


def classify_block(text: str) -> str:
    """'de' | 'en' | 'mixed' | 'neutral' für einen Textblock.

    'mixed' = Block enthält deutsche UND englische Signale (zweisprachige
    Beschriftung) – das ist für den internationalen Einkauf in Ordnung.
    """
    words = [w.lower() for w in WORD.findall(text)]
    words = [w for w in words if w not in NEUTRAL]
    if not words:
        return "neutral"
    de = sum(1 for w in words if w in GERMAN_WORDS)
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    de += 2 * len(UMLAUT.findall(text))  # Umlaute sind ein starkes Signal
    if de and en:
        return "mixed"
    if de:
        return "de"
    if en:
        return "en"
    return "neutral"


def check_language(ctx: CheckContext) -> None:
    """Markiert deutsche Textblöcke ohne englische Entsprechung."""
    if not ctx.profile.enabled("LANG.GERMAN"):
        return
    german_blocks = []
    has_english = False
    for block in ctx.pdf.blocks():
        cls = classify_block(block.text)
        if cls == "de":
            german_blocks.append(block)
        elif cls in ("en", "mixed"):
            has_english = True

    if not german_blocks:
        return

    max_markers = int(ctx.profile.params.get("max_language_markers", 12))
    note = (" (Zeichnung enthält auch englischen Text – prüfen, ob durchgehend "
            "zweisprachig)" if has_english else "")
    for block in german_blocks[:max_markers]:
        snippet = block.text.replace("\n", " ")
        if len(snippet) > 60:
            snippet = snippet[:57] + "…"
        ctx.add(
            "LANG.GERMAN",
            f"Deutschsprachige Beschriftung: „{snippet}“",
            bbox=block.bbox, page=block.page,
            detail="Für internationalen Einkauf englisch oder zweisprachig "
                   "beschriften." + note,
        )
    rest = len(german_blocks) - max_markers
    if rest > 0:
        ctx.add(
            "LANG.GERMAN",
            f"… und {rest} weitere deutschsprachige Textstellen",
            detail="Nur die ersten Fundstellen sind im Bild markiert.",
        )


# ======================================================================
# doc_checks
# ======================================================================
# Dokumenten-Formalien: Vollständigkeit und Beherrschbarkeit der Datei.
#
# Fehler, die nichts mit der Konstruktion zu tun haben, aber im Einkauf
# regelmäßig zu Rückfragen, Nachträgen oder falsch gefertigten Teilen führen:
#
#   DOC.SHEET_COUNT  „Blatt 1 von 3", geliefert wird 1 Seite – die Zeichnung
#                    ist unvollständig; die fehlenden Blätter enthalten oft
#                    genau die Toleranz- und Schweißangaben.
#   DOC.ANNOTATIONS  Das PDF enthält nachträgliche Kommentare, Stempel oder
#                    Freihandmarkierungen. Solche Rotstiftänderungen sind
#                    nicht Teil des freigegebenen Standes.
#   DOC.DATE_FUTURE  Datum auf der Zeichnung liegt in der Zukunft oder
#                    unplausibel weit zurück – Hinweis auf Tippfehler im
#                    Änderungsstand.
#   DOC.DECIMAL_MIXED Dezimalkomma und Dezimalpunkt gemischt. Für einen
#                    internationalen Lieferanten ein echtes Risiko
#                    („1.500" = 1,5 oder 1500?).



import datetime as _dt
import logging
import re



# „Blatt 1 von 3", „Blatt 1/3", „Sheet 2 of 4", „Bl. 1 v. 2"
RE_SHEET_OF = re.compile(
    r"\b(?:blatt|bl\.?|sheet|feuille|page)\s*(\d{1,2})\s*"
    r"(?:von|v\.|of|/)\s*(\d{1,2})\b", re.IGNORECASE)
# Anmerkungstypen, die eine echte Nachbearbeitung darstellen.
MARKUP_ANNOTS = {
    "Text", "FreeText", "Ink", "Square", "Circle", "Line", "Polygon",
    "PolyLine", "Highlight", "Underline", "Squiggly", "StrikeOut", "Stamp",
    "Caret", "FileAttachment",
}
# Zahlen mit Dezimaltrenner (ohne Normbezeichnungen wie „ISO 2768-1").
RE_DEC_COMMA = re.compile(r"(?<![\d.,])\d{1,4},\d{1,3}(?![\d.,])")
RE_DEC_POINT = re.compile(r"(?<![\d.,])\d{1,4}\.\d{1,3}(?![\d.,])")


def run_doc_checks(ctx: CheckContext) -> None:
    check_sheet_count(ctx)
    check_annotations(ctx)
    check_dates(ctx)
    check_decimal_separator(ctx)


def check_sheet_count(ctx: CheckContext) -> None:
    """Angekündigte Blattzahl gegen die tatsächlichen PDF-Seiten prüfen."""
    if not ctx.profile.enabled("DOC.SHEET_COUNT"):
        return
    declared = 0
    for block in ctx.pdf.blocks():
        for _no, total in RE_SHEET_OF.findall(block.text):
            declared = max(declared, int(total))
    if declared <= 1:
        return
    actual = ctx.pdf.page_count
    if actual >= declared:
        return
    ctx.add("DOC.SHEET_COUNT",
            f"Zeichnung ist unvollständig: angekündigt sind {declared} "
            f"Blätter, das Paket enthält {actual}",
            detail="Fehlende Folgeblätter enthalten erfahrungsgemäß "
                   "Schweiß-, Toleranz- und Prüfangaben. Vollständiges "
                   "Dokument anfordern, bevor angefragt wird.")


def check_annotations(ctx: CheckContext) -> None:
    """Nachträgliche PDF-Markierungen (Rotstift) erkennen."""
    if not ctx.profile.enabled("DOC.ANNOTATIONS"):
        return
    found: list[tuple[str, int, BBox | None]] = []
    try:
        for pno, page in enumerate(ctx.pdf.doc):
            for annot in page.annots() or []:
                kind = (annot.type[1] if isinstance(annot.type, (list, tuple))
                        else str(annot.type))
                if kind not in MARKUP_ANNOTS:
                    continue
                r = annot.rect
                found.append((kind, pno, BBox(r.x0, r.y0, r.x1, r.y1)))
    except Exception:      # pragma: no cover - defekte/exotische PDFs
        log.debug("Annotationen nicht lesbar", exc_info=True)
        return
    if not found:
        return
    kinds = ", ".join(sorted({k for k, _p, _b in found}))
    kind, page, bbox = found[0]
    ctx.add("DOC.ANNOTATIONS",
            f"{len(found)} nachträgliche Markierung(en) im PDF ({kinds})",
            bbox=bbox, page=page,
            detail="Kommentare, Stempel oder Freihandeinträge gehören nicht "
                   "zum freigegebenen Stand. Entweder in die Zeichnung "
                   "einarbeiten und den Index hochsetzen oder entfernen – "
                   "ein Lieferant sieht sie je nach Betrachter gar nicht.")


def check_dates(ctx: CheckContext) -> None:
    """Datumsangaben auf Plausibilität prüfen."""
    if not ctx.profile.enabled("DOC.DATE_FUTURE"):
        return
    pass  # (Import entfaellt - alles ein Modul)

    today = _dt.date.today()
    dates = [d for d in _candidates(ctx.pdf.full_text())]
    if not dates:
        return
    newest = max(dates)
    if newest > today:
        ctx.add("DOC.DATE_FUTURE",
                f"Datum auf der Zeichnung liegt in der Zukunft: "
                f"{newest.isoformat()}",
                detail="Meist ein Tippfehler im Änderungsdatum. Für die "
                       "Dokumentation des Prüflaufs wird das Datum trotzdem "
                       "übernommen.")


def check_decimal_separator(ctx: CheckContext) -> None:
    """Gemischte Dezimaltrenner erkennen (international missverständlich)."""
    if not ctx.profile.enabled("DOC.DECIMAL_MIXED"):
        return
    text = ctx.pdf.full_text()
    commas = len(RE_DEC_COMMA.findall(text))
    points = len(RE_DEC_POINT.findall(text))
    minimum = int(ctx.profile.rule_param("DOC.DECIMAL_MIXED", "min_count", 3))
    if commas < minimum or points < minimum:
        return
    ctx.add("DOC.DECIMAL_MIXED",
            f"Dezimaltrenner gemischt: {commas}× Komma, {points}× Punkt",
            detail="Aus Sicht eines internationalen Lieferanten mehrdeutig – "
                   "„1.500\" kann 1,5 oder 1500 bedeuten. Durchgängig einen "
                   "Trenner verwenden (ISO 80000-1 empfiehlt das Komma, "
                   "verbreitet ist im Export der Punkt).")


# ======================================================================
# scale_checks
# ======================================================================
# Maßstabsbasierte Prüfungen: gemessene Ansicht statt Maßtext.
#
# Aus Schriftfeld-Maßstab und der gemessenen Größe der Zeichnungsansicht
# ergibt sich die Bauteilgröße – völlig unabhängig von der Maßtext-Extraktion.
# Das liefert zwei Prüfungen:
#
#   SCALE.MISMATCH   Gemessene Ansicht passt nicht zu den eingetragenen Maßen:
#                    entweder ist die Zeichnung nicht maßstäblich oder der
#                    Maßstab im Schriftfeld ist falsch.
#   GEO.VIEW_SIZE    Gemessene Ansicht passt nicht zum STEP-Modell. Greift
#                    auch dann, wenn die Maßextraktion nichts hergibt
#                    (schlechter Textlayer, OCR).
#
# Beide sind bewusst großzügig toleriert: Detail- und Schnittansichten mit
# abweichendem Maßstab, Bemaßungsüberstände und gerundete Maßstabsangaben
# dürfen nicht zu Fehlalarmen führen.



import logging




def measure_largest_view(ctx: CheckContext, scale: float
                         ) -> tuple[float, float, object] | None:
    """Größte Zeichnungsansicht in Bauteil-Millimetern.

    Rückgabe: (Breite, Höhe, Ansicht) oder None.
    """
    pass  # (Import entfaellt - alles ein Modul)

    try:
        views = extract_views(ctx.pdf)
    except Exception:  # Stub-PDFs in Tests
        return None
    if not views:
        return None
    factor = mm_per_point(scale)
    best = None
    for v in views:
        x0, y0, x1, y1 = v.bbox
        w, h = (x1 - x0) * factor, (y1 - y0) * factor
        if best is None or w * h > best[0] * best[1]:
            best = (w, h, v)
    return best


def check_scale_consistency(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Gemessene Ansichtsgröße gegen die eingetragenen Maße prüfen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte.
    """
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return ""
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return ""
    width, height, view = measured
    largest_view = max(width, height)
    if largest_view < 1:
        return ""

    values = [d.value for d in dims
              if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)]
    summary = (f"Ansicht gemessen {width:.0f} × {height:.0f} mm "
               f"(Maßstab 1:{scale:g})")
    if not values:
        return summary
    if not ctx.profile.enabled("SCALE.MISMATCH"):
        return summary        # nur messen, nicht bewerten
    largest_dim = max(values)
    tol = float(ctx.profile.params.get("scale_tol", 0.15))
    # Bewusst einseitig: Eine Ansicht kann durch unvollständig erkannte
    # Konturlinien zu KLEIN gemessen werden – das ist kein Zeichnungsfehler.
    # Nur eine Ansicht, die GRÖSSER ist als das größte eingetragene Maß,
    # ist ein sicheres Zeichen für einen falschen Maßstab.
    deviation = (largest_view - largest_dim) / max(largest_dim, 1)
    if deviation > tol:
        ctx.add("SCALE.MISMATCH",
                f"Zeichnung nicht maßstäblich: gemessene Ansicht "
                f"{largest_view:.0f} mm überschreitet das größte eingetragene "
                f"Maß ({largest_dim:g} mm) bei Maßstab 1:{scale:g}",
                bbox=_view_bbox(view), page=0,
                detail="Entweder stimmt der Maßstab im Schriftfeld nicht, "
                       "oder die Ansicht wurde nachträglich verzerrt/skaliert. "
                       "Für den Lieferanten ist die Zeichnung dann nur noch "
                       "über die Maßzahlen nutzbar.")
    return summary


def check_view_vs_model(ctx: CheckContext, geometry, dims: list[DimValue]
                        ) -> None:
    """Gemessene Ansichtsgröße gegen die Modell-Bounding-Box prüfen.

    Unabhängig von den Maßtexten – deshalb auch bei schwachem Textlayer
    aussagekräftig.
    """
    if not ctx.profile.enabled("GEO.VIEW_SIZE") or geometry.backend != "occ":
        return
    scale = extract_scale(ctx.pdf)
    if scale is None:
        return
    measured = measure_largest_view(ctx, scale)
    if measured is None:
        return
    width, height, view = measured
    largest_view = max(width, height)
    obb_max = geometry.obb_dims[0]
    if largest_view < 1 or obb_max <= 0:
        return
    tol = float(ctx.profile.params.get("view_model_tol", 0.2))
    # Ebenfalls einseitig (s. check_scale_consistency): zu klein gemessene
    # Ansichten sind ein Erkennungs-, kein Zeichnungsproblem.
    deviation = (largest_view - obb_max) / obb_max
    if deviation <= tol:
        return
    # Bei bereits erkanntem Einheiten- oder Maßstabsfehler nicht doppelt melden.
    known = {f.code for f in ctx.findings}
    if {"GEO.UNIT_MISMATCH", "SCALE.MISMATCH"} & known:
        return
    ctx.add("GEO.VIEW_SIZE",
            f"Gemessene Ansicht ({largest_view:.0f} mm) ist größer als das "
            f"Modell ({obb_max:.0f} mm)",
            bbox=_view_bbox(view), page=0,
            detail=f"Abweichung {deviation * 100:.0f} % bei Maßstab "
                   f"1:{scale:g}. Unabhängig von den Maßzahlen gemessen – "
                   f"stützt den Verdacht auf ein falsch zugeordnetes Modell.")


def _view_bbox(view):
    pass  # (Import entfaellt - alles ein Modul)

    x0, y0, x1, y1 = view.bbox
    return BBox(x0, y0, x1, y1)


# ========================================================================
# pruef_bemassung
# ========================================================================
# Pruefungen an Bemassung und GPS: Masse, Toleranzen, Form und Lage.
#
# Beides haengt so eng zusammen, dass eine Trennung nur Importe erzeugt
# haette: eine Positionstoleranz ohne theoretisch genaues Mass ist ein
# Bemassungsfehler und ein GPS-Fehler zugleich.
# ======================================================================
# dimension_checks
# ======================================================================
# Bemaßungs- und Fertigungsprüfungen.
#
# Deckt die klassischen Bemaßungsfehler (ISO 129-1 / DIN 406) und die
# typischen Kostentreiber der Zerspanung ab:
#
#   DIM.CHAIN        Geschlossene Maßkette: Teilmaße summieren sich exakt zum
#                    Gesamtmaß und alle sind toleriert -> Toleranzkonflikt
#                    (Überbestimmung, das Maß ist doppelt festgelegt).
#   DIM.NO_TOLERANCE Kein einziges Maß trägt eine Einzeltoleranz, obwohl
#                    Passungen/Funktionsmaße zu erwarten wären.
#   MFG.TIGHT_TOL    Sehr enge Toleranz (IT ≤ 5 bzw. Spanne < 0,01 mm) –
#                    starker Kostentreiber, nur bei Funktionsbedarf sinnvoll.
#   MFG.DEEP_HOLE    Bohrungstiefe/Durchmesser > 5 – Tiefbohren nötig.
#   MFG.SHARP_CORNER "R0" bzw. scharfe Innenecke gefordert – mit Fräser nicht
#                    herstellbar (Erodieren nötig).
#   SURF.UNREALISTIC Rauheit feiner als das angegebene Verfahren liefern kann
#                    (z. B. Ra 0,2 auf einer Gussfläche).
#   SURF.TOL_MISMATCH Rauheit zu grob für die geforderte Toleranz – eine
#                    H7-Passung lässt sich mit Rz 63 nicht einhalten, weil
#                    das Rauheitsprofil selbst schon die halbe Toleranz
#                    verbraucht.
#   DIM.TOL_ORDER    Grenzabmaße vertauscht (oberes Abmaß kleiner als das
#                    untere) – das Maß ist so nicht fertigbar.
#   DIM.BASIC_TOL    Theoretisch genaues Maß (eingerahmt) zusätzlich
#                    toleriert – Widerspruch nach ISO 1101.
#   THRD.DEPTH       Gewinde tiefer gefordert als die Bohrung – so nicht
#                    herstellbar (der Bohrer kommt nicht weiter).
#   THRD.SHORT       Einschraubtiefe unter 1×D – die Verbindung trägt die
#                    Schraubenfestigkeit nicht.



import re
from itertools import combinations


RE_SHARP_CORNER = re.compile(
    r"\bR\s*0(?![.,]\d*[1-9])\b|scharfkantig\s+innen|sharp\s+internal"
    r"|keine\s+radien|no\s+corner\s+radius|ecke\s+scharf", re.IGNORECASE)
RE_RA_VALUE = re.compile(r"\bRa\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
RE_RZ_VALUE = re.compile(r"\bRz\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
# Verfahren mit ihrer praktisch erreichbaren Feinheit (Ra in µm).
PROCESS_RA_LIMIT = {
    "guss": (re.compile(r"\bguss|casting|\bcast\b|EN[-\s]?GJ|rohteil"
                        r"|unbearbeitet|as[-\s]cast", re.IGNORECASE), 6.3),
    "brennschnitt": (re.compile(r"brennschnitt|autogen|plasmaschnitt"
                                r"|flame[-\s]cut", re.IGNORECASE), 12.5),
    "schmieden": (re.compile(r"geschmiedet|schmiedeteil|forged",
                             re.IGNORECASE), 6.3),
}
# Verfahren, die sehr feine Oberflächen rechtfertigen.
RE_FINE_PROCESS = re.compile(
    r"geschliffen|schleifen|läppen|honen|poliert|ground|lapped|honed"
    r"|polished|superfinish", re.IGNORECASE)


def _axis_groups(dims: list[DimValue], tol: float
                 ) -> list[tuple[str, list[DimValue]]]:
    """Gruppiert Maße zu möglichen Maßketten (gleiche Maßlinie).

    Horizontale Kette: Maßtexte liegen auf gleicher Höhe (y), nebeneinander.
    Vertikale Kette: gleiche Spalte (x), untereinander.
    """
    groups: list[tuple[str, list[DimValue]]] = []
    for axis, key, other in (("h", lambda d: d.bbox.center[1],
                              lambda d: d.bbox.center[0]),
                             ("v", lambda d: d.bbox.center[0],
                              lambda d: d.bbox.center[1])):
        buckets: dict[int, list[DimValue]] = {}
        for d in dims:
            buckets.setdefault(int(key(d) / tol), []).append(d)
        # Nachbarschaftsbuckets zusammenführen (Maßtexte sitzen nicht exakt
        # auf derselben Koordinate).
        merged: dict[int, list[DimValue]] = {}
        for b, items in sorted(buckets.items()):
            target = merged.get(b - 1)
            if target is not None:
                merged[b - 1] = target + items
            else:
                merged[b] = list(items)
        for items in merged.values():
            if len(items) >= 3:
                groups.append((axis, sorted(items, key=other)))
    return groups


def _is_adjacent_chain(parts: list[DimValue], axis: str) -> bool:
    """Teilmaße müssen nebeneinander liegen (keine Überlappung)."""
    spans = []
    for d in parts:
        b = d.bbox
        spans.append((b.x0, b.x1) if axis == "h" else (b.y0, b.y1))
    spans.sort()
    for (_, end), (start, _) in zip(spans, spans[1:]):
        if start < end - 1.0:      # deutliche Überlappung -> keine Kette
            return False
    return True


def check_dimension_chain(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Geschlossene, durchtolerierte Maßkette erkennen.

    Eine echte Kette erfüllt drei Bedingungen gleichzeitig:
      1. die Teilmaße liegen auf EINER Maßlinie und nebeneinander,
      2. ihre Summe ergibt ein weiteres Maß derselben Richtung,
      3. Gesamtmaß und mehrere Teilmaße sind toleriert.
    Ohne die räumliche Prüfung liefert die reine Zahlensuche auf
    maßreichen Zeichnungen Zufallstreffer.
    """
    if not ctx.profile.enabled("DIM.CHAIN"):
        return
    linear = [d for d in dims if d.kind is DimKind.LINEAR and d.value >= 5]
    if len(linear) < 4:
        return
    eps = float(ctx.profile.params.get("chain_epsilon", 0.05))
    line_tol = float(ctx.profile.params.get("chain_line_tol", 8.0))
    reported = 0

    for axis, group in _axis_groups(linear, line_tol):
        toler = [d for d in group if d.tolerance_span]
        if len(toler) < 2:
            continue
        # Kandidaten für das Gesamtmaß: toleriert und größer als der Rest
        for total in sorted(toler, key=lambda d: -d.value):
            parts_pool = [d for d in group
                          if d is not total and d.value < total.value]
            if len(parts_pool) < 2:
                continue
            found = None
            for n in (2, 3, 4):
                if n > len(parts_pool):
                    break
                for combo in combinations(parts_pool, n):
                    if abs(sum(d.value for d in combo) - total.value) > eps:
                        continue
                    if sum(1 for d in combo if d.tolerance_span) < 1:
                        continue
                    if not _is_adjacent_chain(list(combo), axis):
                        continue
                    found = combo
                    break
                if found:
                    break
            if not found:
                continue
            chain = " + ".join(f"{d.value:g}" for d in found)
            ctx.add("DIM.CHAIN",
                    f"Geschlossene Maßkette mit Toleranzkonflikt: "
                    f"{chain} = {total.value:g}, Teil- und Gesamtmaß toleriert",
                    bbox=total.bbox, page=total.page,
                    detail="Bei geschlossenen Ketten summieren sich die "
                           "Einzeltoleranzen; ein Maß muss als Hilfsmaß "
                           "(eingeklammert) oder ohne Toleranz ausgeführt "
                           "werden (ISO 129-1, DIN 406-11).")
            reported += 1
            if reported >= 2:
                return
            break


def check_tight_tolerances(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Sehr enge Toleranzen als Kostentreiber melden."""
    if not ctx.profile.enabled("MFG.TIGHT_TOL"):
        return
    limit_mm = float(ctx.profile.params.get("tight_tol_mm", 0.01))
    limit_it = int(ctx.profile.params.get("tight_tol_it", 5))
    tight = []
    for d in dims:
        span = d.tolerance_span
        grade = d.it_grade
        if (span is not None and span < limit_mm) or (
                grade is not None and grade <= limit_it):
            tight.append(d)
    if not tight:
        return
    max_report = int(ctx.profile.params.get("max_tight_tol_markers", 5))
    for d in tight[:max_report]:
        span = d.tolerance_span
        grade_txt = f" (IT{d.it_grade})" if d.it_grade else ""
        span_txt = f"{span * 1000:.0f} µm" if span else "sehr eng"
        ctx.add("MFG.TIGHT_TOL",
                f"Sehr enge Toleranz: {d.raw} → {span_txt}{grade_txt}",
                bbox=d.bbox, page=d.page,
                detail="Enge Toleranzen sind der stärkste Kostentreiber in "
                       "der Zerspanung (Sonderwerkzeuge, Messmittel, "
                       "Ausschussrisiko). Nur an funktionsrelevanten Maßen "
                       "vorsehen.")
    if len(tight) > max_report:
        ctx.add("MFG.TIGHT_TOL",
                f"… und {len(tight) - max_report} weitere sehr enge Toleranzen",
                detail="Nur die ersten Fundstellen sind im Bild markiert.")


def check_deep_holes(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Tiefe Bohrungen (Tiefe/Durchmesser > Schwelle)."""
    if not ctx.profile.enabled("MFG.DEEP_HOLE"):
        return
    ratio_limit = float(ctx.profile.params.get("deep_hole_ratio", 5.0))
    for d in dims:
        if d.kind not in (DimKind.DIAMETER, DimKind.THREAD) or not d.depth:
            continue
        if d.value <= 0:
            continue
        ratio = d.depth / d.value
        if ratio > ratio_limit:
            ctx.add("MFG.DEEP_HOLE",
                    f"Tiefe Bohrung: ⌀{d.value:g} × {d.depth:g} mm tief "
                    f"(Verhältnis {ratio:.1f}:1)",
                    bbox=d.bbox, page=d.page,
                    detail="Ab etwa 5:1 sind Tiefbohrwerkzeuge, "
                           "Spanbruchstrategien und ggf. Innenkühlung nötig – "
                           "Kosten und Lieferzeit steigen deutlich.")


def check_sharp_corners(ctx: CheckContext) -> None:
    """Scharfe Innenecken bzw. R0 gefordert."""
    if not ctx.profile.enabled("MFG.SHARP_CORNER"):
        return
    for b in ctx.pdf.blocks():
        m = RE_SHARP_CORNER.search(b.text)
        if m:
            ctx.add("MFG.SHARP_CORNER",
                    f"Scharfe Innenecke gefordert („{m.group(0)}“)",
                    bbox=b.bbox, page=b.page,
                    detail="Fräser erzeugen immer einen Eckenradius. Scharfe "
                           "Innenecken erfordern Erodieren oder Räumen – "
                           "Eckenradius zulassen, wenn funktional möglich.")
            return


def check_surface_plausibility(ctx: CheckContext) -> None:
    """Rauheitsangabe feiner, als das genannte Verfahren liefern kann."""
    if not ctx.profile.enabled("SURF.UNREALISTIC"):
        return
    text = ctx.pdf.full_text()
    if RE_FINE_PROCESS.search(text):
        return  # Feinbearbeitung ist angegeben -> plausibel
    ra_values = [float(v.replace(",", ".")) for v in RE_RA_VALUE.findall(text)]
    if not ra_values:
        return
    finest = min(ra_values)
    for name, (regex, limit) in PROCESS_RA_LIMIT.items():
        m = regex.search(text)
        if m and finest < limit / 4:
            ctx.add("SURF.UNREALISTIC",
                    f"Rauheit Ra {finest:g} µm bei Verfahren „{m.group(0)}“ "
                    f"nicht erreichbar",
                    detail=f"Ohne Nachbearbeitung liefert dieses Verfahren "
                           f"etwa Ra {limit} µm. Entweder Feinbearbeitung "
                           f"(Schleifen/Honen) vorgeben oder die "
                           f"Rauheitsforderung anpassen.")
            return
    # Sehr feine Rauheit ohne jedes Feinbearbeitungsverfahren
    fine_limit = float(ctx.profile.params.get("fine_ra_limit", 0.4))
    if finest < fine_limit:
        ctx.add("SURF.UNREALISTIC",
                f"Sehr feine Rauheit Ra {finest:g} µm ohne Angabe eines "
                f"Feinbearbeitungsverfahrens",
                severity=ctx.profile.severity("SURF.UNREALISTIC_MINOR"),
                detail="Ra < 0,4 µm erfordert Schleifen, Honen oder Läppen – "
                       "Verfahren angeben, sonst kalkuliert der Lieferant "
                       "auf Verdacht.")


def check_tolerance_order(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Vertauschte Grenzabmaße und tolerierte TED-Maße melden."""
    for d in dims:
        if (ctx.profile.enabled("DIM.TOL_ORDER")
                and d.tol_plus is not None and d.tol_minus is not None
                and d.tol_plus < d.tol_minus):
            ctx.add("DIM.TOL_ORDER",
                    f"Grenzabmaße vertauscht bei „{d.raw}“: oberes Abmaß "
                    f"{d.tol_plus:+g} liegt unter dem unteren "
                    f"{d.tol_minus:+g}",
                    bbox=d.bbox, page=d.page,
                    detail="So beschrieben ist das Toleranzfeld leer – das "
                           "Maß kann nicht gefertigt werden. Nach ISO 129-1 "
                           "steht das obere Abmaß oben bzw. zuerst.")
        if (ctx.profile.enabled("DIM.BASIC_TOL") and d.is_basic
                and (d.tol_plus is not None or d.tol_minus is not None
                     or d.fit)):
            ctx.add("DIM.BASIC_TOL",
                    f"Theoretisch genaues Maß „{d.raw}“ trägt zusätzlich "
                    f"eine Toleranz",
                    bbox=d.bbox, page=d.page,
                    detail="Ein eingerahmtes Maß (TED) ist per Definition "
                           "toleranzfrei; die Abweichung regelt allein die "
                           "zugehörige Lagetoleranz (ISO 1101). Entweder den "
                           "Rahmen entfernen oder die Toleranz streichen.")


def check_roughness_vs_tolerance(ctx: CheckContext,
                                 dims: list[DimValue]) -> None:
    """Rauheit gegen die engste Maßtoleranz prüfen.

    Praxisregel: Das Rauheitsprofil darf die Maßtoleranz nicht aufzehren.
    Üblich ist Rz ≤ 1/4 der Toleranzbreite; gemeldet wird erst ab der
    Hälfte, damit nur eindeutige Widersprüche auffallen.
    """
    if not ctx.profile.enabled("SURF.TOL_MISMATCH"):
        return
    coarsest = _coarsest_roughness_um(ctx)
    if coarsest is None:
        return
    tightest = None
    for d in dims:
        span = d.tolerance_span
        if span and (tightest is None or span < tightest[0]):
            tightest = (span, d)
    if tightest is None:
        return
    span_mm, dim = tightest
    span_um = span_mm * 1000.0
    ratio = float(ctx.profile.rule_param("SURF.TOL_MISMATCH", "max_ratio", 0.5))
    if coarsest <= span_um * ratio:
        return
    ctx.add("SURF.TOL_MISMATCH",
            f"Rauheit Rz {coarsest:g} µm ist zu grob für die Toleranz von "
            f"„{dim.raw}“ ({span_um:.0f} µm)",
            bbox=dim.bbox, page=dim.page,
            detail=f"Das Rauheitsprofil verbraucht "
                   f"{coarsest / span_um * 100:.0f} % der Toleranzbreite; "
                   f"üblich sind höchstens 25 %. Entweder eine feinere "
                   f"Oberfläche fordern (Rz ≤ {span_um / 4:.1f} µm) oder die "
                   f"Toleranz aufweiten. Sonst ist das Maß nicht "
                   f"reproduzierbar messbar.")


def _coarsest_roughness_um(ctx: CheckContext) -> float | None:
    """Gröbste Rauheitsangabe der Zeichnung als Rz in µm.

    Ra-Angaben werden mit dem in der Praxis üblichen Faktor 4 auf Rz
    umgerechnet (Rz ≈ 4 × Ra für spanend erzeugte Oberflächen).
    """
    text = ctx.pdf.full_text()
    values: list[float] = []
    for m in RE_RZ_VALUE.finditer(text):
        values.append(_num(m.group(1)))
    for m in RE_RA_VALUE.finditer(text):
        values.append(_num(m.group(1)) * 4.0)
    values = [v for v in values if 0 < v <= 200]
    return max(values) if values else None


def _num(raw: str) -> float:
    return float(raw.replace(",", "."))


# Mindest-Einschraubtiefe als Vielfaches des Nenndurchmessers. Faustwerte
# der Verbindungstechnik (VDI 2230): Stahl 1×D, Guss 1,25×D, Alu 1,5–2×D.
MIN_ENGAGEMENT = {"stahl": 1.0, "guss": 1.25, "alu": 1.5}
RE_SOFT_MATERIAL = re.compile(
    r"\bAl(?:Mg|Si|Cu|Zn)|EN\s?AW|aluminium|\bGD-?Al|kunststoff|\bPA6|POM",
    re.IGNORECASE)


def check_thread_depths(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Gewindetiefe gegen Bohrtiefe und gegen die Mindesteinschraubtiefe.

    Beide Fälle stehen auf der Zeichnung, werden aber selten gegengerechnet:
    „M10 ↧25" mit „⌀8,5 ↧20" ist nicht herstellbar, und „M10 ↧6" trägt in
    Aluminium nicht.
    """
    threads = [d for d in dims if d.kind is DimKind.THREAD and d.depth]
    if not threads:
        return
    weich = bool(RE_SOFT_MATERIAL.search(ctx.pdf.full_text()))
    faktor = MIN_ENGAGEMENT["alu"] if weich else MIN_ENGAGEMENT["stahl"]
    bohrungen = [d for d in dims if d.kind is DimKind.DIAMETER and d.depth]

    for t in threads:
        if ctx.profile.enabled("THRD.DEPTH"):
            core = _core_hole(t.value)
            passende = [b for b in bohrungen
                        if core and abs(b.value - core) <= 0.6]
            for b in passende:
                if t.depth > b.depth + 0.5:
                    ctx.add("THRD.DEPTH",
                            f"Gewinde „{t.raw}“ ist {t.depth:g} mm tief "
                            f"gefordert, die Bohrung ⌀{b.value:g} nur "
                            f"{b.depth:g} mm",
                            bbox=t.bbox, page=t.page,
                            detail="Das Gewinde kann nicht tiefer sein als "
                                   "die Kernbohrung. Üblich sind 2–5 mm "
                                   "Bohrungsüberlauf für den Gewindeauslauf "
                                   "(bei Grundlöchern zwingend).")
                    break
        if ctx.profile.enabled("THRD.SHORT") and t.depth < t.value * faktor:
            werkstoff = "weichem Werkstoff (Alu/Kunststoff)" if weich else "Stahl"
            ctx.add("THRD.SHORT",
                    f"Einschraubtiefe {t.depth:g} mm bei „{t.raw}“ ist kurz – "
                    f"in {werkstoff} sind mindestens "
                    f"{t.value * faktor:.0f} mm üblich",
                    bbox=t.bbox, page=t.page,
                    detail="Unter etwa 1×D (Stahl) bzw. 1,5×D (Aluminium) "
                           "reißt das Gewinde aus, bevor die Schraube ihre "
                           "Festigkeit erreicht (VDI 2230). Entweder tiefer "
                           "gewinden oder Gewindeeinsatz vorsehen.")


def _core_hole(nominal: float) -> float | None:
    pass  # (Import entfaellt - alles ein Modul)

    return THREAD_CORE_DIA.get(int(nominal))


def run_dimension_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_dimension_chain(ctx, dims)
    check_tight_tolerances(ctx, dims)
    check_deep_holes(ctx, dims)
    check_sharp_corners(ctx)
    check_surface_plausibility(ctx)
    check_tolerance_order(ctx, dims)
    check_roughness_vs_tolerance(ctx, dims)
    check_thread_depths(ctx, dims)


# ======================================================================
# gps_checks
# ======================================================================
# GPS-Tiefenprüfung: Bezugssystem, Hüllbedingung, theoretisch genaue Maße.
#
# Deckt die in der Praxis teuersten Tolerierungsfehler ab (Quellen: DGQ zu
# ISO-GPS-Tolerierungsgrundsätzen, GD&T-Reviewpraxis):
#
#   GPS.ENVELOPE        Passung (z. B. ⌀20 H7) ohne Hüllbedingung Ⓔ und ohne
#                       Formtoleranz. Nach ISO 8015 gilt das Unabhängigkeits-
#                       prinzip: die Toleranz begrenzt nur das lokale
#                       Zweipunktmaß – das Teil darf krumm/unrund sein.
#   GPS.DATUM_UNDEFINED Toleranzrahmen verweist auf Bezug A/B/C, der nirgends
#                       als Bezugsstelle definiert ist.
#   GPS.DATUM_UNUSED    Bezug definiert, aber in keinem Toleranzrahmen benutzt.
#   GPS.POSITION_NO_TED Positionstoleranz ohne theoretisch genaue Maße (TED):
#                       der Sollort ist damit nicht festgelegt.
#   GPS.MOD_ON_FORM     Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz – nur bei
#                       Größenmaßen zulässig.



import re


# Symbolgruppen (Unicode-GD&T)
SYM_POSITION = "⌖"
SYM_FORM = "⏤⏥○⌭⌒"
SYM_ORIENTATION = "∥⊥∠"
SYM_RUNOUT = "↗⌰"
SYM_PROFILE = "⌓⌔"
SYM_LOCATION = SYM_POSITION + "◎⌯"
SYM_NEEDS_DATUM = SYM_POSITION + SYM_ORIENTATION + SYM_RUNOUT + "◎⌯"
SYM_ALL = SYM_FORM + SYM_NEEDS_DATUM + SYM_PROFILE

# Hüllbedingung Ⓔ (U+24BA) bzw. als "(E)" geschriebene Ersatzform.
RE_ENVELOPE = re.compile(r"Ⓔ|\(\s*E\s*\)|ISO\s*14405[-\s]?1?.{0,20}?Ⓔ")
# Bezugsstellen-Definition: Buchstabe im Bezugsdreieck; im Textlayer meist
# als alleinstehender Großbuchstabe bei "Bezug"/"Datum" oder im Rahmen.
RE_DATUM_DEF = re.compile(
    r"(?:bezug|bezüge|datum|datums)\s*:?\s*([A-Z](?:\s*[,/-]\s*[A-Z])*)",
    re.IGNORECASE)
# Bezüge in einem Toleranzrahmen: Symbol, Wert, dann 1-3 Bezugsbuchstaben.
# Nur auf DERSELBEN Zeile ([ \t] statt \s) und als isolierte Großbuchstaben –
# sonst greift der Regex in Folgewörter ("Bezug" -> B).
RE_FCF_DATUMS = re.compile(
    rf"[{SYM_NEEDS_DATUM}][ \t]*⌀?[ \t]*\d+(?:[.,]\d+)?[ \t]*[ⓂⓁ]?"
    r"((?:[ \t]*[-–|]?[ \t]*\b[A-Z]\b(?![a-zäöüß])"
    r"(?:[ \t]*[ⓂⓁ])?){1,3})")
RE_MODIFIER_ON_FORM = re.compile(
    rf"[{SYM_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?\s*[ⓂⓁ]")
# Formtoleranz an einem Größenmaß (Rundheit/Zylindrizität) – hebt den
# Hüllbedingungs-Hinweis auf, weil die Form dann geregelt ist.
RE_FORM_TOL = re.compile(rf"[{SYM_FORM}]\s*⌀?\s*\d+(?:[.,]\d+)?")


def _blocks_text(ctx: CheckContext) -> str:
    return ctx.pdf.full_text()


def _find_block(ctx: CheckContext, regex: re.Pattern):
    for b in ctx.pdf.blocks():
        m = regex.search(b.text)
        if m:
            return m, b.bbox, b.page
    return None


def check_envelope_requirement(ctx: CheckContext,
                               dims: list[DimValue]) -> None:
    """Passungen ohne Hüllbedingung und ohne Formtoleranz."""
    if not ctx.profile.enabled("GPS.ENVELOPE"):
        return
    text = _blocks_text(ctx)
    # Nur relevant, wenn das Unabhängigkeitsprinzip gilt (ISO 8015 /
    # ISO 14405 bzw. keine gegenteilige Angabe) – das ist der Normalfall.
    if RE_ENVELOPE.search(text):
        return
    if RE_FORM_TOL.search(text):
        return  # Form ist über eine Formtoleranz geregelt
    # Enge Passungen (IT ≤ 8) an Größenmaßen sind die kritischen Fälle.
    critical = [d for d in dims
                if d.fit and (d.it_grade or 99) <= 8
                and d.kind in (DimKind.DIAMETER, DimKind.LINEAR)]
    if not critical:
        return
    example = critical[0]
    names = ", ".join(sorted({f"⌀{d.value:g} {d.fit}" for d in critical})[:4])
    ctx.add("GPS.ENVELOPE",
            f"Enge Passung ohne Hüllbedingung Ⓔ und ohne Formtoleranz "
            f"({names})",
            bbox=example.bbox, page=example.page,
            detail="Nach ISO 8015 (Unabhängigkeitsprinzip) begrenzt die "
                   "Passungstoleranz nur das lokale Zweipunktmaß – Form "
                   "(Rundheit, Geradheit) bleibt unbegrenzt. Für Fügeflächen "
                   "Ⓔ ergänzen oder Formtoleranz angeben.")


def check_datum_consistency(ctx: CheckContext) -> None:
    """Bezüge in Toleranzrahmen vs. definierte Bezugsstellen.

    Ein Bezug gilt als definiert, wenn sein Buchstabe AUSSERHALB der
    Toleranzrahmen vorkommt (Bezugsdreieck, "Bezug A = …"). Kommt er nur
    innerhalb von Toleranzrahmen vor, fehlt die Bezugsstelle (ISO 5459).
    """
    text = _blocks_text(ctx)
    referenced: dict[str, int] = {}
    for m in RE_FCF_DATUMS.finditer(text):
        for letter in re.findall(r"[A-Z]", m.group(1)):
            referenced[letter] = referenced.get(letter, 0) + 1
    # Zusätzlich die grafisch erkannten Toleranzrahmen auswerten – auf
    # realen CAD-Zeichnungen liegt GD&T meist als Vektorgrafik vor.
    for frame in ctx.feature_frames:
        for letter in frame.datums:
            referenced[letter] = referenced.get(letter, 0) + 1
    if not referenced:
        return

    # Vorkommen je Buchstabe als eigenständiges Wort im gesamten Text.
    standalone: dict[str, int] = {}
    for w in ctx.pdf.words():
        t = w.text.strip().strip("[]()")
        if len(t) == 1 and t.isalpha() and t.isupper():
            standalone[t] = standalone.get(t, 0) + 1
    # Explizite Definitionen ("Bezug A", "datum A-B") zählen extra.
    explicit: set[str] = set()
    for m in RE_DATUM_DEF.finditer(text):
        explicit.update(re.findall(r"[A-Z]", m.group(1)))

    if ctx.profile.enabled("GPS.DATUM_UNDEFINED"):
        missing = sorted(
            letter for letter, n_ref in referenced.items()
            if letter not in explicit and standalone.get(letter, 0) <= n_ref)
        if missing:
            hit = _find_block(ctx, RE_FCF_DATUMS)
            bbox, page = (hit[1], hit[2]) if hit else (None, 0)
            ctx.add("GPS.DATUM_UNDEFINED",
                    f"Toleranzrahmen verweist auf nicht definierte Bezüge: "
                    f"{', '.join(missing)}",
                    bbox=bbox, page=page,
                    detail="Der Bezugsbuchstabe kommt nur im Toleranzrahmen "
                           "vor – ohne Bezugsstelle am Formelement ist das "
                           "Bezugssystem unvollständig und die Lage nicht "
                           "prüfbar (ISO 5459).")
    if ctx.profile.enabled("GPS.DATUM_UNUSED"):
        unused = sorted(d for d in explicit - set(referenced) if d in "ABCDEFG")
        if unused and len(unused) <= 3:
            ctx.add("GPS.DATUM_UNUSED",
                    f"Bezug {', '.join(unused)} definiert, aber in keinem "
                    f"Toleranzrahmen verwendet",
                    detail="Entweder fehlt eine Lagetoleranz oder der Bezug "
                           "ist überflüssig – bitte klären.")


def check_position_needs_ted(ctx: CheckContext, dims: list[DimValue]) -> None:
    """Positionstoleranz ohne theoretisch genaue Maße."""
    if not ctx.profile.enabled("GPS.POSITION_NO_TED"):
        return
    text = _blocks_text(ctx)
    if SYM_POSITION not in text:
        return
    if any(d.is_basic for d in dims):
        return
    hit = _find_block(ctx, re.compile(re.escape(SYM_POSITION)))
    bbox, page = (hit[1], hit[2]) if hit else (None, 0)
    ctx.add("GPS.POSITION_NO_TED",
            "Positionstoleranz ⌖ verwendet, aber keine theoretisch genauen "
            "Maße (eingerahmt) erkennbar",
            bbox=bbox, page=page,
            detail="Der Sollort muss mit TED (eingerahmten Maßen) festgelegt "
                   "sein; tolerierte Maße dürfen dafür nicht verwendet werden "
                   "(ISO 1101/5458). Hinweis: eingerahmte Maße sind im "
                   "PDF-Textlayer nicht immer erkennbar – bitte sichtprüfen.")


def check_modifier_placement(ctx: CheckContext) -> None:
    """Materialbedingung Ⓜ/Ⓛ an einer Formtoleranz."""
    if not ctx.profile.enabled("GPS.MOD_ON_FORM"):
        return
    hit = _find_block(ctx, RE_MODIFIER_ON_FORM)
    if hit:
        m, bbox, page = hit
        ctx.add("GPS.MOD_ON_FORM",
                f"Materialbedingung an einer Formtoleranz („{m.group(0)}“)",
                bbox=bbox, page=page,
                detail="Ⓜ/Ⓛ sind nur bei Größenmaßen (Bohrung, Welle) "
                       "zulässig, nicht bei Ebenheit/Geradheit/Rundheit "
                       "(ISO 2692).")


def check_diameter_zone_needs_datum(ctx: CheckContext) -> None:
    """⌀-Toleranzzone ohne Bezug.

    Eine kreis-/zylinderförmige Toleranzzone gibt es nur bei Lage- und
    Positionstoleranzen – und die brauchen zwingend ein Bezugssystem
    (ISO 1101/5459). Formtoleranzen haben nie eine ⌀-Zone.
    """
    if not ctx.profile.enabled("GPS.ZONE_NO_DATUM"):
        return
    for frame in ctx.feature_frames:
        if frame.diameter_zone and not frame.has_datums:
            ctx.add("GPS.ZONE_NO_DATUM",
                    f"Toleranzrahmen mit ⌀-Toleranzzone (⌀{frame.value:g}) "
                    f"ohne Bezug",
                    bbox=frame.bbox, page=frame.page,
                    detail="Kreisförmige Toleranzzonen kommen nur bei Lage-/"
                           "Positionstoleranzen vor; ohne Bezugssystem ist die "
                           "Lage nicht definiert (ISO 1101).")
            return


def check_gdt_readability(ctx: CheckContext) -> None:
    """Toleranzrahmen als Grafik: Symbolart nicht maschinell prüfbar."""
    if not ctx.profile.enabled("DOC.GDT_GRAPHIC"):
        return
    graphic = [f for f in ctx.feature_frames if not f.symbol]
    if not graphic:
        return
    text_symbols = any(c in ctx.pdf.full_text() for c in SYM_ALL)
    if text_symbols:
        return
    ctx.add("DOC.GDT_GRAPHIC",
            f"{len(graphic)} Toleranzrahmen erkannt, deren GD&T-Symbol nur "
            f"als Grafik vorliegt",
            bbox=graphic[0].bbox, page=graphic[0].page,
            detail="Toleranzwerte und Bezüge werden geprüft, die Art der "
                   "Toleranz (Position, Ebenheit, Rundlauf …) jedoch nicht – "
                   "diese Angaben bitte visuell prüfen.")


def run_gps_checks(ctx: CheckContext, dims: list[DimValue]) -> None:
    check_envelope_requirement(ctx, dims)
    check_datum_consistency(ctx)
    check_position_needs_ted(ctx, dims)
    check_modifier_placement(ctx)
    check_diameter_zone_needs_datum(ctx)
    check_gdt_readability(ctx)


# ========================================================================
# pruef_geometrie
# ========================================================================
# Abgleich Zeichnung gegen STEP-Modell.
#
# Huellmass, Bohrbild, Gewindekern, Spiegelung, Einheiten - und die
# Silhouetten-Projektion, die das Modell so darstellt, wie es die Ansicht
# zeigen muesste. Alles OpenCascade-Code liegt hier beisammen; die
# Importe sind bewusst traege, damit das Tool ohne OCP startet.
# ======================================================================
# geometry_checks
# ======================================================================
# Vertiefte Geometrieprüfungen: Masse und Bohrbild.
#
# Ergänzen den Hüllmaß-Abgleich (step_compare) um zwei unabhängige Indizien
# für "falsche Konfiguration gespeichert":
#
#   GEO.MASS       Gewichtsangabe der Zeichnung vs. STEP-Volumen × Dichte
#                  des erkannten Werkstoffs. Sehr trennscharf, weil Volumen
#                  und Dichte unabhängig von der Bemaßungsqualität sind.
#   GEO.HOLE_COUNT Explizite Mehrfachangaben der Zeichnung ("4×⌀18") vs.
#                  tatsächlich im Modell vorhandene Bohrungen gleichen
#                  Durchmessers.
#   GEO.THREAD     Gewindeangaben ("M12") ohne passendes Kernloch im Modell.
#
# Alle drei melden konservativ: Ein Treffer ist ein Prüfhinweis, kein
# automatisches K.O. – nur grobe Abweichungen (Faktor) werden hart bewertet.



import logging



# Kernlochdurchmesser für metrisches Regelgewinde (ISO 261/ISO 262).
THREAD_CORE_DIA = {
    3: 2.5, 4: 3.3, 5: 4.2, 6: 5.0, 8: 6.8, 10: 8.5, 12: 10.2, 14: 12.0,
    16: 14.0, 18: 15.5, 20: 17.5, 22: 19.5, 24: 21.0, 27: 24.0, 30: 26.5,
    33: 29.5, 36: 32.0, 42: 37.5, 48: 43.0,
}


def check_mass(ctx: CheckContext, geometry: StepGeometry) -> str:
    """Vergleicht die Gewichtsangabe der Zeichnung mit dem STEP-Volumen.

    Rückgabe: Kurztext für die Excel-Vergleichswerte ("" wenn nicht prüfbar).
    """
    if not ctx.profile.enabled("GEO.MASS") or geometry.backend != "occ":
        return ""
    drawing_kg = extract_weight_kg(ctx.pdf)
    if drawing_kg is None:
        return ""
    hits = find_materials(ctx)
    density = next((h.material.density for h in hits if h.material.density),
                   None)
    if density is None:
        return ""
    model_kg = geometry.mass_kg(density)
    if not model_kg:
        return ""

    ratio = model_kg / drawing_kg if drawing_kg else 0.0
    summary = (f"Masse: Zeichnung {drawing_kg:.2f} kg vs. Modell "
               f"{model_kg:.2f} kg (Dichte {density} g/cm³)")
    warn_pct = float(ctx.profile.params.get("mass_warn_pct", 15)) / 100.0
    error_pct = float(ctx.profile.params.get("mass_error_pct", 40)) / 100.0
    deviation = abs(model_kg - drawing_kg) / drawing_kg

    if deviation > error_pct:
        ctx.add("GEO.MASS",
                f"Masse weicht stark ab: Zeichnung {drawing_kg:.2f} kg, "
                f"Modell {model_kg:.2f} kg ({deviation * 100:.0f} %)",
                detail=f"Volumen {geometry.volume / 1000:.0f} cm³ × Dichte "
                       f"{density} g/cm³. Faktor {ratio:.2f} – Hinweis auf "
                       f"falsche Konfiguration, falschen Werkstoff oder eine "
                       f"veraltete Gewichtsangabe.")
    elif deviation > warn_pct:
        ctx.add("GEO.MASS",
                f"Masse plausibel, aber abweichend: Zeichnung "
                f"{drawing_kg:.2f} kg, Modell {model_kg:.2f} kg "
                f"({deviation * 100:.0f} %)",
                severity=ctx.profile.severity("GEO.MASS_MINOR"),
                detail="Bei Guss-/Schweißteilen und Rohteilgewichten normal – "
                       "sonst Gewichtsangabe im Schriftfeld aktualisieren.")
    return summary


def check_hole_pattern(ctx: CheckContext, geometry: StepGeometry,
                       dims: list[DimValue]) -> str:
    """Explizite Bohrbildangaben ("4×⌀18") gegen das Modell prüfen."""
    if not ctx.profile.enabled("GEO.HOLE_COUNT") or geometry.backend != "occ":
        return ""
    # Nur eindeutige Mehrfachangaben auswerten – Einzelnennungen sagen
    # nichts über die Stückzahl aus (dasselbe Maß kann mehrfach im Blatt
    # stehen), und koaxiale Absätze fasst das Modell zusammen.
    explicit = [d for d in dims
                if d.kind is DimKind.DIAMETER and d.count > 1]
    if not explicit:
        return ""
    tol = float(ctx.profile.params.get("hole_dia_tol", 0.6))
    notes: list[str] = []
    for d in explicit:
        found = sum(n for dia, n in geometry.holes.items()
                    if abs(dia - d.value) <= tol)
        notes.append(f"{d.count}×⌀{d.value:g}→{found}")
        if found == 0:
            ctx.add("GEO.HOLE_COUNT",
                    f"Zeichnung fordert {d.count}×⌀{d.value:g}, im Modell "
                    f"ist keine Bohrung dieses Durchmessers vorhanden",
                    bbox=d.bbox, page=d.page,
                    detail="Bohrbild fehlt im STEP – falsche Konfiguration "
                           "oder Modell ohne Bohrungen (Rohteil?).")
        elif found < d.count:
            ctx.add("GEO.HOLE_COUNT",
                    f"Bohrbild weicht ab: Zeichnung {d.count}×⌀{d.value:g}, "
                    f"Modell {found}×",
                    severity=ctx.profile.severity("GEO.HOLE_COUNT_MINOR"),
                    bbox=d.bbox, page=d.page,
                    detail="Teilbohrungen/Symmetrieangaben können die Zählung "
                           "verkürzen – bitte visuell prüfen.")
    return "Bohrbild " + ", ".join(notes) if notes else ""


def check_threads(ctx: CheckContext, geometry: StepGeometry,
                  dims: list[DimValue]) -> None:
    """Gewindeangaben ohne passendes Kernloch im Modell."""
    if not ctx.profile.enabled("GEO.THREAD") or geometry.backend != "occ":
        return
    threads = {round(d.value, 1): d for d in dims if d.kind is DimKind.THREAD}
    if not threads:
        return
    if not geometry.holes:
        return  # Modell ohne jede Bohrung: Fall deckt GEO.HOLE_COUNT ab
    tol = float(ctx.profile.params.get("thread_core_tol", 0.8))
    missing = []
    for nominal, dim in threads.items():
        core = THREAD_CORE_DIA.get(int(nominal))
        if core is None:
            continue
        # Kernloch ODER Durchgangsloch (Nenndurchmesser) akzeptieren –
        # viele Modelle zeigen das Gewinde als glatte Bohrung.
        ok = any(abs(dia - core) <= tol or abs(dia - nominal) <= tol
                 for dia in geometry.holes)
        if not ok:
            missing.append((nominal, core, dim))
    for nominal, core, dim in missing[:5]:
        ctx.add("GEO.THREAD",
                f"Gewinde M{nominal:g} auf der Zeichnung, im Modell kein "
                f"passendes Loch (Kern ⌀{core}, Nenn ⌀{nominal:g})",
                bbox=dim.bbox, page=dim.page,
                detail="Gewinde werden im STEP oft als glatte Bohrung "
                       "modelliert – fehlt auch die, passt das Modell nicht "
                       "zur Zeichnung.")


# Faktor zwischen Zoll und Millimeter – der Klassiker bei internationalem
# Datenaustausch (STEP in inch exportiert, Zeichnung in mm bemaßt).
INCH_MM = 25.4


def check_unit_mismatch(ctx: CheckContext, geometry: StepGeometry,
                        dims: list[DimValue]) -> bool:
    """Zoll/mm-Verwechslung zwischen Zeichnung und Modell erkennen.

    Liegt das Verhältnis des größten Zeichnungsmaßes zur längsten
    Modellkante nahe 25,4 (oder 1/25,4), ist das Modell in der falschen
    Einheit exportiert – ein Fehler, der wie eine falsche Konfiguration
    aussieht, aber eine ganz andere Ursache (und Lösung) hat.

    Rückgabe: True, wenn ein Einheitenfehler gemeldet wurde.
    """
    if not ctx.profile.enabled("GEO.UNIT_MISMATCH"):
        return False
    envelope = [d.value for d in dims
                if d.kind in (DimKind.LINEAR, DimKind.DIAMETER)]
    if not envelope or not geometry.obb_dims[0]:
        return False
    ratio = max(envelope) / geometry.obb_dims[0]
    tol = float(ctx.profile.params.get("unit_ratio_tol", 0.06))
    for factor, text in ((INCH_MM, "Modell in Zoll, Zeichnung in mm"),
                         (1 / INCH_MM, "Modell in mm, Zeichnung in Zoll")):
        if abs(ratio - factor) / factor <= tol:
            ctx.add("GEO.UNIT_MISMATCH",
                    f"Einheiten-Verwechslung wahrscheinlich: {text} "
                    f"(Verhältnis {ratio:.1f} ≈ {factor:.3g})",
                    detail="STEP-Datei mit der richtigen Längeneinheit neu "
                           "exportieren; die Geometrie selbst ist vermutlich "
                           "korrekt.")
            return True
    return False


def check_assembly_vs_part(ctx: CheckContext, geometry: StepGeometry) -> None:
    """Baugruppe im Modell, aber Einzelteilzeichnung (oder umgekehrt)."""
    if not ctx.profile.enabled("GEO.ASSEMBLY") or geometry.backend != "occ":
        return
    pass  # (Import entfaellt - alles ein Modul)

    has_bom = bool(RE_BOM_HEADER.search(ctx.pdf.full_text()))
    if geometry.disjoint_solids > 1 and not has_bom:
        ctx.add("GEO.ASSEMBLY",
                f"Modell enthält {geometry.disjoint_solids} räumlich getrennte "
                f"Körper, die Zeichnung ist aber ein Einzelteil "
                f"(keine Stückliste)",
                detail="Vermutlich wurde die Baugruppe statt des Einzelteils "
                       "gespeichert – falsches Dokument im Paket.")
    elif (geometry.solid_count > 1 and geometry.disjoint_solids == 1
            and ctx.profile.enabled("GEO.NOT_FUSED")):
        ctx.add("GEO.NOT_FUSED",
                f"Modell besteht aus {geometry.solid_count} sich berührenden, "
                f"nicht verschmolzenen Körpern",
                severity=ctx.profile.severity("GEO.NOT_FUSED"),
                detail="Volumen- und Masseberechnung bleiben korrekt, aber "
                       "das Modell ist kein sauberer Einzelkörper – für "
                       "Folgeprozesse (CAM, FEM) oft problematisch.")
    elif geometry.disjoint_solids == 1 and geometry.solid_count == 1 and has_bom:
        ctx.add("GEO.ASSEMBLY",
                "Zeichnung enthält eine Stückliste, das Modell aber nur einen "
                "Körper",
                severity=ctx.profile.severity("GEO.ASSEMBLY_MINOR"),
                detail="Bei Baugruppenzeichnungen sollte das Modell die "
                       "Einzelteile enthalten – bitte prüfen, ob das richtige "
                       "Dokument hinterlegt ist.")


# ======================================================================
# step_compare
# ======================================================================
# Geometrieabgleich: STEP-Modell gegen die aus der Zeichnung ermittelten Maße.
#
# Ziel: falsch gespeicherte Konfigurationen erkennen (Zeichnung und 3D-Modell
# gehören nicht zusammen).
#
# Zwei Backends:
#   * OCC (cadquery-ocp / OpenCascade): exakte optimale Bounding-Box (OBB,
#     orientierungsunabhängig), Volumen, Zylinderflächen-Durchmesser.
#   * Fallback ohne OCC: Punktwolke aller CARTESIAN_POINT-Einträge der
#     STEP-Datei, PCA-orientierte Bounding-Box. Kein Volumen, keine Zylinder.
#
# Ergebnis ist bewusst dreistufig: passt / passt nicht / nicht sicher bewertbar.
# Bei Guss-/Schweißprofilen sind die Toleranzbänder größer und "passt nicht"
# wird per Profil auf warning herabgestuft (siehe rules/profiles.yaml).



import gc
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path




@dataclass
class StepGeometry:
    obb_dims: tuple[float, float, float]      # Kantenlängen der OBB, absteigend
    volume: float | None = None               # mm³ (nur OCC)
    cylinder_diameters: list[float] = field(default_factory=list)  # nur OCC
    # Bohrbild aus dem Modell: {Durchmesser: Anzahl} – getrennt nach
    # Innenzylindern (Bohrungen) und Außenzylindern (Wellen/Zapfen).
    holes: dict[float, int] = field(default_factory=dict)
    shafts: dict[float, int] = field(default_factory=dict)
    planar_faces: int = 0
    face_count: int = 0
    solid_count: int = 1          # Volumenkörper im Modell
    disjoint_solids: int = 1      # davon räumlich getrennt (echte Baugruppe)
    backend: str = "fallback"
    point_count: int = 0

    @property
    def diagonal(self) -> float:
        a, b, c = self.obb_dims
        return (a * a + b * b + c * c) ** 0.5

    def mass_kg(self, density_g_cm3: float) -> float | None:
        """Masse aus Volumen und Werkstoffdichte (g/cm³) in kg."""
        if not self.volume or density_g_cm3 <= 0:
            return None
        return self.volume / 1000.0 * density_g_cm3 / 1000.0


class StepError(Exception):
    pass


# ---------------------------------------------------------------- Backends
def analyze_step(path: Path) -> StepGeometry:
    """STEP auswerten und den OpenCascade-Speicher wieder freigeben.

    Wichtig für den Dauerlauf: Der STEP-Leser hält das übertragene Modell
    fest (~25 MB je Datei). Ohne das ausdrückliche Freigeben unten wächst
    der Prozess über eine Materialgruppe um Gigabyte und stirbt irgendwann
    – gemessen mit `python -m tools.messen langlauf`.
    """
    try:
        return _analyze_occ(path)
    except ImportError:
        log.info("OCP nicht verfügbar – nutze Punktwolken-Fallback für %s", path.name)
        return _analyze_pointcloud(path)


def _analyze_occ(path: Path) -> StepGeometry:
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    try:
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise StepError(f"STEP-Datei nicht lesbar: {path}")
        reader.TransferRoots()
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepError(f"STEP-Datei enthält keine Geometrie: {path}")
        return _measure(shape)
    finally:
        # OpenCascade-Speicher ausdrücklich freigeben (siehe analyze_step).
        reader = None
        shape = None
        gc.collect()


def _box_bounds(box) -> tuple:
    """Eckpunkte einer Bnd_Box - fassungsunabhängig.

    Die OpenCascade-Bindung heißt je nach Fassung anders: OCP 8.x kennt
    `GetXMin()`, das ältere OCP 7.9 (letzte Fassung für Python 3.10) nur
    `CornerMin()`/`CornerMax()`. Beides wird bedient, sonst läuft das
    Werkzeug je nach Python-Fassung des Zielrechners nicht.
    """
    if hasattr(box, "CornerMin"):
        a, b = box.CornerMin(), box.CornerMax()
        return (a.X(), a.Y(), a.Z(), b.X(), b.Y(), b.Z())
    return (box.GetXMin(), box.GetYMin(), box.GetZMin(),
            box.GetXMax(), box.GetYMax(), box.GetZMax())


def _measure(shape) -> StepGeometry:
    """Vermisst die eingelesene Gestalt (Hüllmaße, Volumen, Zylinder)."""
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    # Getrennte Volumenkörper zählen (Baugruppe vs. Einzelteil)
    from OCP.TopAbs import TopAbs_SOLID

    from OCP.Bnd import Bnd_Box

    solid_boxes = []
    sexp = TopExp_Explorer(shape, TopAbs_SOLID)
    while sexp.More():
        box = Bnd_Box()
        BRepBndLib.Add_s(sexp.Current(), box, True)
        if not box.IsVoid():
            solid_boxes.append(_box_bounds(box))
        sexp.Next()
    solids = len(solid_boxes)
    disjoint = _count_disjoint_groups(solid_boxes)

    obb = Bnd_OBB()
    BRepBndLib.AddOBB_s(shape, obb, True, True, True)
    dims = tuple(sorted(
        (2 * obb.XHSize(), 2 * obb.YHSize(), 2 * obb.ZHSize()), reverse=True))

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume = max(props.Mass(), 0.0)

    # Zylinderflächen einsammeln und zu physischen Bohrungen/Zapfen
    # zusammenfassen: mehrere Teilflächen derselben Achse gehören zusammen.
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED

    cylinders: dict[tuple, dict] = {}
    planar = 0
    n_faces = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        n_faces += 1
        surf = BRepAdaptor_Surface(face)
        stype = surf.GetType()
        if stype == GeomAbs_Plane:
            planar += 1
        elif stype == GeomAbs_Cylinder:
            cyl = surf.Cylinder()
            radius = cyl.Radius()
            ax = cyl.Axis()
            d, loc = ax.Direction(), ax.Location()
            # Achsschlüssel: Richtung (vorzeichenneutral) + Aufpunkt, auf die
            # Ebene senkrecht zur Achse projiziert -> identisch für alle
            # Teilflächen derselben Bohrung.
            dir_key = _axis_dir_key(d.X(), d.Y(), d.Z())
            perp = _perp_offset((loc.X(), loc.Y(), loc.Z()),
                                (d.X(), d.Y(), d.Z()))
            key = (round(radius, 2), dir_key, perp)
            entry = cylinders.setdefault(
                key, {"radius": radius, "inner": 0, "outer": 0})
            if face.Orientation() == TopAbs_REVERSED:
                entry["inner"] += 1
            else:
                entry["outer"] += 1
        exp.Next()

    holes: dict[float, int] = {}
    shafts: dict[float, int] = {}
    for entry in cylinders.values():
        dia = round(2 * entry["radius"], 2)
        target = holes if entry["inner"] >= entry["outer"] else shafts
        target[dia] = target.get(dia, 0) + 1

    diameters = sorted({*holes, *shafts}, reverse=True)
    return StepGeometry(
        obb_dims=dims, volume=volume, cylinder_diameters=diameters,
        holes=holes, shafts=shafts, planar_faces=planar, face_count=n_faces,
        solid_count=max(solids, 1), disjoint_solids=max(disjoint, 1),
        backend="occ",
    )


def _count_disjoint_groups(boxes: list[tuple], slack: float = 0.01) -> int:
    """Zählt räumlich getrennte Körpergruppen anhand ihrer Bounding-Boxen.

    Sich berührende oder überlappende Körper gehören zu einem Bauteil
    (nur nicht verschmolzen); getrennte Gruppen sind eine echte Baugruppe.
    """
    n = len(boxes)
    if n <= 1:
        return n
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def overlaps(a, b):
        ax0, ay0, az0, ax1, ay1, az1 = a
        bx0, by0, bz0, bx1, by1, bz1 = b
        return (ax0 - slack <= bx1 and bx0 - slack <= ax1
                and ay0 - slack <= by1 and by0 - slack <= ay1
                and az0 - slack <= bz1 and bz0 - slack <= az1)

    for i in range(n):
        for j in range(i + 1, n):
            if overlaps(boxes[i], boxes[j]):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri
    return len({find(i) for i in range(n)})


def _axis_dir_key(x: float, y: float, z: float, ndigits: int = 2) -> tuple:
    """Richtungsschlüssel ohne Vorzeichen (Achse ±d ist dieselbe Achse)."""
    v = (x, y, z)
    # Vorzeichen an der ersten signifikanten Komponente normieren
    for c in v:
        if abs(c) > 1e-9:
            if c < 0:
                v = (-x, -y, -z)
            break
    return tuple(round(c, ndigits) for c in v)


def _perp_offset(point: tuple, direction: tuple, ndigits: int = 1) -> tuple:
    """Aufpunkt der Achse, senkrecht zur Achsrichtung projiziert."""
    px, py, pz = point
    dx, dy, dz = direction
    norm = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
    dx, dy, dz = dx / norm, dy / norm, dz / norm
    t = px * dx + py * dy + pz * dz
    return (round(px - t * dx, ndigits), round(py - t * dy, ndigits),
            round(pz - t * dz, ndigits))


RE_CARTESIAN = re.compile(
    r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*"
    r"(-?[\d.Ee+-]+)\s*,\s*(-?[\d.Ee+-]+)\s*,\s*(-?[\d.Ee+-]+)\s*\)\s*\)"
)


def _analyze_pointcloud(path: Path) -> StepGeometry:
    """PCA-orientierte Bounding-Box über alle kartesischen Punkte der Datei.

    Kontrollpunkte von Freiformflächen können leicht außerhalb der Geometrie
    liegen – für den Konfigurationsabgleich (grobe Hüllmaße) ist das ausreichend.
    """
    import numpy as np

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise StepError(f"STEP-Datei nicht lesbar: {path} ({exc})") from exc
    pts = np.array(
        [[float(a), float(b), float(c)] for a, b, c in RE_CARTESIAN.findall(text)],
        dtype=float,
    )
    if len(pts) < 4:
        raise StepError(f"Keine auswertbaren Punkte in STEP-Datei: {path}")

    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    _eigval, eigvec = np.linalg.eigh(cov)
    proj = centered @ eigvec
    extents = proj.max(axis=0) - proj.min(axis=0)
    dims = tuple(sorted((float(x) for x in extents), reverse=True))
    return StepGeometry(obb_dims=dims, backend="fallback", point_count=len(pts))


# ----------------------------------------------------------------- Abgleich
@dataclass
class CompareResult:
    verdict: str            # "passt" | "passt_nicht" | "unsicher"
    summary: str            # menschenlesbare Vergleichswerte (für Excel)
    detail: str = ""
    main_ok: bool = False   # größtes Zeichnungsmaß passt zur größten OBB-Kante


def _tol(profile, value: float) -> float:
    t = profile.step_tolerance
    return max(float(t.get("rel", 0.05)) * value, float(t.get("abs", 2.0)))


def compare_step_to_drawing(
    geometry: StepGeometry, dims: list[DimValue], profile
) -> CompareResult:
    envelope = estimate_envelope(dims)
    obb = geometry.obb_dims
    summary_parts = [
        f"STEP-OBB {obb[0]:.1f} × {obb[1]:.1f} × {obb[2]:.1f} mm"
        + (f", V={geometry.volume / 1000.0:.1f} cm³" if geometry.volume else "")
        + f" [{geometry.backend}]",
        "Zeichnungsmaße (Top): " + (
            ", ".join(f"{v:g}" for v in envelope) if envelope else "keine extrahiert"),
    ]
    summary = " | ".join(summary_parts)

    if not envelope:
        return CompareResult("unsicher", summary,
                             "Keine Maße aus der Zeichnung extrahierbar.")

    # 1) Hauptmaß: das größte Zeichnungsmaß muss zur größten OBB-Kante passen.
    main = envelope[0]
    main_dev = abs(main - obb[0])
    main_ok = main_dev <= _tol(profile, main)

    # 2) Kein Zeichnungsmaß darf größer als die Raumdiagonale des STEP sein.
    diag = geometry.diagonal
    oversized = [v for v in envelope if v > diag + _tol(profile, v)]

    # 3) Wie viele Top-Maße finden eine Entsprechung in einer OBB-Kante,
    #    der Diagonale einer OBB-Seitenfläche oder einem Zylinderdurchmesser?
    face_diags = [
        (obb[0] ** 2 + obb[1] ** 2) ** 0.5,
        (obb[0] ** 2 + obb[2] ** 2) ** 0.5,
        (obb[1] ** 2 + obb[2] ** 2) ** 0.5,
    ]
    targets = list(obb) + face_diags + list(geometry.cylinder_diameters)
    matched = sum(
        1 for v in envelope
        if any(abs(v - t) <= _tol(profile, v) for t in targets)
    )
    ratio = matched / len(envelope)

    drawing_dia = sorted(
        {round(d.value, 2) for d in dims if d.kind == DimKind.DIAMETER}, reverse=True)
    dia_note = ""
    if drawing_dia and geometry.cylinder_diameters:
        hits = sum(
            1 for v in drawing_dia
            if any(abs(v - c) <= _tol(profile, v) for c in geometry.cylinder_diameters)
        )
        dia_note = f" ⌀-Treffer: {hits}/{len(drawing_dia)}."

    detail = (f"Hauptmaß {main:g} vs. OBB {obb[0]:.1f} "
              f"(Abw. {main_dev:.1f} mm). Maß-Zuordnung: {matched}/{len(envelope)}."
              + dia_note)

    if oversized:
        return CompareResult(
            "passt_nicht", summary,
            f"Zeichnungsmaß(e) {', '.join(f'{v:g}' for v in oversized)} mm größer "
            f"als die STEP-Raumdiagonale ({diag:.1f} mm). " + detail,
            main_ok=main_ok)
    # Hinweis: Zwischenmaße (Absatzlängen, Lochabstände) finden naturgemäß
    # keine OBB-Entsprechung – deshalb genügt neben dem Hauptmaß eine
    # moderate Zuordnungsquote für "passt".
    if main_ok and ratio >= 0.3:
        return CompareResult("passt", summary, detail, main_ok=True)
    if not main_ok and ratio < 0.34:
        # Richtung der Abweichung entscheidet über die Härte:
        #   Zeichnungsmaß GRÖSSER als das Modell -> Widerspruch, das Teil
        #   kann das Maß nicht enthalten.
        #   Modell GRÖSSER als jedes bemaßte Maß -> meist fehlt schlicht das
        #   Gesamtmaß auf dem Blatt (Maßkette, Fortsetzungsblatt). Am
        #   Kalibriersatz aus 92 echten Zeichnungen war das die Ursache für
        #   drei von vier K.O.-Fehlurteilen – deshalb nur "unsicher".
        if main > obb[0]:
            return CompareResult("passt_nicht", summary, detail, main_ok=False)
        return CompareResult(
            "unsicher", summary,
            detail + " Das Modell ist größer als jedes bemaßte Maß – "
            "möglicherweise fehlt das Gesamtmaß auf der Zeichnung.",
            main_ok=False)
    return CompareResult("unsicher", summary, detail, main_ok=main_ok)


def _check_mirrored(ctx: CheckContext, step: Path,
                     geometry: StepGeometry) -> None:
    """Prüft, ob die falsche Hand (gespiegeltes Teil) gespeichert wurde.

    Ein gespiegeltes Bauteil hat dieselben Hüllmaße, dasselbe Volumen,
    dieselbe Masse und dasselbe Bohrbild – es kommt durch jede andere
    Prüfung. Nur der Umriss in den Ansichten unterscheidet sich.
    """
    if not ctx.profile.enabled("GEO.MIRROR") or geometry.backend != "occ":
        return
    try:
        pass  # (im selben Modul)

        gerade, gespiegelt, ansichten = check_mirrored(ctx.pdf, step)
    except ImportError:
        return
    except Exception as exc:
        log.warning("Spiegelprüfung fehlgeschlagen für %s: %s", step.name, exc)
        return
    if ansichten < 2:
        return
    abstand = float(ctx.profile.rule_param("GEO.MIRROR", "min_abstand", 0.15))
    mindest = float(ctx.profile.rule_param("GEO.MIRROR", "min_score", 0.5))
    if gespiegelt >= mindest and gespiegelt - gerade >= abstand:
        ctx.add("GEO.MIRROR",
                "Die Ansichten passen besser zum GESPIEGELTEN Modell – "
                "vermutlich die falsche Ausführung (linke/rechte Hand) "
                "gespeichert",
                detail=f"Konturübereinstimmung: gespiegelt {gespiegelt:.2f} "
                       f"gegen {gerade:.2f} wie gespeichert, über "
                       f"{ansichten} Ansichten. Hüllmaße, Volumen und "
                       f"Bohrbild sind bei gespiegelten Teilen identisch – "
                       f"diese Prüfung ist die einzige, die den Fall findet. "
                       f"Vor dem Bestellen die Ausführung klären.")


def _apply_contour_stage(ctx: CheckContext, step: Path, result: CompareResult,
                         geometry: StepGeometry) -> CompareResult:
    """Ausbaustufe Konturprojektion: schärft das Maß-Urteil, ersetzt es nicht.

    * "unsicher" + klar guter Kontur-Score + Hauptmaß ok  -> "passt"
    * "passt"    + klar schlechter Kontur-Score           -> "unsicher"
    * "passt_nicht" bleibt immer bestehen.
    Läuft nur mit OCC-Backend und wenn GEO.CONTOUR im Profil aktiv ist.
    """
    if not ctx.profile.enabled("GEO.CONTOUR") or geometry.backend != "occ":
        return result
    if result.verdict == "passt_nicht":
        return result
    try:
        pass  # (im selben Modul)

        contour = compare_contours(ctx.pdf, step)
    except ImportError:
        return result
    except Exception as exc:
        log.warning("Konturprojektion fehlgeschlagen für %s: %s", step.name, exc)
        return result
    if contour.views_used == 0:
        return result

    summary = result.summary + (
        f" | Kontur-Score {contour.score:.2f} ({contour.views_used} Ansichten)")
    detail = result.detail + " " + contour.detail
    verdict = result.verdict
    if verdict == "unsicher" and contour.score >= SCORE_GOOD and result.main_ok:
        verdict = "passt"
        detail += " Konturprojektion bestätigt die Zuordnung."
    elif verdict == "passt" and contour.score <= SCORE_BAD:
        verdict = "unsicher"
        detail += (" Konturprojektion widerspricht trotz passender Maße – "
                   "bitte Sichtprüfung.")
    return CompareResult(verdict, summary, detail, main_ok=result.main_ok)


def check_step(ctx: CheckContext, dims: list[DimValue]) -> str:
    """Führt den kompletten STEP-Check aus; liefert die Summary für Excel."""
    step = ctx.package.step_file
    if step is None:
        if ctx.profile.enabled("DOC.NO_STEP"):
            ctx.add("DOC.NO_STEP",
                    "Kein STEP im Paket – Geometrieprüfung entfällt")
        return ""
    try:
        geometry = analyze_step(step)
    except StepError as exc:
        ctx.add("GEO.UNCERTAIN", f"STEP-Datei nicht auswertbar: {exc}")
        return ""

    result = compare_step_to_drawing(geometry, dims, ctx.profile)
    result = _apply_contour_stage(ctx, step, result, geometry)

    # Vertiefte Einzelprüfungen (unabhängig vom Hüllmaß-Urteil)
    pass  # (im selben Modul)

    _check_mirrored(ctx, step, geometry)
    unit_error = check_unit_mismatch(ctx, geometry, dims)
    extra = [check_mass(ctx, geometry), check_hole_pattern(ctx, geometry, dims)]
    if geometry.backend == "occ" and geometry.volume:
        # Diagnose zur Massenabweichung: passt die Gewichtsangabe zu einem
        # ANDEREN Werkstoff? (kopiertes Schriftfeld, Werkstoff geändert)
        pass  # (Import entfaellt - alles ein Modul)

        check_density_hint(ctx, geometry.volume)
    check_threads(ctx, geometry, dims)
    check_assembly_vs_part(ctx, geometry)
    pass  # (Import entfaellt - alles ein Modul)

    check_view_vs_model(ctx, geometry, dims)
    if unit_error:
        # Bei falscher Einheit sind Hüllmaß-Abweichungen die Folge, nicht die
        # Ursache – den Maß-Mismatch dann nicht zusätzlich als K.O. melden.
        ctx.findings = [f for f in ctx.findings if f.code != "GEO.MISMATCH"]
        result = CompareResult("unsicher", result.summary,
                               result.detail + " (Einheitenfehler erkannt)")
    if result.verdict == "passt_nicht" and ctx.pdf.ocr_used:
        # Maße aus OCR sind nicht sicher genug für ein K.O.-Urteil: ein
        # falsch gelesenes Maß darf keine Zeichnung sperren.
        ctx.add("GEO.UNCERTAIN",
                "Geometrie passt rechnerisch nicht – die Maße stammen aber "
                "aus OCR, deshalb nur als Prüfhinweis",
                detail=result.detail + " " + ctx.pdf.ocr_note())
    elif result.verdict == "passt_nicht":
        ctx.add("GEO.MISMATCH",
                "Geometrie passt nicht zur Zeichnung – vermutlich falsche "
                "Konfiguration gespeichert", detail=result.detail)
    elif result.verdict == "unsicher":
        ctx.add("GEO.UNCERTAIN",
                "Geometrieabgleich nicht sicher bewertbar – bitte manuell prüfen",
                detail=result.detail)
    if not dims and ctx.profile.enabled("GEO.NO_DIMS"):
        ctx.add("GEO.NO_DIMS",
                "Keine Maße aus der Zeichnung extrahierbar (Geometrieabgleich "
                "nur eingeschränkt möglich)")
    return " | ".join([result.summary, *[e for e in extra if e]])


# ======================================================================
# contour_projection
# ======================================================================
# Ausbaustufe Geometrieabgleich: Konturprojektion STEP vs. Zeichnungsansichten.
#
# Idee: Das STEP-Modell wird aus den drei Hauptachsenrichtungen als
# 2D-Silhouette projiziert (OpenCascade HLR, sichtbare Kanten + Umrisse).
# Aus dem PDF werden die Vektorlinien extrahiert und zu Ansichten geclustert
# (Blattrahmen/Schriftfeld werden verworfen). Beide Seiten werden auf ein
# normiertes Rasterbild gezeichnet und per IoU verglichen – rotations- und
# spiegelinvariant (8 Orientierungen je Ansicht).
#
# Grenzen (bewusst): Maßhilfslinien und Schraffuren verschmutzen die
# Ansichts-Cluster, Schnittansichten entsprechen keiner Außensilhouette.
# Der Score wird deshalb nur KONSERVATIV verwendet: Ein klar guter Score kann
# ein "unsicher" des Maßabgleichs bestätigen, ein klar schlechter Score ein
# "passt" auf "unsicher" herabstufen – er erzeugt nie allein ein "passt nicht".



import gc
import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


RASTER = 224          # Kantenlänge des Vergleichsrasters (Pixel)
MARGIN = 12
LINE_W = 3
DILATE = 5            # Toleranzband um Linien (MaxFilter-Kern)
MIN_VIEW_FRACTION = 0.06   # Cluster-Diagonale mind. 6 % der Seiten-Diagonale
MAX_VIEWS = 4
# Score-Schwellen (kalibriert an den Mockzeichnungen, s. tests):
# richtige Paarungen ~0.58-0.80, falsche ~0.12-0.31 -> dazwischen neutral.
SCORE_GOOD = 0.45
SCORE_BAD = 0.20

Segment = tuple[float, float, float, float]
WSegment = tuple[float, float, float, float, float]  # + Strichbreite


@dataclass
class ViewCluster:
    segments: list[Segment]        # Konturlinien (breite Striche, ISO 128)
    bbox: tuple[float, float, float, float]
    all_count: int = 0             # inkl. Maß-/Hilfslinien (nur Statistik)


@dataclass
class ContourResult:
    score: float                  # bestes Mittel der Ansichts-Scores (0..1)
    views_used: int
    per_view: list[float] = field(default_factory=list)
    detail: str = ""


# ======================================================================
# STEP-Seite: Silhouetten über HLR
# ======================================================================
def project_step_silhouettes(step_path: Path) -> list[list[Segment]]:
    """Projiziert das Modell entlang der drei OBB-Hauptachsen.

    Liefert je Richtung eine Liste von 2D-Segmenten (sichtbare Kanten und
    Umrisse). Benötigt OCP; ImportError wird nach oben gereicht.
    """
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Ax3
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step_path)) != IFSelect_RetDone:
        raise ValueError(f"STEP nicht lesbar: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    try:
        return _project_shape(shape)
    finally:
        # Ohne ausdrückliches Freigeben behält OpenCascade das Modell im
        # Speicher (rund 25 MB je Datei) – im Dauerlauf tödlich.
        reader = None
        shape = None
        gc.collect()


def _project_shape(shape) -> list[list[Segment]]:
    """Projiziert eine eingelesene Gestalt entlang ihrer OBB-Hauptachsen."""
    from OCP.Bnd import Bnd_OBB
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.gp import gp_Ax2, gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    obb = Bnd_OBB()
    BRepBndLib.AddOBB_s(shape, obb, True, True, True)
    center = obb.Center()
    axes = [obb.XDirection(), obb.YDirection(), obb.ZDirection()]

    silhouettes: list[list[Segment]] = []
    for i, axis in enumerate(axes):
        direction = gp_Dir(axis.X(), axis.Y(), axis.Z())
        # Up-Vektor: eine der beiden anderen Achsen
        other = axes[(i + 1) % 3]
        up = gp_Dir(other.X(), other.Y(), other.Z())
        ax2 = gp_Ax2(gp_Pnt(center.X(), center.Y(), center.Z()), direction, up)
        projector = HLRAlgo_Projector(ax2)

        algo = HLRBRep_Algo()
        algo.Add(shape)
        algo.Projector(projector)
        algo.Update()
        algo.Hide()
        extractor = HLRBRep_HLRToShape(algo)

        segments: list[Segment] = []
        for compound in (extractor.VCompound(), extractor.OutLineVCompound()):
            if compound.IsNull():
                continue
            exp = TopExp_Explorer(compound, TopAbs_EDGE)
            while exp.More():
                edge = TopoDS.Edge(exp.Current())
                exp.Next()
                try:
                    curve = BRepAdaptor_Curve(edge)
                    disc = GCPnts_QuasiUniformDeflection(curve, 0.2)
                    if not disc.IsDone() or disc.NbPoints() < 2:
                        continue
                    pts = [disc.Value(k) for k in range(1, disc.NbPoints() + 1)]
                    for a, b in zip(pts, pts[1:]):
                        # HLR liefert Kanten bereits in Projektionskoordinaten
                        segments.append((a.X(), a.Y(), b.X(), b.Y()))
                except Exception:
                    continue
        if segments:
            silhouettes.append(segments)
    return silhouettes


# ======================================================================
# PDF-Seite: Vektorlinien -> Ansichts-Cluster
# ======================================================================
def extract_views(pdf, page: int = 0) -> list[ViewCluster]:
    """Clustert die Vektorgrafik der Seite zu Ansichten.

    Blattrahmen (Cluster, der fast die ganze Seite umspannt – Schriftfeld
    hängt daran) und Winzcluster (Symbole, Pfeile) werden verworfen.
    """
    pg = pdf.doc[page]
    W, H = pg.rect.width, pg.rect.height
    wsegments = _collect_segments(pg)
    if not wsegments:
        return []

    clusters = _cluster_segments(wsegments, cell=max(W, H) / 80.0)
    page_diag = (W * W + H * H) ** 0.5
    views: list[ViewCluster] = []
    for wsegs in clusters:
        # ISO-128-Filter: sichtbare Körperkanten sind breit gezeichnet,
        # Maß-/Hilfs-/Mittellinien schmal. Nur breite Striche bilden die
        # Kontur der Ansicht; die Bounding-Box kommt ebenfalls von ihnen.
        max_w = max(s[4] for s in wsegs)
        thick = [s[:4] for s in wsegs if s[4] >= 0.6 * max_w]
        if len(thick) < 4:
            thick = [s[:4] for s in wsegs]
        xs = [c for s in thick for c in (s[0], s[2])]
        ys = [c for s in thick for c in (s[1], s[3])]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if bw > 0.85 * W and bh > 0.85 * H:
            continue  # Blattrahmen (+ angedocktes Schriftfeld)
        if (bw * bw + bh * bh) ** 0.5 < MIN_VIEW_FRACTION * page_diag:
            continue  # zu klein für eine Ansicht
        views.append(ViewCluster(thick, bbox, all_count=len(wsegs)))
    views.sort(key=lambda v: len(v.segments), reverse=True)
    return views[:MAX_VIEWS]


def _collect_segments(pg) -> list[WSegment]:
    segments: list[WSegment] = []

    for path in pg.get_drawings():
        width = float(path.get("width") or 0.0) or 0.1

        def add(p, q):
            segments.append((p.x, p.y, q.x, q.y, width))

        for item in path["items"]:
            kind = item[0]
            if kind == "l":
                add(item[1], item[2])
            elif kind == "re":
                r = item[1]
                for a, b in ((r.tl, r.tr), (r.tr, r.br), (r.br, r.bl),
                             (r.bl, r.tl)):
                    add(a, b)
            elif kind == "qu":
                q = item[1]
                for a, b in ((q.ul, q.ur), (q.ur, q.lr), (q.lr, q.ll),
                             (q.ll, q.ul)):
                    add(a, b)
            elif kind == "c":
                # Bezier grob in 8 Sehnen zerlegen
                p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
                prev = p0
                for k in range(1, 9):
                    t = k / 8.0
                    mt = 1 - t
                    x = (mt**3 * p0.x + 3 * mt**2 * t * p1.x
                         + 3 * mt * t**2 * p2.x + t**3 * p3.x)
                    y = (mt**3 * p0.y + 3 * mt**2 * t * p1.y
                         + 3 * mt * t**2 * p2.y + t**3 * p3.y)

                    class _P:  # noqa: N801 - Mini-Punkt
                        pass

                    cur = _P(); cur.x, cur.y = x, y
                    add(prev, cur)
                    prev = cur
    return segments


def _cluster_segments(segments: list[WSegment], cell: float) -> list[list[WSegment]]:
    """Union-Find über belegte Rasterzellen (8er-Nachbarschaft)."""
    parent: dict[int, int] = {}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    cell_of: dict[tuple[int, int], int] = {}
    seg_cells: list[list[int]] = []
    for idx, (x0, y0, x1, y1, _w) in enumerate(segments):
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) / cell))
        ids = []
        for k in range(n + 1):
            t = k / n
            cx = int((x0 + (x1 - x0) * t) / cell)
            cy = int((y0 + (y1 - y0) * t) / cell)
            key = (cx, cy)
            if key not in cell_of:
                cid = len(parent)
                parent[cid] = cid
                cell_of[key] = cid
            ids.append(cell_of[key])
        seg_cells.append(ids)
        for a, b in zip(ids, ids[1:]):
            union(a, b)
    # Nachbarzellen verschmelzen
    for (cx, cy), cid in list(cell_of.items()):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nb = cell_of.get((cx + dx, cy + dy))
                if nb is not None:
                    union(cid, nb)

    groups: dict[int, list[WSegment]] = {}
    for seg, ids in zip(segments, seg_cells):
        groups.setdefault(find(ids[0]), []).append(seg)
    return list(groups.values())


# ======================================================================
# Vergleich: normiertes Raster + IoU
# ======================================================================
def rasterize(segments: list[Segment]) -> Image.Image:
    xs = [c for s in segments for c in (s[0], s[2])]
    ys = [c for s in segments for c in (s[1], s[3])]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0) or 1.0
    scale = (RASTER - 2 * MARGIN) / span
    img = Image.new("L", (RASTER, RASTER), 0)
    draw = ImageDraw.Draw(img)
    for sx0, sy0, sx1, sy1 in segments:
        draw.line(
            [(MARGIN + (sx0 - x0) * scale, MARGIN + (sy0 - y0) * scale),
             (MARGIN + (sx1 - x0) * scale, MARGIN + (sy1 - y0) * scale)],
            fill=255, width=LINE_W)
    return img.filter(ImageFilter.MaxFilter(DILATE))


def iou(a: Image.Image, b: Image.Image) -> float:
    pa, pb = a.tobytes(), b.tobytes()
    inter = on_a = on_b = 0
    for xa, xb in zip(pa, pb):
        va, vb = xa > 0, xb > 0
        on_a += va
        on_b += vb
        inter += va and vb
    union = on_a + on_b - inter
    return inter / union if union else 0.0


def _orientations(img: Image.Image, mirrored: bool | None = None):
    """Lagevarianten einer Ansicht.

    mirrored=None: alle (Drehungen und Spiegelungen)
    mirrored=False: nur Drehungen  – passt zum Modell wie gespeichert
    mirrored=True: nur Spiegelungen – passt zur gespiegelten Ausführung
    """
    if mirrored is not True:
        yield img
        yield img.transpose(Image.ROTATE_90)
        yield img.transpose(Image.ROTATE_180)
        yield img.transpose(Image.ROTATE_270)
    if mirrored is not False:
        m = img.transpose(Image.FLIP_LEFT_RIGHT)
        yield m
        yield m.transpose(Image.ROTATE_90)
        yield m.transpose(Image.ROTATE_180)
        yield m.transpose(Image.ROTATE_270)


def match_views(views: list[ViewCluster],
                silhouettes: list[list[Segment]],
                mirrored: bool | None = None) -> ContourResult:
    if not views or not silhouettes:
        return ContourResult(0.0, 0, detail="keine Ansichten/Silhouetten")
    sil_imgs = [rasterize(s) for s in silhouettes]
    per_view: list[float] = []
    for view in views:
        vimg = rasterize(view.segments)
        best = 0.0
        for oriented in _orientations(vimg, mirrored):
            for simg in sil_imgs:
                best = max(best, iou(oriented, simg))
        per_view.append(round(best, 3))
    per_view.sort(reverse=True)
    top = per_view[:2]
    score = sum(top) / len(top)
    return ContourResult(
        score=round(score, 3), views_used=len(views), per_view=per_view,
        detail=f"Ansichts-Scores: {per_view} gegen {len(silhouettes)} "
               f"Silhouetten")


def compare_contours(pdf, step_path: Path) -> ContourResult:
    """Kompletter Konturabgleich Zeichnung (Seite 0) gegen STEP."""
    silhouettes = project_step_silhouettes(step_path)
    views = extract_views(pdf)
    return match_views(views, silhouettes)


def check_mirrored(pdf, step_path: Path) -> tuple[float, float, int]:
    """Passt die Zeichnung besser zur GESPIEGELTEN Ausführung?

    Der klassische Fall „falsche Hand gespeichert": Hüllmaße, Volumen,
    Masse und Bohrbild sind bei einem gespiegelten Teil identisch – alle
    anderen Prüfungen laufen also durch. Nur die Kontur verrät es.

    Liefert (Score gerade, Score gespiegelt, Anzahl Ansichten). Verglichen
    wird dieselbe Silhouette einmal nur mit Drehungen und einmal nur mit
    Spiegelungen; das ist gleichwertig dazu, das Modell selbst zu spiegeln,
    aber ohne zweite HLR-Projektion.
    """
    silhouettes = project_step_silhouettes(step_path)
    views = extract_views(pdf)
    if not views or not silhouettes:
        return (0.0, 0.0, 0)
    gerade = match_views(views, silhouettes, mirrored=False)
    gespiegelt = match_views(views, silhouettes, mirrored=True)
    return (gerade.score, gespiegelt.score, len(views))


# ========================================================================
# ocr
# ========================================================================
# OCR-Fallback für gescannte Zeichnungen ohne Textlayer.
#
# Technische Zeichnungen sind für OCR ein Sonderfall: Der Text steht nicht in
# Absätzen, sondern verstreut zwischen Linien, ist teilweise um 90° gedreht
# (Maße an senkrechten Maßlinien) und besteht überwiegend aus Codes
# („1.4301", „M12x1,5", „⌀20 H7"), die kein Wörterbuch kennt. Die
# Standardeinstellungen von Tesseract sind darauf nicht ausgelegt.
#
# Der Pfad hier bündelt, was sich in freien OCR-Pipelines (OCRmyPDF,
# tesseract-Rezepte) als wirksam erwiesen hat, zugeschnitten auf Zeichnungen:
#
#   1. Hohe Renderauflösung (Standard 400 dpi) in Graustufen.
#   2. Binarisierung nach Otsu – entfernt Scan-Rauschen und Grauschleier.
#   3. Optionale Schräglagenkorrektur über das Projektionsprofil.
#   4. Seitensegmentierung „sparse text" (PSM 11) statt Absatzlayout.
#   5. Zweiter Durchgang auf dem um 90° gedrehten Bild; die Fundstellen
#      werden zurückgerechnet. Erst das findet die gedrehten Maßtexte.
#   6. Wörterbücher aus – sonst „korrigiert" Tesseract Codes kaputt.
#   7. Nachkorrektur der typischen Verwechslungen (O/0, l/1, Ø-Varianten).
#
# Alle Stellschrauben lassen sich ohne Codeänderung über Umgebungsvariablen
# setzen (DRAWING_CHECKER_OCR_*), damit die Einstellung am Zielrechner
# nachjustiert werden kann – siehe `OcrSettings`.
# ======================================================================
# ocr
# ======================================================================
# OCR-Fallback für gescannte Zeichnungen ohne Textlayer.
#
# Technische Zeichnungen sind für OCR ein Sonderfall: Der Text steht nicht in
# Absätzen, sondern verstreut zwischen Linien, ist teilweise um 90° gedreht
# (Maße an senkrechten Maßlinien) und besteht überwiegend aus Codes
# („1.4301", „M12x1,5", „⌀20 H7"), die kein Wörterbuch kennt. Die
# Standardeinstellungen von Tesseract sind darauf nicht ausgelegt.
#
# Der Pfad hier bündelt, was sich in freien OCR-Pipelines (OCRmyPDF,
# tesseract-Rezepte) als wirksam erwiesen hat, zugeschnitten auf Zeichnungen:
#
#   1. Hohe Renderauflösung (Standard 400 dpi) in Graustufen.
#   2. Binarisierung nach Otsu – entfernt Scan-Rauschen und Grauschleier.
#   3. Optionale Schräglagenkorrektur über das Projektionsprofil.
#   4. Seitensegmentierung „sparse text" (PSM 11) statt Absatzlayout.
#   5. Zweiter Durchgang auf dem um 90° gedrehten Bild; die Fundstellen
#      werden zurückgerechnet. Erst das findet die gedrehten Maßtexte.
#   6. Wörterbücher aus – sonst „korrigiert" Tesseract Codes kaputt.
#   7. Nachkorrektur der typischen Verwechslungen (O/0, l/1, Ø-Varianten).
#
# Alle Stellschrauben lassen sich ohne Codeänderung über Umgebungsvariablen
# setzen (DRAWING_CHECKER_OCR_*), damit die Einstellung am Zielrechner
# nachjustiert werden kann – siehe `OcrSettings`.



import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pymupdf


if TYPE_CHECKING:
    pass  # (Import entfaellt - alles ein Modul)



@dataclass
class OcrSettings:
    """Einstellungen des OCR-Pfads (Umgebungsvariablen in Klammern)."""

    dpi: int = 400                  # DRAWING_CHECKER_OCR_DPI
    min_conf: int = 50              # DRAWING_CHECKER_OCR_MIN_CONF
    lang: str = "deu+eng"           # DRAWING_CHECKER_OCR_LANG
    psm: int = 11                   # DRAWING_CHECKER_OCR_PSM (11 = sparse)
    # Zusätzliche Durchgänge auf gedrehtem Bild (Grad, im Uhrzeigersinn).
    rotations: tuple[int, ...] = (90,)     # DRAWING_CHECKER_OCR_ROTATIONS
    # Gedrehte Durchgänge liefern auf waagerechtem Text Unsinn – deshalb
    # dort strenger schwellen UND nur hochkant stehende Funde übernehmen
    # (echter gedrehter Text ist im Original höher als breit).
    rotation_conf_bonus: int = 10
    rotation_min_aspect: float = 1.2
    binarize: bool = True           # DRAWING_CHECKER_OCR_BINARIZE=0
    # Zeichnungs-, Maß- und Rahmenlinien vor der Erkennung tilgen. Standard
    # aus: Am Messsatz (saubere Vorlagen) bringt es nichts. Bei echten
    # Archivscans, deren Linien in die Schrift verlaufen, lohnt der Versuch:
    # DRAWING_CHECKER_OCR_LINES=1
    remove_lines: bool = False      # DRAWING_CHECKER_OCR_LINES=1
    line_min_frac: float = 0.06     # Mindestlänge, Anteil der Bildbreite
    deskew: bool = True             # DRAWING_CHECKER_OCR_DESKEW=0
    max_skew_deg: float = 3.0
    fix_tokens: bool = True         # DRAWING_CHECKER_OCR_FIX=0
    extra_config: str = ""          # DRAWING_CHECKER_OCR_CONFIG

    @classmethod
    def from_env(cls) -> "OcrSettings":
        s = cls()
        s.dpi = _env_int("DPI", s.dpi)
        s.min_conf = _env_int("MIN_CONF", s.min_conf)
        s.lang = os.environ.get("DRAWING_CHECKER_OCR_LANG", s.lang)
        s.psm = _env_int("PSM", s.psm)
        raw = os.environ.get("DRAWING_CHECKER_OCR_ROTATIONS")
        if raw is not None:
            s.rotations = tuple(int(x) for x in re.findall(r"-?\d+", raw))
        s.binarize = _env_bool("BINARIZE", s.binarize)
        s.remove_lines = _env_bool("LINES", s.remove_lines)
        s.deskew = _env_bool("DESKEW", s.deskew)
        s.fix_tokens = _env_bool("FIX", s.fix_tokens)
        s.extra_config = os.environ.get("DRAWING_CHECKER_OCR_CONFIG",
                                        s.extra_config)
        return s

    def config(self, psm: int | None = None) -> str:
        """Kommandozeile für Tesseract."""
        parts = [
            "--oem 1",                        # LSTM-Engine
            f"--psm {psm if psm is not None else self.psm}",
            f"--dpi {self.dpi}",
            "-c preserve_interword_spaces=1",
            # Wörterbücher aus: „1.4301" ist kein Wort, „M12" auch nicht.
            "-c load_system_dawg=0",
            "-c load_freq_dawg=0",
            "-c load_punc_dawg=0",
            "-c load_number_dawg=0",
        ]
        if self.extra_config:
            parts.append(self.extra_config)
        return " ".join(parts)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[f"DRAWING_CHECKER_OCR_{name}"])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(f"DRAWING_CHECKER_OCR_{name}")
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "nein", "off", "")


# --------------------------------------------------------------- Einstieg
def ocr_words(doc: "pymupdf.Document",
              settings: OcrSettings | None = None,
              pages: list[int] | None = None) -> "list[Word] | None":
    """OCR über (ausgewählte) Seiten; None, wenn Tesseract fehlt.

    Liefert Wort-Bounding-Boxen in PDF-Punkten, damit sie mit dem
    Textlayer-Pfad austauschbar sind.
    """
    tess = _tesseract()
    if tess is None:
        return None
    pytesseract, Image = tess
    cfg = settings or OcrSettings.from_env()

    pass  # (Import entfaellt - alles ein Modul)

    words: list[Word] = []
    todo = pages if pages is not None else range(doc.page_count)
    for pno in todo:
        page = doc[pno]
        img = _render(page, cfg, Image)
        angle = _skew_angle(img, cfg) if cfg.deskew else 0.0
        if angle:
            log.info("OCR Seite %d: Schräglage %.1f° korrigiert", pno + 1, angle)
            gerade = img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
            img.close()
            img = gerade
        try:
            words.extend(_ocr_page(img, pno, cfg, pytesseract, Image, Word))
        finally:
            # Eine A1-Seite bei 400 dpi sind über 100 MB Bilddaten. Ohne
            # ausdrückliches Schließen wächst der Prozess im Dauerlauf mit
            # jeder gescannten Zeichnung (gemessen mit tools/messen.py langlauf).
            img.close()
            release_memory()
    words = _dedupe_words(words)
    if cfg.fix_tokens:
        words = [_fixed(w, Word) for w in words]
    log.info("OCR: %d Wörter erkannt (%d dpi, PSM %d, Drehungen %s)",
             len(words), cfg.dpi, cfg.psm,
             ",".join(str(r) for r in (0,) + tuple(cfg.rotations)))
    return words


def _tesseract():
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        log.warning("pytesseract nicht installiert – OCR-Fallback nicht verfügbar")
        return None
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        log.warning("Tesseract-Binary nicht gefunden – OCR-Fallback nicht verfügbar")
        return None
    return pytesseract, Image


# ------------------------------------------------------------- Bildaufbau
def _render(page, cfg: OcrSettings, Image):
    pix = page.get_pixmap(dpi=cfg.dpi, colorspace=pymupdf.csGRAY)
    img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if cfg.binarize:
        img = _binarize(img, Image)
    if cfg.remove_lines:
        img = _remove_lines(img, cfg, Image)
    return img


def _remove_lines(img, cfg: OcrSettings, Image):
    """Lange Linien (Rahmen, Maß-, Körperkanten) vor der Erkennung tilgen.

    Auf Zeichnungen berühren Maßlinien und Kanten die Schrift; Tesseract
    liest sie als Zeichen mit oder verwirft ganze Wörter. Erkannt werden
    Linien über eine Erosion in Laufrichtung: Nur Pixel, die in einer
    langen ununterbrochenen Kette liegen, überleben – Buchstabenstriche
    sind zu kurz dafür. Anschließend werden die Linien weiß gesetzt.
    """
    import numpy as np

    arr = np.asarray(img)
    dark = arr < 128
    if not dark.any():
        return img
    length_h = max(int(arr.shape[1] * cfg.line_min_frac), 20)
    length_v = max(int(arr.shape[0] * cfg.line_min_frac), 20)
    lines = _runs(dark, length_h, axis=1) | _runs(dark, length_v, axis=0)
    if not lines.any():
        return img
    cleaned = np.where(lines, 255, arr).astype("uint8")
    return Image.fromarray(cleaned)


def _runs(mask, length: int, axis: int):
    """Maske der Pixel, die in einer Kette von `length` Pixeln liegen.

    Erosion und Dilatation in Laufrichtung, verdoppelnd – damit sind es
    log(length) statt length Schritte.
    """
    import numpy as np

    eroded = mask
    done, step = 1, 1
    while done < length:
        step = min(step, length - done)
        eroded = eroded & np.roll(eroded, -step, axis=axis)
        done += step
        step = max(step * 2, 1)
    grown = eroded
    done, step = 1, 1
    while done < length:
        step = min(step, length - done)
        grown = grown | np.roll(grown, step, axis=axis)
        done += step
        step = max(step * 2, 1)
    return grown & mask


def _binarize(img, Image):
    """Otsu-Schwellwert – trennt Linien/Text sauber vom Scan-Untergrund."""
    import numpy as np

    arr = np.asarray(img)
    hist = np.bincount(arr.ravel(), minlength=256).astype(float)
    total = hist.sum()
    if total == 0:
        return img
    omega = np.cumsum(hist) / total
    mu = np.cumsum(hist * np.arange(256)) / total
    mu_t = mu[-1]
    denom = omega * (1.0 - omega)
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_b = np.where(denom > 0, (mu_t * omega - mu) ** 2 / denom, 0.0)
    threshold = int(np.argmax(sigma_b))
    out = Image.fromarray(((arr > threshold) * 255).astype("uint8"))
    del arr, hist, omega, mu, sigma_b
    img.close()
    return out


def _skew_angle(img, cfg: OcrSettings) -> float:
    """Schräglage über das Projektionsprofil schätzen (±max_skew_deg).

    Bei waagerechter Schrift ist die Varianz der Zeilensummen maximal.
    Bewusst grob (0,5°-Raster) – mehr braucht ein Scan nicht, und jede
    Drehung kostet Bildqualität.
    """
    import numpy as np
    from PIL import Image as PILImage

    small = img.resize((img.width // 4 or 1, img.height // 4 or 1))
    base = np.asarray(small, dtype=np.float32)
    small.close()
    base = 255.0 - base                      # Schrift = hohe Werte
    best_angle, best_score = 0.0, -1.0
    step = 0.5
    angle = -cfg.max_skew_deg
    while angle <= cfg.max_skew_deg + 1e-9:
        if abs(angle) < 1e-9:
            arr = base
        else:
            rotated = PILImage.fromarray(base.astype("uint8")).rotate(
                angle, resample=PILImage.BILINEAR, fillcolor=0)
            arr = np.asarray(rotated, dtype=np.float32)
            rotated.close()
        profile = arr.sum(axis=1)
        score = float(np.var(profile))
        if score > best_score:
            best_angle, best_score = angle, score
        angle += step
    return best_angle if abs(best_angle) >= step else 0.0


# ----------------------------------------------------------- Erkennung
def _ocr_page(img, pno: int, cfg: OcrSettings, pytesseract, Image, Word
              ) -> "list[Word]":
    scale = 72.0 / cfg.dpi
    out: list[Word] = []
    out.extend(_pass(img, pno, cfg, cfg.min_conf, 0, scale, img.height,
                     pytesseract, Word))
    for angle in cfg.rotations:
        rotated = img.rotate(-angle, expand=True, fillcolor=255)
        try:
            out.extend(_pass(rotated, pno, cfg,
                             cfg.min_conf + cfg.rotation_conf_bonus, angle,
                             scale, img.height, pytesseract, Word))
        finally:
            rotated.close()
    return out


def _pass(img, pno: int, cfg: OcrSettings, min_conf: int, angle: int,
          scale: float, orig_height: int, pytesseract, Word) -> "list[Word]":
    """Ein Tesseract-Durchgang; rechnet die Fundstellen ins Seitenmaß zurück."""
    try:
        data = pytesseract.image_to_data(
            img, lang=cfg.lang, config=cfg.config(),
            output_type=pytesseract.Output.DICT)
    except Exception as exc:                 # pragma: no cover - Laufzeitfehler
        log.warning("OCR-Durchgang (%d°) fehlgeschlagen: %s", angle, exc)
        return []
    words: list[Word] = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < min_conf:
            continue
        x, y = float(data["left"][i]), float(data["top"][i])
        w, h = float(data["width"][i]), float(data["height"][i])
        if angle:
            x, y, w, h = _unrotate(x, y, w, h, angle, orig_height)
            # Was im gedrehten Bild erkannt wurde, aber im Original quer
            # liegt, stammt aus waagerechter Schrift – dort liest der
            # gedrehte Durchgang nur Buchstabensalat.
            if h < w * cfg.rotation_min_aspect:
                continue
        words.append(Word(text, BBox(x * scale, y * scale,
                                     (x + w) * scale, (y + h) * scale),
                          pno, conf))
    return words


def _unrotate(x: float, y: float, w: float, h: float, angle: int,
              orig_height: int) -> tuple[float, float, float, float]:
    """Rechnet eine Fundstelle aus dem gedrehten Bild aufs Original zurück.

    Gedreht wird im Uhrzeigersinn um `angle`; unterstützt werden 90 und 270
    (alles andere bleibt unverändert, dann stimmt nur die Textzuordnung).
    """
    if angle % 360 == 90:
        # Uhrzeigersinn: x_neu = H-1-y_alt, y_neu = x_alt
        return (y, orig_height - x - w, h, w)
    if angle % 360 == 270:
        return (orig_height - y - h, x, h, w)
    return (x, y, w, h)


def _dedupe_words(words: "list[Word]") -> "list[Word]":
    """Doppelfunde aus mehreren Durchgängen entfernen.

    Zwei Funde gelten als derselbe, wenn sich ihre Rechtecke deutlich
    überlappen. Behalten wird der längere Text – der gedrehte Durchgang
    liefert auf waagerechter Schrift meist nur Bruchstücke.
    """
    kept: list = []
    for word in sorted(words, key=lambda w: -len(w.text)):
        if any(_overlap(word.bbox, k.bbox) > 0.5 for k in kept
               if k.page == word.page):
            continue
        kept.append(word)
    return sorted(kept, key=lambda w: (w.page, w.bbox.y0, w.bbox.x0))


def _overlap(a: BBox, b: BBox) -> float:
    """Flächenanteil der Überlappung, bezogen auf das kleinere Rechteck."""
    dx = min(a.x1, b.x1) - max(a.x0, b.x0)
    dy = min(a.y1, b.y1) - max(a.y0, b.y0)
    if dx <= 0 or dy <= 0:
        return 0.0
    inter = dx * dy
    area_a = max((a.x1 - a.x0) * (a.y1 - a.y0), 1e-6)
    area_b = max((b.x1 - b.x0) * (b.y1 - b.y0), 1e-6)
    return inter / min(area_a, area_b)


# -------------------------------------------------------- Nachkorrektur
# Verwechslungen, die in Zeichnungstexten regelmäßig auftreten.
_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1",
                            "|": "1", "S": "5", "B": "8"})
RE_MOSTLY_DIGITS = re.compile(r"^[0-9OolI|SB.,]+$")
RE_DIA_PREFIX = re.compile(r"^[@©®0OQø∅Ø]\s?(\d)")
# Nur eindeutiger Schmutz wird abgeschnitten – Klammern bleiben, weil
# "[50]" ein theoretisch genaues Maß kennzeichnet.
RE_LEADING_JUNK = re.compile(r"^[|¦\"'`~^*_]+|[|¦\"'`~^*_]+$")


def _fix_token(text: str) -> str:
    """Typische OCR-Verwechslungen in Zeichnungstexten geraderücken.

    Bewusst konservativ: Buchstaben werden nur in Token ersetzt, die sonst
    ausschließlich aus Ziffern bestehen. „S235JR" bleibt damit unangetastet,
    „1O0" wird zu „100".
    """
    cleaned = text.strip()
    # Durchmesserzeichen wird häufig als 0/O/@ erkannt: "@20" -> "⌀20".
    # Muss VOR dem Abschneiden von Schmutz laufen.
    m = RE_DIA_PREFIX.match(cleaned)
    if m and len(cleaned) > 2:
        cleaned = "⌀" + cleaned[1:].lstrip()
    cleaned = RE_LEADING_JUNK.sub("", cleaned).strip()
    if not cleaned:
        return text.strip()
    if RE_MOSTLY_DIGITS.match(cleaned) and any(c.isdigit() for c in cleaned):
        cleaned = cleaned.translate(_DIGIT_FIX)
    return cleaned


def _fixed(word, Word):
    text = _fix_token(word.text)
    return (word if text == word.text
            else Word(text, word.bbox, word.page, word.conf))


# ======================================================================
# ocr_check
# ======================================================================
# Werkzeug: OCR-Fähigkeit prüfen und an einer Datei ausprobieren.
#
#     drawing-checker --ocr-check                  # nur Installation prüfen
#     drawing-checker --ocr-check zeichnung.pdf    # Datei durch die OCR jagen
#
# Zeigt, ob Tesseract und die Sprachpakete vorhanden sind, wie die aktuellen
# Einstellungen lauten und – mit Datei – was die Erkennung liefert. Damit
# lässt sich am Zielrechner in einem Schritt klären, ob ein Scan überhaupt
# auswertbar ist, statt es am Prüfergebnis zu raten.



from pathlib import Path


def ocr_check(pdf_path: Path | None = None) -> int:
    pass  # (im selben Modul)

    cfg = OcrSettings.from_env()
    tess = _tesseract()
    print("OCR-Einstellungen:")
    print(f"  Auflösung        {cfg.dpi} dpi")
    print(f"  Sprachen         {cfg.lang}")
    print(f"  Segmentierung    PSM {cfg.psm} (11 = verstreuter Text)")
    print(f"  Drehungen        0°" + "".join(f", {r}°" for r in cfg.rotations))
    print(f"  Mindestkonfidenz {cfg.min_conf} %")
    print(f"  Binarisierung    {'an' if cfg.binarize else 'aus'}, "
          f"Schräglagenkorrektur {'an' if cfg.deskew else 'aus'}")
    print("  (änderbar über DRAWING_CHECKER_OCR_* – siehe README)\n")

    if tess is None:
        print("Tesseract ist NICHT verfügbar – gescannte Zeichnungen können "
              "nicht gelesen werden.")
        print("Windows: https://github.com/UB-Mannheim/tesseract/wiki "
              "installieren (Sprachen deu + eng mitwählen),")
        print("danach `pip install pytesseract`. Ohne OCR meldet der Checker "
              "DOC.NO_TEXT und prüft nur, was ohne Text geht.")
        return 2
    pytesseract, _Image = tess
    print(f"Tesseract {pytesseract.get_tesseract_version()} gefunden.")
    try:
        langs = pytesseract.get_languages()
        print("Sprachpakete: " + ", ".join(sorted(langs)))
        fehlend = [l for l in cfg.lang.split("+") if l not in langs]
        if fehlend:
            print(f"ACHTUNG: Sprachpaket(e) fehlen: {', '.join(fehlend)}")
            return 1
    except Exception:
        pass

    if pdf_path is None:
        print("\nMit Dateiangabe wird die Erkennung an einer Zeichnung "
              "vorgeführt: --ocr-check zeichnung.pdf")
        return 0
    if not pdf_path.is_file():
        print(f"Datei nicht gefunden: {pdf_path}")
        return 2
    return _try_file(pdf_path)


def _try_file(pdf_path: Path) -> int:
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    with DrawingPdf(pdf_path) as pdf:
        words = pdf.words()
        print(f"\nDatei: {pdf_path.name} ({pdf.page_count} Seite(n))")
        if not pdf.ocr_used:
            print("Die Zeichnung hat einen Textlayer – OCR war nicht nötig.")
        else:
            print(pdf.ocr_note())
        print(f"Wörter gesamt: {len(words)}")
        if not words:
            print("Nichts erkannt. Mögliche Ursachen: sehr schwacher Scan, "
                  "zu geringe Auflösung, gedrehte Seite.")
            print("Versuch: DRAWING_CHECKER_OCR_DPI=600 setzen.")
            return 1
        dims = extract_dimensions(pdf, 6000)
        print(f"Maße erkannt:  {len(dims)}")
        print("\nLeseprobe (die 15 sichersten Wörter):")
        for w in sorted(words, key=lambda w: -w.conf)[:15]:
            print(f"  {w.conf:5.0f} %  {w.text}")
        schwach = [w for w in words if w.conf < 60]
        if schwach:
            print(f"\n{len(schwach)} Wörter unter 60 % Erkennungsgüte – "
                  f"davon werden Zahlen nicht als Maß übernommen.")
    return 0


# ========================================================================
# bericht
# ========================================================================
# Ausgabe: markiertes Bild, Excel-Rueckschrieb, HTML-Bericht.
#
# Drei Ausgabewege auf dieselben Ergebnisse - deshalb ein Modul.
# ======================================================================
# annotate
# ======================================================================
# Annotation des Zeichnungsbildes: Marker an den Fundstellen + Legende.
#
# Das PDF wird hochauflösend gerendert; Findings mit bbox bekommen nummerierte
# farbige Marker, alle Findings erscheinen in einer Legendenspalte rechts.



import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont



COLORS = {
    Severity.INFO: (70, 130, 180),      # Stahlblau
    Severity.WARNING: (230, 145, 0),    # Orange
    Severity.ERROR: (200, 30, 30),      # Rot
    Severity.BLOCKER: (140, 0, 140),    # Violett (K.O.)
}
LEGEND_WIDTH = 560
PAD = 14


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(pdf: DrawingPdf, result: MaterialResult, out_path: Path,
             dpi: int = RENDER_DPI) -> Path:
    """Rendert Seite 0 (und weitere Seiten mit Findings) und annotiert sie.

    Mehrseitige PDFs: Es wird je Seite mit Findings ein Bild erzeugt, Seite 0
    immer. Rückgabe ist der Pfad des Bildes zu Seite 0; weitere Seiten hängen
    "_s2", "_s3" … an.
    """
    pages = sorted({f.page for f in result.findings if f.bbox} | {0})
    scale = dpi / 72.0
    first: Path | None = None
    for page in pages:
        pix = pdf.render_page(page, dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        canvas = _draw_page(img, result, page, scale)
        path = out_path if page == 0 else out_path.with_stem(
            f"{out_path.stem}_s{page + 1}")
        canvas.save(path)
        # Bilder ausdrücklich schließen: eine A1-Seite bei 200 dpi sind rund
        # 100 MB Rohdaten; im Dauerlauf summiert sich das sonst auf.
        canvas.close()
        img.close()
        pix = None
        if page == 0:
            first = path
    assert first is not None
    return first


def _draw_page(img: Image.Image, result: MaterialResult, page: int,
               scale: float) -> Image.Image:
    findings = result.sorted_findings()
    canvas = Image.new("RGB", (img.width + LEGEND_WIDTH, img.height), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    f_marker = _font(26)
    f_head = _font(24)
    f_text = _font(17)

    # Marker auf der Zeichnung (nur Findings dieser Seite mit Position)
    for idx, finding in enumerate(findings, start=1):
        if finding.bbox is None or finding.page != page:
            continue
        color = COLORS[finding.severity]
        x0, y0, x1, y1 = (v * scale for v in finding.bbox.as_tuple())
        m = 6
        draw.rectangle([x0 - m, y0 - m, x1 + m, y1 + m], outline=color, width=4)
        r = 20
        cx, cy = x1 + m + r + 4, max(y0 - m, r + 2)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        draw.text((cx, cy), str(idx), font=f_marker, fill="white", anchor="mm")

    # Status-Stempel oben links (Gesamturteil auf einen Blick)
    if page == 0:
        worst = result.worst_severity
        if worst is None or worst <= Severity.INFO:
            stamp, color = "OK", (47, 125, 50)
        else:
            stamp = {Severity.WARNING: "PRÜFEN", Severity.ERROR: "FEHLER",
                     Severity.BLOCKER: "K.O."}[worst]
            color = COLORS[worst]
        f_stamp = _font(34)
        text = f" {stamp} · {result.material} "
        tw = draw.textlength(text, font=f_stamp)
        draw.rectangle([16, 16, 16 + tw + 12, 70], outline=color, width=5)
        draw.text((22, 26), text, font=f_stamp, fill=color)

    # Legende rechts
    lx = img.width + PAD
    y = PAD
    draw.rectangle([img.width, 0, canvas.width - 1, canvas.height - 1],
                   outline=(180, 180, 180), width=1)
    draw.text((lx, y), f"Prüfergebnis  {result.material}", font=f_head, fill="black")
    y += 40
    if not findings:
        draw.text((lx, y), "Keine Beanstandungen.", font=f_text, fill=(0, 120, 0))
    for idx, finding in enumerate(findings, start=1):
        color = COLORS[finding.severity]
        marker = f"{idx}." if finding.bbox is not None else "–"
        tag = SEVERITY_LABEL[finding.severity]
        lines = _wrap(f"{marker} [{tag}] {finding.code}: {finding.text}",
                      f_text, LEGEND_WIDTH - 2 * PAD, draw)
        for line in lines:
            if y > canvas.height - 30:
                draw.text((lx, y), "… (weitere siehe Excel)", font=f_text,
                          fill="black")
                return canvas
            draw.text((lx, y), line, font=f_text, fill=color)
            y += 22
        y += 6
    if result.step_summary:
        y += 10
        for line in _wrap("Geometrie: " + result.step_summary, f_text,
                          LEGEND_WIDTH - 2 * PAD, draw):
            if y > canvas.height - 30:
                break
            draw.text((lx, y), line, font=f_text, fill=(60, 60, 60))
            y += 22
    return canvas


def _wrap(text: str, font, width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        probe = (cur + " " + w).strip()
        if draw.textlength(probe, font=font) <= width:
            cur = probe
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ======================================================================
# excel_writer
# ======================================================================
# Excel-Rückschrieb: Ergebnis-Spalten in eine Kopie der Input-Datei.
#
# Das Original bleibt unangetastet; geschrieben wird `<name>_geprüft.xlsx`.
# Nach jeder Materialnummer wird gespeichert, damit auch bei Abbruch ein
# verwertbarer Stand existiert.



import logging
import shutil
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import column_index_from_string, get_column_letter



RESULT_HEADERS = [
    "Prüfstatus", "Geprüft am", "Schwerste Bewertung", "Anzahl Findings",
    "Festgestellte Mängel", "Geometrieabgleich",
    "Letzte Zeichnungsänderung", "Fertigungsverfahren",
    "Screenshot", "Prüfdauer [s]",
]
WIDE_HEADERS = {"Festgestellte Mängel", "Geometrieabgleich",
                "Fertigungsverfahren"}
FILL = {
    "ok": PatternFill("solid", fgColor="C6EFCE"),
    "warn": PatternFill("solid", fgColor="FFEB9C"),
    "error": PatternFill("solid", fgColor="FFC7CE"),
    "failed": PatternFill("solid", fgColor="D9D9D9"),
}
STATUS_TEXT = {
    JobStatus.OK: "OK",
    JobStatus.FINDINGS: "Findings",
    JobStatus.FAILED: "Prüfung fehlgeschlagen",
    JobStatus.SKIPPED: "Übersprungen",
}


# Wie viele Findings in die Zelle geschrieben werden. Eine Zeichnung mit
# 30 Beanstandungen liest niemand in einer Excel-Zelle; die vollständige
# Liste steht im Bild und im HTML-Bericht. Der Erläuterungstext (detail)
# kommt nur bei den schwersten Punkten mit, sonst platzt die Zelle.
MAX_FINDINGS_IN_CELL = 12
MAX_DETAILS_IN_CELL = 3


def _findings_text(result: MaterialResult) -> str:
    """Mängelspalte: die schwersten zuerst, gedeckelt und lesbar."""
    findings = result.sorted_findings()
    zeilen = []
    for i, f in enumerate(findings[:MAX_FINDINGS_IN_CELL]):
        zeile = f"[{SEVERITY_LABEL[f.severity]}] {f.code}: {f.text}"
        if f.detail and i < MAX_DETAILS_IN_CELL:
            zeile += f" – {f.detail}"
        zeilen.append(zeile)
    rest = len(findings) - MAX_FINDINGS_IN_CELL
    if rest > 0:
        zeilen.append(f"… und {rest} weitere Punkte – vollständig im "
                      f"annotierten Bild und im HTML-Bericht.")
    return "\n".join(zeilen)


class ResultWorkbook:
    def __init__(self, config: RunConfig):
        self.config = config
        self.path = config.excel_path.with_stem(config.excel_path.stem + "_geprüft")
        if not self.path.exists():
            shutil.copy2(config.excel_path, self.path)
        self.wb = openpyxl.load_workbook(self.path)
        if config.sheet_name not in self.wb.sheetnames:
            raise ValueError(f"Blatt {config.sheet_name!r} nicht in {self.path.name}")
        self.ws = self.wb[config.sheet_name]
        self.cols = self._ensure_headers()
        self.first_col = self.cols[RESULT_HEADERS[0]]

    def _ensure_headers(self) -> dict[str, int]:
        """Findet oder erzeugt die Ergebnis-Spalten rechts der Tabelle.

        Fehlende Spalten (z. B. nach einem Tool-Update mit neuen
        Dokumentationsspalten) werden rechts angefügt.
        """
        header_row = self.config.header_row
        existing = {
            (c.value or ""): c.column
            for c in self.ws[header_row]
            if isinstance(c.value, str)
        }
        cols: dict[str, int] = {}
        next_col = (self.ws.max_column or 0) + 1
        for name in RESULT_HEADERS:
            if name in existing:
                cols[name] = existing[name]
                continue
            cell = self.ws.cell(row=header_row, column=next_col, value=name)
            cell.font = Font(bold=True)
            self.ws.column_dimensions[get_column_letter(next_col)].width = (
                46 if name in WIDE_HEADERS else 18)
            cols[name] = next_col
            next_col += 1
        return cols

    def write_result(self, result: MaterialResult) -> None:
        r = result.row
        worst = result.worst_severity
        findings_txt = _findings_text(result)
        status_txt = STATUS_TEXT.get(result.status, result.status.value)
        if result.status == JobStatus.FAILED and result.error:
            status_txt += f": {result.error}"

        values = {
            "Prüfstatus": status_txt,
            "Geprüft am": result.checked_at,
            "Schwerste Bewertung":
                SEVERITY_LABEL[worst] if worst is not None else "",
            "Anzahl Findings": len(result.findings),
            "Festgestellte Mängel": findings_txt,
            "Geometrieabgleich": result.step_summary,
            "Letzte Zeichnungsänderung": result.drawing_rev_date,
            "Fertigungsverfahren": ", ".join(result.processes),
            "Screenshot": "",  # Hyperlink, s. u.
            "Prüfdauer [s]": round(result.duration_s, 1),
        }
        for name, v in values.items():
            cell = self.ws.cell(row=r, column=self.cols[name], value=v)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

        if result.screenshot:
            cell = self.ws.cell(row=r, column=self.cols["Screenshot"])
            cell.value = result.screenshot.name
            cell.hyperlink = result.screenshot.resolve().as_uri()
            cell.font = Font(color="0563C1", underline="single")

        status_cell = self.ws.cell(row=r, column=self.cols["Prüfstatus"])
        if result.status == JobStatus.FAILED:
            status_cell.fill = FILL["failed"]
        elif worst is None or worst <= Severity.INFO:
            status_cell.fill = FILL["ok"]
        elif worst == Severity.WARNING:
            status_cell.fill = FILL["warn"]
        else:
            status_cell.fill = FILL["error"]

    def finalize(self, results: list[MaterialResult],
                 offen: list[tuple[int, str]] | None = None) -> None:
        """Abschluss eines Laufs: Autofilter, Fixierung, Zusammenfassung."""
        header_row = self.config.header_row
        last_col = get_column_letter(max(self.cols.values()))
        last_row = max((r.row for r in results), default=header_row)
        self.ws.auto_filter.ref = f"A{header_row}:{last_col}{last_row}"
        self.ws.freeze_panes = self.ws.cell(row=header_row + 1, column=1)
        self._write_summary(results, offen or [])

    def _write_summary(self, results: list[MaterialResult],
                       offen: list[tuple[int, str]]) -> None:
        from collections import Counter

        name = "Prüfzusammenfassung"
        if name in self.wb.sheetnames:
            del self.wb[name]
        ws = self.wb.create_sheet(name)
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 70

        n = {s: sum(1 for r in results if r.status == s) for s in JobStatus}
        rows = [
            ("Zeichnungsprüfung – Zusammenfassung", "", "", ""),
            ("Geprüft am", results[-1].checked_at if results else "", "", ""),
            ("Materialnummern gesamt", len(results), "", ""),
            ("OK", n[JobStatus.OK], "", ""),
            ("Mit Findings", n[JobStatus.FINDINGS], "", ""),
            ("Fehlgeschlagen", n[JobStatus.FAILED], "", ""),
            ("Noch offen", len(offen),
             "", (f"Lauf angehalten bei Zeile {offen[0][0]} "
                  f"(Materialnummer {offen[0][1]}). Beim nächsten Start "
                  f"dort fortsetzen." if offen else "")),
            ("", "", "", ""),
            ("Regel", "Bewertung", "Anzahl", "Beispiel"),
        ]
        counter: Counter[tuple[str, Severity]] = Counter()
        example: dict[str, str] = {}
        for r in results:
            for f in r.findings:
                counter[(f.code, f.severity)] += 1
                example.setdefault(f.code, f.text)
        for (code, sev), count in counter.most_common():
            rows.append((code, SEVERITY_LABEL[sev], count,
                         example.get(code, "")))
        for row in rows:
            ws.append(list(row))
        for cell in (ws["A1"], *ws[8]):
            cell.font = Font(bold=True)

    def save(self) -> None:
        try:
            self.wb.save(self.path)
        except PermissionError:
            # Datei ist vermutlich in Excel geöffnet – Ausweichdatei schreiben.
            alt = self.path.with_stem(self.path.stem + "_neu")
            log.warning("Ergebnisdatei gesperrt, schreibe nach %s", alt.name)
            self.wb.save(alt)


def read_materials(config: RunConfig) -> list[tuple[int, str]]:
    """Liest (Zeile, Materialnummer) aus der gewählten Spalte der Input-Excel."""
    wb = openpyxl.load_workbook(config.excel_path, read_only=True, data_only=True)
    try:
        ws = wb[config.sheet_name]
        col = column_index_from_string(config.material_column)
        out: list[tuple[int, str]] = []
        for row in ws.iter_rows(min_row=config.header_row + 1,
                                min_col=col, max_col=col):
            cell = row[0]
            value = cell.value
            if value is None:
                continue
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            text = str(value).strip()
            if text:
                out.append((cell.row, text))
        return out
    finally:
        wb.close()


# ======================================================================
# html_report
# ======================================================================
# HTML-Übersichtsbericht je Prüflauf.
#
# Eine einzelne, selbsterklärende HTML-Datei im Laufordner: Kennzahlen,
# Mängel-Ranking und die komplette Ergebnistabelle mit Links auf die
# annotierten Zeichnungsbilder (relative Pfade – der Ordner ist als Ganzes
# teil-/archivierbar).



import html
import time
from collections import Counter
from pathlib import Path


REPORT_NAME = "bericht.html"

_SEV_COLOR = {
    Severity.INFO: "#4682b4",
    Severity.WARNING: "#e69100",
    Severity.ERROR: "#c81e1e",
    Severity.BLOCKER: "#8c008c",
}
_STATUS_COLOR = {
    JobStatus.OK: "#2f7d32",
    JobStatus.FINDINGS: "#e69100",
    JobStatus.FAILED: "#c81e1e",
    JobStatus.SKIPPED: "#888888",
}
_STATUS_TEXT = {
    JobStatus.OK: "OK",
    JobStatus.FINDINGS: "Findings",
    JobStatus.FAILED: "Fehlgeschlagen",
    JobStatus.SKIPPED: "Übersprungen",
}

_CSS = """
.hilfe{background:#f7f9fc;border:1px solid #dde3ec;border-radius:6px;
  padding:10px 14px;margin:6px 0 18px}
.hilfe p{margin:6px 0}

body{font-family:'Segoe UI',Arial,sans-serif;margin:0;background:#f4f5f7;color:#1c1c1c}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#666;margin-bottom:20px;font-size:13px}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.tile{background:#fff;border-radius:8px;padding:14px 20px;min-width:120px;
      box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tile b{display:block;font-size:26px;margin-top:2px}
table{border-collapse:collapse;width:100%;background:#fff;border-radius:8px;
      box-shadow:0 1px 3px rgba(0,0,0,.08);font-size:13px;margin-bottom:24px}
th{background:#2b3a4a;color:#fff;text-align:left;padding:8px 10px;position:sticky;top:0}
td{padding:7px 10px;border-top:1px solid #eceff1;vertical-align:top}
tr:hover td{background:#f6f9fc}
.badge{display:inline-block;color:#fff;border-radius:10px;padding:1px 9px;
       font-size:12px;white-space:nowrap}
.code{font-family:Consolas,monospace;font-size:12px}
a{color:#0563c1;text-decoration:none} a:hover{text-decoration:underline}
h2{font-size:16px;margin:24px 0 8px}
.small{color:#666;font-size:12px}
"""


def write_html_report(config: RunConfig, results: list[MaterialResult],
                      run_dir: Path, profile_name: str,
                      duration_s: float) -> Path:
    total = len(results)
    n_ok = sum(1 for r in results if r.status == JobStatus.OK)
    n_find = sum(1 for r in results if r.status == JobStatus.FINDINGS)
    n_fail = sum(1 for r in results if r.status == JobStatus.FAILED)
    counter: Counter[tuple[str, Severity]] = Counter()
    example: dict[str, str] = {}
    for r in results:
        for f in r.findings:
            counter[(f.code, f.severity)] += 1
            example.setdefault(f.code, f.text)

    def esc(s) -> str:
        return html.escape(str(s))

    rows = []
    for r in sorted(results, key=lambda x: (-int(x.worst_severity or -1), x.row)):
        codes = sorted({f.code for f in r.findings})
        shot = ""
        if r.screenshot:
            shot = (f'<a href="{esc(r.screenshot.name)}" target="_blank">'
                    f'{esc(r.screenshot.name)}</a>')
        worst = r.worst_severity
        worst_badge = ("" if worst is None else
                       f'<span class="badge" style="background:{_SEV_COLOR[worst]}">'
                       f'{SEVERITY_LABEL[worst]}</span>')
        status_badge = (f'<span class="badge" style="background:'
                        f'{_STATUS_COLOR[r.status]}">'
                        f'{_STATUS_TEXT.get(r.status, r.status.value)}</span>')
        rows.append(
            "<tr>"
            f"<td>{esc(r.material)}</td><td>{status_badge}</td>"
            f"<td>{worst_badge}</td><td>{len(r.findings)}</td>"
            f'<td class="code">{esc(", ".join(codes))}</td>'
            f"<td>{esc(', '.join(r.processes))}</td>"
            f"<td>{esc(r.drawing_rev_date)}</td>"
            f"<td>{shot}</td><td>{esc(r.checked_at)}</td>"
            "</tr>")

    top = []
    for (code, sev), n in counter.most_common(15):
        top.append(
            "<tr>"
            f'<td class="code">{esc(code)}</td>'
            f'<td><span class="badge" style="background:{_SEV_COLOR[sev]}">'
            f'{SEVERITY_LABEL[sev]}</span></td>'
            f"<td>{n}</td><td>{esc(example.get(code, ''))}</td></tr>")

    doc = f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<title>Prüfbericht {esc(config.excel_path.stem)}</title>
<style>{_CSS}</style></head><body><div class="wrap">
<h1>Zeichnungsprüfung – Bericht</h1>
<div class="sub">{esc(config.excel_path.name)} · Blatt {esc(config.sheet_name)}
 · Spalte {esc(config.material_column)} · Profil {esc(profile_name)}
 · erstellt {time.strftime("%d.%m.%Y %H:%M")}
 · Dauer {duration_s / 60:.1f} min</div>
<div class="tiles">
<div class="tile">Geprüft<b>{total}</b></div>
<div class="tile">OK<b style="color:#2f7d32">{n_ok}</b></div>
<div class="tile">Mit Findings<b style="color:#e69100">{n_find}</b></div>
<div class="tile">Fehlgeschlagen<b style="color:#c81e1e">{n_fail}</b></div>
</div>
<h2>So lesen Sie diesen Bericht</h2>
<div class="hilfe">
<p><b>Reihenfolge:</b> Arbeiten Sie die Liste „Häufigste Mängel“ von oben ab –
 dort steht, was am meisten Zeichnungen betrifft. Ein Punkt, der 40-mal
 auftaucht, ist meist ein Vorlagen- oder Gewohnheitsfehler und mit einer
 Entscheidung für alle erledigt.</p>
<p><b>Die vier Bewertungen:</b>
 <span class="badge" style="background:{_SEV_COLOR[Severity.BLOCKER]}">K.O.</span>
 Paket unbrauchbar oder Geometrie passt nicht – nicht anfragen.
 <span class="badge" style="background:{_SEV_COLOR[Severity.ERROR]}">Fehler</span>
 klare Beanstandung, Zeichnung nachbessern.
 <span class="badge" style="background:{_SEV_COLOR[Severity.WARNING]}">Prüfen</span>
 vom Programm nicht sicher entscheidbar – kurz ansehen.
 <span class="badge" style="background:{_SEV_COLOR[Severity.INFO]}">Hinweis</span>
 nur zur Information.</p>
<p><b>Wo steht was:</b> Jede Zeile der Ergebnis-Excel enthält Uhrzeit der
 Prüfung, die gefundenen Mängel im Klartext, das letzte Änderungsdatum der
 Zeichnung, die erkannten Fertigungsverfahren und den Verweis auf das
 annotierte Bild. Im Bild sind die Fundstellen nummeriert und rechts in
 einer Legende erklärt.</p>
<p><b>Wenn etwas falsch gemeldet wirkt:</b> Das Bild zeigt, worauf sich die
 Meldung bezieht. Regeln lassen sich einzeln abschalten oder anders
 bewerten (Datei <code>regeln/profiles.yaml</code>) – bitte an die
 Systembetreuung melden, statt den Bericht zu ignorieren.</p>
</div>

<h2>Häufigste Mängel</h2>
<table><tr><th>Regel</th><th>Bewertung</th><th>Anzahl</th><th>Beispiel</th></tr>
{''.join(top) or '<tr><td colspan="4">Keine Findings.</td></tr>'}</table>
<h2>Alle Materialnummern</h2>
<table><tr><th>Materialnummer</th><th>Status</th><th>Schwerste</th><th>Anzahl</th>
<th>Regeln</th><th>Fertigungsverfahren</th><th>Letzte Änderung</th>
<th>Zeichnung</th><th>Geprüft am</th></tr>
{''.join(rows)}</table>
<div class="small">Details je Materialnummer: Ergebnis-Excel
 ({esc(config.excel_path.stem)}_geprüft.xlsx) und annotierte Zeichnungsbilder
 in diesem Ordner. Erzeugt vom Drawing Checker.</div>
</div></body></html>"""

    path = run_dir / REPORT_NAME
    path.write_text(doc, encoding="utf-8")
    return path


# ========================================================================
# sap_sitzung
# ========================================================================
# SAP-Sitzung: verbinden, Fenster huetten, Popups, Download, Diagnose.
#
# Alles, was mit der laufenden SAP GUI zu tun hat - inklusive der Schranke
# von fuenf Fenstern und dem Waechter, der SAP nach einem Absturz wieder
# hochbringt.
# ======================================================================
# adapter
# ======================================================================
# Adapter-Interface zur SAP-Beschaffung der YMATDOCS-Pakete.
#
# Der Orchestrator kennt nur dieses Interface. Implementierungen:
#   * SapGuiAdapter (sap/session.py): echtes SAP GUI Scripting (nur Windows).
#   * MockSapAdapter (sap/mock.py): liefert ZIPs aus einem Ordner – für
#     Entwicklung/Tests ohne SAP und für die Mockdaten-Läufe.



import abc
from pathlib import Path


class SapUnavailable(Exception):
    """SAP-Session tot/abgestürzt: Watchdog-Fall, Job wird neu eingereiht."""


class MaterialNotFound(Exception):
    """YMATDOCS kennt die Materialnummer nicht bzw. liefert kein Paket."""


class SapAdapter(abc.ABC):
    @abc.abstractmethod
    def ensure_ready(self) -> None:
        """Stellt eine nutzbare Session her (verbinden, ggf. neu starten)."""

    @abc.abstractmethod
    def fetch_package(self, material: str, target_dir: Path) -> Path:
        """Führt YMATDOCS für die Materialnummer aus und lädt das ZIP herunter.

        Rückgabe: Pfad des heruntergeladenen ZIP.
        Wirft MaterialNotFound (fachlich) oder SapUnavailable (technisch).
        """

    @abc.abstractmethod
    def close(self) -> None:
        """Ressourcen freigeben (Session NICHT zwingend beenden)."""


# ======================================================================
# session
# ======================================================================
# SAP GUI Scripting: Verbindung zu P11 und Ausführung von YMATDOCS.
#
# Nur unter Windows lauffähig (COM). Voraussetzungen:
#   * SAP GUI installiert, Scripting client- und serverseitig freigeschaltet
#     (sapgui/user_scripting = TRUE – ist laut Basis bereits aktiv).
#   * pywin32 installiert (pip install pywin32).
#
# Der konkrete Transaktionsablauf steckt in ymatdocs.py und wird aus dem
# .vbs-Mitschnitt der Transaktion portiert (Element-IDs 1:1 übernehmen).



import logging
import time
from pathlib import Path



# SAP erlaubt je Anmeldung nur eine begrenzte Zahl von Modi (Fenstern) –
# üblich sind 6. Der Checker bleibt bewusst darunter, damit der Anwender
# parallel weiterarbeiten kann und kein Fenster verloren geht. Wird die
# Grenze erreicht, oeffnet der Checker KEIN weiteres, sondern meldet es.
DEFAULT_MAX_SESSIONS = 5


class SapGuiAdapter(SapAdapter):
    def __init__(self, connection_name: str = "P11",
                 saplogon_path: str | None = None,
                 flow_path: Path | None = None,
                 diagnose_dir: Path | None = None,
                 watch_dirs: list[Path] | None = None,
                 max_sessions: int = DEFAULT_MAX_SESSIONS):
        self.connection_name = connection_name
        self.watchdog = SapWatchdog(connection_name, saplogon_path)
        self.session = None
        self.flow_path = flow_path
        self.diagnose_dir = diagnose_dir
        self.watch_dirs = watch_dirs
        self.max_sessions = max_sessions
        # Vom Checker selbst geöffnete Session: die wird am Ende wieder
        # geschlossen, damit über mehrere Läufe keine Fenster auflaufen.
        self._selbst_geoeffnet = False
        # Wird vom Orchestrator gesetzt: liefert True, wenn abgebrochen
        # werden soll (Knopf in der GUI).
        self.stop_event = None

    # ------------------------------------------------------------- Anbindung
    def ensure_ready(self) -> None:
        if self.session is not None and self._session_alive():
            return
        self.session = self._attach_or_open()

    def _session_alive(self) -> bool:
        try:
            _ = self.session.Info.SystemName  # wirft bei toter Session
            return True
        except Exception:
            return False

    def _attach_or_open(self):
        """Bestehende P11-Session nutzen, sonst Verbindung öffnen.

        Bei totem SAP GUI übernimmt der Watchdog Neustart + Login.
        """
        try:
            import win32com.client
        except ImportError as exc:  # pragma: no cover - nur auf Nicht-Windows
            raise SapUnavailable(
                "pywin32 fehlt – SAP-Anbindung nur unter Windows möglich"
            ) from exc

        try:
            sapgui = win32com.client.GetObject("SAPGUI")
            app = sapgui.GetScriptingEngine
        except Exception:
            log.info("SAP GUI läuft nicht – Watchdog startet es")
            app = self.watchdog.start_sapgui()

        # Vorhandene Session zum Zielsystem wiederverwenden – das ist der
        # Normalfall und öffnet gar kein neues Fenster.
        vorhanden = zaehle_sessions(app)
        for ci in range(app.Children.Count):
            conn = app.Children(ci)
            for si in range(conn.Children.Count):
                sess = conn.Children(si)
                try:
                    if sess.Info.SystemName.upper() in self.connection_name.upper():
                        log.info("Nutze bestehende SAP-Session (%s), %d Fenster "
                                 "offen", sess.Info.SystemName, vorhanden)
                        return sess
                except Exception:
                    continue

        self._pruefe_grenze(app)

        log.info("Öffne Verbindung %r (bisher %d Fenster offen)",
                 self.connection_name, vorhanden)
        try:
            conn = app.OpenConnection(self.connection_name, True)
        except Exception as exc:
            raise SapUnavailable(
                f"Verbindung {self.connection_name!r} nicht möglich: {exc}"
            ) from exc
        session = conn.Children(0)
        self._selbst_geoeffnet = True
        self.watchdog.login_if_needed(session)
        return session

    # ------------------------------------------------------------ Beschaffung
    def fetch_package(self, material: str, target_dir: Path) -> Path:
        pass  # (Import entfaellt - alles ein Modul)

        self.ensure_ready()
        try:
            return self._run(material, target_dir)
        except SapUnavailable:
            # Einmaliger Selbstheilungsversuch: neu verbinden und wiederholen.
            log.warning("Session verloren bei %s – Neuverbindung", material)
            self._write_diagnosis(material)
            self.session = None
            self.watchdog.recover()
            self.ensure_ready()
            return self._run(material, target_dir)

    def _run(self, material: str, target_dir: Path) -> Path:
        pass  # (Import entfaellt - alles ein Modul)

        return run_ymatdocs(self.session, material, target_dir,
                            flow_path=self.flow_path,
                            watch_dirs=self.watch_dirs,
                            abbruch=self._abbruch)

    def _abbruch(self) -> bool:
        """True, sobald der Anwender in der GUI auf Abbrechen gedrückt hat."""
        ev = self.stop_event
        return bool(ev is not None and ev.is_set())

    def _write_diagnosis(self, material: str) -> None:
        """Bei technischen Fehlern Elementbaum und Bildschirmfoto sichern."""
        if self.diagnose_dir is None or self.session is None:
            return
        try:
            pass  # (im selben Modul)

            diagnose_failure(self.session, material, self.diagnose_dir)
        except Exception:
            log.debug("Diagnose konnte nicht geschrieben werden",
                      exc_info=True)

    def _pruefe_grenze(self, app) -> None:
        """Kein weiteres SAP-Fenster öffnen, wenn die Grenze erreicht ist.

        SAP erlaubt je Anmeldung nur eine begrenzte Zahl von Modi. Wer die
        aufbraucht, blockiert sich selbst und den Anwender. Lieber sauber
        melden als das letzte Fenster verbrauchen.
        """
        offen = zaehle_sessions(app)
        if offen >= self.max_sessions:
            raise SapUnavailable(
                f"In SAP sind bereits {offen} Fenster offen (Grenze "
                f"{self.max_sessions}), aber keines für {self.connection_name}. "
                f"Der Checker öffnet kein weiteres. Bitte ein SAP-Fenster "
                f"schließen oder sich in {self.connection_name} anmelden und "
                f"den Lauf fortsetzen.")

    def blockwechsel(self) -> None:
        """Nach jedem Block: SAP auf einen sauberen Stand bringen.

        Offene Dialoge wegräumen, zurück auf das Selektionsbild und die
        Zahl der offenen Fenster prüfen. So startet jeder Block unter
        denselben Bedingungen, statt sich über Stunden zu verzetteln.
        """
        if self.session is None:
            return
        try:
            pass  # (im selben Modul)

            geschlossen = handle_popups(self.session)
            if geschlossen:
                log.info("Blockwechsel: %d Dialog(e) geschlossen", geschlossen)
        except Exception:
            log.debug("Blockwechsel: Dialoge nicht prüfbar", exc_info=True)
        try:
            # Zurück auf das Einstiegsbild der Transaktion.
            self.session.FindById("wnd[0]/tbar[0]/okcd").Text = "/n"
            self.session.FindById("wnd[0]").SendVKey(0)
        except Exception:
            log.debug("Blockwechsel: Rücksprung nicht möglich", exc_info=True)
        try:
            offen = zaehle_sessions(self.session.Parent.Parent)
            if offen > self.max_sessions:
                log.warning("In SAP sind %d Fenster offen (Grenze %d) - "
                            "bitte nicht benötigte schließen",
                            offen, self.max_sessions)
        except Exception:
            log.debug("Blockwechsel: Fensterzahl unbekannt", exc_info=True)

    def close(self) -> None:
        """Aufräumen. Eine selbst geöffnete Session wird auch geschlossen.

        Sonst bleibt nach jedem Lauf ein SAP-Fenster stehen, und nach fünf
        Läufen ist die Grenze erreicht.
        """
        if self._selbst_geoeffnet and self.session is not None:
            try:
                verbindung = self.session.Parent
                verbindung.CloseSession(self.session.ID)
                log.info("Selbst geöffnete SAP-Session geschlossen")
            except Exception:
                log.debug("Session ließ sich nicht schließen", exc_info=True)
        self._selbst_geoeffnet = False
        self.session = None


def zaehle_sessions(app) -> int:
    """Wie viele SAP-Fenster (Modi) sind insgesamt offen?"""
    gesamt = 0
    try:
        for ci in range(app.Children.Count):
            gesamt += app.Children(ci).Children.Count
    except Exception:
        log.debug("Session-Zahl nicht ermittelbar", exc_info=True)
    return gesamt


def wait_ready(session, timeout: float = 60.0) -> None:
    """Wartet, bis SAP nicht mehr busy ist; SapUnavailable bei Timeout/COM-Tod."""
    deadline = time.time() + timeout
    while True:
        try:
            if not session.Busy:
                return
        except Exception as exc:
            raise SapUnavailable(f"SAP-Session antwortet nicht: {exc}") from exc
        if time.time() > deadline:
            raise SapUnavailable(f"SAP bleibt busy (> {timeout:.0f}s)")
        time.sleep(0.25)


def find_element(session, element_id: str):
    """FindById ohne Exception; None, wenn das Element nicht existiert."""
    try:
        return session.FindById(element_id, False)
    except Exception:
        return None


# ======================================================================
# popups
# ======================================================================
# Behandlung unerwarteter SAP-Dialoge.
#
# In einem Dauerlauf tauchen Popups auf, die im Mitschnitt nicht vorkamen:
# Mehrfachanmeldung, „Datei existiert bereits", Informationsmeldungen,
# Druckdialoge. Ohne Behandlung blockieren sie den gesamten Lauf.
#
# Strategie: bekannte Dialoge anhand ihres Titels/Textes automatisch
# beantworten, unbekannte protokollieren und mit Enter bzw. Abbrechen
# schließen – der Lauf darf nie an einem Dialog hängen bleiben.



import logging
import re


# Dialoge, die bestätigt werden dürfen (Enter / „Ja" / „Ersetzen").
CONFIRM_PATTERNS = [
    re.compile(r"ersetzen|überschreiben|replace|overwrite", re.IGNORECASE),
    re.compile(r"wirklich|fortfahren|continue|proceed", re.IGNORECASE),
    re.compile(r"informationen?|hinweis|information", re.IGNORECASE),
]
# Dialoge, die abgebrochen werden müssen (nicht bestätigen!).
CANCEL_PATTERNS = [
    re.compile(r"drucken|print", re.IGNORECASE),
    re.compile(r"löschen|delete|verwerfen|discard", re.IGNORECASE),
]
# Mehrfachanmeldung: bestehende Sitzung fortsetzen (Option 1).
MULTI_LOGON = re.compile(r"mehrfachanmeldung|multiple\s+logon", re.IGNORECASE)

MAX_POPUP_ROUNDS = 5


def handle_popups(session, *, on_popup=None, skip_windows=()) -> int:
    """Räumt offene Modaldialoge ab. Liefert die Anzahl behandelter Popups.

    skip_windows: Fenster, die der Ablauf selbst bedient (z. B. der
    Datei-Dialog des Downloads). Sie dürfen NICHT weggeklickt werden –
    sonst schließt der Automat den Speichern-Dialog, bevor Pfad und
    Dateiname eingetragen sind.
    """
    handled = 0
    skip = set(skip_windows)
    for _round in range(MAX_POPUP_ROUNDS):
        window = _topmost_popup(session, skip)
        if window is None:
            break
        title, text = _popup_text(session, window)
        info = f"{title} {text}".strip()
        if on_popup:
            on_popup(window, info)

        if MULTI_LOGON.search(info):
            _select_multi_logon(session, window)
        elif any(p.search(info) for p in CANCEL_PATTERNS):
            log.warning("Dialog abgebrochen: %s", info[:120])
            _press_button(session, window, cancel=True)
        elif any(p.search(info) for p in CONFIRM_PATTERNS):
            log.info("Dialog bestätigt: %s", info[:120])
            _press_button(session, window, cancel=False)
        else:
            log.warning("Unbekannter Dialog, wird bestätigt: %s", info[:160])
            _press_button(session, window, cancel=False)
        handled += 1
    return handled


def _topmost_popup(session, skip: set[str] | None = None):
    for window in ("wnd[2]", "wnd[1]"):
        if skip and window in skip:
            continue
        try:
            element = session.FindById(window, False)
        except Exception:
            element = None
        if element is not None:
            return window
    return None


def _popup_text(session, window: str) -> tuple[str, str]:
    title = _safe_attr(session, window, "Text")
    parts: list[str] = []
    for candidate in (f"{window}/usr/txtMESSTXT1", f"{window}/usr/txtMESSTXT2",
                      f"{window}/usr/txtSPOP-TEXTLINE1",
                      f"{window}/usr/txtSPOP-TEXTLINE2"):
        value = _safe_attr(session, candidate, "Text")
        if value:
            parts.append(value)
    return title, " ".join(parts)


def _safe_attr(session, element_id: str, attribute: str) -> str:
    try:
        element = session.FindById(element_id, False)
        if element is None:
            return ""
        return str(getattr(element, attribute, "") or "")
    except Exception:
        return ""


def _select_multi_logon(session, window: str) -> None:
    """Bestehende Anmeldung fortsetzen statt neue Sitzung zu öffnen."""
    for option in (f"{window}/usr/radMULTI_LOGON_OPT2",
                   f"{window}/usr/radMULTI_LOGON_OPT1"):
        try:
            element = session.FindById(option, False)
            if element is not None:
                element.Select()
                break
        except Exception:
            continue
    _press_button(session, window, cancel=False)


def _press_button(session, window: str, *, cancel: bool) -> None:
    """Dialog schließen: erst über die Symbolleiste, sonst per Tastendruck."""
    button = "btn[12]" if cancel else "btn[0]"
    for element_id in (f"{window}/tbar[0]/{button}",
                       f"{window}/usr/btnSPOP-OPTION{'2' if cancel else '1'}"):
        try:
            element = session.FindById(element_id, False)
            if element is not None:
                element.Press()
                return
        except Exception:
            continue
    try:
        session.FindById(window).SendVKey(12 if cancel else 0)
    except Exception:
        log.error("Dialog %s ließ sich nicht schließen", window)


# ======================================================================
# download
# ======================================================================
# Erkennung der heruntergeladenen ZIP-Datei.
#
# Wohin YMATDOCS das Paket ablegt, ist bis zum Durchstich unbekannt. Deshalb
# werden mehrere Wege gleichzeitig überwacht:
#
#   1. der erwartete Zielpfad (aus dem Datei-Dialog),
#   2. der Zielordner insgesamt (falls SAP den Dateinamen selbst vergibt),
#   3. zusätzliche Ordner (Windows-Download, SAP-Arbeitsverzeichnis, Temp).
#
# Erkannt wird jede Datei, die nach dem Start des Downloads neu entstanden
# ist; gewartet wird, bis ihre Größe stabil ist (Schreibvorgang beendet).



import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIMEOUT_S = 180.0
STABLE_SECONDS = 1.5
POLL_INTERVAL_S = 0.4
# Endungen, die als Ergebnis in Frage kommen (SAP legt teils .zip.tmp an).
CANDIDATE_SUFFIXES = (".zip", ".sar", ".rar", ".7z")
TEMP_SUFFIXES = (".tmp", ".part", ".crdownload", ".filepart")


def default_watch_dirs() -> list[Path]:
    """Ordner, in denen ein Download landen könnte."""
    dirs: list[Path] = []
    home = Path.home()
    for candidate in (home / "Downloads", home / "Documents" / "SAP",
                      home / "SAP" / "SAP GUI", Path(os.environ.get("TEMP", ""))
                      if os.environ.get("TEMP") else None):
        if candidate and candidate.is_dir():
            dirs.append(candidate)
    return dirs


@dataclass
class DownloadWatcher:
    """Überwacht mehrere Ordner auf eine neu entstandene Archivdatei."""

    expected: Path | None = None
    watch_dirs: list[Path] = field(default_factory=list)
    timeout_s: float = DEFAULT_TIMEOUT_S
    _before: dict[Path, set[Path]] = field(default_factory=dict, init=False)
    _started: float = field(default=0.0, init=False)

    def start(self) -> None:
        """Ausgangszustand festhalten (vor dem Auslösen des Downloads)."""
        self._started = time.time()
        self._before = {}
        if self.expected is not None:
            # Eine alte Datei gleichen Namens darf nicht als Treffer gelten.
            try:
                self.expected.unlink(missing_ok=True)
            except OSError:
                log.warning("Alte Datei %s ließ sich nicht entfernen",
                            self.expected)
        for directory in self._all_dirs():
            self._before[directory] = set(_list_files(directory))

    def wait(self, abbruch=None) -> Path:
        """Wartet auf die fertige Datei und liefert ihren Pfad.

        Wirft TimeoutError, wenn nichts erscheint. `abbruch` ist eine
        Funktion ohne Argumente; liefert sie True, wird das Warten sofort
        beendet – sonst müsste der Anwender nach dem Abbrechen-Knopf noch
        bis zu drei Minuten auf den Zeitablauf warten.
        """
        deadline = time.time() + self.timeout_s
        stable_since: dict[Path, tuple[int, float]] = {}
        while time.time() < deadline:
            if abbruch is not None and abbruch():
                raise TimeoutError("Download vom Anwender abgebrochen")
            for candidate in self._new_files():
                size = _size(candidate)
                if size <= 0:
                    continue
                last = stable_since.get(candidate)
                if last is not None and last[0] == size:
                    if time.time() - last[1] >= STABLE_SECONDS:
                        log.info("Download erkannt: %s (%d Bytes)",
                                 candidate, size)
                        return candidate
                else:
                    stable_since[candidate] = (size, time.time())
            time.sleep(POLL_INTERVAL_S)
        raise TimeoutError(
            f"Kein Download erkannt (Zielpfad {self.expected}, überwacht: "
            f"{', '.join(str(d) for d in self._all_dirs()) or 'keine Ordner'})")

    # ------------------------------------------------------------- Intern
    def _all_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self.expected is not None:
            dirs.append(self.expected.parent)
        for d in self.watch_dirs:
            if d not in dirs:
                dirs.append(d)
        return [d for d in dirs if d.is_dir()]

    def _new_files(self) -> list[Path]:
        found: list[Path] = []
        if self.expected is not None and self.expected.exists():
            found.append(self.expected)
        for directory in self._all_dirs():
            before = self._before.get(directory, set())
            for path in _list_files(directory):
                if path in before or path in found:
                    continue
                if not _is_candidate(path):
                    continue
                if path.stat().st_mtime < self._started - 5:
                    continue      # älter als der Downloadstart
                found.append(path)
        return found


def _list_files(directory: Path) -> list[Path]:
    try:
        return [p for p in directory.iterdir() if p.is_file()]
    except OSError:
        return []


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return -1


def _is_candidate(path: Path) -> bool:
    name = path.name.lower()
    if name.endswith(TEMP_SUFFIXES):
        return False
    return name.endswith(CANDIDATE_SUFFIXES)


# ======================================================================
# watchdog
# ======================================================================
# Watchdog: erkennt SAP-Abstürze und startet P11 automatisch neu.
#
# Ablauf bei recover():
#   1. SAP-Prozesse sauber beenden (nur SAP-eigene Prozesse).
#   2. saplogon.exe starten und auf die Scripting-Engine warten.
#   3. Verbindung öffnen; Login übernimmt SSO oder hinterlegte Credentials
#      (Windows Credential Manager, niemals Klartext auf Platte).
#   4. Exponentielles Backoff über mehrere Versuche.



import logging
import os
import subprocess
import time



SAP_PROCESSES = ["saplogon.exe", "sapgui.exe", "SAPgui.exe"]
DEFAULT_SAPLOGON = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"
CREDENTIAL_TARGET = "drawing-checker/P11"  # Eintrag im Windows Credential Manager

MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 5


class SapWatchdog:
    def __init__(self, connection_name: str, saplogon_path: str | None = None):
        self.connection_name = connection_name
        self.saplogon_path = saplogon_path or os.environ.get(
            "SAPLOGON_PATH", DEFAULT_SAPLOGON)

    # -------------------------------------------------------------- Recovery
    def recover(self) -> None:
        """Kompletter Neustart-Zyklus mit Backoff. Wirft SapUnavailable,
        wenn alle Versuche scheitern."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                log.warning("SAP-Recovery, Versuch %d/%d", attempt, MAX_ATTEMPTS)
                self.kill_sap()
                self.start_sapgui()
                return
            except Exception as exc:
                last_error = exc
                wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
                log.error("Recovery-Versuch %d fehlgeschlagen: %s – warte %ds",
                          attempt, exc, wait)
                time.sleep(wait)
        raise SapUnavailable(
            f"SAP-Neustart nach {MAX_ATTEMPTS} Versuchen fehlgeschlagen: {last_error}")

    def kill_sap(self) -> None:
        for proc in SAP_PROCESSES:
            subprocess.run(
                ["taskkill", "/F", "/IM", proc],
                capture_output=True, check=False,
            )
        time.sleep(2)

    def start_sapgui(self):
        """Startet saplogon.exe und liefert die Scripting-Engine."""
        try:
            import win32com.client
        except ImportError as exc:  # pragma: no cover
            raise SapUnavailable("pywin32 fehlt") from exc

        if not os.path.exists(self.saplogon_path):
            raise SapUnavailable(
                f"saplogon.exe nicht gefunden: {self.saplogon_path} "
                "(SAPLOGON_PATH setzen)")
        subprocess.Popen([self.saplogon_path])

        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                sapgui = win32com.client.GetObject("SAPGUI")
                return sapgui.GetScriptingEngine
            except Exception:
                time.sleep(1.5)
        raise SapUnavailable("SAP GUI startet, aber Scripting-Engine kommt nicht hoch")

    # ----------------------------------------------------------------- Login
    def login_if_needed(self, session) -> None:
        """Füllt den Login-Screen, falls er erscheint (kein SSO).

        Credentials kommen aus dem Windows Credential Manager
        (Eintrag 'drawing-checker/P11'); die GUI legt sie bei der ersten
        Nutzung dort ab. Bei SSO erscheint kein Login-Screen -> no-op.
        """
        pass  # (im selben Modul)

        wait_ready(session)
        user_field = find_element(session, "wnd[0]/usr/txtRSYST-BNAME")
        if user_field is None:
            return  # SSO oder bereits angemeldet
        user, password = self._load_credentials()
        if not user:
            raise SapUnavailable(
                "SAP-Login erforderlich, aber keine Credentials hinterlegt "
                "(GUI: Einstellungen → SAP-Anmeldung)")
        user_field.Text = user
        session.FindById("wnd[0]/usr/pwdRSYST-BCODE").Text = password
        session.FindById("wnd[0]").SendVKey(0)  # Enter
        wait_ready(session)
        # Mehrfachanmeldungs-Dialog: bestehende Anmeldung übernehmen.
        multi = find_element(session, "wnd[1]/usr/radMULTI_LOGON_OPT2")
        if multi is not None:
            multi.Select()
            session.FindById("wnd[1]/tbar[0]/btn[0]").Press()
            wait_ready(session)

    @staticmethod
    def _load_credentials() -> tuple[str, str]:
        try:
            import win32cred  # pragma: no cover - nur Windows

            cred = win32cred.CredRead(CREDENTIAL_TARGET,
                                      win32cred.CRED_TYPE_GENERIC)
            return cred["UserName"], cred["CredentialBlob"].decode("utf-16-le")
        except Exception:
            return "", ""

    @staticmethod
    def store_credentials(user: str, password: str) -> None:
        import win32cred  # pragma: no cover - nur Windows

        win32cred.CredWrite({
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": CREDENTIAL_TARGET,
            "UserName": user,
            "CredentialBlob": password.encode("utf-16-le"),
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }, 0)


# ======================================================================
# diagnostics
# ======================================================================
# Diagnose-Werkzeuge für den SAP-Durchstich.
#
# Wenn morgen ein Schritt nicht greift, entscheidet die Diagnose darüber, wie
# schnell die Ursache gefunden ist:
#
#   dump_screen     Elementbaum des aktuellen Bildes (welche Felder gibt es,
#                   wie heißen sie?) – der Ersatz für „raten".
#   save_screenshot Bildschirmfoto des SAP-Fensters zum Fehlerzeitpunkt.
#   describe_session Verbindungsdaten (System, Mandant, Benutzer, Transaktion).



import logging
from pathlib import Path


MAX_DEPTH = 6
INTERESTING = ("txt", "ctxt", "btn", "chk", "rad", "cmb", "lbl", "tbl",
               "shell", "tabs", "sub", "usr", "ssub")


def describe_session(session) -> str:
    """Kurzinfo zur Verbindung – für Protokoll und Fehlermeldungen."""
    try:
        info = session.Info
        return (f"System {info.SystemName}, Mandant {info.Client}, "
                f"Benutzer {info.User}, Transaktion "
                f"{getattr(info, 'Transaction', '?')}")
    except Exception as exc:
        return f"Sessioninfo nicht lesbar: {exc}"


def dump_screen(session, root: str = "wnd[0]", max_depth: int = MAX_DEPTH
                ) -> str:
    """Elementbaum des aktuellen Bildes als Text.

    Zeigt Id, Typ, Beschriftung und Inhalt – daraus lassen sich die
    Element-IDs für den Ablauf ablesen, ohne ein neues .vbs aufzunehmen.
    """
    lines: list[str] = [f"Elementbaum ab {root}:"]
    try:
        element = session.FindById(root, False)
    except Exception as exc:
        return f"{root} nicht lesbar: {exc}"
    if element is None:
        return f"{root} nicht vorhanden"
    _walk(element, lines, depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _walk(element, lines: list[str], depth: int, max_depth: int) -> None:
    if depth > max_depth:
        return
    try:
        element_id = str(getattr(element, "Id", "?"))
        kind = str(getattr(element, "Type", "?"))
        text = str(getattr(element, "Text", "") or "")
        tooltip = str(getattr(element, "Tooltip", "") or "")
    except Exception:
        return
    short = element_id.split("/")[-1] if "/" in element_id else element_id
    if depth == 0 or any(short.lower().startswith(p) for p in INTERESTING) \
            or kind.startswith("GuiButton"):
        label = f" „{text[:40]}“" if text else ""
        tip = f" [{tooltip[:30]}]" if tooltip and tooltip != text else ""
        lines.append(f"{'  ' * depth}{element_id}  ({kind}){label}{tip}")
    try:
        children = element.Children
        count = children.Count
    except Exception:
        return
    for i in range(count):
        try:
            _walk(children(i), lines, depth + 1, max_depth)
        except Exception:
            continue


def save_screenshot(session, path: Path) -> Path | None:
    """Bildschirmfoto des SAP-Fensters (HardCopy); None wenn nicht möglich."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        window = session.FindById("wnd[0]")
        window.HardCopy(str(path))
        if path.exists():
            return path
    except Exception as exc:
        log.debug("HardCopy nicht möglich: %s", exc)
    # Fallback: kompletter Bildschirm
    try:
        import mss

        with mss.mss() as sct:
            sct.shot(output=str(path))
        return path if path.exists() else None
    except Exception as exc:
        log.debug("Bildschirmfoto nicht möglich: %s", exc)
        return None


def diagnose_failure(session, material: str, out_dir: Path) -> Path:
    """Schreibt einen Diagnosebericht zum Fehlerzeitpunkt."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"sap_diagnose_{material}.txt"
    parts = [
        f"SAP-Diagnose für Materialnummer {material}",
        describe_session(session),
        "",
        dump_screen(session),
    ]
    for window in ("wnd[1]", "wnd[2]"):
        try:
            if session.FindById(window, False) is not None:
                parts += ["", f"Offener Dialog {window}:",
                          dump_screen(session, window, max_depth=4)]
        except Exception:
            pass
    report.write_text("\n".join(parts), encoding="utf-8")
    shot = save_screenshot(session, out_dir / f"sap_bild_{material}.png")
    if shot:
        parts.append(f"\nBildschirmfoto: {shot}")
    log.info("SAP-Diagnose geschrieben: %s", report)
    return report


# ========================================================================
# sap_ablauf
# ========================================================================
# Der aufgezeichnete SAP-Ablauf: einlesen (.vbs) und abspielen.
#
# Der Transaktionsablauf wird nicht programmiert, sondern aufgenommen.
# Hier steht beides beisammen: der Parser des Mitschnitts und der Spieler,
# der die Schritte gegen SAP ausfuehrt.
# ======================================================================
# script_flow
# ======================================================================
# Aufgezeichneter SAP-Ablauf als abspielbare Schrittfolge.
#
# Statt den Transaktionsablauf fest zu programmieren, spielt der Adapter die
# Schritte ab, die aus dem .vbs-Mitschnitt der Transaktion stammen. Vorteile:
#
#   * Kein manuelles Übertragen von Element-IDs (fehleranfällig).
#   * Der Ablauf darf beliebig aussehen (mehrere Selektionsfelder, Layout-
#     Auswahl, Zwischenbilder) – abgespielt wird, was aufgezeichnet wurde.
#   * Platzhalter erlauben es, dieselbe Aufzeichnung für jede Materialnummer
#     zu verwenden.
#
# Platzhalter in Werten:
#   {material}     Materialnummer der aktuellen Zeile
#   {target_dir}   Zielordner für den Download
#   {filename}     Dateiname des ZIP (z. B. "10473215.zip")
#   {target_path}  Vollständiger Pfad (Ordner + Dateiname)



import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml



@dataclass
class Step:
    """Eine Aktion im aufgezeichneten Ablauf.

    Neben den benannten Aktionen (set_text, press …) gibt es zwei
    generische Formen, mit denen JEDE Scripting-Anweisung abspielbar ist:

      action: "call"      method + args  -> element.<method>(*args)
      action: "set_prop"  member + value -> element.<member> = value

    Damit funktionieren auch ALV-Grid- und Baum-Methoden
    (pressToolbarButton, setCurrentCell, selectItem …), ohne dass der
    Player sie einzeln kennen muss.
    """

    action: str                 # set_text | press | send_vkey | call |
                                # set_prop | start_transaction | sleep | ...
    element: str = ""           # findById-Pfad, leer bei Sonderaktionen
    value: Any = None           # Text, VKey-Nummer, Index …
    optional: bool = False      # fehlendes Element ist kein Fehler
    comment: str = ""           # Herkunft/Erläuterung (aus dem .vbs)
    method: str = ""            # bei action="call"
    member: str = ""            # bei action="set_prop"
    args: list = field(default_factory=list)   # Argumente für "call"

    def resolve(self, context: dict[str, str]) -> Any:
        """Platzhalter im Wert ersetzen."""
        return _fill(self.value, context)

    def resolved_args(self, context: dict[str, str]) -> list:
        return [_fill(a, context) for a in self.args]


def _fill(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        try:
            return value.format(**context)
        except (KeyError, IndexError, ValueError):
            return value
    return value


@dataclass
class ScriptFlow:
    """Kompletter Ablauf einer Transaktion."""

    name: str = "ymatdocs"
    transaction: str = ""
    steps: list[Step] = field(default_factory=list)
    # Element-IDs, die für die Automatisierung besonders wichtig sind.
    material_field: str = ""
    download_step_index: int | None = None
    # Verbindung/System aus dem Mitschnitt (z. B. "P11"), falls die
    # Aufzeichnung sie hergibt – dann muss niemand sie eintippen.
    connection: str = ""
    notes: str = ""

    # ------------------------------------------------------------ Persistenz
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "transaction": self.transaction,
            "material_field": self.material_field,
            "download_step_index": self.download_step_index,
            "connection": self.connection,
            "notes": self.notes,
            "steps": [
                {k: v for k, v in {
                    "action": s.action,
                    "element": s.element,
                    "method": s.method,
                    "member": s.member,
                    "value": s.value,
                    "args": list(s.args) or None,
                    "optional": s.optional or None,
                    "comment": s.comment or None,
                }.items() if v is not None and v != ""}
                for s in self.steps
            ],
        }

    def save(self, path: Path) -> None:
        path.write_text(
            "# Aufgezeichneter SAP-Ablauf (aus .vbs importiert).\n"
            "# Platzhalter: {material}, {target_dir}, {filename}, {target_path}\n"
            "# Schritte dürfen von Hand nachgebessert werden.\n\n"
            + yaml.safe_dump(self.to_dict(), allow_unicode=True,
                             sort_keys=False),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ScriptFlow":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        steps = [
            Step(action=s["action"], element=s.get("element", ""),
                 value=s.get("value"), optional=bool(s.get("optional", False)),
                 comment=s.get("comment", ""), method=s.get("method", ""),
                 member=s.get("member", ""), args=list(s.get("args") or []))
            for s in data.get("steps", [])
        ]
        return cls(
            name=data.get("name", "ymatdocs"),
            transaction=data.get("transaction", ""),
            steps=steps,
            material_field=data.get("material_field", ""),
            download_step_index=data.get("download_step_index"),
            connection=data.get("connection", ""),
            notes=data.get("notes", ""),
        )


# ---------------------------------------------------------------- Abspielen
class FlowError(Exception):
    """Ein Schritt konnte nicht ausgeführt werden."""

    def __init__(self, message: str, step: Step, index: int):
        super().__init__(message)
        self.step = step
        self.index = index


class Abgebrochen(Exception):
    """Der Anwender hat den Lauf abgebrochen."""


def play(session, flow: ScriptFlow, context: dict[str, str], *,
         wait_ready=None, on_step=None, popup_handler=None,
         stop_after: int | None = None, abbruch=None) -> None:
    """Spielt den Ablauf auf einer SAP-Session ab.

    wait_ready:    Funktion, die auf ein antwortbereites SAP wartet.
    on_step:       Callback(index, step, resolved) – für Diagnose/Protokoll.
    popup_handler: Funktion(session, step), die unerwartete Dialoge
                   wegräumt; wird vor jedem Schritt aufgerufen. Der
                   anstehende Schritt wird mitgegeben, damit das Fenster,
                   das dieser Schritt bedient, stehen bleibt.
    stop_after:    Nur die ersten n Schritte ausführen (Schrittbetrieb).
    abbruch:       Funktion ohne Argumente; liefert sie True, wird vor dem
                   nächsten Schritt abgebrochen (Knopf in der GUI).
    """
    for index, step in enumerate(flow.steps):
        if stop_after is not None and index >= stop_after:
            return
        if abbruch is not None and abbruch():
            raise Abgebrochen(
                f"Abgebrochen vor Schritt {index + 1} ({step.action})")
        resolved = step.resolve(context)
        if on_step:
            on_step(index, step, resolved)
        if popup_handler:
            popup_handler(session, step)
        try:
            _execute(session, step, resolved, context)
        except FlowError:
            raise
        except Exception as exc:
            if step.optional:
                log.info("Optionaler Schritt %d (%s) übersprungen: %s",
                         index, step.action, exc)
                continue
            raise FlowError(
                f"Schritt {index + 1} ({step.action} {step.element}) "
                f"fehlgeschlagen: {exc}", step, index) from exc
        if wait_ready:
            wait_ready(session)


def _execute(session, step: Step, value: Any,
             context: dict[str, str] | None = None) -> None:
    action = step.action
    if action == "sleep":
        time.sleep(float(value or 0.5))
        return
    if action == "start_transaction":
        session.FindById("wnd[0]/tbar[0]/okcd").Text = value
        session.FindById("wnd[0]").SendVKey(0)
        return

    element = None
    if step.element:
        element = _find_element(session, step.element)
        if element is None:
            if step.optional:
                return
            raise FlowError(
                f"Element {step.element!r} nicht gefunden", step, -1)

    if action == "set_text":
        element.Text = "" if value is None else str(value)
    elif action == "press":
        element.Press()
    elif action == "select":
        element.Select()
    elif action == "set_focus":
        element.SetFocus()
    elif action == "set_checked":
        element.Selected = bool(value)
    elif action == "set_key":
        element.Key = str(value)
    elif action == "send_vkey":
        target = element if element is not None else _find_element(session, "wnd[0]")
        target.SendVKey(int(value))
    elif action == "maximize":
        (element or _find_element(session, "wnd[0]")).Maximize()
    elif action == "select_node":
        element.SelectedNode = str(value)
    elif action == "double_click_node":
        element.DoubleClickNode(str(value))
    elif action == "set_caret":
        element.CaretPosition = int(value)
    elif action == "call":
        # Generisch: beliebige Scripting-Methode mit Argumenten
        method = _resolve_member(element, step.method)
        if method is None:
            raise FlowError(
                f"Methode {step.method!r} an {step.element} nicht vorhanden",
                step, -1)
        method(*step.resolved_args(context or {}))
    elif action == "set_prop":
        member = _actual_member_name(element, step.member)
        if member is None:
            raise FlowError(
                f"Eigenschaft {step.member!r} an {step.element} nicht vorhanden",
                step, -1)
        setattr(element, member, value)
    else:
        raise FlowError(f"Unbekannte Aktion {action!r}", step, -1)


def _actual_member_name(element, name: str) -> str | None:
    """COM ist case-insensitiv, Python nicht – passende Schreibweise finden."""
    if hasattr(element, name):
        return name
    lowered = name.lower()
    for candidate in dir(element):
        if candidate.lower() == lowered:
            return candidate
    # Bei echten COM-Objekten listet dir() nichts Brauchbares: Großschreibung
    # der ersten Buchstaben ist die übliche Form (pressToolbarButton ->
    # PressToolbarButton).
    return name[0].upper() + name[1:] if name else None


def _resolve_member(element, name: str):
    actual = _actual_member_name(element, name)
    if actual is None:
        return None
    member = getattr(element, actual, None)
    return member if callable(member) else None


def _find_element(session, element_id: str):
    try:
        return session.FindById(element_id, False)
    except TypeError:
        # Manche COM-Wrapper kennen den zweiten Parameter nicht.
        try:
            return session.FindById(element_id)
        except Exception:
            return None
    except Exception:
        return None


# ======================================================================
# vbs_parser
# ======================================================================
# Import eines SAP-GUI-Skript-Mitschnitts (.vbs) als abspielbarer Ablauf.
#
# Der Mitschnitt aus „Skript aufzeichnen und abspielen" sieht so aus:
#
#     session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"
#     session.findById("wnd[0]").sendVKey 0
#     session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = "10473215"
#     session.findById("wnd[0]").sendVKey 8
#     session.findById("wnd[0]/tbar[1]/btn[13]").press
#
# Der Parser übersetzt das in Schritte, erkennt automatisch
#
#   * den Transaktionscode,
#   * das Feld, in das die Materialnummer eingetragen wird,
#   * Datei-Dialog-Felder (Pfad/Dateiname) für den Download,
#
# und ersetzt die aufgezeichneten Werte durch Platzhalter. Damit ist der
# Ablauf sofort für beliebige Materialnummern verwendbar.



import logging
import re
from pathlib import Path



# session.findById("...").text = "wert"      (auch .Text, ohne Klammern)
RE_SET_PROP = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s*=\s*(.+?)\s*$',
    re.IGNORECASE)
# session.findById("...").press / .select / .setFocus / .maximize
RE_CALL = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s*(?:\(\s*\))?\s*$',
    re.IGNORECASE)
# session.findById("...").sendVKey 8   /  .selectNode "F00001"
RE_CALL_ARG = re.compile(
    r'findById\(\s*"([^"]+)"\s*\)\s*\.\s*(\w+)\s+(.+?)\s*$', re.IGNORECASE)

RE_TRANSACTION = re.compile(r'^/n?\s*(\w+)', re.IGNORECASE)
# Verbindung aus dem Mitschnitt: application.OpenConnection "P11 Produktion"
# bzw. OpenConnectionByConnectionString. Aus dem Eintrag wird das erste
# Wort als Systemname genommen ("P11 [PUBLIC]" -> "P11").
RE_OPEN_CONNECTION = re.compile(
    r'OpenConnection(?:ByConnectionString)?\s*\(?\s*"([^"]+)"', re.IGNORECASE)
RE_SYSTEM_HINT = re.compile(r"\b([A-Z][A-Z0-9]{2})\b")
# Werte, die wie eine Materialnummer aussehen (6–18 Stellen, ggf. führende 0).
RE_MATERIAL_VALUE = re.compile(r"^\d{6,18}$")
RE_PATH_VALUE = re.compile(r"^[A-Za-z]:\\|^\\\\|/")

# Feld-IDs, die typischerweise Datei-Dialoge betreffen.
PATH_FIELD_HINTS = ("DY_PATH", "PATH", "VERZEICHNIS", "DIRECTORY")
NAME_FIELD_HINTS = ("DY_FILENAME", "FILENAME", "DATEINAME")

PROP_ACTIONS = {
    "text": "set_text",
    "caretposition": "set_caret",
    "selected": "set_checked",
    "key": "set_key",
    "selectednode": "select_node",
}
CALL_ACTIONS = {
    "press": "press",
    "select": "select",
    "setfocus": "set_focus",
    "maximize": "maximize",
    "sendvkey": "send_vkey",
    "selectnode": "select_node",
    "doubleclicknode": "double_click_node",
}
# Aktionen, die für den automatischen Ablauf irrelevant sind.
SKIP_ACTIONS = {"set_caret", "set_focus", "maximize"}
# Methoden, die einen Download auslösen können (für die Trigger-Erkennung).
DOWNLOAD_HINTS = re.compile(
    r"download|export|speichern|save|lokal|sichern|xxl|excel|zip",
    re.IGNORECASE)


def parse_vbs(path: Path | str, *, keep_cosmetic: bool = False) -> ScriptFlow:
    """Liest einen .vbs-Mitschnitt und liefert den Ablauf."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    flow = ScriptFlow(name=Path(path).stem)
    material_values: list[tuple[int, str, str]] = []   # (index, element, wert)

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("'") or line.lower().startswith("rem "):
            continue
        if not flow.connection:
            m = RE_OPEN_CONNECTION.search(line)
            if m:
                flow.connection = _system_aus_eintrag(m.group(1))
        if "findbyid" not in line.lower():
            continue

        step = _parse_line(line)
        if step is None:
            log.debug("Zeile nicht interpretierbar: %s", line)
            continue
        if step.action in SKIP_ACTIONS and not keep_cosmetic:
            continue

        # Transaktionscode erkennen und als eigenen Schritt führen
        if step.action == "set_text" and step.element.endswith("okcd"):
            m = RE_TRANSACTION.match(str(step.value).strip())
            if m:
                flow.transaction = m.group(1).upper()
            flow.steps.append(Step("start_transaction",
                                   value=str(step.value).strip(),
                                   comment="Transaktionsstart"))
            continue
        # Das direkt folgende Enter gehört zum Transaktionsstart
        if (step.action == "send_vkey" and flow.steps
                and flow.steps[-1].action == "start_transaction"
                and str(step.value) == "0"):
            continue

        if step.action == "set_text" and isinstance(step.value, str):
            value = step.value
            if RE_MATERIAL_VALUE.match(value):
                material_values.append((len(flow.steps), step.element, value))
            elif _is_path_field(step.element) or RE_PATH_VALUE.match(value):
                step.value = ("{target_dir}" if _is_path_field(step.element)
                              else "{target_path}")
                step.comment = step.comment or "Datei-Dialog: Zielordner"
            elif _is_name_field(step.element):
                step.value = "{filename}"
                step.comment = step.comment or "Datei-Dialog: Dateiname"
        flow.steps.append(step)

    _apply_material_placeholder(flow, material_values)
    _mark_download_step(flow)
    return flow


def _system_aus_eintrag(eintrag: str) -> str:
    """Systemname aus dem Verbindungseintrag des SAP Logon.

    Die Einträge heißen z. B. "P11 Produktion" oder "P11 [PUBLIC]" – für
    die Verbindung genügt der Systemname davor.
    """
    eintrag = eintrag.strip()
    m = RE_SYSTEM_HINT.search(eintrag.upper())
    return m.group(1) if m else eintrag.split()[0] if eintrag else ""


def _parse_line(line: str) -> Step | None:
    """Eine Skriptzeile in einen Schritt übersetzen.

    Bekannte Aktionen bekommen sprechende Namen; alles andere wird
    generisch als `call`/`set_prop` abgebildet, damit auch ALV-Grid- und
    Baum-Methoden abspielbar sind.
    """
    m = RE_SET_PROP.search(line)
    if m:
        element, prop, value = m.group(1), m.group(2), m.group(3)
        action = PROP_ACTIONS.get(prop.lower())
        if action:
            return Step(action, element, _literal(value))
        return Step("set_prop", element, _literal(value), member=prop,
                    comment=f"aus .vbs: .{prop}")

    m = RE_CALL_ARG.search(line)
    if m:
        element, call, arg = m.group(1), m.group(2), m.group(3)
        action = CALL_ACTIONS.get(call.lower())
        args = _split_args(arg)
        if action:
            return Step(action, element, args[0] if args else None)
        return Step("call", element, method=call, args=args,
                    comment=f"aus .vbs: .{call}")

    m = RE_CALL.search(line)
    if m:
        element, call = m.group(1), m.group(2)
        action = CALL_ACTIONS.get(call.lower())
        if action:
            return Step(action, element)
        return Step("call", element, method=call,
                    comment=f"aus .vbs: .{call}")
    return None


def _split_args(raw: str) -> list:
    """Argumentliste einer VBS-Methode zerlegen: 'a', 5, "b, c" -> [...]"""
    args: list = []
    current = ""
    in_string = False
    for char in raw.strip().strip("()"):
        if char == '"':
            in_string = not in_string
            current += char
        elif char == "," and not in_string:
            args.append(_literal(current))
            current = ""
        else:
            current += char
    if current.strip():
        args.append(_literal(current))
    return args


def _literal(raw: str):
    """VBS-Literal in einen Python-Wert wandeln."""
    value = raw.strip().rstrip(";")
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('""', '"')
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _is_path_field(element: str) -> bool:
    up = element.upper()
    return any(h in up for h in PATH_FIELD_HINTS)


def _is_name_field(element: str) -> bool:
    up = element.upper()
    return any(h in up for h in NAME_FIELD_HINTS)


def _apply_material_placeholder(
        flow: ScriptFlow, candidates: list[tuple[int, str, str]]) -> None:
    """Setzt {material} in die Felder, die die Materialnummer bekommen.

    Kommt derselbe Zahlenwert mehrfach vor (z. B. Von/Bis-Feld einer
    Select-Option), werden alle Vorkommen ersetzt.
    """
    if not candidates:
        return
    # Häufigsten Wert als Materialnummer annehmen (Von/Bis identisch).
    from collections import Counter

    counts = Counter(value for _i, _e, value in candidates)
    material_value = counts.most_common(1)[0][0]
    first = True
    for index, element, value in candidates:
        if value != material_value:
            continue
        flow.steps[index].value = "{material}"
        flow.steps[index].comment = "Materialnummer"
        if first:
            flow.material_field = element
            first = False
    # Andere Zahlenfelder bleiben unverändert (z. B. Werk, Layoutnummer).


def _mark_download_step(flow: ScriptFlow) -> None:
    """Merkt sich den Schritt, der den Download auslöst.

    Heuristik: der letzte Tastendruck vor dem ersten Datei-Dialog-Feld,
    sonst der letzte press-Schritt überhaupt.
    """
    # 1) Methode, deren Name nach Download klingt (ALV-Toolbar u. a.)
    for i, step in enumerate(flow.steps):
        haystack = " ".join(
            [step.method or "", step.element or ""]
            + [str(a) for a in step.args])
        if step.action in ("call", "press") and DOWNLOAD_HINTS.search(haystack):
            flow.download_step_index = i
            step.comment = step.comment or "löst den Download aus"
            return
    # 2) Sonst: letzter Tastendruck vor dem Datei-Dialog
    dialog_index = next(
        (i for i, s in enumerate(flow.steps)
         if isinstance(s.value, str)
         and s.value in ("{target_dir}", "{filename}", "{target_path}")),
        None)
    if dialog_index is not None:
        for i in range(dialog_index - 1, -1, -1):
            if flow.steps[i].action in ("press", "send_vkey", "call"):
                flow.download_step_index = i
                flow.steps[i].comment = (flow.steps[i].comment
                                         or "löst den Download aus")
                return
    for i in range(len(flow.steps) - 1, -1, -1):
        if flow.steps[i].action == "press":
            flow.download_step_index = i
            return


def describe(flow: ScriptFlow) -> str:
    """Menschenlesbare Übersicht des importierten Ablaufs."""
    lines = [
        f"Ablauf {flow.name!r}"
        + (f", Transaktion {flow.transaction}" if flow.transaction else ""),
        f"SAP-System: {flow.connection or 'nicht im Mitschnitt enthalten'}",
        f"Materialnummer-Feld: {flow.material_field or 'NICHT ERKANNT'}",
        f"Schritte: {len(flow.steps)}",
        "",
    ]
    for i, s in enumerate(flow.steps, start=1):
        detail = ""
        if s.action == "call":
            arglist = ", ".join(repr(a) for a in s.args)
            detail = f".{s.method}({arglist})"
        elif s.action == "set_prop":
            detail = f".{s.member} = {s.value!r}"
        elif s.value is not None:
            detail = f" = {s.value!r}"
        marker = " <== DOWNLOAD" if i - 1 == flow.download_step_index else ""
        note = f"   # {s.comment}" if s.comment else ""
        lines.append(
            f"{i:3}. {s.action:<18} {s.element}{detail}{note}{marker}")
    if not flow.material_field:
        lines += [
            "",
            "WARNUNG: Kein Feld mit einer Materialnummer erkannt. Bitte im",
            "erzeugten YAML den passenden Schritt auf value: '{material}'",
            "setzen und material_field eintragen.",
        ]
    return "\n".join(lines)


def kurzbericht(flow: ScriptFlow) -> tuple[bool, list[str]]:
    """Klartext-Rückmeldung zu einem eingelesenen Mitschnitt.

    Liefert (verstanden, Zeilen). „Verstanden" heißt: Das Programm weiß, in
    welches Feld die Materialnummer gehört und womit der Download ausgelöst
    wird – mehr braucht es nicht, alles andere steht im Ablauf.
    """
    zeilen = [
        f"Transaktion: {flow.transaction or 'nicht erkannt'}",
        f"SAP-System: {flow.connection or 'nicht im Mitschnitt'}",
        f"Schritte: {len(flow.steps)}",
    ]
    if flow.material_field:
        zeilen.append(f"Materialnummer geht in: {flow.material_field}")
    else:
        zeilen.append("ACHTUNG: Kein Feld für die Materialnummer erkannt.")
    if flow.download_step_index is not None:
        schritt = flow.steps[flow.download_step_index]
        zeilen.append(f"Download über: {schritt.element or schritt.action}")
    else:
        zeilen.append("ACHTUNG: Kein Download-Schritt erkannt.")
    ok = bool(flow.material_field and flow.download_step_index is not None)
    return ok, zeilen


def uebernehmen(pfad: Path, ziel: Path) -> tuple[ScriptFlow, bool, list[str]]:
    """Mitschnitt einlesen, als Ablauf speichern, Kurzbericht liefern.

    Gemeinsame Logik für GUI und Kommandozeile – ohne Dialoge, damit sie
    sich testen lässt.
    """
    flow = parse_vbs(pfad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    flow.save(ziel)
    pass  # (Import entfaellt - alles ein Modul)

    _flow_cache.clear()          # neu eingelesenen Ablauf sofort verwenden
    ok, zeilen = kurzbericht(flow)
    return flow, ok, zeilen


# ========================================================================
# sap_ymatdocs
# ========================================================================
# YMATDOCS beschaffen: Schnittstelle, echter Weg, Mock, Testsitzung.
#
# Die Schnittstelle, die der Orchestrator sieht, und die drei Wege sie zu
# erfuellen: echtes SAP, Ordner mit ZIPs, und eine nachgebaute Sitzung
# fuer Tests und den Trockenlauf.
# ======================================================================
# ymatdocs
# ======================================================================
# Transaktionsablauf YMATDOCS: Report ausführen und ZIP-Paket herunterladen.
#
# Der Ablauf wird NICHT fest programmiert, sondern aus dem .vbs-Mitschnitt der
# Transaktion importiert und abgespielt (siehe `vbs_parser.py`,
# `script_flow.py`). Damit entfällt das fehleranfällige Abtippen von
# Element-IDs, und ein abweichender Ablauf (zusätzliche Selektionsfelder,
# Layout-Auswahl, Zwischenbilder) funktioniert ohne Codeänderung.
#
# Ablauf je Materialnummer:
#   1. Ablauf laden (einmalig, aus `regeln/ymatdocs_flow.yaml` bzw. dem über
#      `--sap-flow` angegebenen Pfad).
#   2. Download-Überwachung starten (erwarteter Pfad + Ordner).
#   3. Schritte abspielen, dabei Popups automatisch behandeln.
#   4. Auf die fertige Datei warten und sie an den Zielort verschieben.
#
# Ohne importierten Ablauf greift der eingebaute Standardablauf (die früher
# hartcodierte Variante) – er dient nur als Notnagel und meldet klar, dass
# der Mitschnitt fehlt.



import logging
import shutil
from pathlib import Path



DOWNLOAD_TIMEOUT_S = 180
FLOW_FILENAME = "ymatdocs_flow.yaml"

# Notnagel-Ablauf, falls kein Mitschnitt importiert wurde. Die IDs sind die
# üblichen Muster eines Selektionsbilds – sie stimmen fast sicher NICHT mit
# YMATDOCS überein, liefern aber eine verständliche Fehlermeldung.
FALLBACK_FLOW = ScriptFlow(
    name="ymatdocs-fallback",
    transaction="YMATDOCS",
    material_field="wnd[0]/usr/ctxtP_MATNR",
    steps=[
        Step("start_transaction", value="/nYMATDOCS",
             comment="Transaktionsstart"),
        Step("set_text", "wnd[0]/usr/ctxtP_MATNR", "{material}",
             comment="Materialnummer (Standardannahme)"),
        Step("send_vkey", "wnd[0]", 8, comment="Ausführen (F8)"),
        Step("press", "wnd[0]/tbar[1]/btn[13]", optional=True,
             comment="Download (Standardannahme)"),
        Step("set_text", "wnd[1]/usr/ctxtDY_PATH", "{target_dir}",
             optional=True),
        Step("set_text", "wnd[1]/usr/ctxtDY_FILENAME", "{filename}",
             optional=True),
        Step("press", "wnd[1]/tbar[0]/btn[0]", optional=True),
    ],
    download_step_index=3,
    notes="Eingebauter Notnagel – bitte den .vbs-Mitschnitt importieren.",
)

_flow_cache: dict[str, ScriptFlow] = {}


def flow_search_paths() -> list[Path]:
    """Orte, an denen der importierte Ablauf gesucht wird."""
    pass  # (Import entfaellt - alles ein Modul)

    paths = [d / FLOW_FILENAME for d in rules_dirs()]
    paths.append(Path.cwd() / FLOW_FILENAME)
    return paths


def load_flow(explicit: Path | None = None) -> tuple[ScriptFlow, Path | None]:
    """Lädt den Ablauf; liefert (Ablauf, Quelle) – Quelle None = Notnagel."""
    candidates = [explicit] if explicit else flow_search_paths()
    for path in candidates:
        if path and Path(path).is_file():
            key = str(path)
            if key not in _flow_cache:
                _flow_cache[key] = ScriptFlow.load(Path(path))
                log.info("SAP-Ablauf geladen: %s (%d Schritte)",
                         path, len(_flow_cache[key].steps))
            return _flow_cache[key], Path(path)
    return FALLBACK_FLOW, None


def run_ymatdocs(session, material: str, target_dir: Path, *,
                 flow_path: Path | None = None,
                 watch_dirs: list[Path] | None = None,
                 on_step=None,
                 timeout_s: float = DOWNLOAD_TIMEOUT_S,
                 abbruch=None) -> Path:
    """Führt YMATDOCS für eine Materialnummer aus, liefert den ZIP-Pfad.

    abbruch: Funktion ohne Argumente; liefert sie True, wird der Ablauf
    beim nächsten Schritt bzw. beim Warten auf den Download abgebrochen.
    Damit wirkt der Abbrechen-Knopf der GUI sofort und nicht erst nach
    dem Zeitablauf des Downloads.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    flow, source = load_flow(flow_path)
    if source is None:
        log.warning("Kein importierter SAP-Ablauf gefunden – Notnagel aktiv. "
                    "Mitschnitt mit --sap-import-vbs einlesen!")

    filename = f"{_safe(material)}.zip"
    expected = target_dir / filename
    context = {
        "material": material,
        "target_dir": str(target_dir),
        "filename": filename,
        "target_path": str(expected),
    }

    watcher = DownloadWatcher(
        expected=expected,
        watch_dirs=list(watch_dirs) if watch_dirs is not None
        else default_watch_dirs(),
        timeout_s=timeout_s)
    watcher.start()

    try:
        play(session, flow, context,
             wait_ready=lambda s: wait_ready(s, timeout=120),
             on_step=on_step,
             popup_handler=_popup_handler,
             abbruch=abbruch)
    except FlowError as exc:
        _raise_flow_error(session, material, exc, source)

    status = _status_message(session)
    if status and _looks_like_not_found(status):
        raise MaterialNotFound(f"{material}: {status}")
    _raise_on_error_status(session, context=f"Ausführung für {material}")

    try:
        downloaded = watcher.wait(abbruch=abbruch)
    except TimeoutError as exc:
        if abbruch is not None and abbruch():
            raise Abgebrochen(f"{material}: vom Anwender abgebrochen") from exc
        if status:
            raise MaterialNotFound(f"{material}: kein Paket ({status})") from exc
        raise SapUnavailable(str(exc)) from exc

    if downloaded != expected:
        log.info("Download lag unter %s – wird nach %s verschoben",
                 downloaded, expected)
        shutil.move(str(downloaded), str(expected))
    return expected


def _popup_handler(session, step) -> int:
    """Dialoge abräumen – außer dem Fenster, das der Schritt selbst bedient.

    Ohne diese Ausnahme würde der Automat den Speichern-Dialog des
    Downloads bestätigen, bevor Zielordner und Dateiname eingetragen sind.
    """
    return handle_popups(session, skip_windows=_step_windows(step))


def _step_windows(step) -> set[str]:
    element = getattr(step, "element", "") or ""
    if element.startswith("wnd["):
        return {element.split("/", 1)[0]}
    return set()


def _raise_flow_error(session, material: str, exc: FlowError,
                      source: Path | None) -> None:
    """Ordnet einen Ablauffehler fachlich oder technisch ein."""
    status = _status_message(session)
    if status and _looks_like_not_found(status):
        raise MaterialNotFound(f"{material}: {status}") from exc
    where = f"aus {source.name}" if source else "aus dem Notnagel-Ablauf"
    hint = ""
    if source is None:
        hint = (" – es ist kein .vbs-Mitschnitt importiert. "
                "Mit `drawing-checker --sap-import-vbs <datei.vbs>` einlesen.")
    raise SapUnavailable(f"{material}: {exc} ({where}){hint}") from exc


def _safe(material: str) -> str:
    import re

    return re.sub(r"[^\w.-]", "_", material.strip()) or "unbenannt"


# ------------------------------------------------------------------ Status
def _status_message(session) -> str:
    sbar = find_element(session, "wnd[0]/sbar")
    try:
        return (sbar.Text or "").strip() if sbar is not None else ""
    except Exception:
        return ""


def _status_type(session) -> str:
    sbar = find_element(session, "wnd[0]/sbar")
    try:
        return (sbar.MessageType or "") if sbar is not None else ""
    except Exception:
        return ""


def _looks_like_not_found(status: str) -> bool:
    s = status.lower()
    return any(k in s for k in (
        "nicht vorhanden", "existiert nicht", "keine dokumente", "nicht gefunden",
        "kein dokument", "keine daten", "no documents", "not found",
        "does not exist", "no data"))


def _raise_on_error_status(session, context: str) -> None:
    if _status_type(session) in ("E", "A"):
        msg = _status_message(session)
        if _looks_like_not_found(msg):
            raise MaterialNotFound(msg)
        raise SapUnavailable(f"{context}: SAP-Fehler: {msg}")


# ======================================================================
# mock
# ======================================================================
# Mock-SAP-Adapter: liefert YMATDOCS-Pakete aus einem Ordner.
#
# Erwartet je Materialnummer eine Datei `<material>.zip` im Quellordner.
# Dient der Entwicklung ohne SAP und den End-to-End-Tests; optional lässt
# sich ein SAP-Absturz injizieren, um Watchdog/Retry-Pfade zu testen.



import shutil
import time
from pathlib import Path



class MockSapAdapter(SapAdapter):
    def __init__(self, source_dir: Path, latency_s: float = 0.0,
                 crash_on: set[str] | None = None):
        self.source_dir = Path(source_dir)
        self.latency_s = latency_s
        self.crash_on = crash_on or set()   # Materialien, die 1x "abstürzen"
        self._crashed: set[str] = set()
        self.ready = False

    def ensure_ready(self) -> None:
        if not self.source_dir.is_dir():
            raise SapUnavailable(f"Mock-Quellordner fehlt: {self.source_dir}")
        self.ready = True

    def fetch_package(self, material: str, target_dir: Path) -> Path:
        if not self.ready:
            raise SapUnavailable("Mock-Adapter nicht verbunden (ensure_ready fehlt)")
        if material in self.crash_on and material not in self._crashed:
            # Simulierter Absturz: genau einmal, danach klappt der Retry.
            self._crashed.add(material)
            self.ready = False
            raise SapUnavailable(f"Simulierter SAP-Absturz bei {material}")
        if self.latency_s:
            time.sleep(self.latency_s)
        src = self.source_dir / f"{material}.zip"
        if not src.exists():
            raise MaterialNotFound(
                f"{material}: kein Dokumentpaket vorhanden (Mock)")
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = target_dir / src.name
        shutil.copy2(src, dst)
        return dst

    def close(self) -> None:
        self.ready = False


# ======================================================================
# fake_session
# ======================================================================
# Nachbau einer SAP-GUI-Scripting-Session für Tests und Trockenläufe.
#
# Bildet die Teile der COM-API nach, die der Adapter nutzt (FindById, Text,
# Press, SendVKey, Busy, sbar …). Damit lässt sich der komplette Ablauf –
# Ablaufabspielen, Popup-Behandlung, Fehlerpfade, Download-Erkennung – ohne
# SAP-Installation prüfen. Wird ausschließlich in Tests und im Trockenlauf
# (`--sap-dry-run`) verwendet.



from pathlib import Path


class FakeElement:
    def __init__(self, session: "FakeSession", element_id: str,
                 kind: str = "generic"):
        self.session = session
        self.Id = element_id
        self.kind = kind
        self._text = ""
        self.Selected = False
        self.Key = ""
        self.CaretPosition = 0
        self.SelectedNode = ""

    # --- Eigenschaften -----------------------------------------------------
    @property
    def Text(self) -> str:
        return self._text

    @Text.setter
    def Text(self, value: str) -> None:
        self._text = value
        self.session.log.append(("set_text", self.Id, value))

    # --- Methoden ----------------------------------------------------------
    def Press(self) -> None:
        self.session.log.append(("press", self.Id, None))
        self.session._handle_press(self.Id)

    def Select(self) -> None:
        self.session.log.append(("select", self.Id, None))
        self.session._close_popup(self.Id)

    def SetFocus(self) -> None:
        self.session.log.append(("set_focus", self.Id, None))

    def Maximize(self) -> None:
        self.session.log.append(("maximize", self.Id, None))

    def SendVKey(self, key: int) -> None:
        self.session.log.append(("send_vkey", self.Id, key))
        self.session._handle_vkey(key)

    def DoubleClickNode(self, node: str) -> None:
        self.session.log.append(("double_click_node", self.Id, node))

    def __getattr__(self, name: str):
        """Unbekannte Scripting-Methoden generisch annehmen.

        Echte Grid- und Baum-Steuerelemente haben Dutzende Methoden
        (pressToolbarButton, setCurrentCell, selectItem …). Die Simulation
        nimmt jede davon an, protokolliert sie und löst – falls sie als
        Download-Auslöser konfiguriert ist – den simulierten Download aus.
        """
        if name.startswith("_"):
            raise AttributeError(name)

        def _generic(*args):
            self.session.log.append((f"call:{name}", self.Id, args))
            self.session._fire(self.Id, name)
            self.session._close_popup(self.Id)
            return None

        return _generic


class FakeStatusBar(FakeElement):
    def __init__(self, session: "FakeSession"):
        super().__init__(session, "wnd[0]/sbar", "statusbar")
        self.MessageType = ""

    @property
    def Text(self) -> str:
        return self._text

    @Text.setter
    def Text(self, value: str) -> None:
        self._text = value


class FakeInfo:
    def __init__(self, system: str = "P11"):
        self.SystemName = system
        self.Client = "100"
        self.User = "TESTUSER"
        self.Transaction = ""


class FakeSession:
    """Minimale SAP-Session für Tests.

    Parameter:
      download_target  Datei, die beim Auslösen des Downloads entsteht.
      download_bytes   Inhalt dieser Datei.
      popup_after      Element-ID, nach deren Press ein Popup erscheint.
      fail_on          Element-ID, deren Zugriff einen COM-Fehler auslöst.
      missing          Element-IDs, die es nicht gibt.
      status           (Text, Typ) für die Statuszeile nach dem Ausführen.
    """

    def __init__(self, *, download_target: Path | None = None,
                 download_bytes: bytes = b"PK\x03\x04 fake zip",
                 download_trigger: str | None = None,
                 popup_after: str | None = None,
                 fail_on: str | None = None,
                 missing: set[str] | None = None,
                 status: tuple[str, str] = ("", ""),
                 busy_cycles: int = 0):
        self.log: list[tuple[str, str, object]] = []
        self.elements: dict[str, FakeElement] = {}
        self.download_target = Path(download_target) if download_target else None
        self.download_bytes = download_bytes
        self.download_trigger = download_trigger
        self.popup_after = popup_after
        self.fail_on = fail_on
        self.missing = set(missing or ())
        self.open_popups: set[str] = set()
        self.alive = True
        self._busy_cycles = busy_cycles
        self.Info = FakeInfo()
        self.sbar = FakeStatusBar(self)
        self.sbar.Text, self.sbar.MessageType = status
        self.elements["wnd[0]/sbar"] = self.sbar

    # --- COM-Oberfläche ----------------------------------------------------
    @property
    def Busy(self) -> bool:
        if not self.alive:
            raise RuntimeError("Session ist tot (simulierter Absturz)")
        if self._busy_cycles > 0:
            self._busy_cycles -= 1
            return True
        return False

    def FindById(self, element_id: str, raise_missing: bool = True):
        if not self.alive:
            raise RuntimeError("Session ist tot (simulierter Absturz)")
        if self.fail_on and element_id == self.fail_on:
            raise RuntimeError(f"COM-Fehler an {element_id}")
        if element_id in self.missing:
            if raise_missing:
                raise RuntimeError(f"Element {element_id} nicht gefunden")
            return None
        # Popup-Elemente gibt es nur, solange das Popup offen ist.
        if element_id.startswith(("wnd[1]", "wnd[2]")):
            window = element_id.split("/")[0]
            if window not in self.open_popups:
                if raise_missing:
                    raise RuntimeError(f"Fenster {window} ist nicht offen")
                return None
        if element_id not in self.elements:
            self.elements[element_id] = FakeElement(self, element_id)
        return self.elements[element_id]

    # --- Simuliertes Verhalten --------------------------------------------
    def _handle_press(self, element_id: str) -> None:
        self._fire(element_id)
        self._close_popup(element_id)

    def _handle_vkey(self, key: int) -> None:
        self._fire(f"vkey:{key}")

    def _matches(self, trigger: str | None, element_id: str,
                 method: str | None) -> bool:
        """Passt der konfigurierte Auslöser auf diese Aktion?

        Erlaubt sind die Element-ID selbst, `ID:methode` und der reine
        Methodenname (z. B. "pressToolbarButton") sowie `vkey:<n>`.
        """
        if not trigger:
            return False
        if trigger == element_id:
            return True
        if method and trigger in (f"{element_id}:{method}", method):
            return True
        return False

    def _fire(self, element_id: str, method: str | None = None) -> None:
        """Simulierte Nebenwirkungen einer Aktion (Popup, Download).

        Wird von Press, SendVKey und jeder generischen Scripting-Methode
        aufgerufen, damit auch ALV-Grid-Auslöser wie
        `pressToolbarButton "DOWNLOAD"` einen Datei-Dialog öffnen.
        """
        if self._matches(self.popup_after, element_id, method):
            self.open_popups.add("wnd[1]")
        if self._matches(self.download_trigger, element_id, method):
            self._write_download()

    def _close_popup(self, element_id: str) -> None:
        if element_id.startswith("wnd[1]"):
            self.open_popups.discard("wnd[1]")
        elif element_id.startswith("wnd[2]"):
            self.open_popups.discard("wnd[2]")

    def _write_download(self) -> None:
        if self.download_target is None:
            return
        self.download_target.parent.mkdir(parents=True, exist_ok=True)
        self.download_target.write_bytes(self.download_bytes)

    def crash(self) -> None:
        """Simuliert einen SAP-Absturz: alle weiteren Zugriffe scheitern."""
        self.alive = False

    def open_popup(self, window: str = "wnd[1]") -> None:
        self.open_popups.add(window)

    # --- Auswertung für Tests ---------------------------------------------
    def actions(self) -> list[str]:
        return [a for a, _e, _v in self.log]

    def texts_of(self, element_id: str) -> list[object]:
        return [v for a, e, v in self.log if a == "set_text" and e == element_id]


# ========================================================================
# sap_cli
# ========================================================================
# Kommandozeilen-Werkzeuge für den SAP-Durchstich.
#
# --sap-import-vbs DATEI   Mitschnitt einlesen, Ablauf anzeigen und speichern
# --sap-show-flow          gespeicherten Ablauf anzeigen
# --sap-dry-run [MATNR]    Ablauf gegen eine simulierte Session abspielen
#                          (prüft Platzhalter und Reihenfolge ohne SAP)
# --sap-test MATNR         eine Materialnummer echt über SAP holen
# --sap-dump               Elementbaum des aktuellen SAP-Bildes ausgeben
import logging
import tempfile
from pathlib import Path


DEFAULT_FLOW_NAME = "ymatdocs_flow.yaml"


def import_vbs(vbs_path: Path, out_path: Path | None = None) -> int:
    pass  # (Import entfaellt - alles ein Modul)

    if not vbs_path.is_file():
        print(f"Datei nicht gefunden: {vbs_path}")
        return 2
    pass  # (Import entfaellt - alles ein Modul)

    target = out_path or _default_flow_path()
    flow, verstanden, zeilen = uebernehmen(vbs_path, target)
    print(describe(flow))
    print()
    print("Kurzfassung:")
    for zeile in zeilen:
        print(f"  {zeile}")
    print(f"\nAblauf gespeichert: {target}")
    print("Nächster Schritt: `drawing-checker --sap-dry-run 4711` "
          "(prüft den Ablauf ohne SAP), danach `--sap-test <echte Nummer>`.")
    if not flow.material_field:
        print("\nACHTUNG: Materialnummer-Feld wurde nicht erkannt. Bitte im "
              "YAML den betreffenden Schritt auf value: '{material}' setzen.")
        return 1
    return 0


def show_flow(flow_path: Path | None = None) -> int:
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    flow, source = load_flow(flow_path)
    if source is None:
        print("Kein importierter Ablauf gefunden – es greift der Notnagel.")
        print("Mit `--sap-import-vbs <datei.vbs>` einlesen.\n")
    else:
        print(f"Quelle: {source}\n")
    print(describe(flow))
    return 0 if source else 1


def dry_run(material: str = "4711", flow_path: Path | None = None) -> int:
    """Spielt den Ablauf gegen eine simulierte Session ab.

    Prüft ohne SAP: Sind alle Platzhalter gesetzt? Stimmt die Reihenfolge?
    Wird ein Download ausgelöst? Landet die Datei am erwarteten Ort?
    """
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    flow, source = load_flow(flow_path)
    print(f"Trockenlauf mit Ablauf: {source or 'NOTNAGEL (kein Import!)'}")
    with tempfile.TemporaryDirectory() as tmp:
        target_dir = Path(tmp) / "pakete"
        expected = target_dir / f"{material}.zip"
        popup_trigger, download_trigger = _dry_run_triggers(flow)
        session = FakeSession(download_target=expected,
                              popup_after=popup_trigger,
                              download_trigger=download_trigger)
        steps_log: list[str] = []

        def on_step(index, step, resolved):
            if step.action == "call":
                detail = "." + step.method + "(" + ", ".join(
                    repr(a) for a in step.args) + ")"
            elif step.action == "set_prop":
                detail = f".{step.member} = {resolved!r}"
            else:
                detail = "" if resolved is None else f" = {resolved!r}"
            steps_log.append(f"  {index + 1:3}. {step.action:<18} "
                             f"{step.element}{detail}")

        try:
            result = run_ymatdocs(session, material, target_dir,
                                  flow_path=flow_path, watch_dirs=[],
                                  on_step=on_step, timeout_s=10)
        except Exception as exc:
            print("\n".join(steps_log))
            print(f"\nTrockenlauf FEHLGESCHLAGEN: {exc}")
            if source is None:
                print("Ursache: Es ist kein .vbs-Mitschnitt importiert – der "
                      "Notnagel-Ablauf kann nicht funktionieren.\n"
                      "Zuerst `--sap-import-vbs <datei.vbs>` ausführen.")
            return 1
        print("\n".join(steps_log))
        print(f"\nTrockenlauf ok – Paket würde liegen unter: {result.name}")
        print(_dry_run_summary(flow, session, material, popup_trigger,
                               download_trigger))

    unresolved = [s for s in flow.steps
                  if isinstance(s.value, str) and "{" in s.value
                  and s.value not in ("{material}", "{target_dir}",
                                      "{filename}", "{target_path}")]
    if unresolved:
        print("\nWARNUNG: unbekannte Platzhalter in Schritten: "
              + ", ".join(s.value for s in unresolved))
        return 1
    if not flow.material_field:
        print("\nWARNUNG: Kein Materialnummer-Feld im Ablauf markiert.")
        return 1
    if source is None:
        print("\nACHTUNG: Geprüft wurde nur der Notnagel-Ablauf. Erst mit "
              "dem echten Mitschnitt (--sap-import-vbs) ist der Trockenlauf "
              "aussagekräftig.")
        return 1
    return 0


def sap_test(material: str, system: str = "P11",
             flow_path: Path | None = None,
             out_dir: Path | None = None) -> int:
    """Holt eine einzelne Materialnummer über die echte SAP-Verbindung."""
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    out = out_dir or Path.cwd() / "sap_test"
    out.mkdir(parents=True, exist_ok=True)
    adapter = SapGuiAdapter(connection_name=system, flow_path=flow_path,
                            diagnose_dir=out)
    try:
        adapter.ensure_ready()
    except Exception as exc:
        print(f"Verbindung fehlgeschlagen: {exc}")
        return 2
    print(describe_session(adapter.session))
    try:
        zip_path = adapter.fetch_package(material, out)
    except Exception as exc:
        print(f"\nAbruf fehlgeschlagen: {exc}")
        try:
            report = diagnose_failure(adapter.session, material, out)
            print(f"Diagnose geschrieben: {report}")
            print("Darin steht der Elementbaum des aktuellen Bildes – daraus "
                  "lassen sich die richtigen Element-IDs ablesen.")
        except Exception:
            pass
        return 1

    size = zip_path.stat().st_size
    print(f"\nPaket geladen: {zip_path} ({size} Bytes)")
    _describe_package(zip_path)
    return 0


def dump_screen_cli(system: str = "P11") -> int:
    dump = dump_screen_cli
    pass  # (Import entfaellt - alles ein Modul)

    adapter = SapGuiAdapter(connection_name=system)
    try:
        adapter.ensure_ready()
    except Exception as exc:
        print(f"Verbindung fehlgeschlagen: {exc}")
        return 2
    print(describe_session(adapter.session))
    print()
    print(dump(adapter.session))
    for window in ("wnd[1]", "wnd[2]"):
        try:
            if adapter.session.FindById(window, False) is not None:
                print(f"\n--- Dialog {window} ---")
                print(dump(adapter.session, window))
        except Exception:
            pass
    return 0


# ---------------------------------------------------------------- Intern
def _default_flow_path() -> Path:
    pass  # (Import entfaellt - alles ein Modul)

    for directory in rules_dirs():
        if directory.name == "regeln":
            return directory / DEFAULT_FLOW_NAME
    return Path.cwd() / "regeln" / DEFAULT_FLOW_NAME


def _download_trigger(flow) -> str | None:
    """Element/Aktion, die den Download anstößt (Auslöseschritt des Ablaufs)."""
    if flow.download_step_index is None:
        return None
    step = flow.steps[flow.download_step_index]
    if step.action == "send_vkey":
        return f"vkey:{step.value}"
    return step.element


def _dialog_confirm_trigger(flow) -> str | None:
    """Schaltfläche, mit der der Datei-Dialog bestätigt wird.

    In SAP entsteht die Datei erst, wenn im Dialog gespeichert wird – der
    Trockenlauf bildet das nach, damit auch das Füllen von Pfad und
    Dateiname geprüft wird.
    """
    last = None
    for step in flow.steps:
        if step.element.startswith("wnd[1]") and step.action in (
                "press", "call", "send_vkey"):
            last = (f"vkey:{step.value}" if step.action == "send_vkey"
                    else step.element)
    return last


def _dry_run_triggers(flow) -> tuple[str | None, str | None]:
    """(Popup-Auslöser, Download-Auslöser) für die simulierte Session.

    Gibt es im Ablauf einen Datei-Dialog, öffnet der Auslöseschritt das
    Fenster wnd[1] und erst dessen Bestätigung schreibt die Datei. Ohne
    Dialog (stiller Download) schreibt der Auslöseschritt direkt.
    """
    trigger = _download_trigger(flow)
    confirm = _dialog_confirm_trigger(flow)
    if confirm:
        return trigger, confirm
    return trigger, trigger


def _dry_run_summary(flow, session, material: str,
                     popup_trigger: str | None,
                     download_trigger: str | None) -> str:
    """Kurzbericht: Was hat der Ablauf tatsächlich getan?"""
    written = [(e, v) for a, e, v in session.log if a == "set_text"]
    material_fields = [e for e, v in written if str(v) == material]
    lines = ["\nZusammenfassung:",
             f"  Materialnummer geschrieben in: "
             + (", ".join(material_fields) or "NIRGENDS (!)"),
             f"  Download ausgelöst durch: {popup_trigger or 'unbekannt'}"]
    if download_trigger and download_trigger != popup_trigger:
        lines.append(f"  Datei-Dialog bestätigt mit: {download_trigger}")
    else:
        lines.append("  Kein Datei-Dialog im Ablauf – stiller Download in den "
                     "SAP-Standardordner wird überwacht.")
    dialog_fields = [e for e, v in written
                     if e.startswith(("wnd[1]", "wnd[2]"))]
    if dialog_fields:
        lines.append(f"  Dialogfelder gefüllt: {', '.join(dialog_fields)}")
    if not material_fields:
        lines.append("  ACHTUNG: Die Materialnummer landet in keinem Feld – "
                     "im YAML den richtigen Schritt auf '{material}' setzen.")
    return "\n".join(lines)


def _describe_package(zip_path: Path) -> None:
    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        print("Inhalt: KEINE gültige ZIP-Datei – bitte prüfen, ob der "
              "Download vollständig war.")
        return
    print(f"Inhalt ({len(names)} Dateien):")
    for name in names[:20]:
        print(f"  {name}")
    pdfs = [n for n in names if n.lower().endswith(".pdf")]
    steps = [n for n in names if n.lower().endswith((".stp", ".step"))]
    print(f"\n-> {len(pdfs)} PDF, {len(steps)} STEP erkannt.")
    if not pdfs:
        print("   ACHTUNG: kein PDF im Paket – Prüfung wäre nicht möglich.")


# ========================================================================
# ablauf
# ========================================================================
# Orchestrator: arbeitet die Materialliste vollautomatisch ab.
#
# Läuft in einem Worker-Thread (GUI bleibt bedienbar). Fortschritt und
# Ergebnisse gehen über Callbacks nach außen; Pause/Abbruch über Events.
# Nach jeder Materialnummer werden Zustand und Excel gespeichert – der Lauf
# ist damit jederzeit fortsetzbar.
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

_SapAbgebrochen = Abgebrochen
pkg = sys.modules[__name__]


MAX_JOB_RETRIES = 2   # technische Retries je Materialnummer (nach SAP-Recovery)


class _Abgebrochen(Exception):
    """Der Anwender hat abgebrochen – die laufende Nummer bleibt offen."""


@dataclass
class Progress:
    total: int = 0
    done: int = 0
    batch: int = 0          # laufender Block (1-basiert)
    batches: int = 0        # Anzahl Blöcke insgesamt
    current: str = ""
    ok: int = 0
    findings: int = 0
    failed: int = 0
    message: str = ""
    eta_s: float | None = None   # geschätzte Restdauer


@dataclass
class Callbacks:
    """GUI-Hooks; alle optional und aus dem Worker-Thread aufgerufen."""

    on_progress: Callable[[Progress], None] = lambda p: None
    on_result: Callable[[MaterialResult], None] = lambda r: None
    on_log: Callable[[str], None] = lambda m: None
    on_finished: Callable[[Progress], None] = lambda p: None


class Orchestrator:
    def __init__(self, config: RunConfig, adapter: SapAdapter,
                 callbacks: Callbacks | None = None, resume: bool = False):
        self.config = config
        self.adapter = adapter
        self.cb = callbacks or Callbacks()
        self.pause_event = threading.Event()   # gesetzt = pausiert
        self.stop_event = threading.Event()
        self.progress = Progress()

        self.run_dir = self._resolve_run_dir(resume)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "pakete").mkdir(exist_ok=True)
        self.state = (RunState.load(config, self.run_dir) if resume
                      else RunState(config, self.run_dir))
        self.profile = load_profile(config.material_group)
        self.report_path: Path | None = None
        self._durations: list[float] = []
        self._thread: threading.Thread | None = None
        self.guard = DiskGuard(self.run_dir / "pakete",
                               min_free_mb=config.min_free_mb)
        self._freed_mb = 0.0

    def _resolve_run_dir(self, resume: bool) -> Path:
        """Ordner des Laufs: fortsetzen nur, wenn er zur Auswahl passt."""
        base = self.config.output_dir
        if resume:
            treffer = finde_fortsetzbaren_lauf(self.config)
            if treffer:
                ordner, fertig, _gesamt = treffer
                log.info("Setze Lauf %s fort (%d bereits geprüft)",
                         ordner.name, fertig)
                return ordner
            log.info("Kein passender Lauf zum Fortsetzen gefunden – neuer Lauf")
        return base / time.strftime("lauf_%Y%m%d_%H%M%S")

    # ------------------------------------------------------------- Steuerung
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="pruef-worker",
                                        daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ------------------------------------------------------------ Hauptlauf
    def _run(self) -> None:
        # Lauf-Logdatei im Ergebnisordner (zusätzlich zum globalen Log).
        run_log = logging.FileHandler(self.run_dir / "lauf.log",
                                      encoding="utf-8")
        run_log.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(run_log)
        try:
            self._run_inner()
        except Exception as exc:  # letzte Verteidigungslinie des Threads
            log.exception("Prüflauf abgebrochen")
            self.progress.message = f"Lauf abgebrochen: {exc}"
            self.cb.on_log(self.progress.message)
        finally:
            logging.getLogger().removeHandler(run_log)
            run_log.close()
            self.cb.on_finished(self.progress)

    def _run_inner(self) -> None:
        # Der Adapter darf wissen, wann abgebrochen wurde: dann bricht auch
        # ein laufender SAP-Schritt oder das Warten auf den Download ab,
        # statt bis zum Zeitablauf weiterzulaufen.
        try:
            self.adapter.stop_event = self.stop_event
        except Exception:
            pass
        materials = read_materials(self.config)
        workbook = ResultWorkbook(self.config)
        self.progress.total = len(materials)
        self._log(f"{len(materials)} Materialnummern in Spalte "
                  f"{self.config.material_column} gefunden")

        # Bereits erledigte (Resume) vorab in die Zählung übernehmen.
        todo: list[tuple[int, str]] = []
        for row, material in materials:
            if self.state.is_done(row, material):
                result = self.state.results[f"{row}:{material}"]
                self._count(result)
                self.progress.done += 1
                self.cb.on_result(result)
            else:
                todo.append((row, material))
        if self.progress.done:
            self._log(f"Fortsetzen: {self.progress.done} bereits geprüft, "
                      f"{len(todo)} offen")

        self._log(f"Freier Speicherplatz: {free_mb(self.run_dir):.0f} MB")
        offen: list[tuple[int, str]] = list(todo)
        # Blockweise abarbeiten: nach jedem Block wird gesichert, aufgeräumt
        # und ein Zwischenbericht geschrieben. Bei einem Abbruch (Absturz,
        # Feierabend, SAP-Wartung) ist damit höchstens der laufende Block
        # betroffen, alles davor ist fertig dokumentiert.
        groesse = self.config.batch_size or len(todo) or 1
        self.progress.batches = max((len(todo) + groesse - 1) // groesse, 0)
        for row, material in todo:
            self.progress.batch = min(
                self.progress.done // groesse + 1, self.progress.batches) \
                if self.progress.batches else 0
            if self.stop_event.is_set():
                self._log("Lauf vom Anwender abgebrochen")
                break
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            try:
                hinweis = self.guard.check()
            except DiskFull as exc:
                self.progress.message = str(exc)
                self._log(str(exc))
                break
            if hinweis:
                self._log(hinweis)

            self.progress.current = material
            self.cb.on_progress(self.progress)
            try:
                result = self._process_with_retries(row, material)
            except _Abgebrochen:
                # Abbruch mitten in der Materialnummer: NICHT als Ergebnis
                # festhalten, sonst gilt sie beim Fortsetzen als erledigt.
                self._log(f"Abgebrochen bei {material} – diese Nummer wird "
                          f"beim Fortsetzen erneut geprüft")
                break

            self.state.record(result)
            if (row, material) in offen:
                offen.remove((row, material))
            workbook.write_result(result)
            workbook.save()
            self._count(result)
            self.progress.done += 1
            self._durations.append(max(result.duration_s, 0.1))
            remaining = self.progress.total - self.progress.done
            if self._durations and remaining > 0:
                avg = sum(self._durations) / len(self._durations)
                self.progress.eta_s = avg * remaining
            else:
                self.progress.eta_s = None
            self.cb.on_result(result)
            self.cb.on_progress(self.progress)

            if self.config.batch_size and not self.progress.done % groesse:
                self._blockwechsel(workbook)

        # Abschluss: Zusammenfassung in Excel + HTML-Bericht
        all_results = list(self.state.results.values())
        try:
            workbook.finalize(all_results, offen)
            workbook.save()
        except Exception:
            log.exception("Excel-Zusammenfassung fehlgeschlagen")
        try:
            self._write_findings_csv(all_results)
        except Exception:
            log.exception("findings.csv fehlgeschlagen")
        try:
            pass  # (Import entfaellt - alles ein Modul)

            self.report_path = write_html_report(
                self.config, all_results, self.run_dir, self.profile.name,
                duration_s=time.time() - self.state.started)
            self._log(f"Bericht erstellt: {self.report_path.name}")
        except Exception:
            log.exception("HTML-Bericht fehlgeschlagen")

        try:
            self.adapter.close()
        except Exception:
            log.debug("Adapter ließ sich nicht sauber schließen", exc_info=True)

        self.progress.current = ""
        self.progress.message = (
            f"Fertig: {self.progress.ok} ok, {self.progress.findings} mit "
            f"Findings, {self.progress.failed} fehlgeschlagen "
            f"(von {self.progress.total})")
        if self._freed_mb:
            self._log(f"Aufgeräumt: {self._freed_mb:.0f} MB Pakete gelöscht, "
                      f"{free_mb(self.run_dir):.0f} MB frei")
        self._log(self.progress.message)

    def _blockwechsel(self, workbook) -> None:
        """Zwischenstand nach einem Block sichern und aufräumen.

        Gesichert wird ohnehin nach jeder Materialnummer; hier kommen die
        teureren Dinge dazu, die man nicht jedes Mal machen will:
        Zwischenbericht, Speicher zurückgeben, SAP-Session aufräumen.
        """
        nummer, gesamt = self.progress.batch, self.progress.batches
        self._log(f"Block {nummer} von {gesamt} abgeschlossen "
                  f"({self.progress.done}/{self.progress.total} geprüft)")
        try:
            workbook.save()
        except Exception:
            log.exception("Zwischenspeichern der Excel fehlgeschlagen")
        try:
            self._write_zwischenbericht()
        except Exception:
            log.debug("Zwischenbericht fehlgeschlagen", exc_info=True)
        # SAP zurück auf einen sauberen Stand bringen (Dialoge schließen,
        # Fensterzahl prüfen) - dafür gibt es einen optionalen Haken am
        # Adapter; der Mock-Adapter kennt ihn nicht.
        haken = getattr(self.adapter, "blockwechsel", None)
        if callable(haken):
            try:
                haken()
            except Exception:
                log.warning("SAP-Aufräumen zwischen den Blöcken "
                            "fehlgeschlagen", exc_info=True)
        release_memory()
        if self.config.batch_pause_s:
            time.sleep(self.config.batch_pause_s)

    def _write_zwischenbericht(self) -> None:
        pass  # (Import entfaellt - alles ein Modul)

        self.report_path = write_html_report(
            self.config, list(self.state.results.values()), self.run_dir,
            self.profile.name, duration_s=time.time() - self.state.started)

    def _process_with_retries(self, row: int, material: str) -> MaterialResult:
        last_error = ""
        for attempt in range(1, MAX_JOB_RETRIES + 2):
            if self.stop_event.is_set():
                raise _Abgebrochen()
            try:
                return self._process_one(row, material)
            except (_Abgebrochen, _SapAbgebrochen):
                raise _Abgebrochen()
            except SapUnavailable as exc:
                last_error = str(exc)
                self._log(f"{material}: SAP nicht verfügbar ({exc}) – "
                          f"Recovery, Versuch {attempt}")
                try:
                    self.adapter.ensure_ready()
                except SapUnavailable as exc2:
                    last_error = str(exc2)
            except MaterialNotFound as exc:
                result = MaterialResult(material=material, row=row,
                                        status=JobStatus.FINDINGS)
                result.findings.append(_finding_no_package(str(exc)))
                return result
            except Exception as exc:
                if self.stop_event.is_set():
                    raise _Abgebrochen() from exc
                log.error("Unerwarteter Fehler bei %s:\n%s", material,
                          traceback.format_exc())
                last_error = f"{type(exc).__name__}: {exc}"
                break
        return MaterialResult(material=material, row=row,
                              status=JobStatus.FAILED, error=last_error)

    # ------------------------------------------------- Eine Materialnummer
    def _process_one(self, row: int, material: str) -> MaterialResult:
        """Eine Materialnummer holen, prüfen und danach aufräumen.

        Das Paket wird nach der Prüfung gelöscht (sofern nicht
        `keep_packages`): Bild, Findings und Bericht liegen dann schon im
        Ergebnisordner, das ZIP wird nicht mehr gebraucht. Ohne das wächst
        ein Lauf über eine ganze Materialgruppe um Gigabyte.
        """
        zip_dir = self.run_dir / "pakete"
        zip_path = self.adapter.fetch_package(material, zip_dir)
        content = None
        try:
            try:
                content = pkg.extract_package(zip_path, zip_dir, material)
            except pkg.PackageError as exc:
                raise MaterialNotFound(str(exc)) from exc
            return self._check_package(row, material, content)
        finally:
            freed = cleanup_package(
                content.work_dir if content else None, zip_path,
                keep=self.config.keep_packages)
            self._freed_mb += freed
            # Nach jeder Materialnummer aufräumen: Renderpuffer und
            # OpenCascade-Objekte belegen sonst dauerhaft Speicher.
            release_memory()

    def _check_package(self, row: int, material: str,
                       content: pkg.PackageContent) -> MaterialResult:
        t0 = time.time()
        result = MaterialResult(material=material, row=row,
                                status=JobStatus.RUNNING)

        if content.drawing_pdf is None:
            result.status = JobStatus.FINDINGS
            result.findings.append(_finding_no_package(
                "Kein PDF im YMATDOCS-Paket – Zeichnung fehlt"))
            result.duration_s = time.time() - t0
            return result

        with DrawingPdf(content.drawing_pdf) as pdf:
            ctx = CheckContext(material=material, pdf=pdf, package=content,
                               profile=self.profile)
            if len(content.pdfs) > 1 and self.profile.enabled("DOC.MULTI_PDF"):
                ctx.add("DOC.MULTI_PDF",
                        f"{len(content.pdfs)} PDFs im Paket – geprüft wurde "
                        f"„{content.drawing_pdf.name}“")
            has_text = bool(pdf.words())
            if not has_text:
                ctx.add("DOC.NO_TEXT",
                        "Kein auswertbarer Text (kein Textlayer, OCR nicht "
                        "verfügbar) – textbasierte Checks entfallen, bitte "
                        "manuell prüfen")
            elif pdf.ocr_used:
                result.ocr_used = True
                ctx.add("DOC.OCR",
                        "Zeichnung ohne Textlayer – Prüfung basiert auf OCR "
                        "(eingeschränkte Zuverlässigkeit)",
                        detail=pdf.ocr_note() + ". Unsichere Zahlen werden "
                               "nicht als Maß übernommen; fehlende Angaben "
                               "können auch an der Erkennung liegen – bei "
                               "Beanstandungen die Zeichnung ansehen.")

            # Prüfdokumentation: Änderungsdatum + Fertigungsverfahren
            pass  # (Import entfaellt - alles ein Modul)
            pass  # (Import entfaellt - alles ein Modul)

            result.drawing_rev_date = extract_revision_date(pdf)
            result.processes = detect_processes(pdf)

            dims = []
            scale_note = ""
            mass_note = ""
            if has_text:
                run_drawing_checks(ctx)
                check_language(ctx)
                dims = extract_dimensions(
                    pdf, float(self.profile.params.get("max_plausible_dim", 6000)))
                # Tiefenprüfungen auf Basis der extrahierten Maße
                pass  # (Import entfaellt - alles ein Modul)
                pass  # (Import entfaellt - alles ein Modul)
                pass  # (Import entfaellt - alles ein Modul)
                pass  # (Import entfaellt - alles ein Modul)
                pass  # (Import entfaellt - alles ein Modul)
                pass  # (Import entfaellt - alles ein Modul)

                run_gps_checks(ctx, dims)
                run_dimension_checks(ctx, dims)
                run_process_checks(ctx, dims)
                run_purchasing_checks(ctx, dims)
                run_doc_checks(ctx)
                mass_note = check_mass_plausibility(ctx, dims)
                pass  # (Import entfaellt - alles ein Modul)

                scale_note = check_scale_consistency(ctx, dims)
            result.step_summary = check_step(ctx, dims)
            if has_text:
                result.step_summary = " | ".join(
                    x for x in (result.step_summary, scale_note, mass_note)
                    if x)

            result.findings = ctx.findings
            shot = self.run_dir / f"{pkg._safe_name(material)}.png"
            try:
                result.screenshot = annotate(pdf, result, shot)
            except Exception:
                log.exception("Annotation fehlgeschlagen für %s", material)

        worst = result.worst_severity
        result.status = (JobStatus.OK if worst is None or worst <= Severity.INFO
                         else JobStatus.FINDINGS)
        result.duration_s = time.time() - t0
        return result

    def _write_findings_csv(self, results: list[MaterialResult]) -> None:
        """Maschinenlesbarer Export je Lauf – Grundlage für KPI-Auswertungen
        über mehrere Läufe (häufigste Mängel, Lieferanten-/Gruppenvergleich)."""
        import csv

        pass  # (Import entfaellt - alles ein Modul)

        path = self.run_dir / "findings.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Materialnummer", "Excel-Zeile", "Regel", "Bewertung",
                        "Text", "Detail", "Geprüft am", "Status"])
            for r in results:
                for f in r.sorted_findings():
                    w.writerow([r.material, r.row, f.code,
                                SEVERITY_LABEL[f.severity], f.text, f.detail,
                                r.checked_at, r.status.value])

    # ---------------------------------------------------------------- Utils
    def _wait_if_paused(self) -> None:
        if self.pause_event.is_set():
            self._log("Pausiert …")
            while self.pause_event.is_set() and not self.stop_event.is_set():
                time.sleep(0.2)
            if not self.stop_event.is_set():
                self._log("Fortgesetzt")

    def _count(self, result: MaterialResult) -> None:
        if result.status == JobStatus.OK:
            self.progress.ok += 1
        elif result.status == JobStatus.FINDINGS:
            self.progress.findings += 1
        elif result.status == JobStatus.FAILED:
            self.progress.failed += 1

    def _log(self, msg: str) -> None:
        log.info(msg)
        self.cb.on_log(msg)


def _finding_no_package(text: str):
    pass  # (Import entfaellt - alles ein Modul)

    return Finding(code="DOC.NO_PDF", severity=Severity.BLOCKER, text=text)


# ========================================================================
# gui
# ========================================================================
# Hauptfenster: Drei-Schritte-Wizard für nicht-technische Anwender.
#
#   Schritt 1: Excel-Datei wählen (Dialog oder Drag & Drop) + Blatt wählen
#   Schritt 2: Spalte mit den Materialnummern ANKLICKEN (Vorschau der Tabelle)
#   Schritt 3: Prüfung läuft – Fortschritt, Ampel-Liste, Pause/Abbruch
#
# Der Orchestrator läuft im Worker-Thread; seine Callbacks werden über
# Qt-Signale in den GUI-Thread gehoben.
import logging
import subprocess
import sys
from pathlib import Path
import importlib.util as _ilu
_GUI_VERFUEGBAR = _ilu.find_spec("PySide6") is not None

if _GUI_VERFUEGBAR:


    import openpyxl
    from openpyxl.utils import get_column_letter
    from PySide6.QtCore import QObject, QSettings, Qt, Signal
    from PySide6.QtGui import QColor, QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
        QSpinBox,
        QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
        QProgressBar, QPushButton, QSplitter, QStackedWidget, QTabWidget,
        QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    )



    PREVIEW_ROWS = 50

    STATUS_COLOR = {
        JobStatus.OK: QColor(70, 160, 70),
        JobStatus.FINDINGS: QColor(230, 145, 0),
        JobStatus.FAILED: QColor(200, 30, 30),
        JobStatus.SKIPPED: QColor(150, 150, 150),
    }


    def klartext(exc: Exception) -> str:
        """Technische Ausnahme in eine Anweisung für Anwender übersetzen.

        Nicht-technische Anwender können mit „PermissionError [Errno 13]"
        nichts anfangen – wohl aber mit „Die Datei ist noch in Excel geöffnet".
        """
        text = str(exc)
        if isinstance(exc, PermissionError) or "Errno 13" in text:
            return ("Die Datei ist gesperrt – vermutlich noch in Excel geöffnet. "
                    "Bitte schließen und erneut versuchen.")
        if isinstance(exc, FileNotFoundError):
            return ("Die Datei wurde nicht gefunden. Wurde sie verschoben oder "
                    "umbenannt?")
        if "No space left" in text or "Errno 28" in text:
            return ("Auf dem Laufwerk ist kein Platz mehr. Bitte Speicherplatz "
                    "freigeben; der Lauf lässt sich danach fortsetzen.")
        if "pywin32" in text or "win32com" in text:
            return ("Die SAP-Anbindung fehlt (pywin32). Bitte an die "
                    "Systembetreuung wenden.")
        if "Scripting" in text or "scripting" in text:
            return ("SAP GUI Scripting ist nicht freigeschaltet. In SAP Logon "
                    "unter Optionen → Barrierefreiheit & Skripting aktivieren.")
        if "not a zip file" in text.lower() or "BadZipFile" in text:
            return ("Das heruntergeladene Paket ist unvollständig. Bitte den "
                    "Lauf für diese Materialnummer wiederholen.")
        return text


    class WorkerBridge(QObject):
        """Hebt Orchestrator-Callbacks (Worker-Thread) in den GUI-Thread."""

        progress = Signal(object)
        result = Signal(object)
        log_line = Signal(str)
        finished = Signal(object)

        def callbacks(self) -> Callbacks:
            return Callbacks(
                on_progress=self.progress.emit,
                on_result=self.result.emit,
                on_log=self.log_line.emit,
                on_finished=self.finished.emit,
            )


    class MainWindow(QMainWindow):
        def __init__(self, make_adapter, profiles: list[str],
                     mock_default: Path | None = None):
            """make_adapter(config: RunConfig) -> SapAdapter (echtes SAP oder Mock)."""
            super().__init__()
            self.make_adapter = make_adapter
            self.mock_default = mock_default
            self.setWindowTitle("Drawing Checker – Zeichnungsprüfung")
            self.resize(1080, 720)
            self.setAcceptDrops(True)

            self.excel_path: Path | None = None
            self.selected_column: str | None = None
            self.orchestrator: Orchestrator | None = None
            self.adapter: SapAdapter | None = None
            self.run_dir: Path | None = None

            self.stack = QStackedWidget()
            self.setCentralWidget(self.stack)
            self.stack.addWidget(self._build_step1(profiles))
            self.stack.addWidget(self._build_step2())
            self.stack.addWidget(self._build_step3())
            self._load_settings()
            self._flow_status()

        # ================================================== Schritt 1: Datei
        def _build_step1(self, profiles: list[str]) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addStretch()
            title = QLabel("<h2>Schritt 1 von 3 – Excel-Datei wählen</h2>")
            title.setAlignment(Qt.AlignCenter)
            lay.addWidget(title)
            hint = QLabel("Die Materialliste Ihrer Materialgruppe (.xlsx) hierher "
                          "ziehen oder über den Button auswählen.")
            hint.setAlignment(Qt.AlignCenter)
            lay.addWidget(hint)

            btn = QPushButton("Datei auswählen …")
            btn.setFixedWidth(220)
            btn.clicked.connect(self._pick_file)
            row = QHBoxLayout()
            row.addStretch(); row.addWidget(btn); row.addStretch()
            lay.addLayout(row)

            self.lbl_file = QLabel("")
            self.lbl_file.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.lbl_file)

            form = QHBoxLayout()
            form.addStretch()
            form.addWidget(QLabel("Tabellenblatt:"))
            self.cmb_sheet = QComboBox()
            self.cmb_sheet.setMinimumWidth(180)
            form.addWidget(self.cmb_sheet)
            form.addSpacing(20)
            form.addWidget(QLabel("Materialgruppe (Regelprofil):"))
            self.cmb_profile = QComboBox()
            self.cmb_profile.addItems(profiles)
            form.addWidget(self.cmb_profile)
            form.addStretch()
            lay.addLayout(form)

            # SAP-Ablauf: alles, was das Programm über die Transaktion weiß,
            # kommt aus dem .vbs-Mitschnitt. Ohne ihn geht im Echtbetrieb
            # nichts - deshalb steht er gleich im ersten Schritt.
            sap = QHBoxLayout()
            sap.addStretch()
            self.lbl_flow = QLabel("")
            sap.addWidget(self.lbl_flow)
            sap.addSpacing(12)
            btn_flow = QPushButton("SAP-Mitschnitt (.vbs) einlesen …")
            btn_flow.clicked.connect(self._pick_vbs)
            sap.addWidget(btn_flow)
            sap.addStretch()
            lay.addLayout(sap)

            opts = QHBoxLayout()
            opts.addStretch()
            self.chk_resume = QCheckBox("Letzten Lauf fortsetzen")
            opts.addWidget(self.chk_resume)
            opts.addSpacing(20)
            self.chk_mock = QCheckBox("Testmodus (Mockdaten statt SAP)")
            self.chk_mock.setChecked(self.mock_default is not None)
            opts.addWidget(self.chk_mock)
            opts.addSpacing(20)
            opts.addWidget(QLabel("SAP-System:"))
            self.txt_system = QLineEdit("P11")
            self.txt_system.setFixedWidth(70)
            opts.addWidget(self.txt_system)
            opts.addSpacing(20)
            opts.addWidget(QLabel("Blockgröße:"))
            self.spn_batch = QSpinBox()
            self.spn_batch.setRange(0, 500)
            self.spn_batch.setValue(25)
            self.spn_batch.setFixedWidth(70)
            self.spn_batch.setToolTip(
                "Nach je so vielen Materialnummern wird ein Zwischenstand "
                "gesichert (Excel, Bericht) und SAP aufgeräumt.\n"
                "0 = alles am Stück.")
            opts.addWidget(self.spn_batch)
            opts.addSpacing(12)
            btn_test = QPushButton("Verbindung testen")
            btn_test.clicked.connect(self._test_connection)
            opts.addWidget(btn_test)
            opts.addStretch()
            lay.addLayout(opts)

            nxt = QPushButton("Weiter  ➜")
            nxt.setFixedWidth(160)
            nxt.clicked.connect(self._goto_step2)
            row2 = QHBoxLayout()
            row2.addStretch(); row2.addWidget(nxt); row2.addStretch()
            lay.addLayout(row2)
            lay.addStretch()
            return w

        def dragEnterEvent(self, e):
            if e.mimeData().hasUrls():
                e.acceptProposedAction()

        def dropEvent(self, e):
            for url in e.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in (".xlsx", ".xlsm"):
                    self._set_file(p)
                    return

        def _pick_file(self):
            name, _ = QFileDialog.getOpenFileName(
                self, "Materialliste wählen", "", "Excel-Dateien (*.xlsx *.xlsm)")
            if name:
                self._set_file(Path(name))

        def _set_file(self, path: Path):
            try:
                wb = openpyxl.load_workbook(path, read_only=True)
                sheets = wb.sheetnames
                wb.close()
            except Exception as exc:
                QMessageBox.warning(self, "Datei nicht lesbar",
                                    "Die Datei konnte nicht geöffnet werden:\n"
                                    + klartext(exc))
                return
            self.excel_path = path
            self.lbl_file.setText(f"<b>{path.name}</b>")
            self.cmb_sheet.clear()
            self.cmb_sheet.addItems(sheets)

        def _test_connection(self):
            """Verbindungstest ohne Prüflauf – für den Durchstich mit SAP."""
            if self.excel_path is None:
                # Config braucht einen Pfad; für den reinen Test genügt ein Dummy.
                self.excel_path = Path("verbindungstest.xlsx")
                dummy = True
            else:
                dummy = False
            try:
                cfg = self._make_config(preview=True)
                adapter = self.make_adapter(cfg)
                adapter.ensure_ready()
                adapter.close()
                QMessageBox.information(
                    self, "Verbindungstest",
                    ("Mockmodus bereit (Testdatenordner gefunden)."
                     if cfg.mock_source else
                     f"Verbindung zu {cfg.sap_connection} steht – Session "
                     f"gefunden bzw. Anmeldung erfolgreich."))
            except Exception as exc:
                QMessageBox.critical(
                    self, "Verbindungstest",
                    f"Verbindung nicht möglich:\n{exc}\n\nSAP Logon prüfen "
                    "(läuft es? Scripting aktiviert?) und erneut testen.")
            finally:
                if dummy:
                    self.excel_path = None

        def _goto_step2(self):
            if self.excel_path is None:
                QMessageBox.information(self, "Datei fehlt",
                                        "Bitte zuerst eine Excel-Datei auswählen.")
                return
            self._fill_preview()
            self.stack.setCurrentIndex(1)

        # ============================================== Schritt 2: Spaltenwahl
        def _build_step2(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addWidget(QLabel(
                "<h2>Schritt 2 von 3 – Spalte mit den Materialnummern anklicken</h2>"))
            self.lbl_colinfo = QLabel(
                "Klicken Sie auf die Spaltenüberschrift der Materialnummern.")
            lay.addWidget(self.lbl_colinfo)

            self.table = QTableWidget()
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectColumns)
            self.table.setSelectionMode(QTableWidget.SingleSelection)
            self.table.horizontalHeader().sectionClicked.connect(self._column_clicked)
            self.table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeToContents)
            lay.addWidget(self.table, stretch=1)

            row = QHBoxLayout()
            back = QPushButton("⬅  Zurück")
            back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
            row.addWidget(back)
            row.addStretch()
            self.btn_start = QPushButton("Prüfung starten  ➜")
            self.btn_start.setEnabled(False)
            self.btn_start.setStyleSheet("font-weight: bold; padding: 6px 18px;")
            self.btn_start.clicked.connect(self._start_run)
            row.addWidget(self.btn_start)
            lay.addLayout(row)
            return w

        def _fill_preview(self):
            wb = openpyxl.load_workbook(self.excel_path, read_only=True,
                                        data_only=True)
            ws = wb[self.cmb_sheet.currentText()]
            rows = []
            for r, row in enumerate(ws.iter_rows(values_only=True)):
                rows.append(row)
                if r >= PREVIEW_ROWS:
                    break
            wb.close()
            ncols = max((len(r) for r in rows), default=0)
            self.table.clear()
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(ncols)
            self.table.setHorizontalHeaderLabels(
                [get_column_letter(c + 1) for c in range(ncols)])
            for r, row in enumerate(rows):
                for c in range(ncols):
                    v = row[c] if c < len(row) else None
                    self.table.setItem(
                        r, c, QTableWidgetItem("" if v is None else str(v)))
            self.selected_column = None
            self.btn_start.setEnabled(False)
            self._suggest_column(rows)

        def _suggest_column(self, rows) -> None:
            """Schlägt die wahrscheinlichste Materialnummern-Spalte vor.

            Heuristik: Spalte, in der die meisten Zellen wie Materialnummern
            aussehen (6–10 Ziffern). Der Anwender kann jederzeit umklicken.
            """
            import re

            best, best_hits = None, 0
            ncols = self.table.columnCount()
            for c in range(ncols):
                hits = 0
                for row in rows[1:]:
                    v = row[c] if c < len(row) else None
                    if v is None:
                        continue
                    if isinstance(v, float) and v.is_integer():
                        v = int(v)
                    if re.fullmatch(r"\d{6,10}", str(v).strip()):
                        hits += 1
                if hits > best_hits:
                    best, best_hits = c, hits
            if best is not None and best_hits >= 3:
                self._column_clicked(best)
                self.lbl_colinfo.setText(
                    self.lbl_colinfo.text()
                    + "   (automatisch vorgeschlagen – bei Bedarf andere "
                      "Spalte anklicken)")

        def _column_clicked(self, index: int):
            col = get_column_letter(index + 1)
            self.selected_column = col
            self.table.selectColumn(index)
            # Sofort-Validierung: Wie viele Materialnummern stecken in der Spalte?
            cfg = self._make_config(preview=True)
            try:
                materials = read_materials(cfg)
            except Exception as exc:
                self.lbl_colinfo.setText(f"Spalte {col}: nicht lesbar ({exc})")
                return
            n = len(materials)
            sample = ", ".join(m for _, m in materials[:3])
            self.lbl_colinfo.setText(
                f"Spalte <b>{col}</b> gewählt: <b>{n}</b> Materialnummern erkannt"
                + (f" (z. B. {sample} …)" if sample else "")
                + ("" if n else " – bitte andere Spalte wählen"))
            self.btn_start.setEnabled(n > 0)

        def _make_config(self, preview: bool = False) -> RunConfig:
            assert self.excel_path is not None
            header_row = 1  # Überschrift in Zeile 1; Zeile mit Klick wäre Ausbau
            mock = (self.mock_default
                    if (self.chk_mock.isChecked() and self.mock_default) else None)
            return RunConfig(
                excel_path=self.excel_path,
                sheet_name=self.cmb_sheet.currentText(),
                material_column=self.selected_column or "A",
                header_row=header_row,
                output_dir=self.excel_path.parent / "Ergebnisse",
                material_group=self.cmb_profile.currentText(),
                sap_connection=self.txt_system.text().strip() or "P11",
                mock_source=mock,
                batch_size=self.spn_batch.value(),
            )

        # ================================================= Schritt 3: Lauf
        def _build_step3(self) -> QWidget:
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.addWidget(QLabel("<h2>Schritt 3 von 3 – Prüfung läuft</h2>"))
            self.progress_bar = QProgressBar()
            self.progress_bar.setFormat("%v von %m geprüft")
            lay.addWidget(self.progress_bar)
            self.lbl_current = QLabel("")
            lay.addWidget(self.lbl_current)

            splitter = QSplitter(Qt.Horizontal)
            self.result_list = QListWidget()
            self.result_list.currentItemChanged.connect(self._show_detail)
            self.result_list.itemDoubleClicked.connect(self._open_detail_image)
            splitter.addWidget(self.result_list)

            tabs = QTabWidget()
            detail = QWidget()
            dlay = QVBoxLayout(detail)
            self.detail_text = QTextEdit()
            self.detail_text.setReadOnly(True)
            self.detail_text.setPlaceholderText(
                "Ergebnis links anklicken, um Mängel und Zeichnung zu sehen.")
            dlay.addWidget(self.detail_text, stretch=2)
            self.preview = QLabel()
            self.preview.setAlignment(Qt.AlignCenter)
            self.preview.setMinimumHeight(220)
            self.preview.setStyleSheet("background:#e8e8e8; border:1px solid #bbb;")
            dlay.addWidget(self.preview, stretch=3)
            self.btn_image = QPushButton("Zeichnung in voller Größe öffnen")
            self.btn_image.setEnabled(False)
            self.btn_image.clicked.connect(self._open_detail_image)
            dlay.addWidget(self.btn_image)
            tabs.addTab(detail, "Details")
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            tabs.addTab(self.log_view, "Protokoll")
            splitter.addWidget(tabs)
            splitter.setSizes([340, 720])
            lay.addWidget(splitter, stretch=1)

            row = QHBoxLayout()
            self.btn_pause = QPushButton("Pause")
            self.btn_pause.clicked.connect(self._toggle_pause)
            row.addWidget(self.btn_pause)
            self.btn_stop = QPushButton("Abbrechen")
            self.btn_stop.clicked.connect(self._stop_run)
            row.addWidget(self.btn_stop)
            row.addStretch()
            self.btn_retry = QPushButton("Fehlgeschlagene erneut prüfen")
            self.btn_retry.clicked.connect(self._retry_failed)
            self.btn_retry.setEnabled(False)
            row.addWidget(self.btn_retry)
            self.btn_report = QPushButton("Bericht öffnen")
            self.btn_report.clicked.connect(self._open_report)
            self.btn_report.setEnabled(False)
            row.addWidget(self.btn_report)
            self.btn_open = QPushButton("Ergebnisordner öffnen")
            self.btn_open.clicked.connect(self._open_results)
            self.btn_open.setEnabled(False)
            row.addWidget(self.btn_open)
            self.btn_new = QPushButton("Neue Prüfung")
            self.btn_new.clicked.connect(self._reset)
            self.btn_new.setEnabled(False)
            row.addWidget(self.btn_new)
            lay.addLayout(row)
            return w

        # ------------------------------------------------------ Detailansicht
        SEV_HTML = {
            Severity.INFO: "#4682b4",
            Severity.WARNING: "#e69100",
            Severity.ERROR: "#c81e1e",
            Severity.BLOCKER: "#8c008c",
        }

        def _show_detail(self, item: QListWidgetItem | None, _prev=None) -> None:
            self.preview.clear()
            self.btn_image.setEnabled(False)
            if item is None:
                self.detail_text.clear()
                return
            r: MaterialResult = item.data(Qt.UserRole)
            if r is None:
                return
            parts = [f"<h3>{r.material}</h3>",
                     f"<p>Geprüft am {r.checked_at}"
                     + (f" · letzte Zeichnungsänderung {r.drawing_rev_date}"
                        if r.drawing_rev_date else "")
                     + (f"<br>Fertigungsverfahren: {', '.join(r.processes)}"
                        if r.processes else "") + "</p>"]
            if r.error:
                parts.append(f'<p style="color:#c81e1e"><b>Technischer Fehler:</b> '
                             f"{r.error}</p>")
            if r.step_summary:
                parts.append(f'<p style="color:#555">{r.step_summary}</p>')
            if not r.findings:
                parts.append('<p style="color:#2f7d32"><b>Keine Beanstandungen.'
                             "</b></p>")
            for i, f in enumerate(r.sorted_findings(), start=1):
                color = self.SEV_HTML[f.severity]
                detail = f"<br><small>{f.detail}</small>" if f.detail else ""
                parts.append(
                    f'<p style="color:{color}"><b>{i}. [{SEVERITY_LABEL[f.severity]}]'
                    f" {f.code}</b><br>{f.text}{detail}</p>")
            self.detail_text.setHtml("".join(parts))

            if r.screenshot and Path(r.screenshot).exists():
                pix = QPixmap(str(r.screenshot))
                if not pix.isNull():
                    self.preview.setPixmap(pix.scaled(
                        self.preview.size(), Qt.KeepAspectRatio,
                        Qt.SmoothTransformation))
                    self.btn_image.setEnabled(True)

        def _open_detail_image(self, *_):
            item = self.result_list.currentItem()
            r = item.data(Qt.UserRole) if item else None
            if r and r.screenshot and Path(r.screenshot).exists():
                self._open_path(Path(r.screenshot))

        def _open_report(self):
            if self.orchestrator and self.orchestrator.report_path:
                self._open_path(self.orchestrator.report_path)

        def _retry_failed(self):
            self._start_run(resume=True)

        def _start_run(self, resume: bool | None = None):
            cfg = self._make_config()
            if cfg.mock_source is None and not self._hat_ablauf():
                QMessageBox.warning(
                    self, "SAP-Ablauf fehlt",
                    "Das Programm weiß noch nicht, wie die Transaktion bedient "
                    "wird.\n\nBitte zuerst den .vbs-Mitschnitt einlesen "
                    "(Knopf im ersten Schritt). Er ist alles, was gebraucht "
                    "wird – Transaktion, Felder und Download werden daraus "
                    "gelesen.")
                return
            if resume is None:
                resume = self._frage_fortsetzen(cfg)
            self._save_settings(cfg)
            try:
                self.adapter = self.make_adapter(cfg)
                self.adapter.ensure_ready()
            except Exception as exc:
                QMessageBox.critical(
                    self, "SAP-Verbindung",
                    "Die Verbindung konnte nicht hergestellt werden:\n"
                    + klartext(exc)
                    + "\n\nBitte SAP Logon prüfen und erneut versuchen.")
                return

            self.bridge = WorkerBridge()
            self.bridge.progress.connect(self._on_progress)
            self.bridge.result.connect(self._on_result)
            self.bridge.log_line.connect(self._on_log)
            self.bridge.finished.connect(self._on_finished)
            self.orchestrator = Orchestrator(
                cfg, self.adapter, self.bridge.callbacks(), resume=resume)
            self.run_dir = self.orchestrator.run_dir

            self.result_list.clear()
            self.detail_text.clear()
            self.preview.clear()
            self.log_view.clear()
            self.progress_bar.setValue(0)
            self.btn_pause.setEnabled(True)
            self.btn_pause.setText("Pause")
            self.btn_stop.setEnabled(True)
            self.btn_new.setEnabled(False)
            self.btn_retry.setEnabled(False)
            self.btn_report.setEnabled(False)
            self.stack.setCurrentIndex(2)
            self.orchestrator.start()

        # ------------------------------------------------- SAP-Ablauf (.vbs)
        def _flow_status(self) -> None:
            """Zeigt an, ob ein SAP-Ablauf eingelesen ist - und welcher."""
            pass  # (Import entfaellt - alles ein Modul)

            flow, quelle = load_flow(None)
            if quelle is None:
                self.lbl_flow.setText(
                    "<b style='color:#c81e1e'>SAP-Ablauf fehlt</b> – bitte den "
                    "Mitschnitt einlesen")
                return
            teile = [f"Ablauf gelesen: <b>{flow.transaction or flow.name}</b>"]
            if flow.connection:
                teile.append(f"System {flow.connection}")
            teile.append(f"{len(flow.steps)} Schritte")
            self.lbl_flow.setText("<span style='color:#2f7d32'>✓</span> "
                                  + " · ".join(teile))
            if flow.connection and not self.txt_system.text().strip():
                self.txt_system.setText(flow.connection)

        def _hat_ablauf(self) -> bool:
            pass  # (Import entfaellt - alles ein Modul)

            return load_flow(None)[1] is not None

        def _vbs_vorschlag(self) -> Path | None:
            """Sucht eine .vbs an den üblichen Stellen (Aufzeichnungsordner)."""
            kandidaten: list[Path] = []
            for ordner in (Path.cwd(),
                           Path.home() / "Documents" / "SAP" / "SAP GUI",
                           Path.home() / "Dokumente" / "SAP" / "SAP GUI",
                           Path.home() / "Downloads"):
                try:
                    kandidaten.extend(sorted(ordner.glob("*.vbs")))
                except OSError:
                    continue
            if not kandidaten:
                return None
            return max(kandidaten, key=lambda p: p.stat().st_mtime)

        def _pick_vbs(self) -> None:
            vorschlag = self._vbs_vorschlag()
            start = str(vorschlag.parent) if vorschlag else str(Path.home())
            pfad, _ = QFileDialog.getOpenFileName(
                self, "SAP-Mitschnitt auswählen", start,
                "SAP-Skript (*.vbs);;Alle Dateien (*)")
            if not pfad:
                return
            self._lies_vbs(Path(pfad))

        def _ablauf_uebernehmen(self, pfad: Path):
            """Mitschnitt einlesen, speichern, Anzeige nachziehen.

            Ohne Dialoge - die kommen in `_lies_vbs` obendrauf. So laesst sich
            der eigentliche Vorgang pruefen, ohne dass ein modales Fenster den
            Test anhaelt.
            """
            pass  # (Import entfaellt - alles ein Modul)
            pass  # (Import entfaellt - alles ein Modul)

            ziel = _default_flow_path()
            flow, ok, zeilen = uebernehmen(pfad, ziel)
            if flow.connection:
                self.txt_system.setText(flow.connection)
            self._flow_status()
            return flow, ok, zeilen, ziel

        def _lies_vbs(self, pfad: Path) -> None:
            """Mitschnitt einlesen, speichern und in Klartext zurueckmelden."""
            try:
                flow, ok, zeilen, ziel = self._ablauf_uebernehmen(pfad)
            except Exception as exc:
                QMessageBox.critical(self, "Mitschnitt nicht lesbar",
                                     f"Die Datei konnte nicht ausgewertet "
                                     f"werden:\n{klartext(exc)}")
                return

            text = "\n".join(zeilen)
            if ok:
                QMessageBox.information(
                    self, "Mitschnitt eingelesen",
                    f"Der Ablauf wurde verstanden:\n\n{text}\n\n"
                    f"Gespeichert unter {ziel}. Sie können jetzt starten.")
            else:
                QMessageBox.warning(
                    self, "Mitschnitt unvollständig verstanden",
                    f"{text}\n\nBitte die Aufzeichnung wiederholen und dabei "
                    f"die Materialnummer eintragen und das Paket herunterladen – "
                    f"oder die Datei {ziel.name} von Hand ergänzen.")

        def _frage_fortsetzen(self, cfg) -> bool:
            """Bietet von selbst an, einen unfertigen Lauf fortzusetzen.

            Niemand soll nach einem Abbruch stundenlang schon Geprüftes noch
            einmal prüfen, nur weil ein Haken nicht gesetzt war. Gesucht wird
            ein Lauf zu DIESER Datei, diesem Blatt und dieser Spalte.
            """
            pass  # (Import entfaellt - alles ein Modul)

            if self.chk_resume.isChecked():
                return True
            treffer = finde_fortsetzbaren_lauf(cfg)
            if treffer is None:
                return False
            ordner, fertig, _gesamt = treffer
            antwort = QMessageBox.question(
                self, "Früheren Lauf fortsetzen?",
                f"Zu dieser Liste gibt es einen unfertigen Lauf vom "
                f"{ordner.name.removeprefix('lauf_')[:8]}:\n"
                f"{fertig} Materialnummern sind bereits geprüft.\n\n"
                f"Dort fortsetzen? (Nein = alles noch einmal prüfen)",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            return antwort == QMessageBox.Yes

        def _toggle_pause(self):
            if self.orchestrator is None:
                return
            if self.orchestrator.pause_event.is_set():
                self.orchestrator.resume()
                self.btn_pause.setText("Pause")
            else:
                self.orchestrator.pause()
                self.btn_pause.setText("Fortsetzen")

        def _stop_run(self):
            if self.orchestrator is None:
                return
            if QMessageBox.question(
                    self, "Abbrechen",
                    "Prüfung wirklich abbrechen?\n\n"
                    "Bereits geprüfte Zeilen stehen schon in der Ergebnis-Excel "
                    "und bleiben erhalten. Beim nächsten Start bietet das "
                    "Programm von selbst an, genau hier weiterzumachen."
            ) == QMessageBox.Yes:
                self.btn_stop.setEnabled(False)
                self.btn_stop.setText("Wird abgebrochen ...")
                self.orchestrator.stop()

        def _on_progress(self, p: Progress):
            self.progress_bar.setMaximum(max(p.total, 1))
            self.progress_bar.setValue(p.done)
            if p.batches > 1:
                self.progress_bar.setFormat(
                    f"%v von %m  ·  Block {p.batch} von {p.batches}")
            cur = f"Aktuell: {p.current}" if p.current else ""
            eta = ""
            if p.eta_s is not None and p.eta_s > 5:
                minutes = p.eta_s / 60
                eta = (f"   |   Rest ca. {minutes:.0f} min" if minutes >= 1
                       else "   |   Rest unter 1 min")
            self.lbl_current.setText(
                f"{cur}   |   ✔ {p.ok} ok   ⚠ {p.findings} mit Findings   "
                f"✖ {p.failed} fehlgeschlagen{eta}")

        def _on_result(self, r: MaterialResult):
            texts = {
                JobStatus.OK: "OK",
                JobStatus.FINDINGS: f"{len(r.findings)} Finding(s)",
                JobStatus.FAILED: f"fehlgeschlagen: {r.error}",
                JobStatus.SKIPPED: "übersprungen",
            }
            item = QListWidgetItem(f"{r.material}  –  {texts.get(r.status, '?')}")
            item.setForeground(STATUS_COLOR.get(r.status, QColor(0, 0, 0)))
            item.setData(Qt.UserRole, r)
            self.result_list.addItem(item)
            self.result_list.scrollToBottom()

        def _on_log(self, line: str):
            self.log_view.append(line)

        def _on_finished(self, p: Progress):
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Abbrechen")
            self.btn_open.setEnabled(True)
            self.btn_new.setEnabled(True)
            self.btn_retry.setEnabled(p.failed > 0)
            self.btn_report.setEnabled(
                bool(self.orchestrator and self.orchestrator.report_path))
            self.lbl_current.setText(p.message or "Fertig.")
            offen = max(p.total - p.done, 0)
            if offen:
                QMessageBox.information(
                    self, "Prüfung angehalten",
                    f"{p.message}\n\n{offen} Materialnummern sind noch offen. "
                    f"Die geprüften Zeilen stehen in der Ergebnis-Excel. Beim "
                    f"nächsten Start bietet das Programm an, genau hier "
                    f"weiterzumachen.")
            else:
                QMessageBox.information(
                    self, "Prüfung abgeschlossen",
                    p.message or "Die Prüfung ist abgeschlossen.")

        def _open_results(self):
            target = self.run_dir or (self.excel_path and self.excel_path.parent)
            if target:
                self._open_path(Path(target))

        @staticmethod
        def _open_path(path: Path) -> None:
            if sys.platform == "win32":
                subprocess.Popen(["explorer" if path.is_dir() else "cmd",
                                  *([] if path.is_dir() else ["/c", "start", ""]),
                                  str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        # ---------------------------------------------- Einstellungen merken
        def _save_settings(self, cfg: RunConfig) -> None:
            s = QSettings("DrawingChecker", "DrawingChecker")
            s.setValue("excel_path", str(cfg.excel_path))
            s.setValue("sheet", cfg.sheet_name)
            s.setValue("column", cfg.material_column)
            s.setValue("profile", cfg.material_group)
            s.setValue("system", cfg.sap_connection)

        def _load_settings(self) -> None:
            s = QSettings("DrawingChecker", "DrawingChecker")
            last = s.value("excel_path", "")
            if last and Path(last).exists():
                self._set_file(Path(last))
                sheet = s.value("sheet", "")
                if sheet and self.cmb_sheet.findText(sheet) >= 0:
                    self.cmb_sheet.setCurrentText(sheet)
            profile = s.value("profile", "")
            if profile and self.cmb_profile.findText(profile) >= 0:
                self.cmb_profile.setCurrentText(profile)
            self.txt_system.setText(s.value("system", "P11") or "P11")

        def _reset(self):
            self.orchestrator = None
            self.stack.setCurrentIndex(0)


    def list_profiles() -> list[str]:
        pass  # (Import entfaellt - alles ein Modul)

        names = list(load_profiles_data())
        names.sort(key=lambda n: (n != "default", n))
        return names


# ========================================================================
# app
# ========================================================================
# Logging: Datei je Lauf + Konsole. Anwender sehen Klartext in der GUI,
# Details landen im Logfile.
# ======================================================================
# logging_setup
# ======================================================================
# Logging: Datei je Lauf + Konsole. Anwender sehen Klartext in der GUI,
# Details landen im Logfile.



import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            log_dir / "drawing_checker.log", maxBytes=2_000_000,
            backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)


# ======================================================================
# app
# ======================================================================
# Einstiegspunkt der Anwendung.
#
# drawing-checker                     GUI, echtes SAP (Windows)
# drawing-checker --mock ORDNER       GUI, Mock-Adapter (ZIPs aus ORDNER)
# drawing-checker --headless ...      Lauf ohne GUI (für Tests/Automatisierung)



import argparse
import sys
from pathlib import Path



def build_adapter(config: RunConfig) -> SapAdapter:
    if config.mock_source is not None:
        pass  # (Import entfaellt - alles ein Modul)

        return MockSapAdapter(config.mock_source)
    pass  # (Import entfaellt - alles ein Modul)

    return SapGuiAdapter(connection_name=config.sap_connection,
                         flow_path=config.sap_flow,
                         diagnose_dir=config.output_dir / "sap_diagnose",
                         max_sessions=config.max_sap_sessions)


def main() -> int:
    # Unterbefehle fuer Werkzeuge, die frueher eigene Dateien waren.
    werkzeuge = {"mockdata": main_mockdata, "messen": main_messen,
                 "paket": main_paket}
    if len(sys.argv) > 1 and sys.argv[1] in werkzeuge:
        return werkzeuge[sys.argv[1]](sys.argv[2:])

    parser = argparse.ArgumentParser(description="Drawing Checker")
    parser.add_argument("--export-rules", nargs="?", const="regeln",
                        metavar="ORDNER",
                        help="eingebaute Wissenspakete (YAML) zum Bearbeiten "
                             "herausschreiben (Standard: regeln/)")
    parser.add_argument("--mock", type=Path, metavar="ORDNER",
                        help="Mockmodus: YMATDOCS-ZIPs aus diesem Ordner")
    parser.add_argument("--headless", action="store_true",
                        help="ohne GUI laufen (benötigt --excel/--column)")
    parser.add_argument("--excel", type=Path)
    parser.add_argument("--sheet", default=None)
    parser.add_argument("--column", default=None, help="z. B. C")
    parser.add_argument("--header-row", type=int, default=1)
    parser.add_argument("--profile", default="default")
    parser.add_argument("--system", default="P11")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check-rules", action="store_true",
                        help="Wissenspakete (YAML) validieren und beenden")
    parser.add_argument("--list-rules", action="store_true",
                        help="alle Prüfregeln je Profil ausgeben und beenden")
    parser.add_argument("--ocr-check", nargs="?", const="", metavar="PDF",
                        help="OCR-Installation prüfen (optional an einer "
                             "Zeichnung vorführen)")
    sap = parser.add_argument_group("SAP-Durchstich")
    sap.add_argument("--sap-import-vbs", type=Path, metavar="DATEI",
                     help="Mitschnitt (.vbs) einlesen und als Ablauf speichern")
    sap.add_argument("--sap-flow", type=Path, metavar="YAML",
                     help="bestimmten Ablauf verwenden (sonst Suchpfade)")
    sap.add_argument("--sap-show-flow", action="store_true",
                     help="gespeicherten Ablauf anzeigen")
    sap.add_argument("--sap-dry-run", nargs="?", const="4711",
                     metavar="MATNR",
                     help="Ablauf ohne SAP gegen eine simulierte Session prüfen")
    sap.add_argument("--sap-test", metavar="MATNR",
                     help="eine Materialnummer echt über SAP holen")
    sap.add_argument("--sap-dump", action="store_true",
                     help="Elementbaum des aktuellen SAP-Bildes ausgeben")
    args = parser.parse_args()

    if args.ocr_check is not None:
        pass  # (Import entfaellt - alles ein Modul)

        return ocr_check(Path(args.ocr_check) if args.ocr_check else None)

    if args.sap_import_vbs:
        return import_vbs(args.sap_import_vbs, args.sap_flow)
    if args.sap_show_flow:
        return show_flow(args.sap_flow)
    if args.sap_dry_run:
        return dry_run(args.sap_dry_run, args.sap_flow)
    if args.sap_test:
        return sap_test(args.sap_test, args.system, args.sap_flow)
    if args.sap_dump:
        return dump_screen_cli(args.system)

    if args.export_rules:
        ziel = Path(args.export_rules)
        neu = export_rules(ziel)
        for pfad in neu:
            print(f"geschrieben: {pfad}")
        if not neu:
            print(f"Nichts geschrieben - in {ziel} liegen schon alle Dateien.")
        print(f"\nDiese Dateien ueberlagern die eingebauten Regeln, wenn das "
              f"Programm aus\n{ziel.resolve().parent} gestartet wird "
              f"(oder DRAWING_CHECKER_RULES darauf zeigt).")
        return 0

    if args.list_rules:
        pass  # (Import entfaellt - alles ein Modul)

        for pname in sorted(load_profiles_data(),
                            key=lambda n: (n != "default", n)):
            prof = load_profile(pname)
            print(f"\nProfil {pname!r}  "
                  f"(STEP-Toleranz rel={prof.step_tolerance.get('rel')}, "
                  f"abs={prof.step_tolerance.get('abs')} mm)")
            for code in sorted(prof.rules):
                state = "an " if prof.enabled(code) else "AUS"
                print(f"  [{state}] {code:<24} {prof.severity(code).name.lower()}")
        return 0

    if args.check_rules:
        pass  # (Import entfaellt - alles ein Modul)

        issues, stats = validate_rules()
        print(format_report(issues, stats))
        return 1 if issues else 0

    if args.headless:
        return run_headless(args)
    return run_gui(args)


def run_gui(args) -> int:
    if not _GUI_VERFUEGBAR:
        print("PySide6 fehlt - die Oberflaeche kann nicht starten. Entweder\n"
              "  pip install PySide6-Essentials\n"
              "oder ohne Oberflaeche: --headless --excel ... --column ...")
        return 2
    from PySide6.QtWidgets import QApplication

    pass  # (Import entfaellt - alles ein Modul)

    setup_logging(Path.home() / ".drawing-checker" / "logs")
    app = QApplication(sys.argv)
    app.setApplicationName("Drawing Checker")
    win = MainWindow(build_adapter, list_profiles(), mock_default=args.mock)
    win.show()

    # Handgepflegte Wissenspakete beim Start prüfen: Probleme als Warnung
    # anzeigen (fehlerhafte Einträge werden im Lauf ignoriert, nicht fatal).
    pass  # (Import entfaellt - alles ein Modul)

    issues, _stats = validate_rules()
    if issues:
        from PySide6.QtWidgets import QMessageBox

        text = "\n".join(f"• {i}" for i in issues[:15])
        if len(issues) > 15:
            text += f"\n… und {len(issues) - 15} weitere"
        QMessageBox.warning(
            win, "Regeldateien prüfen",
            "In den Wissenspaketen (YAML) wurden Probleme gefunden. Die "
            "betroffenen Einträge werden ignoriert:\n\n" + text)
    return app.exec()


def run_headless(args) -> int:
    import openpyxl

    pass  # (Import entfaellt - alles ein Modul)

    if not args.excel or not args.column:
        print("--headless benötigt --excel und --column", file=sys.stderr)
        return 2
    sheet = args.sheet
    if sheet is None:
        wb = openpyxl.load_workbook(args.excel, read_only=True)
        sheet = wb.sheetnames[0]
        wb.close()
    config = RunConfig(
        excel_path=args.excel, sheet_name=sheet,
        material_column=args.column.upper(), header_row=args.header_row,
        output_dir=args.excel.parent / "Ergebnisse",
        material_group=args.profile, sap_connection=args.system,
        mock_source=args.mock, sap_flow=args.sap_flow,
    )
    setup_logging(config.output_dir / "logs")
    adapter = build_adapter(config)
    adapter.ensure_ready()
    orch = Orchestrator(config, adapter,
                        Callbacks(on_log=lambda m: print(m)),
                        resume=args.resume)
    orch.start()
    orch.join()
    return 0 if orch.progress.failed == 0 else 1


# ========================================================================
# mockdata
# ========================================================================
# Testdaten: Mockpakete bauen, Kalibrierzeichnungen holen, Fehler einbauen.
#
#     python -m mockdata bauen [ziel]              Mockpakete nach mockdata/out
#     python -m mockdata quellen                   Kalibrierzeichnungen auspacken
#     python -m mockdata fehler <quelle> <ziel>    Referenz- und Fehlerpakete
#
# Die 84 echten Kalibrierzeichnungen liegen als EIN Archiv im Repository
# (mockdata/echt_quellen.zip). `quellen` packt sie nach mockdata/.echt_quellen
# aus - die anderen Unterbefehle tun das bei Bedarf von selbst.
# ======================================================================
# quellen
# ======================================================================
# Zugriff auf die echten Kalibrierzeichnungen.
#
# Die 84 Fremdzeichnungen (plus STEP-Modelle) liegen als EIN Archiv im
# Repository – `mockdata/echt_quellen.zip`. Grund: Als Einzeldateien waren
# es über hundert Einträge, die jede Dateiliste zumüllen und beim
# Weitergeben stören. Wer sie braucht, bekommt sie hier ausgepackt; das
# Auspacken passiert einmalig in einen Cache-Ordner, der nicht im
# Repository liegt.
#
#     from mockdata.daten import zeichnungen
#
#     ordner = zeichnungen()      # Path auf den ausgepackten Ordner
#
# Herkunft und Lizenzen: mockdata/echt_quellen/SOURCES.md
import zipfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
ARCHIV = HIER / "echt_quellen.zip"
CACHE = HIER / ".echt_quellen"          # in .gitignore


def zeichnungen(ziel: Path | None = None, neu: bool = False) -> Path:
    """Packt die Kalibrierzeichnungen aus und liefert den Ordner.

    Beim zweiten Aufruf wird nichts noch einmal ausgepackt, außer mit
    `neu=True`. Fehlt das Archiv, wird ein sprechender Fehler geworfen –
    ohne die Zeichnungen ist eine Kalibrierung sinnlos.
    """
    ordner = ziel or CACHE
    if not ARCHIV.is_file():
        raise FileNotFoundError(
            f"Kalibrierzeichnungen fehlen: {ARCHIV} nicht gefunden. "
            f"Das Archiv liegt nicht im Repository (25 MB Binaerdaten) - "
            f"Herkunft und Wiederbeschaffung: README.md, Abschnitt "
            f"Kalibrierzeichnungen.")
    fertig = ordner / ".ausgepackt"
    if neu or not fertig.exists():
        ordner.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ARCHIV) as zf:
            zf.extractall(ordner)
        fertig.write_text(str(ARCHIV.stat().st_mtime_ns), encoding="ascii")
    return ordner


def anzahl() -> tuple[int, int]:
    """(Zeichnungen, STEP-Modelle) im Archiv – ohne es auszupacken."""
    with zipfile.ZipFile(ARCHIV) as zf:
        namen = zf.namelist()
    pdfs = sum(1 for n in namen if n.lower().endswith(".pdf"))
    steps = sum(1 for n in namen if n.lower().endswith((".step", ".stp")))
    return pdfs, steps


# ======================================================================
# generate
# ======================================================================
# Erzeugt realistische Mock-YMATDOCS-Pakete für Entwicklung und Tests.
#
# Je Materialnummer entsteht ein ZIP wie aus YMATDOCS (PDF + ggf. STEP + native
# Dummy-Datei) sowie eine Input-Excel wie vom Anwender hochgeladen.
#
# Die Zeichnungen sind vektorbasiert (A3, Rahmen, Schriftfeld nach ISO 7200,
# mehrere Ansichten, Maßketten, Symbolik) und enthalten gezielt eingebaute
# Fehler:
#
#   10473215  Schweißkonsole   – Werkstoff 1.4305 trotz Schweißnähten,
#                                deutsche Anmerkungen, ISO 5817 ohne Gruppe;
#                                STEP passt (inkl. Bohrbild 4x18 und Masse).
#   10473216  Gussgehäuse      – keine Allgemeintoleranz, Projektionsmethode
#                                fehlt; STEP ist die FALSCHE Konfiguration
#                                (kürzeres Gehäuse) -> Geometrie-K.O., zusätzlich
#                                Massenabweichung als unabhängiges Indiz.
#   10473217  Antriebswelle    – sauber zweisprachig, vollständig; STEP passt.
#   10473218  Antriebswelle    – nur gescannt (kein Textlayer), kein STEP.
#
# Aufruf:  python -m mockdata bauen [zielordner]   (Default: mockdata/out)
import io
import sys
import zipfile
from pathlib import Path

import pymupdf

MM = 1190.55 / 420.0  # A3 quer: pt je mm
PAGE_W, PAGE_H = 1190.55, 841.89
THIN, THICK = 0.5, 1.4
BLACK = (0, 0, 0)

# Schrift mit vollem Symbolvorrat (⌀, ↗, ⌖ …); Helvetica kennt diese nicht.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find_font(cands: list[str]) -> str | None:
    for c in cands:
        if Path(c).exists():
            return c
    return None


def mm(v: float) -> float:
    return v * MM


class Sheet:
    """A3-Zeichnungsblatt mit Rahmen und ISO-7200-Schriftfeld."""

    def __init__(self):
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.shape = self.page.new_shape()
        self._font = _find_font(_FONT_CANDIDATES)
        self._font_bold = _find_font(_FONT_BOLD_CANDIDATES)
        if self._font:
            self.page.insert_font(fontname="F0", fontfile=self._font)
        if self._font_bold:
            self.page.insert_font(fontname="F1", fontfile=self._font_bold)

    # ------------------------------------------------------------ Grafik
    def line(self, x0, y0, x1, y1, width=THIN):
        self.shape.draw_line((mm(x0), mm(y0)), (mm(x1), mm(y1)))
        self.shape.finish(width=width, color=BLACK)

    def rect(self, x0, y0, x1, y1, width=THIN):
        self.shape.draw_rect(pymupdf.Rect(mm(x0), mm(y0), mm(x1), mm(y1)))
        self.shape.finish(width=width, color=BLACK)

    def circle(self, cx, cy, r, width=THIN, dashes=None):
        self.shape.draw_circle((mm(cx), mm(cy)), mm(r))
        self.shape.finish(width=width, color=BLACK, dashes=dashes)

    def dashed_line(self, x0, y0, x1, y1, pattern="[3 2] 0"):
        self.shape.draw_line((mm(x0), mm(y0)), (mm(x1), mm(y1)))
        self.shape.finish(width=THIN, color=BLACK, dashes=pattern)

    def text(self, x, y, s, size=8, bold=False):
        if bold:
            fname = "F1" if self._font_bold else "hebo"
        else:
            fname = "F0" if self._font else "helv"
        self.page.insert_text((mm(x), mm(y)), s, fontsize=size,
                              fontname=fname, color=BLACK)

    def arrow(self, x, y, direction):
        """Massstabspfeil (gefülltes Dreieck), direction: 'l','r','u','d'."""
        s = 1.2
        pts = {
            "r": [(x, y), (x - 2.5 * s, y - s * 0.7), (x - 2.5 * s, y + s * 0.7)],
            "l": [(x, y), (x + 2.5 * s, y - s * 0.7), (x + 2.5 * s, y + s * 0.7)],
            "d": [(x, y), (x - s * 0.7, y - 2.5 * s), (x + s * 0.7, y - 2.5 * s)],
            "u": [(x, y), (x - s * 0.7, y + 2.5 * s), (x + s * 0.7, y + 2.5 * s)],
        }[direction]
        self.shape.draw_polyline([(mm(a), mm(b)) for a, b in pts + [pts[0]]])
        self.shape.finish(color=BLACK, fill=BLACK, width=0.3)

    # -------------------------------------------------------- Bemaßung
    def dim_h(self, x0, x1, y_ref, y_dim, label, size=8):
        """Horizontale Maßkette zwischen x0..x1, Maßlinie auf y_dim."""
        for x in (x0, x1):
            self.line(x, y_ref, x, y_dim + (1 if y_dim > y_ref else -1))
        self.line(x0, y_dim, x1, y_dim)
        self.arrow(x0, y_dim, "l")
        self.arrow(x1, y_dim, "r")
        w = len(label) * size * 0.22
        self.text((x0 + x1) / 2 - w / 2, y_dim - 1.2, label, size=size)

    def dim_v(self, y0, y1, x_ref, x_dim, label, size=8):
        for y in (y0, y1):
            self.line(x_ref, y, x_dim + (1 if x_dim > x_ref else -1), y)
        self.line(x_dim, y0, x_dim, y1)
        self.arrow(x_dim, y0, "u")
        self.arrow(x_dim, y1, "d")
        self.text(x_dim + 1.2, (y0 + y1) / 2 + 1.0, label, size=size)

    def leader(self, x0, y0, x1, y1, label, size=8):
        self.line(x0, y0, x1, y1)
        self.line(x1, y1, x1 + 6, y1)
        self.arrow(x0, y0, "l" if x1 > x0 else "r")
        self.text(x1 + 7, y1 + 1.0, label, size=size)

    # ---------------------------------------------------- Blattrahmen
    def frame(self):
        self.rect(5, 5, 415, 292, THICK)
        self.rect(10, 10, 410, 287, THIN)
        for i, x in enumerate(range(10, 411, 50)):
            if i:
                self.line(x, 5, x, 10)
                self.line(x, 287, x, 292)
            self.text(x + 22, 8.7, str(i + 1), size=6)
        for i, ch in enumerate("ABCDEF"):
            y = 10 + i * 46.2
            if i:
                self.line(5, y, 10, y)
                self.line(410, y, 415, y)
            self.text(6.5, y + 25, ch, size=6)

    def title_block(self, *, drawno, title_de, title_en, material, weight,
                    scale="1:2", bilingual=True, projection_text=True):
        x0, y0, x1, y1 = 250, 232, 410, 287
        self.rect(x0, y0, x1, y1, THICK)
        rows = [y0 + 11, y0 + 22, y0 + 33, y0 + 44]
        for y in rows:
            self.line(x0, y, x1, y)
        self.line(x0 + 55, y0, x0 + 55, rows[2])
        self.line(x0 + 105, y0, x0 + 105, rows[2])

        def cell(x, y, label_de, label_en, value):
            lbl = f"{label_de} / {label_en}" if bilingual else label_de
            self.text(x + 1.5, y + 3.4, lbl, size=5)
            self.text(x + 1.5, y + 9.2, value, size=8, bold=True)

        cell(x0, y0, "Werkstoff", "Material", material)
        cell(x0 + 55, y0, "Maßstab", "Scale", scale)
        cell(x0 + 105, y0, "Gewicht", "Weight", weight)
        cell(x0, rows[0], "Erstellt", "Drawn", "chp  2025-11-14")
        cell(x0 + 55, rows[0], "Geprüft", "Checked", "mwe  2025-11-20")
        cell(x0 + 105, rows[0], "Freigegeben", "Approved", "kfr  2025-11-21")
        cell(x0, rows[1], "Änderung", "Revision", "B")
        cell(x0 + 55, rows[1], "Datum", "Date", "2026-01-12")
        cell(x0 + 105, rows[1], "Blatt", "Sheet", "1/1")
        self.text(x0 + 1.5, rows[2] + 3.4,
                  "Benennung / Title" if bilingual else "Benennung", size=5)
        self.text(x0 + 1.5, rows[2] + 8.6, title_de, size=9, bold=True)
        if bilingual:
            self.text(x0 + 90, rows[2] + 8.6, title_en, size=8)
        self.text(x0 + 1.5, rows[3] + 3.4,
                  "Zeichnungsnummer / Drawing no." if bilingual
                  else "Zeichnungsnummer", size=5)
        self.text(x0 + 1.5, rows[3] + 9.4, drawno, size=11, bold=True)
        self.text(x0 + 105, rows[3] + 9.4, "MUSTER AG", size=8, bold=True)
        if projection_text:
            self._projection_symbol(x0 - 28, y1 - 14)
            self.text(x0 - 34, y1 - 17, "Projektionsmethode 1 / First angle",
                      size=5)

    def _projection_symbol(self, x, y):
        # Kegelstumpf-Symbol (vereinfachte Grafik) + Ansicht daneben
        self.line(x, y - 4, x + 10, y - 6)
        self.line(x, y + 4, x + 10, y + 6)
        self.line(x, y - 4, x, y + 4)
        self.line(x + 10, y - 6, x + 10, y + 6)
        self.circle(x + 18, y, 4)
        self.circle(x + 18, y, 2.2)

    def notes(self, x, y, lines, size=7):
        for i, line in enumerate(lines):
            self.text(x, y + i * 4.6, line, size=size)

    def save(self, path: Path):
        self.shape.commit()
        self.doc.save(path, deflate=True)
        self.doc.close()


# ===================================================================== Teile
def draw_weld_bracket(path: Path):
    """Schweißkonsole: Grundplatte + Steg + Rippe. Seeded Fehler:
    Werkstoff 1.4305 (Automaten-Edelstahl, NICHT schweißgeeignet) trotz
    Schweißsymbolik + "feuerverzinkt" auf Edelstahl (fachliche Widersprüche),
    deutsche Anmerkungen, ISO 5817 ohne Bewertungsgruppe, ISO 13715 fehlt."""
    s = Sheet()
    s.frame()

    # Vorderansicht (Grundplatte 320x25, Steg 180 hoch, Rippe)
    ox, oy = 45, 175  # Ursprung unten links der Ansicht (in mm auf dem Blatt)
    sc = 0.4          # entspricht exakt dem Schriftfeld-Maßstab 1:2,5
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Grundplatte
    s.rect(X(0), Y(25), X(320), Y(0), THICK)
    # Steg mittig, Dicke 20
    s.rect(X(150), Y(205), X(170), Y(25), THICK)
    # Rippe als Dreieck
    s.shape.draw_polyline([
        (mm(X(170)), mm(Y(25))), (mm(X(260)), mm(Y(25))),
        (mm(X(170)), mm(Y(140))), (mm(X(170)), mm(Y(25)))])
    s.shape.finish(width=THICK, color=BLACK)
    # Bohrungen in Grundplatte (Seitenansicht: Mittellinien)
    for bx in (40, 280):
        s.dashed_line(X(bx), Y(-8), X(bx), Y(33))
    # Kopfbohrung im Steg
    s.circle(X(160), Y(180), 8 * sc, THICK)
    s.dashed_line(X(160) - 8, Y(180), X(160) + 8, Y(180))
    s.dashed_line(X(160), Y(180) - 8 / sc * sc, X(160), Y(180) + 8)

    # Bemaßung Vorderansicht
    s.dim_h(X(0), X(320), Y(0), Y(0) + 14, "320")
    s.dim_h(X(0), X(150), Y(25), Y(25) - 46, "150")
    s.dim_v(Y(205), Y(0), X(320), X(320) + 14, "205")
    s.dim_v(Y(25), Y(0), X(320), X(320) + 26, "25")
    s.leader(X(162), Y(183), X(200), Y(230), "⌀16 H11")
    # Schweißsymbol als Leader (vereinfachter Text)
    s.leader(X(152), Y(35), X(95), Y(80), "a5 △ beidseitig")

    # Draufsicht
    oy2 = 262
    def Y2(v): return oy2 - v * sc
    s.rect(X(0), Y2(120), X(320), Y2(0), THICK)
    for bx in (40, 280):
        for by in (30, 90):
            s.circle(X(bx), Y2(by), 9 * sc, THICK)
            s.dashed_line(X(bx) - 6, Y2(by), X(bx) + 6, Y2(by))
            s.dashed_line(X(bx), Y2(by) - 6, X(bx), Y2(by) + 6)
    s.rect(X(150), Y2(120), X(170), Y2(0), THIN)
    s.dim_h(X(0), X(40), Y2(0), Y2(0) + 12, "40")
    s.dim_h(X(40), X(280), Y2(0), Y2(0) + 12, "240")
    s.dim_v(Y2(120), Y2(0), X(320), X(320) + 14, "120")
    s.dim_v(Y2(90), Y2(30), X(320), X(320) + 26, "60")
    s.leader(X(282), Y2(92), X(315), Y2(115), "4×⌀18")
    s.text(X(120), Y2(130), "Draufsicht", size=7)
    s.text(X(120), 90, "Vorderansicht", size=7)

    # Anmerkungen: bewusst NUR deutsch + ISO 5817 ohne Gruppe (Fehler!)
    s.notes(255, 180, [
        "Anmerkungen:",
        "1. Alle Schweißnähte umlaufend, a5, nicht bemaßte Nähte a4.",
        "2. Schweißnahtgüte nach ISO 5817.",
        "3. Nach dem Schweißen spannungsarm glühen.",
        "4. Konsole komplett feuerverzinkt nach Absprache.",
        "5. Unbemaßte Radien R3.",
    ])
    s.notes(255, 215, [
        "Allgemeintoleranzen ISO 2768-mK",
        "Maße in mm / Dimensions in mm",
        "Ra 12,5, Bohrungen Ra 6,3",
    ])
    s.title_block(
        drawno="DRW-10473215-B", title_de="Schweißkonsole",
        title_en="Welded bracket", material="1.4305",
        weight="10,6 kg", scale="1:2.5")
    s.text(15, 15, "10473215", size=9, bold=True)
    s.save(path)


def draw_cast_housing(path: Path, drawno="DRW-10473216-A"):
    """Gussgehäuse. Seeded Fehler: KEINE Allgemeintoleranz, KEINE
    Projektionsmethode, keine Gusstoleranz (ISO 8062 fehlt)."""
    s = Sheet()
    s.frame()

    ox, oy = 40, 190
    sc = 0.4          # entspricht exakt dem Schriftfeld-Maßstab 1:2,5
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Gehäusekörper 280 x 180 mit Flanschfüßen
    s.rect(X(0), Y(180), X(280), Y(0), THICK)
    s.rect(X(-25), Y(22), X(0), Y(0), THICK)
    s.rect(X(280), Y(22), X(305), Y(0), THICK)
    # Lagerbohrung zentrisch ⌀90, Deckelbund ⌀140
    cx, cy = X(140), Y(100)
    s.circle(cx, cy, 45 * sc, THICK)
    s.circle(cx, cy, 70 * sc, THIN)
    s.dashed_line(cx - 35, cy, cx + 35, cy)
    s.dashed_line(cx, cy - 35, cx, cy + 35)
    # Verschraubungslochkreis ⌀170, 6 Bohrungen ⌀13 (nur 4 gezeichnet)
    s.circle(cx, cy, 85 * sc, width=THIN, dashes="[2 2] 0")
    for ang_deg in (0, 90, 180, 270):
        import math
        bx = cx + 85 * sc * math.cos(math.radians(ang_deg))
        by = cy + 85 * sc * math.sin(math.radians(ang_deg))
        s.circle(bx, by, 6.5 * sc, THIN)

    s.dim_h(X(0), X(280), Y(0), Y(0) + 14, "280 ±0,8")
    s.dim_h(X(-25), X(305), Y(0), Y(0) + 26, "330")
    s.dim_v(Y(180), Y(0), X(305), X(305) + 14, "180")
    s.dim_v(Y(100), Y(0), X(-25), X(-25) - 14, "100")
    s.leader(cx + 14, cy - 14, X(240), Y(160), "⌀90 H7")
    s.leader(cx + 24, cy + 20, X(250), Y(40), "⌀140")
    s.leader(cx - 30, cy - 30, X(30), Y(165), "6×⌀13 auf ⌀170")

    # Seitenansicht (Tiefe 120)
    ox2 = 250
    def X2(v): return ox2 + v * sc
    s.rect(X2(0), Y(180), X2(120), Y(0), THICK)
    s.rect(X2(120), Y(140), X2(150), Y(60), THICK)  # Anschlussstutzen
    s.dim_h(X2(0), X2(120), Y(0), Y(0) + 14, "120")
    s.dim_h(X2(120), X2(150), Y(60), Y(60) - 10, "30")
    s.leader(X2(135), Y(100), X2(160), Y(120), "G1½\"")

    # Anmerkungen zweisprachig, aber ohne Allgemeintoleranz/Gusstoleranz!
    s.notes(30, 240, [
        "Notes / Anmerkungen:",
        "1. Casting material EN-GJS-400-15 / Gussteil EN-GJS-400-15.",
        "2. Machined surfaces Ra 6,3 / bearbeitete Flächen Ra 6,3.",
        "3. Pressure test 6 bar / Druckprüfung 6 bar.",
        "4. Paint RAL 7016 / Lackierung RAL 7016.",
    ])
    s.notes(30, 264, ["◎ ⌀0,3 A   Lagerbohrung zu Fußfläche / bearing bore to base",
                      "Bezug A = Fußfläche / datum A = base face"])
    s.title_block(
        drawno=drawno, title_de="Gussgehäuse",
        title_en="Cast housing", material="EN-GJS-400-15",
        weight="31,2 kg", scale="1:2.5", projection_text=False)
    s.text(15, 15, "10473216", size=9, bold=True)
    s.save(path)


def draw_shaft(path: Path):
    """Antriebswelle: vollständige, zweisprachige Zeichnung (Soll: grün)."""
    s = Sheet()
    s.frame()

    ox, oy = 50, 140
    sc = 0.5          # entspricht exakt dem Schriftfeld-Maßstab 1:2
    def X(v): return ox + v * sc
    def Y(v): return oy - v * sc
    # Wellenkontur (halbe Darstellung gespiegelt): Absätze
    # Abschnitte: ⌀40x80 | ⌀55x120 | ⌀70x60 | ⌀55x90 | ⌀45x70   Gesamt 420
    steps = [(40, 80), (55, 120), (70, 60), (55, 90), (45, 70)]
    x = 0.0
    for dia, ln in steps:
        r = dia / 2
        s.rect(X(x), Y(r) - (0), X(x + ln), Y(-r), THICK)
        x += ln
    total = x
    s.dashed_line(X(-10), Y(0), X(total + 10), Y(0))  # Mittellinie
    # Fasen andeuten
    s.line(X(0), Y(20 - 2), X(2), Y(20))
    s.line(X(total), Y(22.5 - 2), X(total - 2), Y(22.5))

    # Passfedernut im ⌀55-Abschnitt
    s.rect(X(210), Y(8), X(270), Y(-8), THIN)

    # Bemaßung
    y0 = Y(-40)
    s.dim_h(X(0), X(80), Y(-35), y0, "80")
    s.dim_h(X(80), X(200), Y(-35), y0, "120")
    s.dim_h(X(200), X(260), Y(-35), y0, "60")
    s.dim_h(X(260), X(350), Y(-35), y0, "90")
    s.dim_h(X(350), X(420), Y(-35), y0, "70")
    s.dim_h(X(0), X(420), Y(-35), Y(-52), "420 ±0,2")
    s.leader(X(40), Y(20), X(20), Y(55), "⌀40 k6 (E)")
    s.leader(X(140), Y(27.5), X(120), Y(62), "⌀55 h6 (E)")
    s.leader(X(230), Y(35), X(215), Y(68), "⌀70")
    s.leader(X(300), Y(27.5), X(330), Y(62), "⌀55 h6 (E)")
    s.leader(X(390), Y(22.5), X(400), Y(55), "⌀45 k6 (E)")
    s.leader(X(240), Y(8), X(280), Y(30), "Passfeder 16×10 / key 16×10")

    # Detailansicht Nut
    s.text(60, 200, "Detail Nut / detail keyway  M 1:1", size=7)
    s.rect(60, 205, 120, 235, THIN)
    s.rect(75, 212, 105, 228, THICK)
    s.dim_h(75, 105, 228, 242, "60")
    s.dim_v(212, 228, 105, 112, "16 P9")

    # GD&T: Rundlauf
    s.notes(250, 195, [
        "↗ 0,05 A–B   Lagersitze / bearing seats",
        "Bezüge A, B = Zentrierbohrungen / datums A, B = centre holes",
        "Zentrierbohrungen DIN 332-D M8 beidseitig / both ends",
    ])
    s.notes(30, 250, [
        "Allgemeintoleranzen / General tolerances: ISO 2768-fH",
        "Tolerierung nach / Tolerancing per ISO 8015",
        "Hüllbedingung (E) an Lagersitzen / envelope requirement on seats",
        "Kanten / Edges: ISO 13715 -0,3",
        "Oberfläche / Surface: Ra 1,6, Lagersitze / bearing seats Ra 0,8",
        "Maße in mm / Dimensions in mm",
        "Wärmebehandlung / Heat treatment: vergütet +QT / quenched and tempered",
    ])
    s.title_block(
        drawno="DRW-10473217-C", title_de="Antriebswelle",
        title_en="Drive shaft", material="42CrMo4 +QT",
        weight="7,4 kg", scale="1:2")
    s.text(15, 15, "10473217", size=9, bold=True)
    s.save(path)


# ---------------------------------------------------------------- STEP-Teile
def _export_step(shape, path: Path):
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Interface import Interface_Static
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP214")
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP-Export fehlgeschlagen: {path}")


def make_step_bracket(path: Path):
    """Schweißkonsole passend zur Zeichnung (320 × 120 × 205).

    Inklusive des Bohrbilds der Zeichnung: 4×⌀18 in der Grundplatte und
    die Kopfbohrung ⌀16 im Steg – damit prüft der Bohrbildabgleich echt.
    (⌀16 statt ⌀22, weil eine größere Bohrung den 20 mm breiten Steg
    durchtrennen würde – genau das meldet GEO.ASSEMBLY.)
    """
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    base = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 320, 120, 25).Shape()
    web = BRepPrimAPI_MakeBox(gp_Pnt(150, 0, 25), 20, 120, 180).Shape()
    shape = BRepAlgoAPI_Fuse(base, web).Shape()
    # 4×⌀18 Befestigungsbohrungen (Raster 240 × 60)
    for bx in (40, 280):
        for by in (30, 90):
            hole = BRepPrimAPI_MakeCylinder(
                gp_Ax2(gp_Pnt(bx, by, -1), gp_Dir(0, 0, 1)), 9.0, 27).Shape()
            shape = BRepAlgoAPI_Cut(shape, hole).Shape()
    # Kopfbohrung ⌀22 quer durch den Steg
    head = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(160, -1, 180), gp_Dir(0, 1, 0)), 8.0, 122).Shape()
    shape = BRepAlgoAPI_Cut(shape, head).Shape()
    _export_step(shape, path)


def make_step_housing_wrong(path: Path):
    """FALSCHE Konfiguration: Gehäuse nur 200 lang statt 280 (und flacher)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    body = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 200, 120, 140).Shape()
    bore = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(100, -1, 70), gp_Dir(0, 1, 0)), 32.5, 122).Shape()
    shape = BRepAlgoAPI_Cut(body, bore).Shape()
    _export_step(shape, path)


def make_step_shaft(path: Path):
    """Antriebswelle passend zur Zeichnung (Absätze, Gesamtlänge 420)."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    steps = [(40, 80), (55, 120), (70, 60), (55, 90), (45, 70)]
    shape = None
    z = 0.0
    for dia, ln in steps:
        cyl = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), dia / 2, ln).Shape()
        shape = cyl if shape is None else BRepAlgoAPI_Fuse(shape, cyl).Shape()
        z += ln
    _export_step(shape, path)


# ------------------------------------------------------------ Scan-Variante
def rasterize_pdf(src: Path, dst: Path, dpi: int = 150):
    """Erzeugt eine Bild-PDF (wie ein Scan, ohne Textlayer)."""
    with pymupdf.open(src) as doc:
        out = pymupdf.open()
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            p = out.new_page(width=page.rect.width, height=page.rect.height)
            p.insert_image(p.rect, stream=pix.tobytes("png"))
        out.save(dst)
        out.close()


# --------------------------------------------------------------------- Excel
def make_input_excel(path: Path, materials: list[tuple[str, str]]):
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    headers = ["Lfd.Nr.", "Werk", "Materialnummer", "Benennung", "Disponent",
               "Bemerkung"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, (matnr, name) in enumerate(materials, start=1):
        ws.append([i, "1000", matnr, name, "EK-4711", ""])
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 28
    wb.save(path)


# ---------------------------------------------------------------------- Main
def build_all(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_arbeit"
    work.mkdir(exist_ok=True)

    plans = {
        "10473215": ("Schweißkonsole", draw_weld_bracket, make_step_bracket),
        "10473216": ("Gussgehäuse", draw_cast_housing, make_step_housing_wrong),
        "10473217": ("Antriebswelle", draw_shaft, make_step_shaft),
    }
    materials: list[tuple[str, str]] = []
    for matnr, (name, draw_fn, step_fn) in plans.items():
        pdf = work / f"Z_{matnr}.pdf"
        stp = work / f"M_{matnr}.stp"
        draw_fn(pdf)
        try:
            step_fn(stp)
        except ImportError:
            stp = None
        with zipfile.ZipFile(out_dir / f"{matnr}.zip", "w",
                             zipfile.ZIP_DEFLATED) as zf:
            zf.write(pdf, pdf.name)
            if stp:
                zf.write(stp, stp.name)
            zf.writestr(f"N_{matnr}.CATPart", b"native cad dummy")
        materials.append((matnr, name))

    # 10473218: Scan der Welle, kein STEP
    scan_src = work / "Z_10473217.pdf"
    scan_pdf = work / "Z_10473218_scan.pdf"
    rasterize_pdf(scan_src, scan_pdf)
    with zipfile.ZipFile(out_dir / "10473218.zip", "w") as zf:
        zf.write(scan_pdf, scan_pdf.name)
    materials.append(("10473218", "Antriebswelle (Scan)"))

    # 10473219 steht in der Excel, hat aber KEIN Paket (Not-Found-Pfad)
    materials.append(("10473219", "Distanzhülse (kein Paket)"))

    excel = out_dir / "Materialliste_Mock.xlsx"
    make_input_excel(excel, materials)
    print(f"Mockdaten erzeugt in {out_dir}")
    return excel


# ======================================================================
# inject_errors
# ======================================================================
# Baut aus ECHTEN Zeichnungen alter Prüfungen Mock-Pakete mit eingebauten Fehlern.
#
# Gedacht für die Kalibrierung des Checkers an realen Daten: einen Ordner mit
# echten PDFs (und optional passenden STEP-Dateien) hineingeben, das Skript
# erzeugt je Zeichnung YMATDOCS-artige ZIPs – einmal unverändert (Referenz)
# und einmal mit gezielt injizierten Fehlern – plus Input-Excel und ein
# Manifest, das dokumentiert, welcher Fehler wo eingebaut wurde.
#
# Aufruf:
#     python -m mockdata fehler QUELLORDNER ZIELORDNER
#
# Konventionen im Quellordner:
#     <name>.pdf            die Zeichnung (Pflicht)
#     <name>.stp/.step      zugehöriges STEP (optional)
#
# Injizierbare Fehler (werden reihum kombiniert, s. SZENARIEN):
#     german_note      rein deutsche Fertigungsanmerkung einfügen
#     weld_note        Schweißangabe einfügen (erzeugt ggf. Werkstoff-Widerspruch)
#     set_material     Werkstoffangabe auf 1.4305 umschreiben (Widerspruchstest)
#     remove_gentol    Allgemeintoleranz-Angabe (ISO 2768/22081) wegretuschieren
#     remove_edges     Kantenzustand (ISO 13715) wegretuschieren
#     obsolete_norm    veralteten Normbezug (DIN 7168) einfügen
#     rasterize        Zeichnung in Scan ohne Textlayer verwandeln
#     vague_note       unbestimmte Angaben ("ca.", "nach Absprache", TBD)
#     house_norm       Verweis auf eine nicht beziehbare Werknorm
#     impossible_mass  unmögliche Gewichtsangabe (Faktor 1000, g/kg vertauscht)
#     plating_note     galvanische Beschichtung an hochfestem Teil ohne
#                      Entsprödung (EN ISO 4042)
import sys
import zipfile
from pathlib import Path

import pymupdf

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ------------------------------------------------------------- Manipulationen
def _insert_note(page: pymupdf.Page, lines: list[str], anchor: str) -> str:
    """Fügt einen Textblock in einer freien Ecke oberhalb des Schriftfelds ein."""
    rect = page.rect
    x = rect.width * 0.55
    y = rect.height * 0.60
    kwargs = {}
    if Path(FONT).exists():
        page.insert_font(fontname="INJ", fontfile=FONT)
        kwargs["fontname"] = "INJ"
    for i, line in enumerate(lines):
        page.insert_text((x, y + i * 13), line, fontsize=9, **kwargs)
    return f"{anchor}: Textblock bei ({x:.0f},{y:.0f}) eingefügt"


def german_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Zusätzliche Anmerkungen:",
        "1. Alle Kanten gratfrei, scharfkantige Übergänge gebrochen.",
        "2. Teile vor Auslieferung konservieren und einzeln verpacken.",
        "3. Rückfragen ausschließlich an die Fertigungsplanung.",
    ], "german_note")


def weld_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Schweißnaht a4 umlaufend, ISO 5817-C",
    ], "weld_note")


def vague_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Fertigungshinweise:",
        "Bohrung ca. 12 mm, Lage nach Absprache.",
        "Kanten sauber entgraten, Oberfläche wie Muster.",
        "Beschichtung: TBD",
    ], "vague_note")


def house_norm(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Oberflächenschutz nach WN 51204",
        "Prüfumfang nach TL 245",
    ], "house_norm")


def impossible_mass(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Werkstoff: S235JR",
        "Gewicht: 4200 kg",
    ], "impossible_mass")


def plating_note(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Werkstoff: 42CrMo4, vergütet 45 HRC",
        "galvanisch verzinkt nach ISO 2081, 8 µm",
    ], "plating_note")


def obsolete_norm(doc: pymupdf.Document) -> str:
    return _insert_note(doc[0], [
        "Allgemeintoleranzen DIN 7168-m",
    ], "obsolete_norm")


def set_material(doc: pymupdf.Document, new: str = "1.4305") -> str:
    """Ersetzt die erste erkannte Werkstoffbezeichnung durch `new`."""
    pass  # (Import entfaellt - alles ein Modul)
    import re

    for page in doc:
        text = page.get_text()
        for mat in MATERIALS:
            for pat in mat.patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if not m:
                    continue
                quads = page.search_for(m.group(0))
                if not quads:
                    continue
                r = quads[0]
                page.add_redact_annot(r, fill=(1, 1, 1))
                page.apply_redactions()
                kwargs = {}
                if Path(FONT).exists():
                    page.insert_font(fontname="INJ2", fontfile=FONT)
                    kwargs["fontname"] = "INJ2"
                page.insert_text((r.x0, r.y1 - 1), new,
                                 fontsize=max(7, r.height * 0.8), **kwargs)
                return (f"set_material: „{m.group(0)}“ → „{new}“ "
                        f"auf Seite {page.number + 1}")
    return "set_material: keine erkennbare Werkstoffangabe gefunden (übersprungen)"


def _remove_pattern(doc: pymupdf.Document, needles: list[str], name: str) -> str:
    for page in doc:
        for needle in needles:
            for r in page.search_for(needle):
                page.add_redact_annot(r, fill=(1, 1, 1))
                page.apply_redactions()
                return f"{name}: „{needle}“ auf Seite {page.number + 1} entfernt"
    return f"{name}: Muster nicht gefunden (übersprungen)"


def remove_gentol(doc: pymupdf.Document) -> str:
    return _remove_pattern(doc, ["ISO 2768", "ISO 22081"], "remove_gentol")


def remove_edges(doc: pymupdf.Document) -> str:
    return _remove_pattern(doc, ["ISO 13715"], "remove_edges")


MANIPULATIONS = {
    "german_note": german_note,
    "weld_note": weld_note,
    "set_material": set_material,
    "remove_gentol": remove_gentol,
    "remove_edges": remove_edges,
    "obsolete_norm": obsolete_norm,
    "vague_note": vague_note,
    "house_norm": house_norm,
    "impossible_mass": impossible_mass,
    "plating_note": plating_note,
}

# Reihum angewandte Fehlerkombinationen für aufeinanderfolgende Zeichnungen.
SZENARIEN: list[list[str]] = [
    ["german_note", "remove_gentol"],
    ["set_material", "weld_note"],
    ["obsolete_norm", "remove_edges"],
    ["german_note", "set_material"],
    ["vague_note", "house_norm"],
    ["impossible_mass", "remove_edges"],
    ["plating_note", "german_note"],
]


# --------------------------------------------------------------------- Aufbau
def _quellordner(source: Path) -> Path:
    """Ordner mit den Zeichnungen – auch wenn nur das Archiv da ist.

    Die Kalibrierzeichnungen liegen als ein ZIP im Repository. Zeigt
    `source` auf den (nicht ausgepackten) Ordner oder auf das Archiv
    selbst, wird hier ausgepackt.
    """
    if source.is_dir() and any(source.glob("*.pdf")):
        return source
    pass  # (Import entfaellt - alles ein Modul)

    return zeichnungen()


def build(source: Path, target: Path, start_matnr: int = 20500001) -> None:
    import openpyxl
    from openpyxl.styles import Font

    source = _quellordner(source)
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Keine PDFs in {source} gefunden")
    target.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    rows: list[tuple[str, str]] = []
    matnr = start_matnr

    for i, pdf in enumerate(pdfs):
        step = next((p for ext in (".stp", ".step")
                     for p in [pdf.with_suffix(ext)] if p.exists()), None)

        # 1) Referenzpaket: unverändert
        _pack(target, str(matnr), pdf.read_bytes(), pdf.name, step)
        rows.append((str(matnr), f"{pdf.stem} (Original)"))
        manifest.append(f"{matnr}: {pdf.name} unverändert (Referenz)")
        matnr += 1

        # 2) Fehlerpaket: Szenario reihum
        szenario = SZENARIEN[i % len(SZENARIEN)]
        doc = pymupdf.open(pdf)
        applied = [MANIPULATIONS[s](doc) for s in szenario]
        data = doc.tobytes(deflate=True)
        doc.close()
        _pack(target, str(matnr), data, pdf.name, step)
        rows.append((str(matnr), f"{pdf.stem} (Fehler injiziert)"))
        manifest.append(f"{matnr}: {pdf.name} + " + "; ".join(applied))
        matnr += 1

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Lfd.Nr.", "Werk", "Materialnummer", "Benennung"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, (nr, name) in enumerate(rows, start=1):
        ws.append([i, "1000", nr, name])
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 40
    wb.save(target / "Materialliste_Echt.xlsx")
    (target / "MANIFEST.txt").write_text("\n".join(manifest), encoding="utf-8")
    print(f"{len(rows)} Pakete erzeugt in {target} (siehe MANIFEST.txt)")


def _pack(target: Path, matnr: str, pdf_bytes: bytes, pdf_name: str,
          step: Path | None) -> None:
    with zipfile.ZipFile(target / f"{matnr}.zip", "w",
                         zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(pdf_name, pdf_bytes)
        if step is not None:
            zf.write(step, step.name)


# ======================================================================
# Einstieg
# ======================================================================
def main_mockdata(argv: list[str] | None = None) -> int:
    """Verteilt auf die Unterbefehle."""
    argv = list(sys.argv[1:] if argv is None else argv)
    befehl = argv[0] if argv else ""
    rest = argv[1:]

    if befehl == "bauen":
        ziel = Path(rest[0]) if rest else Path(__file__).parent / "out"
        build_all(ziel)
        print(f"Mockpakete gebaut nach: {ziel}")
        return 0
    if befehl == "quellen":
        ordner = zeichnungen()
        pdf, step = anzahl()
        print(f"{pdf} Zeichnungen, {step} STEP-Modelle ausgepackt nach:")
        print(f"  {ordner}")
        return 0
    if befehl == "fehler":
        if len(rest) != 2:
            print("Aufruf: python -m mockdata fehler <quellordner> <zielordner>")
            return 2
        build(Path(rest[0]), Path(rest[1]))
        return 0
    print(__doc__)
    return 2


# ========================================================================
# paket
# ========================================================================
# Baut die Auslieferung: ein ZIP und eine selbstentpackende Datei.
#
#     python -m tools.paket            beide bauen und pruefen
#     python -m tools.paket --nur zip  nur DrawingChecker.zip
#     python -m tools.paket --nur bat  nur DrawingChecker_Setup.bat
#
# Beide Wege liefern dasselbe Programm in EINER Datei. Das ZIP ist der
# unauffaellige Weg (manche Virenscanner mustern selbstentpackende
# Batch-Dateien), die .bat der bequeme: Doppelklick genuegt.
# ======================================================================
# paket_bauen
# ======================================================================
# Baut EINE ZIP-Datei zum Verteilen auf den Anwenderrechner.
#
# Hintergrund: Der Zielrechner bekommt die Dateien über einen Kanal mit
# Begrenzung der Dateianzahl. Deshalb geht alles in ein einziges Archiv –
# entpacken, `Start.bat` doppelklicken, fertig.
#
#     python -m tools.paket_bauen [--ziel dist] [--mit-tests]
#
# Enthalten ist alles, was am Zielrechner gebraucht wird: das Programm samt
# Wissenspaketen, das Startskript, die Anleitungen. NICHT enthalten sind die
# Kalibrierzeichnungen (25 MB Testmaterial), Entwicklungsdateien und alles,
# was sich am Zielrechner ohnehin neu bildet (virtuelle Umgebung, Caches).
#
# Das Archiv wird nach dem Bauen selbst geprüft: Sind alle Pflichtdateien
# drin, ist Start.bat auf oberster Ebene, lässt sich das Programm aus dem
# entpackten Stand heraus importieren?
import argparse
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Alles liegt im Archiv unter EINEM Ordner. Dann landet beim Entpacken
# nichts verstreut im Zielordner, egal welche Variante der Anwender waehlt.
ORDNER_IM_ARCHIV = "DrawingChecker"

# Was ins Paket gehört. Reihenfolge = Reihenfolge im Archiv.
PFLICHT_DATEIEN = [
    "Start.bat",
    "README.md",
    "drawing_checker.py",
]
# Es gibt keine Ordner mehr - das Programm ist eine Datei.
ORDNER: list[str] = []
ORDNER_MIT_TESTS: list[str] = []

# Diese Muster fliegen raus (Caches, Entwicklungsreste, Testmaterial).
AUSSCHLUSS = (
    "__pycache__", ".pyc", ".pyo", ".pytest_cache", ".git",
    "echt_quellen", "mockdata/out", "Ergebnisse", ".venv", "logs/",
)


def gehoert_dazu(pfad: Path) -> bool:
    text = pfad.as_posix()
    return not any(muster in text for muster in AUSSCHLUSS)


def sammle(mit_tests: bool) -> list[tuple[Path, str]]:
    """(Quelldatei, Name im Archiv) für alles, was mitkommt."""
    dateien: list[tuple[Path, str]] = []
    for name in PFLICHT_DATEIEN:
        quelle = WURZEL / name
        if not quelle.is_file():
            raise SystemExit(f"Pflichtdatei fehlt: {name}")
        dateien.append((quelle, name))
    for ordner in (ORDNER_MIT_TESTS if mit_tests else ORDNER):
        basis = WURZEL / ordner
        if not basis.is_dir():
            continue
        for pfad in sorted(basis.rglob("*")):
            if pfad.is_file() and gehoert_dazu(pfad.relative_to(WURZEL)):
                dateien.append((pfad, pfad.relative_to(WURZEL).as_posix()))
    return dateien


def zip_bauen(ziel_dir: Path, mit_tests: bool = False) -> Path:
    dateien = sammle(mit_tests)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    ziel = ziel_dir / "DrawingChecker.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for quelle, name in dateien:
            zf.write(quelle, f"{ORDNER_IM_ARCHIV}/{name}")
    return ziel


def zip_pruefen(archiv: Path) -> list[str]:
    """Das gebaute Archiv gegenprüfen – lieber hier scheitern als morgen."""
    probleme: list[str] = []
    with zipfile.ZipFile(archiv) as zf:
        namen = set(zf.namelist())
        kaputt = zf.testzip()
    if kaputt:
        probleme.append(f"Archiv beschädigt bei {kaputt}")
    for kurz in PFLICHT_DATEIEN:
        pflicht = f"{ORDNER_IM_ARCHIV}/{kurz}"
        if pflicht not in namen:
            probleme.append(f"fehlt im Archiv: {pflicht}")
    if any(n.startswith(("/", "\\")) or ".." in n for n in namen):
        probleme.append("verdächtige Pfade im Archiv")
    if any("__pycache__" in n or n.endswith(".pyc") for n in namen):
        probleme.append("Cache-Dateien im Archiv")

    # Entpacken und das Programm ohne Installation importieren:
    # findet fehlende Wissenspakete und Tippfehler in den YAML-Dateien.
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(archiv) as zf:
            zf.extractall(tmp)
        ergebnis = subprocess.run(
            [sys.executable, "drawing_checker.py", "--check-rules"],
            cwd=Path(tmp) / ORDNER_IM_ARCHIV, capture_output=True, text=True)
        if ergebnis.returncode != 0:
            probleme.append("Regelprüfung im entpackten Stand fehlgeschlagen: "
                            + (ergebnis.stdout + ergebnis.stderr)[-400:])
        elif "in Ordnung" not in ergebnis.stdout:
            probleme.append("Regelprüfung meldet Probleme:\n"
                            + ergebnis.stdout[-400:])
    return probleme




# ======================================================================
# einzeldatei
# ======================================================================
# Baut EINE einzige Datei: DrawingChecker_Setup.bat (selbstentpackend).
#
# Noch einen Schritt weiter als das ZIP: Der Anwender bekommt eine Datei,
# klickt sie an, und alles Weitere passiert von selbst – entpacken entfällt.
#
#     python -m tools.paket --nur bat
#
# Aufbau der erzeugten Datei:
#
#     Batch-Code (entpackt und startet)
#     ::PAYLOAD::            <- Marke
#     Base64 des ZIP-Pakets, eine Zeile je 76 Zeichen
#
# Das Auspacken läuft über die Marke, nicht über gezählte Zeilen: Der
# Batch-Teil sucht `::PAYLOAD::`, nimmt alles danach und dekodiert es.
# Erste Wahl ist PowerShell (rechnet exakt, auf jedem Windows vorhanden),
# Ersatzweg ist `certutil -decode` – und zwar mit beiden möglichen
# Zeilenzählungen, weil `more +N` je nach Windows-Fassung um eine Zeile
# abweicht. Entpackt wird mit `tar` (Windows 10 ab 1803), ersatzweise mit
# PowerShell.
#
# Ehrlich dazugesagt: Manche Virenscanner sehen selbstentpackende
# Batch-Dateien kritisch. Wenn der Scanner meckert, ist das ZIP aus
# das ZIP der unauffälligere Weg – beides ist eine Datei.
import argparse
import base64
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MARKE = "::PAYLOAD::"

KOPF = r"""@echo off
rem ===================================================================
rem  Drawing Checker - Einzeldatei zum Verteilen
rem
rem  Diese Datei enthaelt das komplette Programm. Doppelklick genuegt:
rem  Sie entpackt sich in einen Ordner neben sich und startet dann die
rem  Einrichtung. Es wird nichts in Windows installiert und nichts in
rem  der Registry geaendert - alles bleibt in dem einen Ordner.
rem
rem  Erzeugt von tools/paket.py - nicht von Hand bearbeiten.
rem ===================================================================
setlocal EnableExtensions
title Drawing Checker - Einrichtung
cd /d "%~dp0"

set "ZIEL=%~dp0DrawingChecker"
set "ZIP=%TEMP%\dc_paket_%RANDOM%.zip"
set "B64=%TEMP%\dc_paket_%RANDOM%.b64"

echo.
echo  ============================================================
echo    Drawing Checker - Pruefung technischer Zeichnungen
echo  ============================================================
echo.
if exist "%ZIEL%\Start.bat" (
    echo  Das Programm liegt bereits hier und wird aktualisiert:
) else (
    echo  Das Programm wird entpackt nach:
)
echo    %ZIEL%
echo.
echo  Bitte warten ...

rem --- 1. Weg: PowerShell rechnet die Marke exakt aus.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$z=Get-Content -LiteralPath '%~f0'; $i=[Array]::IndexOf($z,'::PAYLOAD::'); if($i -lt 0){exit 1}; [IO.File]::WriteAllBytes('%ZIP%',[Convert]::FromBase64String(-join $z[($i+1)..($z.Count-1)]))" >nul 2>&1

rem --- 2. Weg: certutil. "more +N" zaehlt je nach Windows-Fassung
rem     unterschiedlich, deshalb beide Varianten versuchen.
if not exist "%ZIP%" call :certutil_weg
if not exist "%ZIP%" goto :fehler_decode

if not exist "%ZIEL%" mkdir "%ZIEL%" >nul 2>&1
tar -xf "%ZIP%" -C "%~dp0" >nul 2>&1
if not exist "%ZIEL%\Start.bat" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
     "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%~dp0' -Force" >nul 2>&1
)
del "%ZIP%" >nul 2>&1
if not exist "%ZIEL%\Start.bat" goto :fehler_entpacken

echo  Entpackt. Die Einrichtung startet jetzt.
echo.
cd /d "%ZIEL%"
call "%ZIEL%\Start.bat"
endlocal
exit /b 0

:certutil_weg
for /f "delims=:" %%z in ('findstr /n /b /c:"::PAYLOAD::" "%~f0"') do set "MARKE=%%z"
if not defined MARKE exit /b 1
call :entziffern %MARKE%
if exist "%ZIP%" exit /b 0
set /a NACH=%MARKE%+1
call :entziffern %NACH%
exit /b 0

:entziffern
more +%1 "%~f0" > "%B64%" 2>nul
certutil -decode "%B64%" "%ZIP%" >nul 2>&1
del "%B64%" >nul 2>&1
if not exist "%ZIP%" exit /b 1
rem Zu kleine Dateien sind Bruchstuecke - dann war die Zeilenzahl falsch.
for %%g in ("%ZIP%") do if %%~zg LSS 20000 del "%ZIP%" >nul 2>&1
exit /b 0

:fehler_decode
echo.
echo  Das eingebettete Paket liess sich nicht auspacken.
echo.
echo  Haeufige Ursache: Die Datei wurde beim Uebertragen veraendert
echo  (z. B. von einem Mailsystem). Bitte erneut uebertragen - oder die
echo  ZIP-Fassung DrawingChecker.zip verwenden.
pause
endlocal
exit /b 1

:fehler_entpacken
echo.
echo  Das Paket liess sich nicht entpacken.
echo  Bitte die ZIP-Fassung DrawingChecker.zip verwenden: entpacken und
echo  darin Start.bat doppelklicken.
pause
endlocal
exit /b 1

rem Ab hier folgt das Paket als Base64 - nicht bearbeiten.
::PAYLOAD::
"""


def bat_bauen(ziel_dir: Path, quelle: Path | None = None) -> Path:
    """Erzeugt die selbstentpackende Datei aus dem ZIP-Paket."""
    ziel_dir.mkdir(parents=True, exist_ok=True)
    if quelle is None:
        quelle = zip_bauen(ziel_dir, mit_tests=False)

    b64 = base64.b64encode(quelle.read_bytes()).decode("ascii")
    zeilen = [b64[i:i + 76] for i in range(0, len(b64), 76)]

    ziel = ziel_dir / "DrawingChecker_Setup.bat"
    # Windows-Zeilenenden: cmd.exe und more/findstr rechnen damit.
    with open(ziel, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(KOPF)
        fh.write("\n".join(zeilen))
        fh.write("\n")
    return ziel


def nutzlast(datei: Path) -> bytes:
    """Holt das eingebettete ZIP heraus – wie es der Batch-Teil tut."""
    text = datei.read_bytes().decode("ascii", errors="replace")
    zeilen = text.split("\r\n")
    if MARKE not in zeilen:
        raise ValueError("Marke ::PAYLOAD:: fehlt")
    ab = zeilen.index(MARKE) + 1
    return base64.b64decode("".join(zeilen[ab:]).strip(), validate=True)


def bat_pruefen(datei: Path) -> list[str]:
    """Prüft die Einzeldatei so weit, wie es ohne Windows geht."""
    probleme: list[str] = []
    roh = datei.read_bytes()
    if b"\r\n" not in roh:
        probleme.append("keine Windows-Zeilenenden")
    if b"::PAYLOAD::" not in roh:
        probleme.append("Marke ::PAYLOAD:: fehlt")
        return probleme
    try:
        daten = nutzlast(datei)
    except Exception as exc:
        probleme.append(f"Nutzlast nicht lesbar: {exc}")
        return probleme

    with tempfile.TemporaryDirectory() as tmp:
        zip_pfad = Path(tmp) / "paket.zip"
        zip_pfad.write_bytes(daten)
        try:
            with zipfile.ZipFile(zip_pfad) as zf:
                namen = zf.namelist()
                if zf.testzip():
                    probleme.append("ZIP beschädigt")
                zf.extractall(tmp)
        except zipfile.BadZipFile as exc:
            probleme.append(f"kein gültiges ZIP: {exc}")
            return probleme
        if "DrawingChecker/Start.bat" not in namen:
            probleme.append("Start.bat fehlt im eingebetteten Paket")
        ergebnis = subprocess.run(
            [sys.executable, "drawing_checker.py", "--check-rules"],
            cwd=Path(tmp) / "DrawingChecker", capture_output=True, text=True)
        if "in Ordnung" not in ergebnis.stdout:
            probleme.append("Regelprüfung im entpackten Stand fehlgeschlagen")
    return probleme




# ======================================================================
# Einstieg
# ======================================================================
def main_paket(argv: list[str] | None = None) -> int:
    """Baut ZIP und Einzeldatei - die .bat aus genau demselben ZIP."""
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ziel", type=Path, default=WURZEL / "dist")
    ap.add_argument("--nur", choices=["zip", "bat"],
                    help="nur eine der beiden Fassungen bauen")
    ap.add_argument("--mit-tests", action="store_true", dest="mit_tests",
                    help="Tests und Mockdaten mitpacken (Selbsttest am "
                         "Zielrechner)")
    a = ap.parse_args(argv)

    fehler = 0
    zip_pfad = None
    if a.nur != "bat":
        zip_pfad = zip_bauen(a.ziel, a.mit_tests)
        mb = zip_pfad.stat().st_size / (1024 * 1024)
        anz = len(zipfile.ZipFile(zip_pfad).namelist())
        print(f"Gebaut: {zip_pfad}  ({mb:.1f} MB, {anz} Dateien im Archiv)")
        probleme = zip_pruefen(zip_pfad)
        if probleme:
            print("\nPROBLEME:")
            for p in probleme:
                print(f"  - {p}")
            fehler = 1
        else:
            print("Archiv geprueft: vollstaendig, entpackbar, Regeln laden sauber.")

    if a.nur != "zip":
        datei = bat_bauen(a.ziel, quelle=zip_pfad)
        mb = datei.stat().st_size / (1024 * 1024)
        print(f"Gebaut: {datei}  ({mb:.1f} MB)")
        probleme = bat_pruefen(datei)
        if probleme:
            print("\nPROBLEME:")
            for p in probleme:
                print(f"  - {p}")
            fehler = 1
        else:
            print("Einzeldatei geprueft: Marke, Base64, ZIP und Regeln in Ordnung.")

    if not fehler:
        print("\nWeitergabe: EINE Datei uebertragen. DrawingChecker_Setup.bat")
        print("doppelklicken - oder DrawingChecker.zip entpacken und darin")
        print("Start.bat doppelklicken.")
    return fehler


# ========================================================================
# messen
# ========================================================================
# Messplaetze und Auswertungen - ein Werkzeugkasten mit Unterbefehlen.
#
#     python -m tools.messen ocr [ordner] [--dpi 200]   OCR-Guete messen
#     python -m tools.messen langlauf --count 200       Speicher/Platte/Zeit
#     python -m tools.messen kalibrier <ordner>         Fehlalarme vs. Treffer
#     python -m tools.messen normen <csv> <yaml>        Normstatus importieren
#
# Vier Werkzeuge, die alle dasselbe tun: eine Behauptung ueber das Tool in
# eine Zahl verwandeln. Sie lagen als vier Dateien nebeneinander - als ein
# Werkzeugkasten mit Unterbefehlen sind sie leichter zu finden.
# ======================================================================
# ocr_bench
# ======================================================================
# Messplatz für den OCR-Fallback.
#
# Nimmt echte Zeichnungen MIT Textlayer, rastert sie (erzeugt also einen
# „Scan" mit bekannter Wahrheit) und misst, wie viel der OCR-Pfad davon
# zurückgewinnt. Damit ist die OCR-Qualität eine Zahl statt eines Gefühls.
#
#     python -m tools.ocr_bench [ordner] [--dpi 200] [--noise]
#
# Gemessen wird:
#   Token-Recall      Anteil der Wahrheits-Token, die die OCR wiederfindet
#   Maß-Recall        dasselbe nur für maßrelevante Token (Zahlen, ⌀, M12 …)
#   Maße              extrahierte Maßwerte OCR vs. Wahrheit (Schnittmenge)
#   Findings          Regelbefunde OCR vs. Wahrheit (Abweichung = Fehlurteil)
#
# Der Scan wird bewusst realistisch verschlechtert (Auflösung, Rauschen,
# leichte Schräglage), damit die Messung nicht zu optimistisch ausfällt.
import argparse
import math
import re
import sys
import tempfile
from pathlib import Path

import pymupdf

# Token, die für die Prüfung zählen (Maße, Werkstoffe, Normen).
RE_RELEVANT = re.compile(r"[⌀ØR]?\d|M\d|ISO|DIN|EN\b|Ra|Rz|H\d|h\d", re.IGNORECASE)


def rasterize_scan(pdf: Path, out: Path, dpi: int = 200, noise: bool = True,
              skew_deg: float = 0.0) -> Path:
    """Erzeugt aus einem Vektor-PDF ein Scan-PDF ohne Textlayer."""
    import numpy as np
    from PIL import Image

    src = pymupdf.open(pdf)
    dst = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if skew_deg:
            img = img.rotate(skew_deg, resample=Image.BICUBIC, fillcolor=255,
                             expand=True)
        if noise:
            arr = np.asarray(img).astype(np.int16)
            rng = np.random.default_rng(42)
            arr = arr + rng.normal(0, 12, arr.shape)
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        new = dst.new_page(width=page.rect.width, height=page.rect.height)
        buf = _png_bytes(img)
        new.insert_image(new.rect, stream=buf)
    dst.save(out)
    dst.close()
    src.close()
    return out


def _png_bytes(img) -> bytes:
    import io

    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def _tokens(words: list[str]) -> tuple[set[str], set[str]]:
    alle = {w for w in words if len(w) > 1}
    return alle, {w for w in alle if RE_RELEVANT.search(w)}


def analyse(pdf_path: Path) -> dict:
    """Ein Durchgang: Token, Maße und Findings eines PDFs (wie im Lauf)."""
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    with DrawingPdf(pdf_path) as pdf:
        ctx = CheckContext("bench", pdf, PackageContent(),
                           load_profile("default"))
        run_drawing_checks(ctx)
        dims = {round(d.value, 1) for d in extract_dimensions(pdf, 6000)}
        alle, relevant = _tokens([w.text.strip() for w in pdf.words()
                                  if w.text.strip()])
        return {"dims": dims, "codes": {f.code for f in ctx.findings},
                "ocr": pdf.ocr_used, "tokens": alle, "relevant": relevant}


def run_ocr(source: Path, dpi: int, noise: bool, skew: float) -> int:
    if not (source.is_dir() and any(source.glob("*.pdf"))):
        # Kalibrierzeichnungen liegen als ein Archiv im Repository.
        pass  # (Import entfaellt - alles ein Modul)

        source = zeichnungen()
    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"Keine PDFs in {source}")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="ocrbench_"))
    rows = []
    for pdf in pdfs:
        truth = analyse(pdf)
        if len(truth["tokens"]) < 20:
            continue                      # selbst schon ein Scan
        scan = rasterize_scan(pdf, tmp / f"{pdf.stem}_scan.pdf", dpi=dpi,
                         noise=noise, skew_deg=skew)
        got = analyse(scan)
        rows.append({
            "name": pdf.stem,
            "recall": _recall(truth["tokens"], got["tokens"]),
            "recall_rel": _recall(truth["relevant"], got["relevant"]),
            "dims_truth": len(truth["dims"]),
            "dims_hit": len(truth["dims"] & got["dims"]),
            "dims_extra": len(got["dims"] - truth["dims"]),
            "codes_miss": len(truth["codes"] - got["codes"]),
            "codes_extra": len(got["codes"] - truth["codes"]),
            "ocr": got["ocr"],
        })
    _print(rows, dpi, noise, skew)
    return 0


def _recall(truth: set[str], got: set[str]) -> float:
    """Anteil der Wahrheits-Token, die (unscharf) wiedergefunden wurden."""
    if not truth:
        return 1.0
    got_norm = {_norm(g) for g in got}
    hit = sum(1 for t in truth if _norm(t) in got_norm)
    return hit / len(truth)


def _norm(s: str) -> str:
    return re.sub(r"[\s,.;:]", "", s).upper()


def _print(rows: list[dict], dpi: int, noise: bool, skew: float) -> None:
    print(f"OCR-Messlauf  (Scan {dpi} dpi, Rauschen={'ja' if noise else 'nein'}, "
          f"Schraeglage={skew} Grad)")
    header = (f"{'Zeichnung':<22}{'Token':>7}{'Masstok':>9}{'Masse':>10}"
              f"{'Fehlmasse':>11}{'Regeln -/+':>12}")
    print(header)
    for r in rows:
        dims = f"{r['dims_hit']}/{r['dims_truth']}"
        regeln = "-%d/+%d" % (r["codes_miss"], r["codes_extra"])
        print(f"{r['name']:<22}{r['recall']:>6.0%}{r['recall_rel']:>9.0%}"
              f"{dims:>10}{r['dims_extra']:>11}{regeln:>12}")
    if not rows:
        return
    n = len(rows)
    dims = "%d/%d" % (sum(r["dims_hit"] for r in rows),
                      sum(r["dims_truth"] for r in rows))
    regeln = "-%d/+%d" % (sum(r["codes_miss"] for r in rows),
                          sum(r["codes_extra"] for r in rows))
    print("-" * len(header))
    print(f"{'Mittel':<22}{sum(r['recall'] for r in rows) / n:>6.0%}"
          f"{sum(r['recall_rel'] for r in rows) / n:>9.0%}"
          f"{dims:>10}{sum(r['dims_extra'] for r in rows):>11}{regeln:>12}")


def main_ocr(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, nargs="?",
                    default=Path("mockdata/echt_quellen"),
                    help="Ordner mit Zeichnungen; ohne Angabe die echten "
                         "Kalibrierzeichnungen aus dem Archiv")
    ap.add_argument("--dpi", type=int, default=200,
                    help="Auflösung des simulierten Scans")
    ap.add_argument("--no-noise", action="store_true")
    ap.add_argument("--skew", type=float, default=0.0,
                    help="Schräglage des Scans in Grad")
    a = ap.parse_args(argv)
    return run_ocr(a.source, a.dpi, not a.no_noise, a.skew)


# ======================================================================
# langlauf
# ======================================================================
# Langlauf-Test: verhält sich das Tool über hunderte Materialnummern sauber?
#
# Der Echtlauf geht über eine ganze Materialgruppe – mehrere hundert Zeilen,
# Stunden Laufzeit, unbeaufsichtigt. Dieser Test beantwortet vorher die
# Fragen, die dabei den Lauf kosten können:
#
#   * Wächst der Speicherbedarf mit der Zeit (Leck in PDF/OCR/STEP)?
#   * Wächst der Ergebnisordner unbegrenzt, oder greift das Aufräumen?
#   * Bleibt die Zeit je Materialnummer konstant?
#
#     python -m tools.langlauf --count 200 [--quelle mockdata/out] [--keep]
#
# Die Pakete werden aus vorhandenen Mockpaketen vervielfältigt; geprüft wird
# mit dem normalen Orchestrator über den Mock-Adapter, also demselben Weg wie
# im Echtbetrieb (nur ohne SAP).
import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path


def rss_mb() -> float:
    """Aktueller Speicherbedarf des Prozesses in MB (0 = nicht messbar)."""
    try:                                     # Linux
        with open("/proc/self/statm", encoding="ascii") as fh:
            pages = int(fh.read().split()[1])
        return pages * 4096 / (1024 * 1024)
    except OSError:
        pass
    try:                                     # Unix allgemein: nur Spitzenwert
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / 1024
    except Exception:
        return 0.0


def build_liste(quelle: Path, ziel: Path, count: int) -> Path:
    """Erzeugt `count` Pakete (Kopien der Vorlagen) plus Input-Excel."""
    import openpyxl

    vorlagen = sorted(quelle.glob("*.zip"))
    if not vorlagen:
        raise SystemExit(f"Keine ZIP-Pakete in {quelle} – erst "
                         f"`python -m mockdata bauen` laufen lassen.")
    ziel.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Materialliste"
    ws.append(["Lfd.Nr.", "Werk", "Materialnummer", "Benennung"])
    for i in range(count):
        matnr = f"9{i + 1:07d}"
        shutil.copy2(vorlagen[i % len(vorlagen)], ziel / f"{matnr}.zip")
        ws.append([i + 1, "1000", matnr, f"Langlauf {i + 1}"])
    excel = ziel / "Langlauf.xlsx"
    wb.save(excel)
    return excel


def run_langlauf(count: int, quelle: Path, keep: bool) -> int:
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)
    pass  # (Import entfaellt - alles ein Modul)

    tmp = Path(tempfile.mkdtemp(prefix="langlauf_"))
    pakete = tmp / "pakete"
    excel = build_liste(quelle, pakete, count)
    out = tmp / "Ergebnisse"

    config = RunConfig(excel_path=excel, sheet_name="Materialliste",
                       material_column="C", header_row=1, output_dir=out,
                       keep_packages=keep)
    adapter = MockSapAdapter(pakete)
    adapter.ensure_ready()

    proben: list[tuple[int, float, float, float]] = []
    start_rss = rss_mb()
    t0 = time.time()

    def on_result(_r):
        n = orch.progress.done + 1
        if n % max(count // 10, 1) == 0 or n == 1:
            proben.append((n, time.time() - t0, rss_mb(),
                           dir_size_mb(orch.run_dir)))

    orch = Orchestrator(config, adapter, Callbacks(on_result=on_result))
    orch.start()
    orch.join(timeout=3600)
    dauer = time.time() - t0

    print(f"\nLanglauf über {count} Materialnummern")
    print(f"{'nach':>6}{'Sekunden':>10}{'Speicher MB':>13}{'Ordner MB':>11}")
    for n, sek, rss, mb in proben:
        print(f"{n:>6}{sek:>10.0f}{rss:>13.0f}{mb:>11.1f}")
    ende_rss = rss_mb()
    print(f"\nGesamtdauer      {dauer:.0f} s "
          f"({dauer / max(count, 1):.2f} s je Materialnummer)")
    print(f"Speicher         {start_rss:.0f} -> {ende_rss:.0f} MB "
          f"(Zuwachs {ende_rss - start_rss:+.0f} MB)")
    print(f"Ergebnisordner   {dir_size_mb(orch.run_dir):.1f} MB")
    print(f"Frei auf Platte  {free_mb(out):.0f} MB")
    print(f"Ergebnis         {orch.progress.message}")

    # Bewertung
    fehler = []
    # Bewertet wird der Zuwachs NACH dem Warmlaufen (Bibliotheken laden
    # einmalig einige hundert MB); entscheidend ist, ob es danach weiter
    # wächst.
    if len(proben) >= 3:
        warm = proben[1][2]
        zuwachs = proben[-1][2] - warm
        je_stueck = zuwachs / max(proben[-1][0] - proben[1][0], 1)
        print(f"Nach dem Warmlaufen {warm:.0f} MB, am Ende "
              f"{proben[-1][2]:.0f} MB ({zuwachs:+.0f} MB, "
              f"{je_stueck:+.2f} MB je Materialnummer)")
        if je_stueck > 1.0:
            fehler.append(f"Speicher wächst um {je_stueck:.1f} MB je "
                          f"Materialnummer – Verdacht auf ein Leck")
    if not keep and dir_size_mb(orch.run_dir / "pakete") > 50:
        fehler.append("Paketordner wurde nicht aufgeräumt")
    if orch.progress.failed:
        fehler.append(f"{orch.progress.failed} Materialnummern fehlgeschlagen")
    if len(proben) >= 4:
        erst = proben[1][1] - proben[0][1]
        letzt = proben[-1][1] - proben[-2][1]
        if erst > 0 and letzt > erst * 3:
            fehler.append("Prüfung wird im Verlauf deutlich langsamer")
    shutil.rmtree(tmp, ignore_errors=True)
    if fehler:
        print("\nBEFUND:")
        for f in fehler:
            print(f"  - {f}")
        return 1
    print("\nBefund: unauffällig (Speicher stabil, Ordner aufgeräumt, "
          "keine Ausfälle).")
    return 0


def main_langlauf(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=200)
    ap.add_argument("--quelle", type=Path, default=Path("mockdata/out"))
    ap.add_argument("--keep", action="store_true",
                    help="Pakete behalten (prüft den Gegenfall)")
    a = ap.parse_args(argv)
    return run_langlauf(a.count, a.quelle, a.keep)


# ======================================================================
# kalibrier_auswertung
# ======================================================================
# Wertet einen Kalibrierlauf aus: Fehlalarme vs. gefundene Injektionen.
#
#     python -m mockdata fehler mockdata/echt_quellen /tmp/kal
#     python -m drawing_checker.app --headless --mock /tmp/kal         --excel /tmp/kal/Materialliste_Echt.xlsx --column C
#     python -m tools.kalibrier_auswertung /tmp/kal
#
# Die Referenzpakete (unveränderte Originalzeichnungen) sind der Maßstab für
# Fehlalarme: Was dort als Fehler gemeldet wird, ist mit hoher
# Wahrscheinlichkeit einer. Die Fehlerpakete zeigen, ob die Injektionen
# gefunden werden.
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path


def lade_manifest(ordner: Path) -> dict[str, str]:
    """{Materialnummer: 'Referenz' | Injektionsbeschreibung}"""
    art: dict[str, str] = {}
    for zeile in (ordner / "MANIFEST.txt").read_text(encoding="utf-8").splitlines():
        if ":" not in zeile:
            continue
        matnr, rest = zeile.split(":", 1)
        art[matnr.strip()] = ("Referenz" if "unverändert" in rest
                              else rest.strip())
    return art


def lade_findings(lauf: Path) -> list[dict]:
    with open(lauf / "findings.csv", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def auswerten(ordner: Path) -> int:
    laeufe = sorted((ordner / "Ergebnisse").glob("lauf_*"), reverse=True)
    if not laeufe:
        print(f"Kein Lauf in {ordner / 'Ergebnisse'} gefunden.")
        return 2
    art = lade_manifest(ordner)
    rows = lade_findings(laeufe[0])

    ref_codes: Counter = Counter()
    err_codes: Counter = Counter()
    ref_hart: Counter = Counter()
    referenzen = {m for m, a in art.items() if a == "Referenz"}
    fehlerhafte = set(art) - referenzen
    for r in rows:
        matnr, code, bewertung = r["Materialnummer"], r["Regel"], r["Bewertung"]
        if matnr in referenzen:
            ref_codes[code] += 1
            if bewertung in ("Fehler", "K.O."):
                ref_hart[code] += 1
        else:
            err_codes[code] += 1

    print(f"Kalibrierlauf: {laeufe[0].name}")
    print(f"{len(referenzen)} Referenzzeichnungen, {len(fehlerhafte)} mit "
          f"injizierten Fehlern\n")
    print("Meldungen auf den UNVERÄNDERTEN Referenzzeichnungen")
    print("(Fehler/K.O. hier sind Fehlalarm-Verdacht):")
    print(f"{'Regel':<26}{'gesamt':>8}{'davon hart':>12}{'je Zeichnung':>14}")
    for code, n in ref_codes.most_common():
        print(f"{code:<26}{n:>8}{ref_hart.get(code, 0):>12}"
              f"{n / max(len(referenzen), 1):>14.2f}")
    print(f"\nHarte Meldungen auf Referenzen gesamt: {sum(ref_hart.values())}"
          f" (in {len(ref_hart)} Regeln)")
    nur_fehler = set(err_codes) - set(ref_codes)
    print(f"\nNur auf den Fehlerpaketen ausgelöst ({len(nur_fehler)} Regeln): "
          + (", ".join(sorted(nur_fehler)) or "keine"))
    return 0


def main_kalibrier(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ordner", type=Path)
    return auswerten(ap.parse_args(argv).ordner)


# ======================================================================
# import_norms_csv
# ======================================================================
# Massenimport von Normstatus-Daten in das Normen-Wissenspaket.
#
# Konvertiert einen Export der Normenverwaltung (Nautos/Perinorm o. ä.) in
# norms-Einträge. Erwartetes CSV (Trennzeichen ; oder ,):
#
#     Dokumentnummer;Status;Nachfolger
#     DIN 7168;zurückgezogen;ISO 2768
#     ISO 1302;ersetzt;ISO 21920-1
#     ISO 13715;gültig;
#
# Nur Zeilen mit Status != gültig werden übernommen. Ausgabe ist eine
# YAML-Datei, die als zusätzliches Paket neben norms.yaml gelegt wird
# (drawing_checker/rules/norms_firma.yaml) und automatisch mitlädt.
#
# Aufruf:
#     python -m tools.messen normen export.csv drawing_checker/rules/norms_firma.yaml
import csv
import re
import sys
from pathlib import Path

VALID = {"gültig", "gueltig", "aktuell", "valid", "current"}


def norm_to_pattern(norm: str) -> str:
    """„DIN EN ISO 1302“ -> robustes Regex mit optionalen Präfixen."""
    m = re.match(r"^\s*((?:DIN|EN|ISO|VDI|VDE|ASME|ANSI|AWS|\s)+)?\s*"
                 r"([\dXY.\-/]+[\w.\-/]*)\s*$", norm, re.IGNORECASE)
    if not m:
        raise ValueError(f"Normbezeichnung nicht interpretierbar: {norm!r}")
    prefixes = (m.group(1) or "").split()
    number = re.escape(m.group(2))
    if not prefixes:
        raise ValueError(f"Norm ohne Präfix (DIN/ISO/…): {norm!r}")
    # Letztes Präfix ist Pflicht, alles davor optional (DIN EN ISO == ISO).
    haupt = prefixes[-1]
    return rf"(?:DIN\s*)?(?:EN\s*)?{haupt}\s*{number}\b"


def convert(csv_path: Path, out_path: Path) -> int:
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        delim = ";" if sample.count(";") >= sample.count(",") else ","
        for row in csv.reader(fh, delimiter=delim):
            if len(row) < 2 or row[0].strip().lower() in ("dokumentnummer",
                                                          "norm", "nummer"):
                continue
            norm, status = row[0].strip(), row[1].strip().lower()
            successor = row[2].strip() if len(row) > 2 else ""
            if not norm or status in VALID:
                continue
            msg = f"{norm} ist {row[1].strip()}"
            if successor:
                msg += f" – Nachfolger: {successor}"
            try:
                rows.append((norm_to_pattern(norm), msg))
            except ValueError as exc:
                print(f"übersprungen: {exc}", file=sys.stderr)

    lines = ["# Automatisch importiert aus " + csv_path.name,
             "# (python -m tools.messen normen) – manuell nachschärfen erlaubt.",
             "", "obsolete:"]
    for pattern, msg in rows:
        p = pattern.replace("'", "''")
        m = msg.replace("'", "''")
        lines.append(f"  - {{pattern: '{p}',")
        lines.append(f"     message: '{m}'}}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} Einträge -> {out_path}")
    return len(rows)


def main_normen(argv: list[str] | None = None) -> int:
    """Normstatus-CSV in ein YAML-Wissenspaket wandeln."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("Aufruf: python -m tools.messen normen <export.csv> <ziel.yaml>")
        return 2
    convert(Path(argv[0]), Path(argv[1]))
    return 0


# ======================================================================
# Einstieg
# ======================================================================
def main_messen(argv: list[str] | None = None) -> int:
    """Verteilt auf die Unterbefehle."""
    import sys as _sys

    argv = list(_sys.argv[1:] if argv is None else argv)
    befehle = {"ocr": main_ocr, "langlauf": main_langlauf,
               "kalibrier": main_kalibrier, "normen": main_normen}
    if not argv or argv[0] not in befehle:
        print(__doc__)
        return 2
    return befehle[argv[0]](argv[1:])


# ========================================================================
# tests
# ========================================================================
# Die Testsuite. Sie wird nur definiert, wenn pytest die Datei laedt:
#     python -m pytest drawing_checker.py -q
# Beim normalen Start ist dieser Abschnitt unsichtbar - keine
# Abhaengigkeit von pytest, kein Ballast im Speicher.
_VBS_BEISPIEL = r"""If Not IsObject(application) Then
   Set SapGuiAuto  = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session    = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session,     "on"
   WScript.ConnectObject application, "on"
End If
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").text = "10473215"
session.findById("wnd[0]/usr/ctxtS_MATNR-HIGH").text = "10473215"
session.findById("wnd[0]/usr/ctxtP_WERKS").text = "1000"
session.findById("wnd[0]/usr/chkP_STEP").selected = true
session.findById("wnd[0]/usr/ctxtS_MATNR-LOW").caretPosition = 8
session.findById("wnd[0]").sendVKey 8
session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").pressToolbarButton "DOWNLOAD"
session.findById("wnd[1]/usr/ctxtDY_PATH").text = "C:\temp\ymatdocs"
session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = "10473215.zip"
session.findById("wnd[1]/tbar[0]/btn[0]").press
session.findById("wnd[0]/tbar[0]/btn[15]").press
"""

if "pytest" in sys.modules:
    import pytest
    import tempfile

    # ========================================================================
    # conftest
    # ========================================================================
    import sys
    from pathlib import Path

    import pytest

    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT))


    @pytest.fixture(scope="session")
    def mock_dir(tmp_path_factory) -> Path:
        """Erzeugt die Mockdaten einmal je Testlauf (Zeichnungen, STEP, ZIPs, Excel)."""
        out = tmp_path_factory.mktemp("mockdaten")
        pass  # (Import entfaellt - alles ein Modul)

        build_all(out)
        return out


    # --------------------------------------------------------- gemeinsame Hilfen
    # Diese Helfer standen vorher in bis zu sechs Testdateien fast wortgleich
    # nebeneinander. Beim Zusammenlegen der Tests wurden daraus eine Fassung.
    # Import in den Testdateien:  from conftest import make_ctx, codes, ...

    FIXTURE = Path(tempfile.gettempdir()) / "dc_ymatdocs_beispiel.vbs"
    FIXTURE.write_text(_VBS_BEISPIEL, encoding="utf-8")


    def echte_zeichnungen() -> Path:
        """Ordner mit den Kalibrierzeichnungen (liegen als ein Archiv im Repo)."""
        pass  # (Import entfaellt - alles ein Modul)

        try:
            return zeichnungen()
        except FileNotFoundError:
            return Path("/nicht/vorhanden")


    ECHT = echte_zeichnungen()


    def make_ctx(tmp_path, items, profile: str = "default",
                 pages: int = 1, name: str = "t.pdf"):
        """Baut ein Prüf-PDF aus Textzeilen und liefert den Prüfkontext.

        `items` ist je Eintrag entweder nur Text (untereinander in der linken
        Spalte), `(x, text)` für eine eigene Spalte oder `(x, y, text)` für eine
        exakte Position – letzteres brauchen die GPS-Prüfungen, bei denen der
        Abstand zwischen zwei Angaben die Aussage trägt.

        Angehängt wird immer eine Füllzeile: unter 40 Zeichen gilt eine Seite
        als „ohne Textlayer", und dann liefe die OCR statt der Textauswertung.
        """
        import pymupdf

        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        doc = pymupdf.open()
        for pno in range(pages):
            page = doc.new_page(width=842, height=595)
            kwargs = {}
            if Path(FONT).exists():
                page.insert_font(fontname="T", fontfile=FONT)
                kwargs["fontname"] = "T"
            if pno:
                continue
            y = 60
            eintraege = list(items) + [
                "Interne Testzeichnung - Blatt 1 von 1, Ausgabestand 2026"]
            for eintrag in eintraege:
                if isinstance(eintrag, tuple) and len(eintrag) == 3:
                    x, yy, text = eintrag
                elif isinstance(eintrag, tuple):
                    (x, text), yy = eintrag, y
                    y += 30
                else:
                    x, yy, text = 40, y, eintrag
                    y += 30
                page.insert_text((x, yy), text, fontsize=10, **kwargs)
        pfad = tmp_path / name
        doc.save(pfad)
        doc.close()
        return CheckContext("123", DrawingPdf(pfad), PackageContent(),
                            load_profile(profile))


    def codes(ctx, *pruefungen) -> dict:
        """Prüfungen laufen lassen und die Befunde nach Regelcode aufschlüsseln."""
        for pruefung in pruefungen:
            pruefung(ctx)
        return {f.code: f for f in ctx.findings}


    def make_config(mock_dir: Path, out: Path, **kw):
        """Standard-Laufkonfiguration gegen die Mockdaten."""
        pass  # (Import entfaellt - alles ein Modul)

        basis = dict(
            excel_path=mock_dir / "Materialliste_Mock.xlsx",
            sheet_name="Materialliste", material_column="C", header_row=1,
            output_dir=out, material_group="default",
        )
        basis.update(kw)
        return RunConfig(**basis)


    # ========================================================================
    # test_regeln
    # ========================================================================
    # Regelwerk: Profile, Wissenspakete und die Prüfungen an der Zeichnung.
    #
    # Der grösste Testblock, weil hier das Fachwissen sitzt. Zu jeder Regel
    # gehört mindestens ein Positiv- und ein Negativfall.
    # ======================================================================
    # profiles
    # ======================================================================


    def test_default_profile():
        p = load_profile("default")
        assert p.enabled("GT.GENERAL_TOL")
        assert p.severity("GEO.MISMATCH") == Severity.BLOCKER
        assert p.step_tolerance["rel"] == 0.05


    def test_guss_inherits_and_overrides():
        p = load_profile("guss")
        # geerbt
        assert p.enabled("LANG.GERMAN")
        assert p.severity("LANG.GERMAN") == Severity.ERROR
        # überschrieben
        assert p.step_tolerance["rel"] == 0.12
        assert p.severity("GEO.MISMATCH") == Severity.WARNING


    def test_unknown_profile_falls_back_to_default():
        p = load_profile("gibt_es_nicht")
        assert p.name == "default"


    def test_title_block_keywords_configured():
        p = load_profile("default")
        kws = p.rule_param("TB.MATERIAL", "keywords")
        assert "Werkstoff" in kws and "Material" in kws


    # ======================================================================
    # rule_catalog
    # ======================================================================
    # Der Regelkatalog muss vollständig bleiben.
    #
    # Neue Regeln ohne Eintrag in README.md fallen hier auf – damit die
    # Dokumentation für den Fachbereich nicht hinter dem Code zurückbleibt.
    import re
    from pathlib import Path


    KATALOG = Path(__file__).resolve().parent / "README.md"


    def documented_codes() -> set[str]:
        text = KATALOG.read_text(encoding="utf-8")
        return set(re.findall(r"`([A-Z]+\.[A-Z_0-9]+)`", text))


    def all_rule_codes() -> set[str]:
        codes: set[str] = set()
        for name in load_profiles_data():
            codes |= set(load_profile(name).rules)
        return codes


    def test_every_rule_is_documented():
        missing = sorted(all_rule_codes() - documented_codes())
        assert not missing, f"nicht im Regelkatalog dokumentiert: {missing}"


    def test_catalog_has_no_stale_entries():
        """Dokumentierte Codes müssen im Regelwerk existieren."""
        stale = sorted(documented_codes() - all_rule_codes())
        assert not stale, f"im Katalog, aber nicht im Regelwerk: {stale}"


    def test_catalog_states_rule_count():
        count = len(load_profile("default").rules)
        assert str(count) in KATALOG.read_text(encoding="utf-8"), (
            f"Regelanzahl im Katalog aktualisieren: aktuell {count}")


    # ======================================================================
    # rules_maintenance
    # ======================================================================
    # Manuelle Pflege der Wissenspakete: externer regeln/-Ordner + Validierung.
    import os

    import pytest

    base = sys.modules[__name__]


    @pytest.fixture()
    def extern_rules(tmp_path, monkeypatch):
        d = tmp_path / "regeln"
        d.mkdir()
        monkeypatch.setenv("DRAWING_CHECKER_RULES", str(d))
        return d


    def reload_materials():
        materials = sys.modules[__name__]

        materials.MATERIALS = materials._load_materials()
        materials.OBSOLETE_NORMS = materials._load_obsolete_norms()
        return materials


    def test_builtin_rules_are_valid():
        issues, stats = validate_rules()
        assert issues == [], "\n".join(map(str, issues))
        assert stats["materialien"] >= 60
        assert stats["normen"] >= 20
        assert stats["profile"] >= 3


    def test_external_dir_is_loaded(extern_rules):
        (extern_rules / "materials_firma.yaml").write_text(
            "materials:\n"
            "  - {name: Hauswerkstoff X1, patterns: ['\\\\bHW-X1\\\\b'],\n"
            "     category: baustahl, weldable: ja}\n", encoding="utf-8")
        (extern_rules / "norms_firma.yaml").write_text(
            "obsolete:\n"
            "  - {pattern: 'WN\\\\s*4711', message: 'Werksnorm WN 4711 zurückgezogen'}\n",
            encoding="utf-8")
        m = reload_materials()
        try:
            assert any(x.name == "Hauswerkstoff X1" for x in m.MATERIALS)
            assert any("WN 4711" in msg for _, msg in m.OBSOLETE_NORMS)
        finally:
            os.environ.pop("DRAWING_CHECKER_RULES", None)
            reload_materials()


    def test_external_profile_override(extern_rules):
        (extern_rules / "profiles_firma.yaml").write_text(
            "profiles:\n"
            "  default:\n"
            "    rules:\n"
            "      LANG.GERMAN: {enabled: true, severity: blocker}\n"
            "  sonderteile:\n"
            "    inherit: default\n", encoding="utf-8")
        pass  # (Import entfaellt - alles ein Modul)

        prof = base.load_profile("default")
        assert prof.severity("LANG.GERMAN") == Severity.BLOCKER
        assert "sonderteile" in base.load_profiles_data()


    def test_validator_reports_broken_entries(extern_rules):
        (extern_rules / "materials_kaputt.yaml").write_text(
            "materials:\n"
            "  - {name: Kaputt1, patterns: ['('], category: baustahl}\n"
            "  - {name: Kaputt2, patterns: ['ok'], category: gibtesnicht}\n"
            "  - {patterns: ['ok2'], category: baustahl}\n", encoding="utf-8")
        (extern_rules / "norms_kaputt.yaml").write_text(
            "obsolete:\n  - {pattern: '[', message: 'x'}\n", encoding="utf-8")
        issues, _ = validate_rules()
        text = "\n".join(map(str, issues))
        assert "ungültiges Regex-Muster" in text
        assert "gibtesnicht" in text
        assert "Pflichtfeld 'name' fehlt" in text
        assert len([i for i in issues if "kaputt" in i.file]) >= 4


    def test_broken_entries_do_not_crash_loading(extern_rules):
        (extern_rules / "materials_kaputt.yaml").write_text(
            "materials:\n  - {name: Kaputt, patterns: 12, category: baustahl}\n",
            encoding="utf-8")
        m = reload_materials()
        try:
            assert len(m.MATERIALS) >= 60  # mitgelieferte Pakete bleiben nutzbar
        finally:
            os.environ.pop("DRAWING_CHECKER_RULES", None)
            reload_materials()


    # ======================================================================
    # language
    # ======================================================================


    def test_pure_german():
        assert classify_block("Alle Kanten gebrochen und entgratet") == "de"
        assert classify_block("Nach dem Schweißen spannungsarm glühen") == "de"


    def test_pure_english():
        assert classify_block("All edges broken and deburred") == "en"


    def test_bilingual_is_mixed():
        assert classify_block("Maßstab / Scale") == "mixed"
        assert classify_block("Werkstoff / Material") == "mixed"
        assert classify_block("Kanten / Edges: ISO 13715 -0,3") == "mixed"
        assert classify_block(
            "Wärmebehandlung / Heat treatment: vergütet / quenched") == "mixed"


    def test_neutral_content():
        assert classify_block("ISO 2768-mK") == "neutral"
        assert classify_block("Ra 3,2") == "neutral"
        assert classify_block("⌀40 H7") == "neutral"
        assert classify_block("42CrMo4 +QT") == "neutral"


    # ======================================================================
    # materials
    # ======================================================================
    # Tests für Werkstofferkennung und fachliche Widerspruchsprüfung.
    #
    # Die Prüf-PDFs werden zur Laufzeit aus Textzeilen gebaut (echte PDFs mit
    # Textlayer), damit exakt derselbe Extraktionspfad wie in Produktion läuft.

    import pymupdf








    # ------------------------------------------------------------- Erkennung
    def test_find_material_variants(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: 1.4305", "alternativ X5CrNi18-10"])
        names = [h.material.name for h in find_materials(ctx)]
        assert "1.4305 (X8CrNiS18-9)" in names
        assert "1.4301 (X5CrNi18-10)" in names


    def test_material_missing(tmp_path):
        ctx = make_ctx(tmp_path, ["Maßstab 1:2", "Allgemeintoleranzen ISO 2768-mK"])
        c = codes(ctx, run_material_checks)
        assert "MAT.MISSING" in c
        assert c["MAT.MISSING"].severity == Severity.ERROR


    def test_material_label_but_unknown(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: Unobtainium X99"])
        c = codes(ctx, run_material_checks)
        assert c["MAT.MISSING"].severity == Severity.WARNING


    def test_material_present_no_finding(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S355J2+N"])
        assert "MAT.MISSING" not in codes(ctx, run_material_checks)


    # ---------------------------------------------------- Widerspruch Schweißen
    def test_1_4305_with_weld_is_conflict(tmp_path):
        ctx = make_ctx(tmp_path, [
            "Werkstoff: 1.4305",
            "Schweißnaht a4 umlaufend, ISO 5817-C",
        ])
        c = codes(ctx, run_material_checks)
        assert "MAT.WELD_CONFLICT" in c
        assert c["MAT.WELD_CONFLICT"].severity == Severity.ERROR
        assert "1.4305" in c["MAT.WELD_CONFLICT"].text


    def test_s355_with_weld_is_fine(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "a4 ISO 5817-B umlaufend"])
        assert "MAT.WELD_CONFLICT" not in codes(ctx, run_material_checks)


    def test_42crmo4_weld_is_limited_warning(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: 42CrMo4 +QT", "geschweißt nach ISO 5817-B"])
        c = codes(ctx, run_material_checks)
        assert c["MAT.WELD_CONFLICT"].severity == Severity.WARNING


    def test_gg25_weld_conflict(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Naht a3 ringsum"])
        assert "MAT.WELD_CONFLICT" in codes(ctx, run_material_checks)


    # ---------------------------------------------- Widerspruch Wärmebehandlung
    def test_s235_hardened_is_conflict(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Oberfläche gehärtet 55 HRC"])
        assert "MAT.HT_CONFLICT" in codes(ctx, run_material_checks)


    def test_c45_hardened_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: C45E", "gehärtet und angelassen"])
        assert "MAT.HT_CONFLICT" not in codes(ctx, run_material_checks)


    def test_16mncr5_case_hardened_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff 16MnCr5", "einsatzgehärtet Eht 0,8"])
        assert "MAT.HT_CONFLICT" not in codes(ctx, run_material_checks)


    def test_pa6_heat_treatment_nonsense(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: PA6 GF30", "vergütet"])
        assert "MAT.HT_CONFLICT" in codes(ctx, run_material_checks)


    # --------------------------------------------------- Widerspruch Beschichtung
    def test_stainless_galvanized_conflict(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: 1.4301", "feuerverzinkt nach ISO 1461"])
        assert "MAT.COATING_CONFLICT" in codes(ctx, run_material_checks)


    def test_steel_anodized_conflict(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S355J2", "schwarz eloxiert"])
        assert "MAT.COATING_CONFLICT" in codes(ctx, run_material_checks)


    def test_alu_anodized_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff EN AW-6082", "natur eloxiert 15 µm"])
        assert "MAT.COATING_CONFLICT" not in codes(ctx, run_material_checks)


    # --------------------------------------------------------- Norm vs. Werkstoff
    def test_alu_with_iso5817_mismatch(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff EN AW-5754", "Schweißnahtgüte ISO 5817-C"])
        assert "NORM.MATERIAL_MISMATCH" in codes(ctx, run_material_checks)


    def test_steel_with_iso10042_mismatch(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Nahtgüte ISO 10042-B"])
        assert "NORM.MATERIAL_MISMATCH" in codes(ctx, run_material_checks)


    # -------------------------------------------------------------- Guss-Kontext
    def test_cast_context_without_cast_material(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: C45", "Gussteil nach ISO 8062-3 DCTG12"])
        assert "MAT.CAST_CONFLICT" in codes(ctx, run_material_checks)


    def test_cast_context_with_gjs_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gusstoleranzen ISO 8062"])
        assert "MAT.CAST_CONFLICT" not in codes(ctx, run_material_checks)


    # ---------------------------------------------------------- Veraltete Normen
    def test_obsolete_norms_flagged(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR",
                                  "Oberflächen nach ISO 1302",
                                  "Allgemeintoleranzen DIN 7168-m"])
        run_material_checks(ctx)
        msgs = [f.text for f in ctx.findings if f.code == "NORM.OBSOLETE"]
        assert any("21920" in m for m in msgs)
        assert any("7168" in m for m in msgs)


    def test_current_norms_not_flagged(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "ISO 21920, ISO 13715,",
                                  "ISO 2768-mK"])
        assert "NORM.OBSOLETE" not in codes(ctx, run_material_checks)


    # ======================================================================
    # process_rules
    # ======================================================================
    # Verfahrensspezifische Vollständigkeit: Schweißen, Guss, Blech.







    def codes_verfahren(ctx) -> dict:
        run_process_checks(ctx, extract_dimensions(ctx.pdf))
        return {f.code: f for f in ctx.findings}


    # ------------------------------------------------------------- Schweißen
    def test_weld_without_size_is_error(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                      "Kehlnaht umlaufend, ISO 5817-C"]))
        assert c["WELD.NO_SIZE"].severity == Severity.ERROR


    def test_weld_with_a_size_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                      "Kehlnaht a4 umlaufend, ISO 5817-C"]))
        assert "WELD.NO_SIZE" not in c


    def test_weld_with_z_size_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                      "Kehlnaht z6 umlaufend"]))
        assert "WELD.NO_SIZE" not in c


    def test_mixed_a_and_z_sizes_warn(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                      "Naht 1: a4 umlaufend",
                                      "Naht 2: z6 beidseitig"]))
        assert c["WELD.AZ_MIXED"].severity == Severity.WARNING
        assert "29" in c["WELD.AZ_MIXED"].detail


    def test_butt_weld_without_preparation_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S355J2",
                                      "V-Naht durchgeschweißt a6, ISO 5817-B"]))
        assert c["WELD.NO_PREP"].severity == Severity.WARNING


    def test_butt_weld_with_preparation_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, [
            "Werkstoff S355J2", "V-Naht a6, Nahtvorbereitung nach ISO 9692-1",
            "Öffnungswinkel 60°, Wurzelspalt 2 mm"]))
        assert "WELD.NO_PREP" not in c


    def test_no_weld_context_no_findings(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45", "gedrehtes Teil"]))
        assert not [k for k in c if k.startswith("WELD.")]


    # ------------------------------------------------------------------ Guss
    def test_casting_without_draft_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15",
                                      "Gussteil nach ISO 8062-3 DCTG12"]))
        assert c["CAST.NO_DRAFT"].severity == Severity.WARNING


    def test_casting_with_draft_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gussteil",
                                      "Formschrägen 2° wenn nicht anders angegeben",
                                      "Bearbeitungszugabe 3 mm"]))
        assert "CAST.NO_DRAFT" not in c
        assert "CAST.NO_RMA" not in c


    def test_machined_casting_without_rma_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJL-250", "Gussteil",
                                      "Formschrägen 2°",
                                      "Passflächen bearbeitet, Ra 3,2"]))
        assert c["CAST.NO_RMA"].severity == Severity.WARNING


    def test_unmachined_casting_needs_no_rma(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                      "Gussteil roh, Formschrägen 3°"]))
        assert "CAST.NO_RMA" not in c


    # ----------------------------------------------------------------- Blech
    def test_sheet_without_thickness_is_error(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR",
                                      "Blech lasergeschnitten, abgekantet"]))
        assert c["SHEET.NO_THICK"].severity == Severity.ERROR


    def test_sheet_with_thickness_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR",
                                      "Blechdicke 3 mm, abgekantet",
                                      "Biegeradius innen R3"]))
        assert "SHEET.NO_THICK" not in c
        assert "SHEET.NO_RADIUS" not in c


    def test_bending_without_radius_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                      "abgekantet 90°"]))
        assert c["SHEET.NO_RADIUS"].severity == Severity.WARNING


    def test_flat_sheet_needs_no_radius(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff S235JR", "Blechdicke 2 mm",
                                      "Blech lasergeschnitten, eben"]))
        assert "SHEET.NO_RADIUS" not in c


    def test_turned_part_no_process_findings(tmp_path):
        """Ein Drehteil darf keine Schweiß-, Guss- oder Blechregel auslösen."""
        c = codes_verfahren(make_ctx(tmp_path, [
            "Werkstoff 42CrMo4 +QT", "Antriebswelle, gedreht und geschliffen",
            "⌀40 k6, Ra 0,8, Allgemeintoleranzen ISO 2768-fH"]))
        assert not c, f"unerwartete Findings: {list(c)}"


    # ------------------------------------------------------ Wärmebehandlung
    def test_heat_treatment_without_hardness_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "vergütet"]))
        assert c["HT.NO_HARDNESS"].severity == Severity.WARNING


    def test_heat_treatment_with_hardness_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4",
                                      "vergütet auf 30-34 HRC"]))
        assert "HT.NO_HARDNESS" not in c


    def test_case_hardening_without_depth_warns(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 16MnCr5",
                                      "einsatzgehärtet 60 HRC"]))
        assert c["HT.NO_DEPTH"].severity == Severity.WARNING


    def test_case_hardening_with_depth_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 16MnCr5",
                                      "einsatzgehärtet 60 HRC, Eht 0,8 mm"]))
        assert "HT.NO_DEPTH" not in c


    def test_nitriding_with_nhd_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 31CrMoV9",
                                      "nitriert 700 HV1, NHD 0,4 mm"]))
        assert "HT.NO_DEPTH" not in c


    def test_hardness_above_material_limit_is_error(tmp_path):
        """C45 erreicht rund 58 HRC – 64 HRC sind nicht darstellbar."""
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45",
                                      "randschichtgehärtet 64 HRC, Rht 1,5 mm"]))
        assert c["HT.HARDNESS_LIMIT"].severity == Severity.ERROR
        assert "C45" in c["HT.HARDNESS_LIMIT"].text


    def test_hardness_within_limit_is_fine(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 100Cr6",
                                      "durchgehärtet 62 HRC"]))
        assert "HT.HARDNESS_LIMIT" not in c


    def test_hardness_limit_needs_known_material(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff Sonderlegierung XY",
                                      "gehärtet 70 HRC"]))
        assert "HT.HARDNESS_LIMIT" not in c


    def test_normed_delivery_state_needs_no_hardness(tmp_path):
        """Bei +QT/+N ist der Zustand normativ definiert (EN 10083)."""
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff 42CrMo4 +QT",
                                      "vergütet / quenched and tempered"]))
        assert "HT.NO_HARDNESS" not in c


    def test_strength_specification_replaces_hardness(tmp_path):
        c = codes_verfahren(make_ctx(tmp_path, ["Werkstoff C45", "vergütet",
                                      "Rm ≥ 700 N/mm²"]))
        assert "HT.NO_HARDNESS" not in c


    # ======================================================================
    # new_rules
    # ======================================================================
    # Tests der Praxisregeln: Eloxal-Legierung, Schweißbolzen/Verzinkung,
    # GD&T-Widersprüche, Positionsballone.









    # ------------------------------------------------ Eloxal-Legierungswahl
    def test_cast_alloy_anodized_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff: AlSi10Mg", "schwarz eloxiert"]), run_drawing_checks)
        assert c["MAT.ANODIZE_ALLOY"].severity == Severity.ERROR


    def test_alcu_alloy_anodized_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-2007", "eloxiert natur"]), run_drawing_checks)
        assert "MAT.ANODIZE_ALLOY" in c


    def test_7075_anodized_is_warning(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-7075", "anodized type II"]), run_drawing_checks)
        assert c["MAT.ANODIZE_ALLOY"].severity == Severity.WARNING


    def test_6082_anodized_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff EN AW-6082", "eloxiert 15 µm"]), run_drawing_checks)
        assert "MAT.ANODIZE_ALLOY" not in c


    # ---------------------------------------- Schweißbolzen auf Verzinkung
    def test_stud_weld_on_galvanized_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff: S235JR",
            "Blech feuerverzinkt nach ISO 1461",
            "4x Schweißbolzen M8 ISO 13918",
        ]), run_drawing_checks)
        assert c["PROC.STUD_ON_ZINC"].severity == Severity.ERROR


    def test_weld_and_zinc_without_sequence_is_warning(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
            "Baugruppe feuerverzinkt",
        ]), run_drawing_checks)
        assert c["PROC.WELD_ZINC_ORDER"].severity == Severity.WARNING


    def test_weld_and_zinc_with_sequence_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff: S355J2", "Naht a4 umlaufend, ISO 5817-C",
            "Nach dem Schweißen komplett feuerverzinken (ISO 1461)",
        ]), run_drawing_checks)
        assert "PROC.WELD_ZINC_ORDER" not in c
        assert "PROC.STUD_ON_ZINC" not in c


    # ---------------------------------------------------- GD&T-Widersprüche
    def test_form_tolerance_with_datum_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1 A"]), run_drawing_checks)
        assert c["GPS.FORM_WITH_DATUM"].severity == Severity.ERROR


    def test_form_tolerance_without_datum_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "⏥ 0,1", "○ 0,05"]), run_drawing_checks)
        assert "GPS.FORM_WITH_DATUM" not in c


    def test_deprecated_concentricity_symbol_warns(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "◎ ⌀0,2 A", "Bezug A"]), run_drawing_checks)
        assert c["GPS.DEPRECATED_SYMBOL"].severity == Severity.WARNING


    # ------------------------------------------------------ Positionsballone
    BOM = [
        (600, "Stückliste"),
        (600, "Pos. Menge Benennung"),
        (600, "1 2 Grundplatte"),
        (600, "2 1 Rippe"),
    ]


    def test_bom_without_balloons_warns(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff S235JR"] + BOM), run_drawing_checks)
        assert c["DOC.BALLOONS"].severity == Severity.WARNING


    def test_bom_with_balloons_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff S235JR",
            (100, "1"), (150, "2"),   # Ballon-Nummern an den Teilen
        ] + BOM), run_drawing_checks)
        assert "DOC.BALLOONS" not in c


    def test_no_bom_no_balloon_check(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "Einzelteil"]), run_drawing_checks)
        assert "DOC.BALLOONS" not in c


    # ------------------------------------ Beschichtung vs. Passung/Gewinde
    def test_zinc_with_fit_warns(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff S355J2", "Bohrung ⌀22 H7", "feuerverzinkt ISO 1461"]), run_drawing_checks)
        assert c["COAT.FIT"].severity == Severity.WARNING


    def test_zinc_with_fit_and_note_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff S355J2", "Bohrung ⌀22 H7",
            "feuerverzinkt ISO 1461, Passung H7 nach dem Verzinken nachreiben"]), run_drawing_checks)
        assert "COAT.FIT" not in c


    def test_anodize_with_thread_warns(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff EN AW-6082", "Gewinde M8", "schwarz eloxiert"]), run_drawing_checks)
        assert "COAT.FIT" in c


    def test_zinc_without_fit_no_warning(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff S235JR", "feuerverzinkt"]), run_drawing_checks)
        assert "COAT.FIT" not in c


    # ------------------------------------------------ Brünieren auf Nichtstahl
    def test_blackening_on_stainless_conflict(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff 1.4301", "brüniert"]), run_drawing_checks)
        assert "MAT.COATING_CONFLICT" in c


    def test_blackening_on_steel_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "brüniert"]), run_drawing_checks)
        assert "MAT.COATING_CONFLICT" not in c


    # ------------------------------------------------------ Mischverbindungen
    def test_alu_plus_steel_welded_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Pos 1: S235JR", "Pos 2: EN AW-5754", "geschweißt nach ISO 5817-C"]), run_drawing_checks)
        assert c["WELD.MIXED"].severity == Severity.ERROR


    def test_stainless_plus_steel_needs_filler(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Pos 1: S355J2", "Pos 2: 1.4301", "Naht a3 umlaufend"]), run_drawing_checks)
        assert c["WELD.MIXED_FILLER"].severity == Severity.WARNING


    def test_stainless_plus_steel_with_309_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Pos 1: S355J2", "Pos 2: 1.4301",
            "Naht a3 umlaufend, Zusatzwerkstoff 309L"]), run_drawing_checks)
        assert "WELD.MIXED_FILLER" not in c


    # --------------------------------------- Schweißteil nur mit ISO 2768
    def test_weld_with_only_2768_warns(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff S355J2", "geschweißt ISO 5817-C",
            "Allgemeintoleranzen ISO 2768-mK"]), run_drawing_checks)
        assert c["NORM.WELD_GENTOL"].severity == Severity.WARNING


    def test_weld_with_13920_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, [
            "Werkstoff S355J2", "geschweißt ISO 5817-C",
            "Allgemeintoleranzen ISO 2768-mK und ISO 13920-BF"]), run_drawing_checks)
        assert "NORM.WELD_GENTOL" not in c


    # -------------------------------------------- Gewinde mit Passungsklasse
    def test_thread_with_fit_class_is_error(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 H7"]), run_drawing_checks)
        assert c["THRD.FIT_CLASS"].severity == Severity.ERROR


    def test_thread_with_correct_class_is_fine(tmp_path):
        c = codes(make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12 - 6H"]), run_drawing_checks)
        assert "THRD.FIT_CLASS" not in c


    # ======================================================================
    # dimensions
    # ======================================================================


    def w(text: str) -> Word:
        return Word(text, BBox(0, 0, 10, 10), 0)


    def parse(text: str, prev: str = ""):
        return _parse_word(w(text), prev)


    def kinds(text: str, prev: str = ""):
        return [(d.kind, d.value) for d in parse(text, prev)]


    def test_diameter_variants():
        assert kinds("⌀40") == [(DimKind.DIAMETER, 40.0)]
        assert kinds("Ø22 H11") == [(DimKind.DIAMETER, 22.0)]
        assert kinds("4×⌀18")[0] == (DimKind.DIAMETER, 18.0)


    def test_linear_with_tolerances_and_fits():
        assert kinds("420") == [(DimKind.LINEAR, 420.0)]
        assert kinds("120,5") == [(DimKind.LINEAR, 120.5)]
        assert kinds("60±0,2")[0][1] == 60.0
        assert kinds("40H7") == [(DimKind.LINEAR, 40.0)]


    def test_radius_and_thread():
        assert kinds("R5") == [(DimKind.RADIUS, 5.0)]
        assert kinds("M12x1,5") == [(DimKind.THREAD, 12.0)]


    def test_exclusions():
        assert parse("2768", prev="iso") == []          # Normbezug
        assert parse("1:2") == []                        # Maßstab
        assert parse("10473215") == []                   # Materialnummer
        assert parse("2025") == []                       # Jahr
        assert parse("45°") == []                        # Winkel
        assert parse("12,5kg") == []                     # Gewicht
        assert parse("1/1") == []                        # Blattangabe


    def test_envelope_top_values():
        dims = [d for t in ("420", "⌀70", "120", "90", "80", "70", "60", "R3")
                for d in parse(t)]
        env = estimate_envelope(dims)
        assert env[0] == 420.0
        assert 3.0 not in env  # Radius zählt nicht als Hüllmaß


    def test_extract_from_real_mock(mock_dir):
        pass  # (Import entfaellt - alles ein Modul)

        with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
            dims = extract_dimensions(pdf)
        values = {d.value for d in dims}
        assert 420.0 in values          # Gesamtlänge
        assert 55.0 in values           # ⌀55
        assert 2768.0 not in values     # ISO 2768 nicht als Maß


    # ======================================================================
    # fcf
    # ======================================================================
    # Toleranzrahmen-Erkennung (Feature Control Frames) als Vektorgrafik.
    #
    # Nutzt die echten Kalibrierzeichnungen aus mockdata/echt_quellen – nur dort
    # liegen Toleranzrahmen so vor wie in der Praxis (Grafik statt Textsymbol).





    needs_echt = pytest.mark.skipif(
        not (ECHT / "lensmount.pdf").exists(),
        reason="Kalibrierzeichnungen nicht vorhanden")


    @needs_echt
    def test_frames_found_on_real_drawing():
        with DrawingPdf(ECHT / "lensmount.pdf") as pdf:
            frames = find_feature_frames(pdf)
        assert len(frames) >= 4
        assert all(f.value is not None for f in frames)


    @needs_echt
    def test_datums_read_from_graphic_frame():
        with DrawingPdf(ECHT / "supportBracket.pdf") as pdf:
            frames = find_feature_frames(pdf)
        with_datums = [f for f in frames if f.has_datums]
        assert with_datums, "kein Rahmen mit Bezügen erkannt"
        assert with_datums[0].datums == ["A", "B", "C"]


    @needs_echt
    def test_frames_are_deduplicated():
        with DrawingPdf(ECHT / "copperThermalMass.pdf") as pdf:
            frames = find_feature_frames(pdf)
        seen = {(f.page, round(f.bbox.x0), round(f.bbox.y0)) for f in frames}
        assert len(seen) == len(frames)


    @needs_echt
    def test_drawing_without_gdt_has_no_frames():
        with DrawingPdf(ECHT / "thermalStrap.pdf") as pdf:
            assert find_feature_frames(pdf) == []


    def _ctx(pdf_path: Path) -> CheckContext:
        return CheckContext("x", DrawingPdf(pdf_path), PackageContent(),
                            load_profile("default"))


    @needs_echt
    def test_graphic_gdt_hint_is_info():
        ctx = _ctx(ECHT / "lensmount.pdf")
        check_gdt_readability(ctx)
        assert ctx.findings[0].code == "DOC.GDT_GRAPHIC"
        assert ctx.findings[0].severity == Severity.INFO


    @needs_echt
    def test_no_hint_without_frames():
        ctx = _ctx(ECHT / "thermalStrap.pdf")
        check_gdt_readability(ctx)
        assert not ctx.findings


    @needs_echt
    def test_diameter_zone_without_datum_is_error():
        ctx = _ctx(ECHT / "thermalStrap.pdf")
        ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                    texts=["⌀0,2"], value=0.2,
                                    diameter_zone=True, datums=[])]
        check_diameter_zone_needs_datum(ctx)
        assert ctx.findings[0].code == "GPS.ZONE_NO_DATUM"
        assert ctx.findings[0].severity == Severity.ERROR


    @needs_echt
    def test_diameter_zone_with_datum_is_fine():
        ctx = _ctx(ECHT / "thermalStrap.pdf")
        ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                    texts=["⌀0,2", "A"], value=0.2,
                                    diameter_zone=True, datums=["A"])]
        check_diameter_zone_needs_datum(ctx)
        assert not ctx.findings


    @needs_echt
    def test_plain_zone_without_datum_is_fine():
        """Ohne ⌀ kann es eine Formtoleranz sein – die braucht keinen Bezug."""
        ctx = _ctx(ECHT / "thermalStrap.pdf")
        ctx._frames = [FeatureFrame(bbox=BBox(0, 0, 50, 10), page=0,
                                    texts=["0,05"], value=0.05,
                                    diameter_zone=False, datums=[])]
        check_diameter_zone_needs_datum(ctx)
        assert not ctx.findings


    # ======================================================================
    # gps_dim_rules
    # ======================================================================
    # GPS-Tiefenprüfung, Bemaßungs- und Fertigungsregeln.
    #
    # Der Helfer platziert Texte an exakten Koordinaten, weil die Maßketten-
    # Erkennung bewusst die räumliche Anordnung auswertet.







    class _FakeBlock:
        """Textblock-Stub mit Dummy-Position."""

        def __init__(self, text, i=0):
            pass  # (Import entfaellt - alles ein Modul)
            self.text = text
            self.bbox = BBox(10, 10 + i * 20, 200, 25 + i * 20)
            self.page = 0


    class _FakePdf:
        """PDF-Stub für symbolbasierte Tests.

        DejaVu (die Testschrift) kann ⌖/Ⓜ/Ⓔ nicht darstellen; echte CAD-PDFs
        schon. Der Stub liefert den Text direkt, damit die Symbolregeln
        unabhängig von der Schriftabdeckung geprüft werden können.
        """

        def __init__(self, lines):
            self._blocks = [_FakeBlock(t, i) for i, t in enumerate(lines)]

        def blocks(self):
            return self._blocks

        def full_text(self):
            return "\n".join(b.text for b in self._blocks)

        def words(self):
            pass  # (Import entfaellt - alles ein Modul)
            pass  # (Import entfaellt - alles ein Modul)
            out = []
            for b in self._blocks:
                for i, t in enumerate(b.text.split()):
                    out.append(Word(t, BBox(b.bbox.x0 + i * 20, b.bbox.y0,
                                            b.bbox.x0 + i * 20 + 15, b.bbox.y1),
                                    0))
            return out


    def sym_ctx(lines, profile="default") -> CheckContext:
        return CheckContext("123", _FakePdf(lines), PackageContent(),
                            load_profile(profile))


    def run_all(ctx) -> dict:
        dims = extract_dimensions(ctx.pdf)
        run_gps_checks(ctx, dims)
        run_dimension_checks(ctx, dims)
        return {f.code: f for f in ctx.findings}


    # =========================================================== GPS-Regeln
    def test_fit_without_envelope_warns():
        """Klassiker: ⌀20 H7 ohne Ⓔ – Form bleibt nach ISO 8015 unbegrenzt."""
        c = run_all(sym_ctx(["Werkstoff C45", "Lagersitz ⌀20 H7",
                             "Tolerierung ISO 8015"]))
        assert c["GPS.ENVELOPE"].severity == Severity.WARNING
        assert "H7" in c["GPS.ENVELOPE"].text


    def test_fit_with_envelope_symbol_is_fine():
        c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7 Ⓔ"]))
        assert "GPS.ENVELOPE" not in c


    def test_fit_with_form_tolerance_is_fine():
        c = run_all(sym_ctx(["Werkstoff C45", "⌀20 H7", "⌭ 0,01"]))
        assert "GPS.ENVELOPE" not in c


    def test_coarse_fit_not_flagged():
        """Grobe Passungen (IT ≥ 9) sind unkritisch."""
        c = run_all(sym_ctx(["Werkstoff C45", "⌀22 H11"]))
        assert "GPS.ENVELOPE" not in c


    def test_undefined_datum_is_error():
        c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 X"]))
        assert c["GPS.DATUM_UNDEFINED"].severity == Severity.ERROR
        assert "X" in c["GPS.DATUM_UNDEFINED"].text


    def test_defined_datum_is_fine():
        c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                             "Bezug A = Auflagefläche"]))
        assert "GPS.DATUM_UNDEFINED" not in c


    def test_position_without_ted_warns():
        c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                             "Bezug A", "Abstand 50±0,1"]))
        assert c["GPS.POSITION_NO_TED"].severity == Severity.WARNING


    def test_position_with_ted_is_fine():
        c = run_all(sym_ctx(["Werkstoff C45", "⌖ ⌀0,2 A",
                             "Bezug A", "[50]", "[30]"]))
        assert "GPS.POSITION_NO_TED" not in c


    def test_modifier_on_form_tolerance_is_error():
        c = run_all(sym_ctx(["Werkstoff C45", "⏥ 0,05 Ⓜ"]))
        assert c["GPS.MOD_ON_FORM"].severity == Severity.ERROR


    # ====================================================== Maßketten-Check
    def test_closed_chain_detected(tmp_path):
        """Echte horizontale Kette: 20+30+50 = 100, Teil und Summe toleriert."""
        items = [
            (40, 300, "20±0,1"), (140, 300, "30±0,1"), (240, 300, "50±0,1"),
            (140, 340, "100±0,1"),
            (40, 60, "Werkstoff C45"),
        ]
        c = run_all(make_ctx(tmp_path, items))
        assert c["DIM.CHAIN"].severity == Severity.WARNING
        assert "Maßkette" in c["DIM.CHAIN"].text


    def test_open_chain_is_fine(tmp_path):
        """Nur das Gesamtmaß toleriert = korrekte offene Kette."""
        items = [
            (40, 300, "20"), (140, 300, "30"), (240, 300, "50"),
            (140, 340, "100±0,1"),
            (40, 60, "Werkstoff C45"),
        ]
        c = run_all(make_ctx(tmp_path, items))
        assert "DIM.CHAIN" not in c


    def test_scattered_dimensions_no_false_chain(tmp_path):
        """Zufällig passende Summen ohne gemeinsame Maßlinie -> kein Finding."""
        items = [
            (40, 100, "20±0,1"), (400, 250, "30±0,1"), (700, 480, "50±0,1"),
            (100, 520, "100±0,1"),
            (40, 60, "Werkstoff C45"),
        ]
        c = run_all(make_ctx(tmp_path, items))
        assert "DIM.CHAIN" not in c


    # ================================================ Fertigungsgerechtigkeit
    def test_tight_tolerance_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Lagersitz ⌀30 h4",
                                        "Länge 80±0,003"]))
        assert c["MFG.TIGHT_TOL"].severity == Severity.WARNING


    def test_normal_tolerance_not_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀30 h9", "80±0,2"]))
        assert "MFG.TIGHT_TOL" not in c


    def test_deep_hole_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀8 ↧80"]))
        assert c["MFG.DEEP_HOLE"].severity == Severity.WARNING
        assert "10.0:1" in c["MFG.DEEP_HOLE"].text


    def test_shallow_hole_not_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "⌀20 ↧40"]))
        assert "MFG.DEEP_HOLE" not in c


    def test_sharp_corner_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R0"]))
        assert c["MFG.SHARP_CORNER"].severity == Severity.WARNING


    def test_normal_radius_not_flagged(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff C45", "Innenecken R3"]))
        assert "MFG.SHARP_CORNER" not in c


    # ============================================== Oberflächen-Plausibilität
    def test_fine_ra_on_cast_surface_is_error(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff EN-GJL-250",
                                        "Gussteil, Oberfläche Ra 0,8"]))
        assert c["SURF.UNREALISTIC"].severity == Severity.ERROR


    def test_fine_ra_with_grinding_is_fine(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4",
                                        "Lagersitze geschliffen, Ra 0,2"]))
        assert "SURF.UNREALISTIC" not in c


    def test_very_fine_ra_without_process_warns(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 0,1"]))
        assert c["SURF.UNREALISTIC"].severity == Severity.WARNING


    def test_normal_ra_is_fine(tmp_path):
        c = run_all(make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Ra 3,2"]))
        assert "SURF.UNREALISTIC" not in c


    # ================================================== Regressionsschutz
    def test_clean_drawing_triggers_no_new_rules(tmp_path):
        """Eine saubere Zeichnung darf keine der neuen Regeln auslösen."""
        c = run_all(make_ctx(tmp_path, [
            "Werkstoff 42CrMo4 +QT",
            "Allgemeintoleranzen ISO 2768-fH, Tolerierung ISO 8015",
            "⌀40 h6 (E), ⌀55 h6 (E)",
            "Oberfläche Ra 1,6, Lagersitze geschliffen Ra 0,8",
            "Kanten ISO 13715, Innenradien R3",
        ]))
        new_codes = {k for k in c
                     if k.startswith(("GPS.", "DIM.", "MFG.", "SURF.UNREAL"))}
        assert not new_codes, f"unerwartete Findings: {new_codes}"


    # ======================================================================
    # scale
    # ======================================================================
    # Maßstabsextraktion und maßstabsbasierte Prüfungen.







    def make_pdf(tmp_path: Path, lines) -> DrawingPdf:
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        kwargs = {}
        if Path(FONT).exists():
            page.insert_font(fontname="T", fontfile=FONT)
            kwargs["fontname"] = "T"
        for i, line in enumerate(
                list(lines)
                + ["Interne Testzeichnung – Blatt 1 von 1, Ausgabestand 2026"]):
            page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
        path = tmp_path / "t.pdf"
        doc.save(path)
        doc.close()
        return DrawingPdf(path)


    def ctx_for(tmp_path, lines, profile="default") -> CheckContext:
        return CheckContext("123", make_pdf(tmp_path, lines), PackageContent(),
                            load_profile(profile))


    # ------------------------------------------------------ Maßstabsextraktion
    @pytest.mark.parametrize("text,expected", [
        ("Maßstab 1:2", 2.0),
        ("Maßstab / Scale 1:2,5", 2.5),
        ("SCALE: 2:1", 0.5),
        ("Maßstab 1:1", 1.0),
        ("Scale 1:10", 10.0),
    ])
    def test_labelled_scales(tmp_path, text, expected):
        with make_pdf(tmp_path, [text]) as pdf:
            assert extract_scale(pdf) == pytest.approx(expected)


    def test_unlabelled_ratio_is_ignored(tmp_path):
        """Blatt-/Zeitangaben dürfen nicht als Maßstab gelesen werden."""
        with make_pdf(tmp_path, ["Blatt 1/1", "Sheet 1:1 of 3", "08:30"]) as pdf:
            assert extract_scale(pdf) is None


    def test_unusual_ratio_is_rejected(tmp_path):
        with make_pdf(tmp_path, ["Maßstab 1:3,7"]) as pdf:
            assert extract_scale(pdf) is None


    def test_mm_per_point():
        assert mm_per_point(1.0) == pytest.approx(25.4 / 72)
        assert mm_per_point(2.0) == pytest.approx(2 * 25.4 / 72)


    @needs_echt
    def test_scale_from_real_drawings():
        with DrawingPdf(ECHT / "lensmount.pdf") as pdf:
            assert extract_scale(pdf) == 1.0
        with DrawingPdf(ECHT / "CassegrainBase.pdf") as pdf:
            assert extract_scale(pdf) == 0.5


    # ------------------------------------------- Messung und Bewertung
    def test_measurement_reported_even_when_rule_disabled(mock_dir):
        """Die gemessene Ansichtsgröße gehört auch ohne Bewertung in die Excel."""
        with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
            ctx = CheckContext("10473217", pdf, PackageContent(),
                               load_profile("default"))
            summary = check_scale_consistency(ctx, [])
        assert "Ansicht gemessen" in summary
        assert "1:2" in summary
        assert not ctx.findings          # Regel ist im Auslieferzustand aus


    def test_mock_drawings_are_exactly_to_scale(mock_dir):
        """Die Mockzeichnungen sind maßstabsgetreu – Messung trifft die Maße."""
        pass  # (Import entfaellt - alles ein Modul)

        with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
            ctx = CheckContext("x", pdf, PackageContent(), load_profile("default"))
            w, h, _view = measure_largest_view(ctx, extract_scale(pdf))
        assert w == pytest.approx(420, abs=6)     # Wellenlänge
        assert h == pytest.approx(70, abs=6)      # größter Durchmesser


    def _enable(profile_name, *codes):
        prof = load_profile(profile_name)
        for c in codes:
            prof.rules.setdefault(c, {})["enabled"] = True
        return prof


    def test_oversized_view_is_flagged_when_enabled(tmp_path):
        ctx = ctx_for(tmp_path, ["Maßstab 1:1", "Werkstoff C45"])
        ctx.profile = _enable("default", "SCALE.MISMATCH")
        # Ansicht künstlich groß: Stub über measure ersetzen
        sc = sys.modules[__name__]

        class _V:
            bbox = (0, 0, 500, 200)
        orig = sc.measure_largest_view
        sc.measure_largest_view = lambda c, s: (200.0, 80.0, _V())
        try:
            check_scale_consistency(ctx, [DimValue(50, DimKind.LINEAR, "50",
                                                   BBox(0, 0, 1, 1), 0)])
        finally:
            sc.measure_largest_view = orig
        assert ctx.findings[0].code == "SCALE.MISMATCH"
        assert ctx.findings[0].severity == Severity.WARNING


    def test_undersized_view_is_never_flagged(tmp_path):
        """Zu klein gemessene Ansichten sind ein Erkennungsproblem, kein Fehler."""
        ctx = ctx_for(tmp_path, ["Maßstab 1:1", "Werkstoff C45"])
        ctx.profile = _enable("default", "SCALE.MISMATCH")
        sc = sys.modules[__name__]

        class _V:
            bbox = (0, 0, 100, 50)
        orig = sc.measure_largest_view
        sc.measure_largest_view = lambda c, s: (30.0, 20.0, _V())
        try:
            check_scale_consistency(ctx, [DimValue(200, DimKind.LINEAR, "200",
                                                   BBox(0, 0, 1, 1), 0)])
        finally:
            sc.measure_largest_view = orig
        assert not ctx.findings


    def test_view_vs_model_needs_occ(tmp_path):
        ctx = ctx_for(tmp_path, ["Maßstab 1:1"])
        ctx.profile = _enable("default", "GEO.VIEW_SIZE")
        geo = StepGeometry(obb_dims=(50, 20, 10), backend="fallback")
        check_view_vs_model(ctx, geo, [])
        assert not ctx.findings


    # ======================================================================
    # beschaffung_und_masse
    # ======================================================================
    # Tests der Regeln aus Runde 3: Masse-Plausibilität, Dokumenten-Formalien,
    # internationale Beschaffung, Bemaßungswidersprüche, Wasserstoffversprödung.
    #
    # Zu jeder Regel ein Positiv- und ein Negativfall (Konvention aus CLAUDE.md).







    def dims_of(ctx) -> list[DimValue]:
        return extract_dimensions(ctx.pdf, 6000)




    # ------------------------------------------------------ Masse-Plausibilität
    def _dim(value: float, kind: DimKind = DimKind.LINEAR, **kw) -> DimValue:
        return DimValue(value=value, kind=kind, raw=f"{value:g}",
                        bbox=BBox(0, 0, 10, 10), page=0, **kw)


    def test_mass_impossible_is_error(tmp_path):
        """100 kg auf 100×80×20 mm Stahl (max. 1,3 kg) kann nicht stimmen."""
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 100 kg"])
        check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)])
        assert "MASS.IMPOSSIBLE" in codes(ctx)
        assert ctx.findings[0].severity == Severity.ERROR


    def test_mass_impossible_nennt_einheitenverdacht(tmp_path):
        """Faktor ≈ 1000 -> Hinweis auf g/kg-Verwechslung."""
        # 100x80x60 mm Stahl = 3,77 kg; angegeben ist das 1000-fache.
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 3768 kg"])
        check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(60)])
        assert "g statt kg" in ctx.findings[0].detail


    def test_mass_plausibel_meldet_nicht(tmp_path):
        """0,9 kg auf 100×80×20 Stahl (max. 1,26 kg) ist plausibel."""
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 0,9 kg"])
        summary = check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)])
        assert not codes(ctx)
        assert "Füllgrad" in summary


    def test_mass_ohne_werkstoff_nicht_pruefbar(tmp_path):
        ctx = make_ctx(tmp_path, ["Gewicht: 100 kg"])
        assert check_mass_plausibility(ctx, [_dim(100), _dim(80), _dim(20)]) == ""
        assert not codes(ctx)


    def test_mass_too_light(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR", "Gewicht: 0,005 kg"])
        check_mass_plausibility(ctx, [_dim(200), _dim(200), _dim(50)])
        assert "MASS.TOO_LIGHT" in codes(ctx)


    def test_density_hint_erkennt_falschen_werkstoff(tmp_path):
        """1 kg auf 128 cm³ = 7,8 g/cm³ – angegeben ist aber Aluminium."""
        ctx = make_ctx(tmp_path, ["Werkstoff: EN AW-6060", "Gewicht: 1,00 kg"])
        check_density_hint(ctx, model_volume_mm3=128000.0)
        assert "MASS.DENSITY_HINT" in codes(ctx)
        assert "g/cm³" in ctx.findings[0].text


    def test_density_hint_schweigt_wenn_passend(tmp_path):
        """345 g auf 128 cm³ = 2,7 g/cm³ – passt zu Aluminium."""
        ctx = make_ctx(tmp_path, ["Werkstoff: EN AW-6060", "Gewicht: 0,345 kg"])
        check_density_hint(ctx, model_volume_mm3=128000.0)
        assert not codes(ctx)


    def test_fertiggewicht_schlaegt_rohgewicht(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Rohteilgewicht: 12,0 kg", "Gewicht: 7,5 kg"])
        assert extract_weight_kg(ctx.pdf) == 7.5


    # ------------------------------------------------------ Dokument-Formalien
    def test_sheet_count_erkennt_fehlende_blaetter(tmp_path):
        ctx = make_ctx(tmp_path, ["Blatt 1 von 3", "Werkstoff: S235JR"])
        run_doc_checks(ctx)
        assert "DOC.SHEET_COUNT" in codes(ctx)


    def test_sheet_count_ok_bei_vollstaendigem_paket(tmp_path):
        ctx = make_ctx(tmp_path, ["Blatt 1 von 2"], pages=2)
        run_doc_checks(ctx)
        assert "DOC.SHEET_COUNT" not in codes(ctx)


    def test_annotations_werden_gemeldet(tmp_path):
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        page.insert_text((40, 60), "Werkstoff: S235JR", fontsize=10)
        page.add_text_annot((100, 100), "bitte noch aendern")
        path = tmp_path / "markup.pdf"
        doc.save(path)
        doc.close()
        ctx = CheckContext("1", DrawingPdf(path), PackageContent(),
                           load_profile("default"))
        run_doc_checks(ctx)
        assert "DOC.ANNOTATIONS" in codes(ctx)


    def test_sauberes_pdf_ohne_annotationsmeldung(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff: S235JR"])
        run_doc_checks(ctx)
        assert "DOC.ANNOTATIONS" not in codes(ctx)


    def test_datum_in_der_zukunft(tmp_path):
        ctx = make_ctx(tmp_path, ["Aenderung vom 01.01.2099", "Werkstoff: S235JR"])
        run_doc_checks(ctx)
        assert "DOC.DATE_FUTURE" in codes(ctx)


    def test_gemischte_dezimaltrenner(tmp_path):
        ctx = make_ctx(tmp_path, ["12,5  30,2  8,75", "12.5  30.2  8.75"])
        run_doc_checks(ctx)
        assert "DOC.DECIMAL_MIXED" in codes(ctx)


    def test_einheitlicher_dezimaltrenner_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["12,5  30,2  8,75  40,0"])
        run_doc_checks(ctx)
        assert "DOC.DECIMAL_MIXED" not in codes(ctx)


    # ------------------------------------------------ Internationale Beschaffung
    def test_vage_angabe_wird_gemeldet(tmp_path):
        ctx = make_ctx(tmp_path, ["Bohrung ca. 12 mm", "Oberflaeche nach Absprache"])
        run_purchasing_checks(ctx, [])
        assert "PUR.VAGUE_SPEC" in codes(ctx)


    def test_praezise_angabe_ohne_meldung(tmp_path):
        ctx = make_ctx(tmp_path, ["Bohrung 12 H7", "Ra 1,6"])
        run_purchasing_checks(ctx, [])
        assert "PUR.VAGUE_SPEC" not in codes(ctx)


    def test_hausnorm_wird_gemeldet(tmp_path):
        ctx = make_ctx(tmp_path, ["Oberflaeche nach WN 51204"])
        run_purchasing_checks(ctx, [])
        assert "PUR.INTERNAL_NORM" in codes(ctx)


    def test_oeffentliche_norm_ohne_meldung(tmp_path):
        ctx = make_ctx(tmp_path, ["Oberflaeche nach EN ISO 1461"])
        run_purchasing_checks(ctx, [])
        assert "PUR.INTERNAL_NORM" not in codes(ctx)


    def test_sonderblechdicke(tmp_path):
        ctx = make_ctx(tmp_path, ["Blechdicke 4,7 mm", "Blech gekantet"])
        run_purchasing_checks(ctx, [])
        assert "PUR.STOCK_SIZE" in codes(ctx)


    def test_lagerblechdicke_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Blechdicke 5,0 mm", "Blech gekantet"])
        run_purchasing_checks(ctx, [])
        assert "PUR.STOCK_SIZE" not in codes(ctx)


    # ------------------------------------------------- Bemaßungswidersprüche
    def test_vertauschte_grenzabmasse(tmp_path):
        ctx = make_ctx(tmp_path, ["x"])
        dim = _dim(40.0, tol_plus=-0.2, tol_minus=0.1)
        check_tolerance_order(ctx, [dim])
        assert "DIM.TOL_ORDER" in codes(ctx)


    def test_korrekte_grenzabmasse_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["x"])
        check_tolerance_order(ctx, [_dim(40.0, tol_plus=0.2, tol_minus=-0.1)])
        assert not codes(ctx)


    def test_ted_mit_toleranz(tmp_path):
        ctx = make_ctx(tmp_path, ["x"])
        check_tolerance_order(ctx, [_dim(40.0, is_basic=True, tol_plus=0.1,
                                         tol_minus=-0.1)])
        assert "DIM.BASIC_TOL" in codes(ctx)


    def test_rauheit_zu_grob_fuer_toleranz(tmp_path):
        ctx = make_ctx(tmp_path, ["Rz 63"])
        check_roughness_vs_tolerance(ctx, [_dim(20.0, fit="H7")])
        assert "SURF.TOL_MISMATCH" in codes(ctx)


    def test_passende_rauheit_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Rz 4"])
        check_roughness_vs_tolerance(ctx, [_dim(20.0, fit="H7")])
        assert not codes(ctx)


    # --------------------------------------------------- Wasserstoffversprödung
    def test_galvanisch_auf_hochfest_ohne_entsproedung(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Haerte 45 HRC",
                                  "galvanisch verzinkt nach ISO 2081"])
        check_hydrogen_embrittlement(ctx)
        assert "COAT.EMBRITTLEMENT" in codes(ctx)


    def test_galvanisch_mit_entsproedung_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff 42CrMo4", "Haerte 45 HRC",
                                  "galvanisch verzinkt nach ISO 2081",
                                  "wasserstoffarm gegluht nach EN ISO 4042"])
        check_hydrogen_embrittlement(ctx)
        assert not codes(ctx)


    def test_galvanisch_auf_baustahl_ohne_meldung(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "galvanisch verzinkt"])
        check_hydrogen_embrittlement(ctx)
        assert not codes(ctx)


    # ========================================================================
    # test_geometrie
    # ========================================================================
    # Abgleich gegen das STEP-Modell: Masse, Bohrbild, Spiegelung, Silhouette.
    # ======================================================================
    # step_compare
    # ======================================================================
    import pytest



    def dv(value, kind=DimKind.LINEAR):
        return DimValue(value, kind, str(value), BBox(0, 0, 1, 1), 0)


    @pytest.fixture(scope="module")
    def profile():
        return load_profile("default")


    def test_occ_analysis_on_shaft(mock_dir):
        geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
        assert geo.obb_dims[0] == pytest.approx(420, abs=1)
        assert geo.obb_dims[1] == pytest.approx(70, abs=1)
        if geo.backend == "occ":
            assert 70.0 in geo.cylinder_diameters
            assert geo.volume > 0


    def test_pointcloud_fallback_on_shaft(mock_dir):
        geo = _analyze_pointcloud(mock_dir / "_arbeit" / "M_10473217.stp")
        assert geo.backend == "fallback"
        assert geo.obb_dims[0] == pytest.approx(420, abs=2)


    def test_matching_geometry_passes(profile):
        geo = StepGeometry(obb_dims=(420.0, 70.0, 70.0),
                           cylinder_diameters=[70.0, 55.0, 45.0, 40.0])
        dims = [dv(420), dv(120), dv(90), dv(70, DimKind.DIAMETER),
                dv(55, DimKind.DIAMETER)]
        res = compare_step_to_drawing(geo, dims, profile)
        assert res.verdict == "passt"


    def test_wrong_config_detected_by_diagonal(profile):
        # Zeichnung 330 lang, STEP nur 200 -> Maß größer als Raumdiagonale
        geo = StepGeometry(obb_dims=(200.0, 140.0, 120.0))
        dims = [dv(330), dv(280), dv(180)]
        res = compare_step_to_drawing(geo, dims, profile)
        assert res.verdict == "passt_nicht"


    def test_no_dims_is_uncertain(profile):
        geo = StepGeometry(obb_dims=(100.0, 50.0, 20.0))
        res = compare_step_to_drawing(geo, [], profile)
        assert res.verdict == "unsicher"


    def test_guss_profile_is_more_tolerant():
        guss = load_profile("guss")
        default = load_profile("default")
        geo = StepGeometry(obb_dims=(255.0, 180.0, 120.0))  # 25 mm unter Nennmaß
        dims = [dv(280), dv(180), dv(120)]
        assert compare_step_to_drawing(geo, dims, guss).verdict == "passt"
        assert compare_step_to_drawing(geo, dims, default).verdict != "passt"


    # --------------------------------------------- OCP-Fassungsunabhaengigkeit
    def test_box_bounds_kommt_mit_beiden_ocp_fassungen_klar():
        """OCP 7.9 (Python 3.10) und OCP 8.x benennen die Bnd_Box anders.

        7.9 kennt nur CornerMin()/CornerMax(), 8.x zusätzlich GetXMin().
        Beides muss dieselben Werte liefern, sonst läuft das Werkzeug je nach
        Python-Fassung des Zielrechners nicht.
        """
        pass  # (Import entfaellt - alles ein Modul)

        class _Punkt:
            def __init__(self, x, y, z):
                self._w = (x, y, z)

            def X(self):
                return self._w[0]

            def Y(self):
                return self._w[1]

            def Z(self):
                return self._w[2]

        class _Alt:            # OCP 7.9
            def CornerMin(self):
                return _Punkt(1, 2, 3)

            def CornerMax(self):
                return _Punkt(4, 5, 6)

        class _Neu:            # OCP 8.x ohne CornerMin
            def GetXMin(self):
                return 1

            def GetYMin(self):
                return 2

            def GetZMin(self):
                return 3

            def GetXMax(self):
                return 4

            def GetYMax(self):
                return 5

            def GetZMax(self):
                return 6

        assert _box_bounds(_Alt()) == (1, 2, 3, 4, 5, 6)
        assert _box_bounds(_Neu()) == (1, 2, 3, 4, 5, 6)


    # ======================================================================
    # geometry_deep
    # ======================================================================
    # Vertiefte Geometrieprüfungen: Masse, Bohrbild, Gewinde, Maßextraktion.
    from pathlib import Path

    import pymupdf


    pytest.importorskip("OCP", reason="Geometrieprüfung benötigt OpenCascade")




    def dv_dia(value, kind=DimKind.DIAMETER, count=1):
        return DimValue(value=value, kind=kind, raw=str(value),
                        bbox=BBox(0, 0, 1, 1), page=0, count=count)


    # --------------------------------------------------------- STEP-Analyse
    def test_bracket_holes_detected(mock_dir):
        geo = analyze_step(mock_dir / "_arbeit" / "M_10473215.stp")
        assert geo.solid_count == 1 and geo.disjoint_solids == 1
        assert geo.holes.get(18.0) == 4       # 4 Befestigungsbohrungen
        assert geo.holes.get(16.0) == 1       # Kopfbohrung im Steg
        assert not geo.shafts                 # Konsole hat keine Außenzylinder


    def test_shaft_steps_detected_as_shafts(mock_dir):
        geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
        assert set(geo.shafts) >= {70.0, 55.0, 45.0, 40.0}
        assert not geo.holes


    def test_mass_from_volume_and_density(mock_dir):
        geo = analyze_step(mock_dir / "_arbeit" / "M_10473217.stp")
        assert geo.mass_kg(7.85) == pytest.approx(7.4, abs=0.2)
        assert geo.mass_kg(0) is None


    # ---------------------------------------------------- Gewichtsextraktion
    def test_weight_units(tmp_path):
        for text, expect in [("Gewicht 18,4 kg", 18.4), ("Weight 950 g", 0.95),
                             ("Masse 1,2 t", 1200.0)]:
            ctx = make_ctx(tmp_path, [text])
            assert extract_weight_kg(ctx.pdf) == pytest.approx(expect)


    def test_weight_prefers_labelled_value(tmp_path):
        ctx = make_ctx(tmp_path, ["Zusatz 3 kg Beilage", "Gewicht / Weight 42,5 kg"])
        assert extract_weight_kg(ctx.pdf) == pytest.approx(42.5)


    def test_no_weight_returns_none(tmp_path):
        assert extract_weight_kg(make_ctx(tmp_path, ["ohne Angabe"]).pdf) is None


    # ----------------------------------------------------------- Masse-Check
    def test_mass_mismatch_is_error(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 30,0 kg"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                           backend="occ")           # 1000 cm³ × 7,85 = 7,85 kg
        summary = check_mass(ctx, geo)
        codes = {f.code: f for f in ctx.findings}
        assert codes["GEO.MASS"].severity == Severity.ERROR
        assert "kg" in summary


    def test_mass_match_no_finding(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 7,9 kg"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                           backend="occ")
        check_mass(ctx, geo)
        assert not [f for f in ctx.findings if f.code.startswith("GEO.MASS")]


    def test_mass_minor_deviation_is_warning(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 9,5 kg"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                           backend="occ")          # 7,85 kg -> 17 % Abweichung
        check_mass(ctx, geo)
        assert ctx.findings[0].severity == Severity.WARNING


    def test_mass_guss_profile_more_tolerant(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff EN-GJS-400-15", "Gewicht 9,0 kg"],
                       profile="guss")
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                           backend="occ")          # 7,1 kg -> 21 % Abweichung
        check_mass(ctx, geo)
        assert not ctx.findings   # unter der Guss-Warnschwelle von 25 %


    def test_mass_needs_occ_backend(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Gewicht 30 kg"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1_000_000,
                           backend="fallback")
        assert check_mass(ctx, geo) == ""
        assert not ctx.findings


    # -------------------------------------------------------- Bohrbild-Check
    def test_hole_count_missing_is_error(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR", "4×⌀18"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={12.0: 2})
        check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
        codes = {f.code: f for f in ctx.findings}
        assert codes["GEO.HOLE_COUNT"].severity == Severity.ERROR


    def test_hole_count_partial_is_warning(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={18.0: 2})
        check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
        assert ctx.findings[0].severity == Severity.WARNING


    def test_hole_count_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={18.0: 4})
        check_hole_pattern(ctx, geo, [dv_dia(18, count=4)])
        assert not ctx.findings


    def test_single_diameter_is_not_counted(tmp_path):
        """Einzelnennungen ohne Multiplikator lösen keinen Zählabgleich aus."""
        ctx = make_ctx(tmp_path, ["Werkstoff S235JR"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={})
        assert check_hole_pattern(ctx, geo, [dv_dia(18), dv_dia(18)]) == ""
        assert not ctx.findings


    def test_hole_pattern_from_dimensions():
        assert hole_pattern([dv_dia(18, count=4), dv_dia(18, count=2), dv_dia(9)]) == {
            18.0: 6, 9.0: 1}


    # --------------------------------------------------------- Gewinde-Check
    def test_thread_without_core_hole(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff C45", "Gewinde M12"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={30.0: 1})
        check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
        assert ctx.findings[0].code == "GEO.THREAD"


    def test_thread_with_core_hole_ok(tmp_path):
        ctx = make_ctx(tmp_path, ["Werkstoff C45"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={10.2: 4})
        check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
        assert not ctx.findings


    def test_thread_with_clearance_hole_ok(tmp_path):
        """Gewinde im Modell oft als glatte Bohrung im Nennmaß dargestellt."""
        ctx = make_ctx(tmp_path, ["Werkstoff C45"])
        geo = StepGeometry(obb_dims=(100, 50, 20), volume=1000, backend="occ",
                           holes={12.0: 2})
        check_threads(ctx, geo, [dv_dia(12, kind=DimKind.THREAD)])
        assert not ctx.findings


    # ----------------------------------------------- Maßextraktion: Toleranzen
    def test_it_grade_spans():
        assert it_grade_span("H7", 40) == pytest.approx(0.025)
        assert it_grade_span("h6", 40) == pytest.approx(0.016)
        assert it_grade_span("js9", 100) == pytest.approx(0.087)
        assert it_grade_span("", 40) is None


    def test_dimension_tolerance_span():
        d = DimValue(40, DimKind.LINEAR, "40", BBox(0, 0, 1, 1), 0,
                     tol_plus=0.2, tol_minus=-0.1)
        assert d.tolerance_span == pytest.approx(0.3)
        f = DimValue(40, DimKind.DIAMETER, "⌀40H7", BBox(0, 0, 1, 1), 0, fit="H7")
        assert f.tolerance_span == pytest.approx(0.025)
        assert f.it_grade == 7


    # ------------------------------------------------------ E2E-Regression
    def test_wrong_config_has_three_independent_indications(mock_dir, tmp_path):
        """Falsches Gussgehäuse: Hüllmaß, Masse und Bohrbild schlagen an."""
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                        sheet_name="Materialliste", material_column="C",
                        header_row=1, output_dir=tmp_path / "erg")
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start(); orch.join(300)
        res = {r.material: r for r in orch.state.results.values()}
        wrong = {f.code for f in res["10473216"].findings}
        assert {"GEO.MISMATCH", "GEO.MASS", "GEO.HOLE_COUNT"} <= wrong
        # Korrekte Teile bleiben frei von Geometrie-Findings
        for ok_material in ("10473215", "10473217"):
            codes = {f.code for f in res[ok_material].findings}
            assert not [c for c in codes if c.startswith("GEO.")]


    # ------------------------------------------- Einheiten und Baugruppe
    def test_inch_mm_mismatch_detected(tmp_path):
        """Modell in Zoll exportiert: Zeichnungsmaß / OBB ≈ 25,4."""
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Länge 254"])
        geo = StepGeometry(obb_dims=(10.0, 4.0, 2.0), volume=80, backend="occ")
        assert check_unit_mismatch(ctx, geo, [dv_dia(254, kind=DimKind.LINEAR)])
        assert ctx.findings[0].code == "GEO.UNIT_MISMATCH"
        assert ctx.findings[0].severity == Severity.ERROR


    def test_matching_units_no_finding(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Werkstoff S355J2"])
        geo = StepGeometry(obb_dims=(250.0, 100.0, 50.0), volume=1000,
                           backend="occ")
        assert not check_unit_mismatch(ctx, geo, [dv_dia(254, kind=DimKind.LINEAR)])
        assert not ctx.findings


    def test_assembly_without_bom_is_error(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Einzelteil"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                           solid_count=3, disjoint_solids=3)
        check_assembly_vs_part(ctx, geo)
        assert ctx.findings[0].code == "GEO.ASSEMBLY"
        assert ctx.findings[0].severity == Severity.ERROR


    def test_unfused_solids_are_info(tmp_path):
        """Sich berührende Körper sind ein Modellierungs-, kein Dokumentfehler."""
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Werkstoff S355J2"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                           solid_count=2, disjoint_solids=1)
        check_assembly_vs_part(ctx, geo)
        assert ctx.findings[0].code == "GEO.NOT_FUSED"
        assert ctx.findings[0].severity == Severity.INFO


    def test_single_solid_part_is_fine(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        ctx = make_ctx(tmp_path, ["Werkstoff S355J2", "Einzelteil"])
        geo = StepGeometry(obb_dims=(200, 100, 50), volume=1000, backend="occ",
                           solid_count=1, disjoint_solids=1)
        check_assembly_vs_part(ctx, geo)
        assert not ctx.findings


    # ======================================================================
    # contour_projection
    # ======================================================================
    # Tests der Ausbaustufe Konturprojektion (STEP-Silhouetten vs. PDF-Ansichten).



    pytest.importorskip("OCP", reason="Konturprojektion benötigt OpenCascade")


    @pytest.fixture(scope="module")
    def shaft_pdf(mock_dir):
        with DrawingPdf(mock_dir / "_arbeit" / "Z_10473217.pdf") as pdf:
            yield pdf


    def test_silhouettes_from_step(mock_dir):
        sil = project_step_silhouettes(mock_dir / "_arbeit" / "M_10473217.stp")
        assert len(sil) == 3
        assert all(len(s) > 10 for s in sil)
        # Eine Projektion muss das 420x70-Längsprofil sein
        spans = []
        for s in sil:
            xs = [c for seg in s for c in (seg[0], seg[2])]
            ys = [c for seg in s for c in (seg[1], seg[3])]
            spans.append(sorted([max(xs) - min(xs), max(ys) - min(ys)], reverse=True))
        assert any(abs(a - 420) < 2 and abs(b - 70) < 2 for a, b in spans)


    def test_extract_views_filters_frame_and_dimensions(shaft_pdf):
        views = extract_views(shaft_pdf)
        assert 1 <= len(views) <= 4
        # ISO-128-Filter: Konturlinien sind deutlich weniger als alle Segmente
        assert views[0].all_count > len(views[0].segments)


    def test_matching_pair_scores_good(mock_dir, shaft_pdf):
        r = compare_contours(shaft_pdf, mock_dir / "_arbeit" / "M_10473217.stp")
        assert r.views_used >= 1
        assert max(r.per_view) >= SCORE_GOOD


    def test_wrong_pair_scores_low(mock_dir):
        with DrawingPdf(mock_dir / "_arbeit" / "Z_10473215.pdf") as bracket:
            wrong = compare_contours(bracket, mock_dir / "_arbeit" / "M_10473217.stp")
            right = compare_contours(bracket, mock_dir / "_arbeit" / "M_10473215.stp")
        assert wrong.score <= SCORE_BAD
        assert right.score >= SCORE_GOOD
        assert right.score > wrong.score + 0.2


    def test_contour_stage_confirms_uncertain(mock_dir, shaft_pdf):
        """Ein 'unsicher' des Maßabgleichs wird durch gute Kontur bestätigt."""
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
        geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
        unsure = CompareResult("unsicher", "s", "d", main_ok=True)
        out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                                   unsure, geometry)
        assert out.verdict == "passt"
        assert "Kontur-Score" in out.summary


    def test_contour_stage_never_overrides_mismatch(mock_dir, shaft_pdf):
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
        geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
        bad = CompareResult("passt_nicht", "s", "d")
        out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                                   bad, geometry)
        assert out.verdict == "passt_nicht"
        assert "Kontur-Score" not in out.summary  # Stufe läuft dann gar nicht


    def test_contour_stage_disabled_by_profile(mock_dir, shaft_pdf, tmp_path,
                                               monkeypatch):
        d = tmp_path / "regeln"
        d.mkdir()
        (d / "profiles_aus.yaml").write_text(
            "profiles:\n  default:\n    rules:\n"
            "      GEO.CONTOUR: {enabled: false}\n", encoding="utf-8")
        monkeypatch.setenv("DRAWING_CHECKER_RULES", str(d))
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        ctx = CheckContext("x", shaft_pdf, PackageContent(), load_profile("default"))
        geometry = StepGeometry(obb_dims=(420.0, 70.0, 70.0), backend="occ")
        unsure = CompareResult("unsicher", "s", "d", main_ok=True)
        out = _apply_contour_stage(ctx, mock_dir / "_arbeit" / "M_10473217.stp",
                                   unsure, geometry)
        assert out.verdict == "unsicher"
        assert "Kontur-Score" not in out.summary


    # ========================================================================
    # test_sap
    # ========================================================================
    # SAP: Mitschnitt, Ablauf, Sitzungsgrenzen, Laufsteuerung, GUI-Anbindung.
    #
    # Alles ohne echtes SAP - die nachgebaute Sitzung deckt den Weg ab.
    # ======================================================================
    # sap_flow
    # ======================================================================
    # Tests der SAP-Schicht ohne SAP: Parser, Player, Popups, Download.
    #
    # Der komplette Durchstich (Mitschnitt einlesen -> abspielen -> Paket liegt
    # am Zielort) wird gegen die simulierte Session geprüft. Damit ist am
    # Einsatztag nur noch der echte .vbs-Mitschnitt einzusetzen.
    from pathlib import Path

    import pytest

    sap_cli = sys.modules[__name__]



    # ------------------------------------------------------------------ Parser
    def test_parser_erkennt_transaktion_und_materialfeld():
        flow = parse_vbs(FIXTURE)
        assert flow.transaction == "YMATDOCS"
        assert flow.material_field == "wnd[0]/usr/ctxtS_MATNR-LOW"
        # Von- und Bis-Feld bekommen beide den Platzhalter.
        matnr_steps = [s for s in flow.steps if s.value == "{material}"]
        assert len(matnr_steps) == 2


    def test_parser_setzt_dialog_platzhalter():
        flow = parse_vbs(FIXTURE)
        werte = {s.element: s.value for s in flow.steps if s.action == "set_text"}
        assert werte["wnd[1]/usr/ctxtDY_PATH"] == "{target_dir}"
        assert werte["wnd[1]/usr/ctxtDY_FILENAME"] == "{filename}"
        # Nicht-Materialzahlen bleiben unangetastet (Werk).
        assert werte["wnd[0]/usr/ctxtP_WERKS"] == "1000"


    def test_parser_bildet_grid_methode_generisch_ab():
        """`pressToolbarButton "DOWNLOAD"` ist keine bekannte Aktion."""
        flow = parse_vbs(FIXTURE)
        calls = [s for s in flow.steps if s.action == "call"]
        assert calls, "ALV-Grid-Methode wurde nicht übernommen"
        assert calls[0].method == "pressToolbarButton"
        assert calls[0].args == ["DOWNLOAD"]
        # und sie ist als Download-Auslöser markiert
        assert flow.steps[flow.download_step_index] is calls[0]


    def test_parser_ueberspringt_kosmetik():
        flow = parse_vbs(FIXTURE)
        assert not [s for s in flow.steps
                    if s.action in ("maximize", "set_focus", "set_caret")]


    def test_flow_speichern_und_laden(tmp_path):
        flow = parse_vbs(FIXTURE)
        ziel = tmp_path / "flow.yaml"
        flow.save(ziel)
        wieder = ScriptFlow.load(ziel)
        assert wieder.to_dict() == flow.to_dict()


    def test_describe_nennt_download_schritt():
        text = describe(parse_vbs(FIXTURE))
        assert "<== DOWNLOAD" in text
        assert "NICHT ERKANNT" not in text


    def test_describe_warnt_ohne_materialfeld():
        flow = ScriptFlow(steps=[Step("press", "wnd[0]/tbar[0]/btn[0]")])
        assert "WARNUNG" in describe(flow)


    # ------------------------------------------------------------------ Player
    def _fixture_flow() -> ScriptFlow:
        return parse_vbs(FIXTURE)


    def test_player_ersetzt_platzhalter():
        flow = _fixture_flow()
        session = FakeSession(popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell")
        play(session, flow, {"material": "10473215", "target_dir": r"C:\ziel",
                             "filename": "10473215.zip",
                             "target_path": r"C:\ziel\10473215.zip"})
        assert session.texts_of("wnd[0]/usr/ctxtS_MATNR-LOW") == ["10473215"]
        assert session.texts_of("wnd[1]/usr/ctxtDY_PATH") == [r"C:\ziel"]
        assert session.texts_of("wnd[1]/usr/ctxtDY_FILENAME") == ["10473215.zip"]


    def test_player_meldet_fehlendes_element():
        flow = ScriptFlow(steps=[Step("set_text", "wnd[0]/usr/ctxtFEHLT", "x")])
        session = FakeSession(missing={"wnd[0]/usr/ctxtFEHLT"})
        with pytest.raises(FlowError) as exc:
            play(session, flow, {})
        assert "ctxtFEHLT" in str(exc.value)


    def test_player_ueberspringt_optionale_schritte():
        flow = ScriptFlow(steps=[
            Step("set_text", "wnd[0]/usr/ctxtFEHLT", "x", optional=True),
            Step("press", "wnd[0]/tbar[0]/btn[0]"),
        ])
        session = FakeSession(missing={"wnd[0]/usr/ctxtFEHLT"})
        play(session, flow, {})
        assert "press" in session.actions()


    def test_player_stop_after():
        flow = _fixture_flow()
        session = FakeSession()
        play(session, flow, {"material": "1", "target_dir": "d",
                             "filename": "f", "target_path": "p"}, stop_after=2)
        assert session.texts_of("wnd[0]/usr/ctxtS_MATNR-HIGH") == []


    def test_player_generische_eigenschaft():
        flow = ScriptFlow(steps=[
            Step("set_prop", "wnd[0]/usr/cntlGRID/shellcont/shell",
                 value=3, member="currentCellRow")])
        session = FakeSession()
        play(session, flow, {})
        element = session.FindById("wnd[0]/usr/cntlGRID/shellcont/shell")
        assert element.__dict__["currentCellRow"] == 3


    # ------------------------------------------------------------------ Popups
    def test_popup_wird_bestaetigt():
        session = FakeSession()
        session.open_popup()
        session.FindById("wnd[1]").Text = "Datei existiert bereits – überschreiben?"
        assert handle_popups(session) == 1
        assert not session.open_popups


    def test_druckdialog_wird_abgebrochen():
        session = FakeSession()
        session.open_popup()
        session.FindById("wnd[1]").Text = "Drucken"
        handle_popups(session)
        gedrueckt = [e for a, e, _v in session.log if a == "press"]
        assert any("btn[12]" in e for e in gedrueckt)


    def test_dateidialog_wird_nicht_weggeklickt():
        """Der Speichern-Dialog des Downloads gehört dem Ablauf, nicht dem Handler."""
        session = FakeSession()
        session.open_popup()
        assert handle_popups(session, skip_windows={"wnd[1]"}) == 0
        assert "wnd[1]" in session.open_popups


    # ---------------------------------------------------------------- Download
    def test_download_watcher_erkennt_datei(tmp_path):
        ziel = tmp_path / "paket.zip"
        watcher = DownloadWatcher(expected=ziel, watch_dirs=[], timeout_s=10)
        watcher.start()
        ziel.write_bytes(b"PK\x03\x04")
        assert watcher.wait() == ziel


    def test_download_watcher_findet_abweichenden_namen(tmp_path):
        ordner = tmp_path / "downloads"
        ordner.mkdir()
        watcher = DownloadWatcher(expected=tmp_path / "erwartet.zip",
                                  watch_dirs=[ordner], timeout_s=10)
        watcher.start()
        (ordner / "SAP_export_4711.zip").write_bytes(b"PK\x03\x04")
        assert watcher.wait().name == "SAP_export_4711.zip"


    def test_download_watcher_laeuft_ab(tmp_path):
        watcher = DownloadWatcher(expected=tmp_path / "nie.zip", watch_dirs=[],
                                  timeout_s=1)
        watcher.start()
        with pytest.raises(TimeoutError):
            watcher.wait()


    # ------------------------------------------------------------ Durchstich
    def test_run_ymatdocs_liefert_paket(tmp_path):
        flow_datei = tmp_path / "flow.yaml"
        parse_vbs(FIXTURE).save(flow_datei)
        ziel = tmp_path / "pakete"
        session = FakeSession(
            download_target=ziel / "10473215.zip",
            popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell",
            download_trigger="wnd[1]/tbar[0]/btn[0]")
        ergebnis = run_ymatdocs(session, "10473215", ziel,
                                flow_path=flow_datei, watch_dirs=[])
        assert ergebnis.is_file()
        assert ergebnis.name == "10473215.zip"


    def test_run_ymatdocs_meldet_nicht_vorhandenes_material(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        flow_datei = tmp_path / "flow.yaml"
        parse_vbs(FIXTURE).save(flow_datei)
        session = FakeSession(status=("Zu dieser Materialnummer sind keine "
                                      "Dokumente vorhanden", "S"),
                              popup_after="wnd[0]/usr/cntlGRID1/shellcont/shell")
        with pytest.raises(MaterialNotFound):
            run_ymatdocs(session, "9999999", tmp_path / "out",
                         flow_path=flow_datei, watch_dirs=[])


    def test_run_ymatdocs_meldet_absturz(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        flow_datei = tmp_path / "flow.yaml"
        parse_vbs(FIXTURE).save(flow_datei)
        session = FakeSession()
        session.crash()
        with pytest.raises(SapUnavailable):
            run_ymatdocs(session, "10473215", tmp_path / "out",
                         flow_path=flow_datei, watch_dirs=[])


    # ------------------------------------------------------------------- CLI
    def test_cli_import_und_trockenlauf(tmp_path, capsys):
        ziel = tmp_path / "ymatdocs_flow.yaml"
        assert sap_cli.import_vbs(FIXTURE, ziel) == 0
        assert ziel.is_file()
        assert sap_cli.dry_run("10473215", ziel) == 0
        ausgabe = capsys.readouterr().out
        assert "Trockenlauf ok" in ausgabe
        assert "wnd[0]/usr/ctxtS_MATNR-LOW" in ausgabe


    def test_cli_trockenlauf_meldet_fehlendes_materialfeld(tmp_path, capsys):
        flow = ScriptFlow(name="ohne", transaction="YMATDOCS", steps=[
            Step("start_transaction", value="/nYMATDOCS"),
            Step("send_vkey", "wnd[0]", 8),
            Step("press", "wnd[0]/tbar[1]/btn[13]", comment="Download"),
        ], download_step_index=2)
        datei = tmp_path / "flow.yaml"
        flow.save(datei)
        assert sap_cli.dry_run("4711", datei) == 1
        assert "Materialnummer-Feld" in capsys.readouterr().out


    def test_cli_trockenlauf_ohne_import_meldet_notnagel(tmp_path, capsys,
                                                         monkeypatch):
        """Ohne Mitschnitt darf der Trockenlauf nicht als 'ok' gelten."""
        ymatdocs = sys.modules[__name__]

        monkeypatch.setattr(ymatdocs, "flow_search_paths",
                            lambda: [tmp_path / "gibtsnicht.yaml"])
        assert sap_cli.dry_run("4711") == 1
        assert "Notnagel" in capsys.readouterr().out


    # ------------------------------------------------ Nur der Mitschnitt reicht
    def test_verbindung_aus_dem_mitschnitt(tmp_path):
        """Steht die Verbindung im .vbs, muss niemand das System eintippen."""
        vbs = tmp_path / "mit_verbindung.vbs"
        vbs.write_text(
            'If Not IsObject(application) Then\n'
            '   Set SapGuiAuto = GetObject("SAPGUI")\n'
            '   Set application = SapGuiAuto.GetScriptingEngine\n'
            'End If\n'
            'Set connection = application.OpenConnection("P11 Produktion", True)\n'
            'session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"\n'
            'session.findById("wnd[0]/usr/ctxtP_MATNR").text = "10473215"\n'
            'session.findById("wnd[0]").sendVKey 8\n'
            'session.findById("wnd[0]/tbar[1]/btn[13]").press\n',
            encoding="utf-8")
        flow = parse_vbs(vbs)
        assert flow.connection == "P11"
        assert flow.transaction == "YMATDOCS"
        assert flow.material_field == "wnd[0]/usr/ctxtP_MATNR"


    def test_verbindung_bleibt_leer_ohne_angabe():
        assert parse_vbs(FIXTURE).connection == ""


    def test_verbindung_ueberlebt_speichern(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        flow = parse_vbs(FIXTURE)
        flow.connection = "Q22"
        ziel = tmp_path / "flow.yaml"
        flow.save(ziel)
        assert ScriptFlow.load(ziel).connection == "Q22"


    def test_uebernehmen_speichert_und_meldet(tmp_path):
        """Ein Aufruf: einlesen, speichern, Klartext-Rückmeldung."""
        pass  # (Import entfaellt - alles ein Modul)

        ziel = tmp_path / "regeln" / "ymatdocs_flow.yaml"
        flow, verstanden, zeilen = uebernehmen(FIXTURE, ziel)
        assert ziel.is_file()
        assert verstanden is True
        text = "\n".join(zeilen)
        assert "YMATDOCS" in text
        assert "Materialnummer geht in" in text
        assert "Download über" in text


    def test_kurzbericht_meldet_luecken():
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        flow = ScriptFlow(steps=[Step("press", "wnd[0]/tbar[0]/btn[0]")])
        verstanden, zeilen = kurzbericht(flow)
        assert verstanden is False
        text = "\n".join(zeilen)
        assert "Kein Feld für die Materialnummer" in text


    # ======================================================================
    # lauf_steuerung
    # ======================================================================
    # Tests der Laufsteuerung: Blockweise, Abbrechen, Fortsetzen, SAP-Fenster.
    #
    # Die drei Anforderungen aus dem Betrieb:
    #   * die Ergebnis-Excel wird fortlaufend geschrieben und der Lauf findet
    #     von selbst wieder, wo er aufgehört hat,
    #   * der Lauf lässt sich per Knopf abbrechen - auch mitten im Download,
    #   * in SAP werden nie mehr als fünf Fenster geöffnet.
    import threading
    import time

    import openpyxl





    def _lauf(cfg, mock_dir, resume=False, adapter=None) -> Orchestrator:
        adapter = adapter or MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks(), resume=resume)
        orch.start()
        orch.join(600)
        return orch


    # ------------------------------------------------------- fortlaufend Excel
    def test_excel_waechst_mit_jeder_materialnummer(mock_dir, tmp_path):
        """Nach jeder Nummer muss die Ergebnis-Excel auf Platte aktuell sein."""
        cfg = make_config(mock_dir, tmp_path / "erg")
        gesehen: list[int] = []

        def on_result(_r):
            pfad = cfg.excel_path.with_stem(cfg.excel_path.stem + "_geprüft")
            if pfad.exists():
                wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
                ws = wb[cfg.sheet_name]
                gefuellt = sum(1 for row in ws.iter_rows(min_row=2, values_only=True)
                               if any("Geprüft" in str(v) or "OK" in str(v)
                                      or "Findings" in str(v) for v in row if v))
                gesehen.append(gefuellt)
                wb.close()

        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks(on_result=on_result))
        orch.start()
        orch.join(600)
        assert gesehen, "keine Zwischenstände gesehen"
        assert gesehen == sorted(gesehen), f"Excel wuchs nicht monoton: {gesehen}"
        assert gesehen[-1] >= len(gesehen) - 1


    # ------------------------------------------------------------- Fortsetzen
    def test_findet_den_passenden_lauf_wieder(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg")
        _lauf(cfg, mock_dir)
        treffer = finde_fortsetzbaren_lauf(cfg)
        assert treffer is not None
        _ordner, fertig, _gesamt = treffer
        assert fertig >= 4


    def test_fremder_lauf_wird_nicht_fortgesetzt(mock_dir, tmp_path):
        """Ein Lauf einer anderen Spalte darf nicht fortgesetzt werden."""
        cfg = make_config(mock_dir, tmp_path / "erg")
        _lauf(cfg, mock_dir)
        andere = make_config(mock_dir, tmp_path / "erg", material_column="A")
        assert finde_fortsetzbaren_lauf(andere) is None


    def test_ohne_frueheren_lauf_kein_treffer(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "leer")
        assert finde_fortsetzbaren_lauf(cfg) is None


    def test_fortsetzen_prueft_nur_das_offene(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg")
        erster = _lauf(cfg, mock_dir)
        geprueft = erster.progress.done

        zweiter = _lauf(cfg, mock_dir, resume=True)
        assert zweiter.run_dir == erster.run_dir, "anderer Lauf-Ordner"
        assert zweiter.progress.done == geprueft
        # Es wurde nichts erneut geholt: der Mock zählt die Abrufe.
        assert zweiter.progress.total == erster.progress.total


    # ---------------------------------------------------------------- Abbruch
    def test_abbruch_haelt_an_und_bleibt_fortsetzbar(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg", batch_size=0)
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())

        def stoppe_nach_erstem(_r):
            orch.stop()

        orch.cb.on_result = stoppe_nach_erstem
        orch.start()
        orch.join(600)

        assert orch.progress.done < orch.progress.total, "Lauf lief komplett durch"
        treffer = finde_fortsetzbaren_lauf(cfg)
        assert treffer is not None, "abgebrochener Lauf nicht fortsetzbar"
        # Bericht und Zusammenfassung wurden trotz Abbruch geschrieben.
        assert (orch.run_dir / "findings.csv").is_file()
        assert orch.report_path and orch.report_path.is_file()


    def test_download_wartet_nicht_nach_abbruch(tmp_path):
        """Der Abbrechen-Knopf wirkt sofort, nicht erst nach dem Zeitablauf."""
        pass  # (Import entfaellt - alles ein Modul)

        watcher = DownloadWatcher(expected=tmp_path / "nie.zip", watch_dirs=[],
                                  timeout_s=120)
        watcher.start()
        t0 = time.time()
        with pytest.raises(TimeoutError, match="abgebrochen"):
            watcher.wait(abbruch=lambda: True)
        assert time.time() - t0 < 5


    def test_ablauf_bricht_zwischen_den_schritten_ab():
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        flow = ScriptFlow(steps=[Step("set_text", "wnd[0]/usr/ctxtA", "1"),
                                 Step("set_text", "wnd[0]/usr/ctxtB", "2")])
        session = FakeSession()
        with pytest.raises(Abgebrochen):
            play(session, flow, {}, abbruch=lambda: True)
        assert not session.log, "trotz Abbruch wurde etwas ausgeführt"


    # --------------------------------------------------------------- Blockweise
    def test_blockweise_schreibt_zwischenberichte(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg", batch_size=2)
        bloecke: list[tuple[int, int]] = []

        def on_progress(p):
            if p.batches:
                bloecke.append((p.batch, p.batches))

        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks(on_progress=on_progress))
        orch.start()
        orch.join(600)

        assert orch.progress.batches >= 2, "keine Blöcke gebildet"
        assert max(b for b, _ in bloecke) >= 2
        assert orch.report_path and orch.report_path.is_file()


    def test_ohne_blockgroesse_ein_einziger_block(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg", batch_size=0)
        orch = _lauf(cfg, mock_dir)
        assert orch.progress.batches == 1


    def test_blockwechsel_haken_wird_gerufen(mock_dir, tmp_path):
        """Der Adapter darf zwischen den Blöcken SAP aufräumen."""
        cfg = make_config(mock_dir, tmp_path / "erg", batch_size=2)
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        gerufen: list[int] = []
        adapter.blockwechsel = lambda: gerufen.append(1)
        orch = Orchestrator(cfg, adapter, Callbacks(), resume=False)
        orch.start()
        orch.join(600)
        assert gerufen, "Blockwechsel-Haken wurde nie gerufen"


    # ------------------------------------------------------- SAP-Fenstergrenze
    class _FakeApp:
        """Nachbau der Scripting-Engine mit einstellbarer Fensterzahl."""

        class _Conn:
            def __init__(self, sessions):
                self._s = sessions

            @property
            def Children(self):
                class _C:
                    Count = len(self._s)

                    def __call__(_self, i):
                        return self._s[i]
                return _C()

        def __init__(self, verbindungen):
            self._c = [self._Conn(s) for s in verbindungen]

        @property
        def Children(self):
            class _C:
                Count = len(self._c)

                def __call__(_self, i):
                    return self._c[i]
            return _C()


    def test_zaehlt_offene_sap_fenster():
        pass  # (Import entfaellt - alles ein Modul)

        app = _FakeApp([[object(), object()], [object()]])
        assert zaehle_sessions(app) == 3


    def test_oeffnet_kein_sechstes_fenster(monkeypatch):
        """Bei fünf offenen Fenstern wird nichts mehr geöffnet."""
        sapsession = sys.modules[__name__]

        class _Fremd:
            class Info:
                SystemName = "Q22"

        app = _FakeApp([[_Fremd()] * 5])
        adapter = sapsession.SapGuiAdapter(connection_name="P11", max_sessions=5)

        with pytest.raises(sapsession.SapUnavailable, match="bereits 5 Fenster"):
            adapter._pruefe_grenze(app)


    def test_unter_der_grenze_wird_geoeffnet():
        sapsession = sys.modules[__name__]

        class _Fremd:
            class Info:
                SystemName = "Q22"

        app = _FakeApp([[_Fremd()] * 2])
        adapter = sapsession.SapGuiAdapter(connection_name="P11", max_sessions=5)
        adapter._pruefe_grenze(app)      # darf nicht werfen


    # ======================================================================
    # gui_ablauf
    # ======================================================================
    # GUI: Der .vbs-Mitschnitt ist alles, was der Anwender mitbringen muss.
    #
    # Läuft offscreen (QT_QPA_PLATFORM=offscreen). Geprüft wird die Logik um den
    # Ablauf herum – nicht das Aussehen: Zeigt die GUI an, ob ein Ablauf da ist?
    # Verhindert sie den Start ohne Ablauf? Übernimmt sie das SAP-System aus dem
    # Mitschnitt?
    import os


    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    pytest.importorskip("PySide6")




    @pytest.fixture()
    def fenster(tmp_path, monkeypatch):
        """MainWindow mit eigenem Regelordner, damit nichts überschrieben wird."""
        from PySide6.QtWidgets import QApplication
        mw = sys.modules[__name__]

        monkeypatch.setenv("DRAWING_CHECKER_RULES", str(tmp_path / "regeln"))
        monkeypatch.setattr(sys.modules[__name__], "_default_flow_path",
                            lambda: tmp_path / "regeln" / "ymatdocs_flow.yaml")
        monkeypatch.setattr(
            sys.modules[__name__], "flow_search_paths",
            lambda: [tmp_path / "regeln" / "ymatdocs_flow.yaml"])
        pass  # (Import entfaellt - alles ein Modul)

        _flow_cache.clear()
        app = QApplication.instance() or QApplication([])
        fenster = mw.MainWindow(lambda cfg: MockSapAdapter(cfg.mock_source),
                                ["default"])
        yield fenster
        _flow_cache.clear()


    def test_meldet_fehlenden_ablauf(fenster):
        assert fenster._hat_ablauf() is False
        assert "fehlt" in fenster.lbl_flow.text()


    def test_zeigt_ablauf_nach_dem_einlesen(fenster, tmp_path):
        uebernehmen(FIXTURE, tmp_path / "regeln" / "ymatdocs_flow.yaml")
        fenster._flow_status()
        assert fenster._hat_ablauf() is True
        text = fenster.lbl_flow.text()
        assert "YMATDOCS" in text and "11 Schritte" in text


    def test_uebernimmt_das_system_aus_dem_mitschnitt(fenster, tmp_path):
        vbs = tmp_path / "mit_system.vbs"
        vbs.write_text(
            'Set connection = application.OpenConnection("Q22 Test", True)\n'
            'session.findById("wnd[0]/tbar[0]/okcd").text = "/nYMATDOCS"\n'
            'session.findById("wnd[0]/usr/ctxtP_MATNR").text = "10473215"\n'
            'session.findById("wnd[0]/tbar[1]/btn[13]").press\n', encoding="utf-8")
        fenster.txt_system.setText("")
        # Bewusst ohne Dialog: ein modales Fenster wuerde den Test anhalten.
        # Die Meldung darum herum ist nur Text zu diesem Ergebnis.
        flow, ok, zeilen, ziel = fenster._ablauf_uebernehmen(vbs)
        assert fenster.txt_system.text() == "Q22"
        assert flow.transaction == "YMATDOCS"
        assert ok is True and ziel.is_file()


    def test_sucht_vbs_an_den_ueblichen_stellen(fenster, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "alt.vbs").write_text("x", encoding="utf-8")
        (tmp_path / "neu.vbs").write_text("y", encoding="utf-8")
        os.utime(tmp_path / "neu.vbs", (10**9 + 100, 10**9 + 100))
        vorschlag = fenster._vbs_vorschlag()
        assert vorschlag is not None and vorschlag.suffix == ".vbs"


    # ========================================================================
    # test_ablauf
    # ========================================================================
    # Der Lauf als Ganzes: Durchstich, Excel, Bericht, OCR, Haushalt.
    # ======================================================================
    # e2e
    # ======================================================================
    # End-to-End: kompletter Prüflauf über die Mockdaten inkl. SAP-Absturz + Resume.
    from pathlib import Path

    import pytest





    @pytest.fixture()
    def run(mock_dir, tmp_path):
        cfg = make_config(mock_dir, tmp_path / "erg")
        adapter = MockSapAdapter(mock_dir, crash_on={"10473216"})
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start()
        orch.join(300)
        return orch


    def result(orch, material):
        return next(r for r in orch.state.results.values()
                    if r.material == material)


    def test_full_run_completes(run):
        assert run.progress.done == 5
        assert run.progress.failed == 0


    def test_clean_drawing_is_ok(run):
        r = result(run, "10473217")
        assert r.status == JobStatus.OK
        assert r.findings == []
        assert r.screenshot and r.screenshot.exists()
        assert "passt" not in ("",)  # Geometrie-Summary vorhanden
        assert "STEP-OBB" in r.step_summary


    def test_weld_bracket_language_and_weld_findings(run):
        r = result(run, "10473215")
        codes = {f.code for f in r.findings}
        assert "LANG.GERMAN" in codes
        assert "WELD.QUALITY" in codes
        assert "GEO.MISMATCH" not in codes          # STEP passt
        # Fachliche Widersprüche: 1.4305 (nicht schweißgeeignet) + Schweißsymbolik,
        # "feuerverzinkt" auf Edelstahl
        assert "MAT.WELD_CONFLICT" in codes
        assert "MAT.COATING_CONFLICT" in codes
        # Sprach-Findings tragen Positionen für die Annotation
        assert any(f.bbox for f in r.findings if f.code == "LANG.GERMAN")


    def test_wrong_step_config_is_blocker(run):
        r = result(run, "10473216")
        codes = {f.code: f for f in r.findings}
        assert "GEO.MISMATCH" in codes
        assert codes["GEO.MISMATCH"].severity == Severity.BLOCKER
        assert "GT.GENERAL_TOL" in codes
        assert "CAST.TOL" in codes


    def test_scan_without_text_degrades_gracefully(run):
        r = result(run, "10473218")
        codes = {f.code for f in r.findings}
        assert "DOC.NO_TEXT" in codes or "DOC.OCR" in codes
        # Auf einer per OCR gelesenen Zeichnung darf nichts hart als Fehler
        # gemeldet werden – Erkennungsfehler sind nicht auszuschließen.
        pass  # (Import entfaellt - alles ein Modul)

        hart = [f for f in r.findings
                if f.severity >= Severity.ERROR and f.code not in ("DOC.NO_PDF",)]
        assert not hart, f"harte Befunde auf OCR-Zeichnung: {[f.code for f in hart]}"


    def test_missing_package_reported(run):
        r = result(run, "10473219")
        assert any(f.code == "DOC.NO_PDF" for f in r.findings)


    def test_sap_crash_recovered(run):
        # 10473216 hat einen simulierten Absturz -> trotzdem geprüft
        assert result(run, "10473216").status != JobStatus.FAILED


    def test_result_excel_written(run, mock_dir):
        assert (mock_dir / "Materialliste_Mock_geprüft.xlsx").exists()


    def test_resume_skips_done(run, mock_dir, tmp_path):
        cfg = make_config(mock_dir, run.config.output_dir)
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        processed = []
        orch2 = Orchestrator(cfg, adapter,
                             Callbacks(on_result=lambda r: processed.append(r)),
                             resume=True)
        orch2.start()
        orch2.join(300)
        # Alle 5 gemeldet, aber nichts neu gerechnet außer evtl. FAILED (hier keine)
        assert len(processed) == 5
        assert orch2.progress.done == 5


    # ======================================================================
    # excel_and_state
    # ======================================================================

    import openpyxl



    def make_config_excel(tmp_path: Path, excel: Path) -> RunConfig:
        return RunConfig(excel_path=excel, sheet_name="Materialliste",
                         material_column="C", header_row=1,
                         output_dir=tmp_path / "out")


    def test_read_materials_skips_blanks(tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Materialliste"
        ws.append(["Nr", "Werk", "Materialnummer"])
        ws.append([1, "1000", "10473215"])
        ws.append([2, "1000", None])
        ws.append([3, "1000", 10473216])   # als Zahl formatiert
        ws.append([4, "1000", "  "])
        excel = tmp_path / "liste.xlsx"
        wb.save(excel)

        mats = read_materials(make_config_excel(tmp_path, excel))
        assert mats == [(2, "10473215"), (4, "10473216")]


    def test_result_workbook_roundtrip(tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Materialliste"
        ws.append(["Nr", "Werk", "Materialnummer"])
        ws.append([1, "1000", "10473215"])
        excel = tmp_path / "liste.xlsx"
        wb.save(excel)

        cfg = make_config_excel(tmp_path, excel)
        rwb = ResultWorkbook(cfg)
        result = MaterialResult(material="10473215", row=2,
                                status=JobStatus.FINDINGS)
        result.findings.append(Finding("LANG.GERMAN", Severity.ERROR, "Test",
                                       BBox(0, 0, 1, 1)))
        rwb.write_result(result)
        rwb.save()

        out = openpyxl.load_workbook(rwb.path)["Materialliste"]
        headers = [c.value for c in out[1]]
        assert RESULT_HEADERS[0] in headers
        col = headers.index(RESULT_HEADERS[0]) + 1
        assert out.cell(row=2, column=col).value == "Findings"

        # Zweites Öffnen erzeugt KEINE doppelten Spalten
        rwb2 = ResultWorkbook(cfg)
        assert rwb2.first_col == rwb.first_col


    def test_state_roundtrip_and_resume(tmp_path):
        excel = tmp_path / "l.xlsx"
        wb = openpyxl.Workbook(); wb.active.title = "Materialliste"; wb.save(excel)
        cfg = make_config_excel(tmp_path, excel)
        run_dir = tmp_path / "lauf"
        run_dir.mkdir()

        state = RunState(cfg, run_dir)
        r = MaterialResult(material="10473215", row=2, status=JobStatus.OK,
                           duration_s=1.5)
        r.findings.append(Finding("X", Severity.WARNING, "t", BBox(1, 2, 3, 4),
                                  page=0, detail="d"))
        state.record(r)

        loaded = RunState.load(cfg, run_dir)
        assert loaded.is_done(2, "10473215")
        assert not loaded.is_done(3, "10473215")
        lr = loaded.results["2:10473215"]
        assert lr.findings[0].severity == Severity.WARNING
        assert lr.findings[0].bbox.x1 == 3


    def test_failed_jobs_are_retried_on_resume(tmp_path):
        excel = tmp_path / "l.xlsx"
        wb = openpyxl.Workbook(); wb.active.title = "Materialliste"; wb.save(excel)
        cfg = make_config_excel(tmp_path, excel)
        run_dir = tmp_path / "lauf"; run_dir.mkdir()
        state = RunState(cfg, run_dir)
        state.record(MaterialResult(material="M", row=5, status=JobStatus.FAILED,
                                    error="SAP weg"))
        loaded = RunState.load(cfg, run_dir)
        assert not loaded.is_done(5, "M")   # FAILED wird beim Fortsetzen erneut geprüft


    # ======================================================================
    # reporting
    # ======================================================================
    # Laufabschluss-Artefakte: HTML-Bericht, Excel-Zusammenfassung, Lauf-Log.




    @pytest.fixture(scope="module")
    def finished_run(mock_dir, tmp_path_factory):
        out = tmp_path_factory.mktemp("erg")
        cfg = RunConfig(
            excel_path=mock_dir / "Materialliste_Mock.xlsx",
            sheet_name="Materialliste", material_column="C", header_row=1,
            output_dir=out)
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start(); orch.join(300)
        return orch


    def test_html_report_written(finished_run):
        path = finished_run.report_path
        assert path is not None and path.exists()
        html = path.read_text(encoding="utf-8")
        assert "Zeichnungsprüfung – Bericht" in html
        assert "10473216" in html          # Geometrie-K.O.-Fall
        assert "GEO.MISMATCH" in html
        assert "10473216.png" in html      # Link auf annotierte Zeichnung


    def test_excel_summary_sheet(finished_run, mock_dir):
        wb = openpyxl.load_workbook(mock_dir / "Materialliste_Mock_geprüft.xlsx")
        assert "Prüfzusammenfassung" in wb.sheetnames
        ws = wb["Prüfzusammenfassung"]
        values = [c.value for row in ws.iter_rows() for c in row if c.value]
        assert "LANG.GERMAN" in values     # häufigster Mängelcode gezählt
        # Ergebnisblatt hat Autofilter und Fixierung
        main = wb["Materialliste"]
        assert main.auto_filter.ref
        assert main.freeze_panes == "A2"


    def test_run_logfile_written(finished_run):
        assert (finished_run.run_dir / "lauf.log").read_text(encoding="utf-8")


    def test_annotated_image_has_stamp(finished_run):
        # Stempel oben links: Pixel im Rahmenbereich sind nicht mehr weiß
        from PIL import Image

        shot = next(r.screenshot for r in finished_run.state.results.values()
                    if r.material == "10473216")
        img = Image.open(shot).convert("RGB")
        box = img.crop((16, 16, 200, 70))
        assert any(p != (255, 255, 255) for p in box.getdata())


    # ======================================================================
    # ocr
    # ======================================================================
    # Tests des OCR-Pfads.
    #
    # Die reinen Rechenteile (Nachkorrektur, Rückrechnung gedrehter Fundstellen,
    # Binarisierung, Schräglagenschätzung, Einstellungen) laufen immer. Die
    # Erkennung selbst braucht Tesseract und wird sonst übersprungen – auf
    # Rechnern ohne OCR fällt der Checker dokumentiert zurück.
    import io

    import pymupdf

    ocrmod = sys.modules[__name__]

    has_tesseract = ocrmod._tesseract() is not None
    needs_ocr = pytest.mark.skipif(not has_tesseract,
                                   reason="Tesseract nicht installiert")


    # ------------------------------------------------------------ Nachkorrektur
    @pytest.mark.parametrize("raw,erwartet", [
        ("1O0", "100"),          # Buchstabe O in reiner Zahl
        ("|2", "2"),             # Strichrest vor der Zahl
        ("Ø20", "⌀20"),          # Durchmesser-Variante vereinheitlichen
        ("@20", "⌀20"),          # Durchmesserzeichen als @ erkannt
        ("S235JR", "S235JR"),    # Werkstoff bleibt unangetastet
        ("[50]", "[50]"),        # theoretisch genaues Maß behält die Klammern
        ("M12x1,5", "M12x1,5"),
        ("1.4301", "1.4301"),
    ])
    def test_fix_token(raw, erwartet):
        assert _fix_token(raw) == erwartet


    def test_fix_token_laesst_buchstaben_in_gemischten_token(): 
        """In "R10x2" darf kein O/0-Tausch passieren – es ist keine reine Zahl."""
        assert _fix_token("R1Ox2") == "R1Ox2"


    # ------------------------------------------------- gedrehte Fundstellen
    def test_unrotate_90_grad():
        """Ein Kasten oben links im gedrehten Bild liegt unten links im Original."""
        # Originalhöhe 100; im 90°-Bild liegt (x=10, y=20, w=30, h=5)
        x, y, w, h = _unrotate(10, 20, 30, 5, 90, orig_height=100)
        assert (x, y, w, h) == (20, 100 - 10 - 30, 5, 30)


    def test_unrotate_laesst_unbekannte_winkel():
        assert _unrotate(1, 2, 3, 4, 45, 100) == (1, 2, 3, 4)


    def test_dedupe_entfernt_doppelfunde():
        a = Word("⌀20", BBox(0, 0, 10, 5), 0, 90)
        b = Word("20", BBox(1, 0, 10, 5), 0, 95)      # gleiche Stelle, kürzer
        kept = ocrmod._dedupe([a, b])
        assert [w.text for w in kept] == ["⌀20"]


    def test_dedupe_behaelt_getrennte_funde():
        a = Word("20", BBox(0, 0, 10, 5), 0, 90)
        b = Word("30", BBox(50, 0, 60, 5), 0, 90)
        assert len(ocrmod._dedupe([a, b])) == 2


    # ------------------------------------------------------------ Einstellungen
    def test_settings_aus_umgebung(monkeypatch):
        monkeypatch.setenv("DRAWING_CHECKER_OCR_DPI", "250")
        monkeypatch.setenv("DRAWING_CHECKER_OCR_PSM", "6")
        monkeypatch.setenv("DRAWING_CHECKER_OCR_ROTATIONS", "90,270")
        monkeypatch.setenv("DRAWING_CHECKER_OCR_BINARIZE", "0")
        cfg = OcrSettings.from_env()
        assert (cfg.dpi, cfg.psm, cfg.rotations, cfg.binarize) == (
            250, 6, (90, 270), False)


    def test_settings_config_schaltet_woerterbuecher_ab():
        cfg = OcrSettings()
        config = cfg.config()
        assert "--psm 11" in config and "load_system_dawg=0" in config


    def test_settings_ignoriert_unsinn(monkeypatch):
        monkeypatch.setenv("DRAWING_CHECKER_OCR_DPI", "keine Zahl")
        assert OcrSettings.from_env().dpi == OcrSettings().dpi


    # ----------------------------------------------------------- Bildaufbau
    def test_binarize_erzeugt_zwei_werte():
        from PIL import Image
        import numpy as np

        arr = np.tile(np.arange(256, dtype="uint8"), (16, 1))
        out = ocrmod._binarize(Image.fromarray(arr), Image)
        assert set(np.unique(np.asarray(out))) <= {0, 255}


    def test_skew_angle_erkennt_schraege():
        from PIL import Image
        import numpy as np

        # Waagerechte Textzeilen, um 2° verdreht -> Schätzer muss gegensteuern.
        arr = np.full((400, 400), 255, dtype="uint8")
        for row in range(40, 360, 40):
            arr[row:row + 6, 40:360] = 0
        img = Image.fromarray(arr).rotate(-2.0, fillcolor=255)
        angle = ocrmod._skew_angle(img, OcrSettings())
        assert 1.0 <= angle <= 3.0


    def test_skew_angle_bei_gerader_vorlage_null():
        from PIL import Image
        import numpy as np

        arr = np.full((400, 400), 255, dtype="uint8")
        for row in range(40, 360, 40):
            arr[row:row + 6, 40:360] = 0
        assert ocrmod._skew_angle(Image.fromarray(arr), OcrSettings()) == 0.0


    # ------------------------------------------------------------- Erkennung
    def _scan_pdf(tmp_path, lines, rotated: list[str] | None = None,
                  dpi: int = 200):
        """Baut ein Text-PDF, rastert es und liefert den Scan-Pfad."""
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        kwargs = {}
        from pathlib import Path

        if Path(FONT).exists():
            page.insert_font(fontname="T", fontfile=FONT)
            kwargs["fontname"] = "T"
        for i, text in enumerate(lines):
            page.insert_text((60, 80 + i * 40), text, fontsize=16, **kwargs)
        for i, text in enumerate(rotated or []):
            # 90° gedreht, wie Maßtexte an senkrechten Maßlinien
            page.insert_text((600 + i * 40, 400), text, fontsize=16,
                             rotate=90, **kwargs)
        src = tmp_path / "text.pdf"
        doc.save(src)
        doc.close()

        scan = tmp_path / "scan.pdf"
        pass  # (Import entfaellt - alles ein Modul)

        rasterize_scan(src, scan, dpi=dpi, noise=False)
        return scan


    @needs_ocr
    def test_ocr_liest_gescannte_zeichnung(tmp_path):
        scan = _scan_pdf(tmp_path, ["Werkstoff S235JR", "Gewicht 12,5 kg",
                                    "Allgemeintoleranz ISO 2768-mK"])
        with DrawingPdf(scan) as pdf:
            text = pdf.full_text()
            assert pdf.ocr_used
            assert "S235JR" in text.replace(" ", "")
            assert "2768" in text


    @needs_ocr
    def test_ocr_findet_gedrehte_masstexte(tmp_path):
        scan = _scan_pdf(tmp_path, ["Ansicht A"], rotated=["148,5", "96,0"])
        with DrawingPdf(scan) as pdf:
            text = pdf.full_text().replace(" ", "")
        assert "148" in text, "gedrehter Maßtext wurde nicht gefunden"


    @needs_ocr
    def test_ocr_wortkonfidenz_wird_uebernommen(tmp_path):
        scan = _scan_pdf(tmp_path, ["Werkstoff S235JR", "Gewicht 12,5 kg"])
        with DrawingPdf(scan) as pdf:
            confs = [w.conf for w in pdf.words()]
        assert confs and all(0 <= c <= 100 for c in confs)
        assert max(confs) < 100.0, "OCR-Wörter dürfen nicht als sicher gelten"


    @needs_ocr
    def test_gemischtes_dokument_nutzt_beide_wege(tmp_path):
        """Seite 1 mit Textlayer, Seite 2 als Scan – beides muss ankommen."""
        doc = pymupdf.open()
        p1 = doc.new_page(width=842, height=595)
        p1.insert_text((60, 80), "Blatt 1 Werkstoff 1.4301 Allgemeintoleranz",
                       fontsize=14)
        src = tmp_path / "seite2.pdf"
        d2 = pymupdf.open()
        d2.new_page(width=842, height=595).insert_text(
            (60, 80), "Blatt 2 Schweissnaht a4 umlaufend", fontsize=16)
        d2.save(src)
        d2.close()
        pass  # (Import entfaellt - alles ein Modul)

        scan2 = rasterize_scan(src, tmp_path / "scan2.pdf", dpi=200, noise=False)
        doc.insert_pdf(pymupdf.open(scan2))
        path = tmp_path / "gemischt.pdf"
        doc.save(path)
        doc.close()

        with DrawingPdf(path) as pdf:
            text = pdf.full_text()
            assert pdf.ocr_used, "Scan-Seite wurde nicht per OCR nachgezogen"
            assert "1.4301" in text, "Textlayer der ersten Seite fehlt"
            assert "umlaufend" in text.lower(), "Scan-Seite wurde nicht gelesen"


    @needs_ocr
    def test_unsichere_kurze_zahlen_werden_kein_mass(tmp_path):
        """Kurze OCR-Schnipsel unter der Konfidenzschwelle sind keine Maße."""
        pass  # (Import entfaellt - alles ein Modul)

        scan = _scan_pdf(tmp_path, ["Laenge 120", "Breite 80"])
        with DrawingPdf(scan) as pdf:
            for w in pdf.words():
                w.conf = 30.0
            assert extract_dimensions(pdf, 6000) == []


    # ------------------------------------------------ Härtegrad bei OCR-Text
    def test_findings_werden_bei_ocr_herabgestuft(tmp_path):
        """Auf OCR-Grundlage darf keine Regel hart als Fehler melden."""
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        class _PdfStub:
            ocr_used = True

        ctx = CheckContext("1", _PdfStub(), PackageContent(),
                           load_profile("default"))
        ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
        assert ctx.findings[0].severity == Severity.WARNING
        assert "Herabgestuft" in ctx.findings[0].detail


    def test_paketfehler_bleibt_hart_trotz_ocr():
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        class _PdfStub:
            ocr_used = True

        ctx = CheckContext("1", _PdfStub(), PackageContent(),
                           load_profile("default"))
        ctx.add("DOC.NO_PDF", "Kein PDF im Paket")
        assert ctx.findings[0].severity == Severity.BLOCKER


    def test_ohne_ocr_bleibt_die_severity(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        class _PdfStub:
            ocr_used = False

        ctx = CheckContext("1", _PdfStub(), PackageContent(),
                           load_profile("default"))
        ctx.add("TB.MATERIAL", "Werkstoff nicht nachweisbar")
        assert ctx.findings[0].severity == Severity.ERROR


    # ------------------------------------------------------ Linienentfernung
    def test_linienentfernung_tilgt_linie_und_laesst_schrift():
        """Lange Linien verschwinden, kurze Buchstabenstriche bleiben."""
        import numpy as np
        from PIL import Image

        arr = np.full((200, 400), 255, dtype="uint8")
        arr[100, 20:380] = 0            # Maßlinie quer über das Blatt
        arr[50:60, 100:106] = 0         # Buchstabenstrich
        out = np.asarray(ocrmod._remove_lines(Image.fromarray(arr),
                                              OcrSettings(), Image))
        assert (out[100, 20:380] == 255).all()
        assert (out[50:60, 100:106] == 0).all()


    def test_linienentfernung_ist_abschaltbar(monkeypatch):
        monkeypatch.setenv("DRAWING_CHECKER_OCR_LINES", "1")
        assert OcrSettings.from_env().remove_lines is True


    # ======================================================================
    # haushalt_und_gewinde
    # ======================================================================
    # Tests für den Dauerlauf-Haushalt (Aufräumen, Plattenplatz) und die
    # Gewinderegeln.


    hk = sys.modules[__name__]


    # ------------------------------------------------------------- Haushalt
    def test_cleanup_entfernt_paket(tmp_path):
        work = tmp_path / "10473215"
        work.mkdir()
        (work / "zeichnung.pdf").write_bytes(b"x" * 1024)
        zip_path = tmp_path / "10473215.zip"
        zip_path.write_bytes(b"y" * 2048)

        freed = hk.cleanup_package(work, zip_path)
        assert not work.exists() and not zip_path.exists()
        assert freed > 0


    def test_cleanup_kann_behalten(tmp_path):
        work = tmp_path / "p"
        work.mkdir()
        (work / "a.pdf").write_bytes(b"x")
        assert hk.cleanup_package(work, None, keep=True) == 0.0
        assert work.exists()


    def test_sweep_raeumt_alles_weg(tmp_path):
        for i in range(3):
            d = tmp_path / f"paket{i}"
            d.mkdir()
            (d / "x.bin").write_bytes(b"x" * 4096)
        hk.sweep_packages(tmp_path)
        assert not list(tmp_path.iterdir())


    def test_diskguard_meldet_ok_bei_platz(tmp_path):
        guard = hk.DiskGuard(tmp_path, min_free_mb=1)
        assert guard.check() == ""


    def test_diskguard_haelt_an_wenn_voll(tmp_path, monkeypatch):
        monkeypatch.setattr(hk, "free_mb", lambda _p: 10.0)
        guard = hk.DiskGuard(tmp_path, min_free_mb=500)
        with pytest.raises(hk.DiskFull) as exc:
            guard.check()
        assert "Platz schaffen" in str(exc.value)


    def test_release_memory_laeuft_durch():
        hk.release_memory()          # darf auf keiner Plattform werfen


    def test_orchestrator_raeumt_pakete_auf(mock_dir, tmp_path):
        """Nach dem Lauf darf im Paketordner nichts liegen bleiben."""
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                        sheet_name="Materialliste", material_column="C",
                        header_row=1, output_dir=tmp_path / "erg")
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start()
        orch.join(300)
        rest = list((orch.run_dir / "pakete").iterdir())
        assert rest == [], f"nicht aufgeräumt: {rest}"
        assert orch._freed_mb > 0


    def test_orchestrator_behaelt_pakete_auf_wunsch(mock_dir, tmp_path):
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        cfg = RunConfig(excel_path=mock_dir / "Materialliste_Mock.xlsx",
                        sheet_name="Materialliste", material_column="C",
                        header_row=1, output_dir=tmp_path / "erg",
                        keep_packages=True)
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start()
        orch.join(300)
        assert list((orch.run_dir / "pakete").iterdir())


    # ------------------------------------------------------------- Gewinde
    class _PdfStub:
        ocr_used = False

        def __init__(self, text: str = ""):
            self._text = text

        def full_text(self) -> str:
            return self._text

        def blocks(self):
            return []


    def _ctx_stub(text: str = "Werkstoff S235JR") -> CheckContext:
        return CheckContext("1", _PdfStub(text), PackageContent(),
                            load_profile("default"))


    def _thread(size: float, depth: float) -> DimValue:
        return DimValue(value=size, kind=DimKind.THREAD, raw=f"M{size:g}",
                        bbox=BBox(0, 0, 10, 10), page=0, depth=depth)


    def _hole(dia: float, depth: float) -> DimValue:
        return DimValue(value=dia, kind=DimKind.DIAMETER, raw=f"⌀{dia:g}",
                        bbox=BBox(0, 0, 10, 10), page=0, depth=depth)


    def test_gewinde_tiefer_als_bohrung(): 
        ctx = _ctx_stub()
        check_thread_depths(ctx, [_thread(10, 25), _hole(8.5, 20)])
        codes = {f.code: f for f in ctx.findings}
        assert "THRD.DEPTH" in codes
        assert codes["THRD.DEPTH"].severity == Severity.ERROR


    def test_gewinde_flacher_als_bohrung_ok():
        ctx = _ctx_stub()
        check_thread_depths(ctx, [_thread(10, 18), _hole(8.5, 24)])
        assert "THRD.DEPTH" not in {f.code for f in ctx.findings}


    def test_zu_kurze_einschraubtiefe_in_stahl():
        ctx = _ctx_stub("Werkstoff S235JR")
        check_thread_depths(ctx, [_thread(12, 6)])
        assert "THRD.SHORT" in {f.code for f in ctx.findings}


    def test_ausreichende_einschraubtiefe_in_stahl():
        ctx = _ctx_stub("Werkstoff S235JR")
        check_thread_depths(ctx, [_thread(12, 14)])
        assert not ctx.findings


    def test_aluminium_verlangt_mehr_einschraubtiefe():
        """1×D reicht in Stahl, in Aluminium nicht."""
        ctx = _ctx_stub("Werkstoff EN AW-6082 T6")
        check_thread_depths(ctx, [_thread(10, 11)])
        codes = [f for f in ctx.findings if f.code == "THRD.SHORT"]
        assert codes and "weichem Werkstoff" in codes[0].text


    # ------------------------------------------------------------ Spiegelung
    def test_spiegelerkennung_unterscheidet_haende():
        """Eine L-Kontur gegen ihr Spiegelbild: gespiegelt muss besser passen."""
        pass  # (Import entfaellt - alles ein Modul)

        # L-förmige, eindeutig unsymmetrische Kontur
        punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
        kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
        gespiegelte = [(-x0, y0, -x1, y1) for x0, y0, x1, y1 in kontur]

        ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
        gerade = match_views([ansicht], [gespiegelte], mirrored=False)
        gespiegelt = match_views([ansicht], [gespiegelte], mirrored=True)
        assert gespiegelt.score > gerade.score + 0.15


    def test_spiegelerkennung_meldet_bei_gleicher_hand_nicht():
        pass  # (Import entfaellt - alles ein Modul)

        punkte = [(0, 0), (40, 0), (40, 10), (10, 10), (10, 30), (0, 30), (0, 0)]
        kontur = [(a[0], a[1], b[0], b[1]) for a, b in zip(punkte, punkte[1:])]
        ansicht = ViewCluster(segments=kontur, bbox=(0, 0, 40, 30))
        gerade = match_views([ansicht], [kontur], mirrored=False)
        gespiegelt = match_views([ansicht], [kontur], mirrored=True)
        assert gerade.score >= gespiegelt.score


    # --------------------------------------------------------- Anwenderseite
    def test_maengelspalte_wird_gedeckelt():
        """30 Findings gehören nicht in eine Excel-Zelle."""
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
        r.findings = [Finding(code=f"X.{i}", severity=Severity.WARNING,
                              text=f"Punkt {i}", detail="Erläuterung " * 10)
                      for i in range(30)]
        text = _findings_text(r)
        assert text.count("\n") + 1 == MAX_FINDINGS_IN_CELL + 1
        assert "und 18 weitere" in text
        assert text.count("Erläuterung") <= 30      # Details nur bei den Ersten


    def test_maengelspalte_ohne_deckel_bei_wenigen():
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        r = MaterialResult(material="1", row=2, status=JobStatus.FINDINGS)
        r.findings = [Finding(code="A.B", severity=Severity.ERROR, text="Ein Punkt")]
        assert _findings_text(r) == "[Fehler] A.B: Ein Punkt"


    def test_klartext_uebersetzt_technische_fehler():
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        pass  # (Import entfaellt - alles ein Modul)

        assert "Excel geöffnet" in klartext(PermissionError(13, "denied"))
        assert "Speicherplatz" in klartext(OSError("[Errno 28] No space left"))
        assert klartext(ValueError("etwas Eigenes")) == "etwas Eigenes"


    # ========================================================================
    # test_auslieferung
    # ========================================================================
    # Auslieferung: Paketbau, Einzeldatei, Startskript, Doku, Modulhygiene.
    # ======================================================================
    # paket
    # ======================================================================
    # Prüft das Verteilpaket: eine ZIP-Datei, die am Zielrechner reicht.
    #
    # Der Anwenderrechner bekommt genau eine Datei. Fehlt darin ein
    # Wissenspaket oder das Startskript, merkt man es erst dort – deshalb wird
    # das Archiv hier gebaut und gegengeprüft.
    import zipfile
    from pathlib import Path

    import pytest

    paket = sys.modules[__name__]



    @pytest.fixture(scope="module")
    def archiv(tmp_path_factory) -> Path:
        ziel = tmp_path_factory.mktemp("paket")
        return paket.zip_bauen(ziel, mit_tests=False)


    def namen(archiv: Path) -> set[str]:
        with zipfile.ZipFile(archiv) as zf:
            return set(zf.namelist())


    def test_alles_liegt_in_einem_ordner(archiv):
        """Beim Entpacken darf nichts verstreut im Zielordner landen."""
        assert all(n.startswith("DrawingChecker/") for n in namen(archiv))


    @pytest.mark.parametrize("datei", [
        "Start.bat", "README.md", "drawing_checker.py",
    ])
    def test_pflichtdateien_enthalten(archiv, datei):
        assert f"DrawingChecker/{datei}" in namen(archiv)


    def test_ballast_bleibt_draussen(archiv):
        """Kalibrierzeichnungen (25 MB) und Caches gehören nicht ins Paket."""
        for n in namen(archiv):
            assert "echt_quellen" not in n
            assert "__pycache__" not in n and not n.endswith(".pyc")
            assert "/.venv/" not in n
        assert archiv.stat().st_size < 5 * 1024 * 1024, "Paket unerwartet groß"


    def test_archiv_ist_lesbar_und_vollstaendig(archiv):
        """Baut, entpackt und lädt die Wissenspakete im entpackten Stand."""
        assert paket.zip_pruefen(archiv) == []




    # ------------------------------------------------- Einzeldatei (self-extract)
    def test_einzeldatei_enthaelt_ein_gueltiges_paket(tmp_path):
        """Die selbstentpackende .bat muss ein brauchbares ZIP tragen."""
    
        datei = paket.bat_bauen(tmp_path)
        assert datei.name == "DrawingChecker_Setup.bat"
        assert paket.bat_pruefen(datei) == []


    def test_einzeldatei_hat_marke_und_windows_zeilenenden(tmp_path):
    
        datei = paket.bat_bauen(tmp_path)
        roh = datei.read_bytes()
        assert b"::PAYLOAD::\r\n" in roh
        assert roh.startswith(b"@echo off\r\n")
        # Der Batch-Teil darf die Nutzlast nie ausfuehren. Getrennt wird an der
        # Markenzeile, nicht am ersten Vorkommen - die Marke steht auch im
        # PowerShell-Aufruf des Kopfes.
        kopf = roh.split(b"\r\n::PAYLOAD::\r\n")[0].decode("ascii")
        assert "exit /b 0" in kopf
        assert kopf.count("::PAYLOAD::") >= 1        # Suche im Kopf vorhanden


    def test_einzeldatei_nutzlast_ist_das_paket(tmp_path):
        """Was drinsteckt, ist genau das gebaute ZIP."""
        import zipfile

    
        zip_pfad = paket.zip_bauen(tmp_path, mit_tests=False)
        datei = paket.bat_bauen(tmp_path, quelle=zip_pfad)
        assert paket.nutzlast(datei) == zip_pfad.read_bytes()
        with zipfile.ZipFile(zip_pfad) as zf:
            assert "DrawingChecker/Start.bat" in zf.namelist()


    # ------------------------------------------- Kalibrierzeichnungen als Archiv


    def test_zeichnungen_werden_ausgepackt(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        ordner = zeichnungen(ziel=tmp_path / "raus")
        assert len(list(ordner.glob("*.pdf"))) >= 80
        # Zweiter Aufruf packt nicht erneut aus.
        marke = (ordner / ".ausgepackt").stat().st_mtime_ns
        zeichnungen(ziel=tmp_path / "raus")
        assert (ordner / ".ausgepackt").stat().st_mtime_ns == marke


    # ======================================================================
    # package
    # ======================================================================




    def make_zip(path: Path, names: dict[str, bytes]):
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in names.items():
                zf.writestr(name, data)


    def test_extract_classifies_content(tmp_path):
        z = tmp_path / "m1.zip"
        make_zip(z, {
            "Z_123.pdf": b"%PDF-1.4 x",
            "M_123.stp": b"ISO-10303-21;",
            "N_123.CATPart": b"native",
        })
        c = extract_package(z, tmp_path / "work", "123")
        assert c.drawing_pdf.name == "Z_123.pdf"
        assert c.step_file.name == "M_123.stp"
        assert len(c.ignored) == 1


    def test_zip_slip_names_flattened(tmp_path):
        z = tmp_path / "m2.zip"
        make_zip(z, {"../../evil.pdf": b"x", "sub/dir/ok.pdf": b"y"})
        c = extract_package(z, tmp_path / "work", "m2")
        names = {p.name for p in c.pdfs}
        assert names == {"evil.pdf", "ok.pdf"}
        for p in c.pdfs:
            assert (tmp_path / "work") in p.parents


    def test_multi_pdf_prefers_material_in_name(tmp_path):
        a = tmp_path / "Anbau.pdf"; a.write_bytes(b"x" * 500)
        b = tmp_path / "Z_10473215.pdf"; b.write_bytes(b"x" * 100)
        c = classify_files([a, b], "10473215")
        assert c.drawing_pdf.name == "Z_10473215.pdf"


    def test_missing_zip_raises(tmp_path):
        with pytest.raises(PackageError):
            extract_package(tmp_path / "fehlt.zip", tmp_path / "w", "x")


    def test_empty_zip_raises(tmp_path):
        z = tmp_path / "leer.zip"
        z.write_bytes(b"")
        with pytest.raises(PackageError):
            extract_package(z, tmp_path / "w", "x")


    # ------------------------------------------------- Schranke fuers Zusammenlegen
    def test_kein_name_wird_im_modul_doppelt_vergeben():
        """Zusammengelegte Module duerfen sich nicht gegenseitig ueberschreiben.

        Beim Flachziehen der Paketstruktur sind zwei verschiedene Regexe unter
        demselben Namen `RE_SCALE` in einem Modul gelandet - der zweite hat den
        ersten verdeckt und die Maßstabserkennung stillgelegt. Gefunden haben
        das die Tests; damit es gar nicht erst passiert, prueft dieser Test
        jedes Modul auf doppelt vergebene Namen auf oberster Ebene.
        """
        import ast
        from collections import Counter
        from pathlib import Path

        def alle(knoten_liste):
            # auch in if/try auf oberster Ebene (GUI-Waechter, Testblock)
            for k in knoten_liste:
                if isinstance(k, (ast.If, ast.Try)):
                    yield from alle(k.body)
                    for h in getattr(k, "handlers", []):
                        yield from alle(h.body)
                    yield from alle(k.orelse)
                else:
                    yield k

        doppelt = {}
        for pfad in [Path(__file__).resolve()]:
            namen = Counter()
            for knoten in alle(ast.parse(pfad.read_text(encoding="utf-8")).body):
                if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef,
                                       ast.ClassDef)):
                    namen[knoten.name] += 1
                elif isinstance(knoten, ast.Assign):
                    for ziel in knoten.targets:
                        if isinstance(ziel, ast.Name):
                            namen[ziel.id] += 1
            mehrfach = {n: z for n, z in namen.items() if z > 1}
            if mehrfach:
                doppelt[pfad.name] = mehrfach
        assert not doppelt, f"Namen doppelt vergeben: {doppelt}"


    # ======================================================================
    # startskript
    # ======================================================================
    # Prüft Start.bat auf die klassischen Batch-Fallen.
    #
    # Unter Linux lässt sich eine .bat-Datei nicht ausführen; die typischen
    # Fehler sind aber statisch erkennbar und haben es in sich – eine unescapte
    # Klammer in einem `if (...)`-Block bricht die Datei mitten im Lauf ab, und
    # das merkt man erst beim Anwender.
    import re


    BAT = Path(__file__).resolve().parent / "Start.bat"
    TEXT = BAT.read_text(encoding="ascii", errors="strict")
    ZEILEN = TEXT.splitlines()


    def test_datei_vorhanden_und_reines_ascii():
        """Umlaute in .bat-Dateien werden je nach Codepage zu Buchstabensalat."""
        assert BAT.is_file()
        TEXT.encode("ascii")          # wirft bei Umlauten


    def _klammer_tiefe(zeile: str, tiefe: int) -> int:
        """Blocktiefe fortschreiben: Anführungszeichen und ^-Escapes beachten."""
        in_string = False
        i = 0
        while i < len(zeile):
            c = zeile[i]
            if c == "^":
                i += 2                # nächstes Zeichen ist escaped
                continue
            if c == '"':
                in_string = not in_string
            elif not in_string and c == "(":
                tiefe += 1
            elif not in_string and c == ")":
                tiefe -= 1
            i += 1
        return tiefe


    def test_bloecke_sind_ausgeglichen():
        tiefe = 0
        for nr, zeile in enumerate(ZEILEN, start=1):
            if zeile.strip().lower().startswith("rem "):
                continue
            tiefe = _klammer_tiefe(zeile, tiefe)
            assert tiefe >= 0, f"Zeile {nr}: schließende Klammer zu viel"
        assert tiefe == 0, "am Dateiende ist ein Block noch offen"


    def test_alle_sprungziele_existieren():
        labels = {z.strip().lstrip(":").lower()
                  for z in ZEILEN if z.strip().startswith(":")}
        ziele = {m.group(1).lower()
                 for m in re.finditer(r"goto\s+:?(\w+)", TEXT, re.IGNORECASE)}
        fehlend = ziele - labels
        assert not fehlend, f"Sprungziele ohne Label: {sorted(fehlend)}"


    def test_keine_verzoegerte_expansion_noetig():
        """Variablen, die in einem Block gesetzt UND gelesen werden.

        Ohne `setlocal EnableDelayedExpansion` liest %VAR% dort den ALTEN
        Wert – der Klassiker unter den Batch-Fehlern.
        """
        tiefe = 0
        gesetzt_im_block: set[str] = set()
        probleme: list[str] = []
        for nr, zeile in enumerate(ZEILEN, start=1):
            if zeile.strip().lower().startswith("rem "):
                continue
            vorher = tiefe
            tiefe = _klammer_tiefe(zeile, tiefe)
            if vorher == 0 and tiefe > 0:
                gesetzt_im_block = set()
            if tiefe > 0 or vorher > 0:
                for m in re.finditer(r'set\s+"?(\w+)=', zeile, re.IGNORECASE):
                    gesetzt_im_block.add(m.group(1).lower())
                for m in re.finditer(r"%(\w+)%", zeile):
                    if m.group(1).lower() in gesetzt_im_block:
                        probleme.append(f"Zeile {nr}: %{m.group(1)}%")
            if tiefe == 0:
                gesetzt_im_block = set()
        assert not probleme, ("verzögerte Expansion nötig oder Zuweisung "
                              f"umstellen: {probleme}")


    def test_ohne_argument_wird_nichts_durchgereicht():
        """`Start.bat neu`/`pruefen` dürfen nicht an das Programm gehen."""
        assert 'if /I "%~1"=="neu" (' in TEXT
        assert re.search(r'if /I "%~1"=="neu" \(\s*\n\s*set "REBUILD=1"\s*\n\s*'
                         r'set "ARGS="', TEXT)


    @pytest.mark.parametrize("schritt", [
        "-m venv",                       # Umgebung anlegen
        "-m pip install \"pymupdf",       # Grundpakete
        "cadquery-ocp", "pytesseract", "pywin32",   # Zusatzpakete
        '"%PROGRAMM%" --check-rules',
        '"%PROGRAMM%" %ARGS%',            # Start mit durchgereichten Optionen
        '"%PROGRAMM%" --sap-import-vbs',
        '"%PROGRAMM%" --sap-dry-run',
        '"%PROGRAMM%" --sap-test',
        '"%PROGRAMM%" --sap-dump',
        '"%PROGRAMM%" --export-rules',
        '-m pytest "%PROGRAMM%" -q',      # Selbsttest
    ])
    def test_wesentliche_schritte_vorhanden(schritt):
        assert schritt in TEXT, f"Schritt fehlt im Startskript: {schritt}"


    def _labelblock(label: str) -> str:
        """Text ab der Label-DEFINITION (nicht ab dem goto) bis exit /b."""
        m = re.search(rf"^:{label}\s*$", TEXT, re.MULTILINE)
        assert m, f"Label :{label} fehlt"
        return TEXT[m.end():].split("exit /b", 1)[0]


    def test_fehlerwege_halten_das_fenster_offen():
        """Bei Doppelklick darf das Fenster im Fehlerfall nicht zuklappen."""
        for label in ("kein_python", "fehler_venv", "fehler_pip", "fehler_lauf"):
            assert "pause" in _labelblock(label), \
                f"{label}: kein pause vor dem Beenden"


    def test_hilfetext_nennt_alle_varianten():
        hilfe = _labelblock("hilfe")
        for variante in ("neu", "pruefen", "--sap-import-vbs"):
            assert variante in hilfe


    # --------------------------------------------------------------- Menue
    def test_menue_deckt_alle_schritte_von_morgen_ab():
        """Ohne Argumente muss ein Menue kommen - morgen tippt niemand Befehle."""
        menue = _labelblock("menu")
        for eintrag in ("Zeichnungen pruefen", "SAP-Mitschnitt einlesen",
                        "Trockenlauf ohne SAP", "Materialnummer testweise",
                        "SAP-Bild anzeigen", "Installation und Regeln pruefen",
                        "Anleitung oeffnen", "Beenden"):
            assert eintrag in menue, f"Menuepunkt fehlt: {eintrag}"


    def test_jede_menuewahl_hat_ein_ziel():
        menue = _labelblock("menu")
        ziele = re.findall(r'if "%WAHL%"=="(\d)" goto :(\w+)', menue)
        assert len(ziele) == 9, f"nicht 9 Menuepunkte verdrahtet: {ziele}"
        labels = {z.strip().lstrip(":").lower()
                  for z in ZEILEN if z.strip().startswith(":")}
        for nummer, ziel in ziele:
            assert ziel.lower() in labels, f"Punkt {nummer} zeigt auf :{ziel}"


    def test_menue_kehrt_zurueck():
        """Nach jeder Aktion muss man wieder im Menue landen."""
        for label in ("m_start", "m_vbs", "m_trocken", "m_test", "m_dump",
                      "m_anleitung", "m_regeln"):
            block = _labelblock(label)
            assert "goto :menu" in block, f"{label} kehrt nicht ins Menue zurueck"


    def test_warnt_beim_start_aus_dem_zip():
        """Aus dem ZIP heraus gestartet gingen alle Ergebnisse verloren."""
        assert 'find /I "\\Temp\\"' in TEXT
        block = _labelblock("aus_zip")
        assert "entpacken" in block.lower()


    # ======================================================================
    # documentation
    # ======================================================================
    # Prüfdokumentation: Zeitstempel, Änderungsdatum, Fertigungsverfahren, Excel.

    import openpyxl
    import pymupdf




    def make_pdf_kurz(tmp_path: Path, lines) -> DrawingPdf:
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        kwargs = {}
        if Path(FONT).exists():
            page.insert_font(fontname="T", fontfile=FONT)
            kwargs["fontname"] = "T"
        lines = list(lines) + ["Interne Testzeichnung – Blatt 1 von 1"]
        for i, line in enumerate(lines):
            page.insert_text((40, 60 + i * 30), line, fontsize=10, **kwargs)
        path = tmp_path / "t.pdf"
        doc.save(path)
        doc.close()
        return DrawingPdf(path)


    # ------------------------------------------------------- Änderungsdatum
    def test_latest_date_wins(tmp_path):
        pdf = make_pdf_kurz(tmp_path, [
            "Erstellt 14.11.2024", "Änderung A 02.03.2025",
            "Änderung B 2026-01-12", "Geprüft 15.11.2024"])
        assert extract_revision_date(pdf) == "2026-01-12"


    def test_us_dates_parsed(tmp_path):
        pdf = make_pdf_kurz(tmp_path, ["REV B 5/23/2021", "REV C 7/14/2021"])
        assert extract_revision_date(pdf) == "2021-07-14"


    def test_norm_years_are_not_dates(tmp_path):
        pdf = make_pdf_kurz(tmp_path, ["ISO 2768:1989", "ISO 8062-3:2007",
                                  "Stand 03.05.2023"])
        assert extract_revision_date(pdf) == "2023-05-03"


    def test_pdf_metadata_fallback(tmp_path):
        pdf = make_pdf_kurz(tmp_path, ["keine Datumsangabe im Text"])
        result = extract_revision_date(pdf)
        # PyMuPDF setzt kein CreationDate -> leer ist hier korrekt; Hauptsache
        # kein Absturz und kein erfundenes Datum.
        assert result == "" or "PDF-Metadatum" in result


    # -------------------------------------------------- Fertigungsverfahren
    def test_detect_processes(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        pdf = make_pdf_kurz(tmp_path, [
            "Werkstoff EN-GJS-400-15, Gussteil nach ISO 8062",
            "Lagerbohrung ⌀90 H7, Ra 6,3",
            "Gewinde M12", "lackiert RAL 7016",
        ])
        procs = detect_processes(pdf)
        assert "Gießen" in procs
        assert "Spanende Bearbeitung" in procs
        assert "Gewindefertigung" in procs
        assert "Lackieren/Beschichten" in procs
        assert "Schweißen" not in procs


    def test_detect_processes_from_castable_material_only(tmp_path):
        pass  # (Import entfaellt - alles ein Modul)

        pdf = make_pdf_kurz(tmp_path, ["Werkstoff EN-GJL-250"])
        assert "Gießen" in detect_processes(pdf)


    # --------------------------------------------------- Excel-Dokumentation
    def test_excel_contains_documentation_columns(mock_dir, tmp_path):
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)
        pass  # (Import entfaellt - alles ein Modul)

        cfg = RunConfig(
            excel_path=mock_dir / "Materialliste_Mock.xlsx",
            sheet_name="Materialliste", material_column="C", header_row=1,
            output_dir=tmp_path / "erg")
        adapter = MockSapAdapter(mock_dir)
        adapter.ensure_ready()
        orch = Orchestrator(cfg, adapter, Callbacks())
        orch.start(); orch.join(300)

        ws = openpyxl.load_workbook(
            mock_dir / "Materialliste_Mock_geprüft.xlsx")["Materialliste"]
        headers = {c.value: c.column for c in ws[1] if isinstance(c.value, str)}
        for required in ("Geprüft am", "Screenshot", "Festgestellte Mängel",
                         "Letzte Zeichnungsänderung", "Fertigungsverfahren"):
            assert required in headers, f"Spalte {required} fehlt"

        # Welle (Zeile 4): alle Dokumentationsfelder gefüllt
        row = 4
        assert ws.cell(row=row, column=headers["Geprüft am"]).value
        assert ws.cell(row=row, column=headers["Letzte Zeichnungsänderung"]
                       ).value == "2026-01-12"
        procs = ws.cell(row=row, column=headers["Fertigungsverfahren"]).value
        assert "Spanende Bearbeitung" in procs and "Gewindefertigung" in procs
        shot = ws.cell(row=row, column=headers["Screenshot"])
        assert shot.hyperlink is not None
        # Schweißkonsole (Zeile 2): Schweißen erkannt
        procs2 = ws.cell(row=2, column=headers["Fertigungsverfahren"]).value
        assert "Schweißen" in procs2


if __name__ == "__main__":
    sys.exit(main())
