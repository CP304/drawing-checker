# Herkunft der echten Testzeichnungen

Reale, frei lizenzierte Fertigungszeichnungen (mit passenden STEP-Modellen,
wo verfügbar) zur Kalibrierung des Checkers. Nur für interne Test-/
Entwicklungszwecke; Lizenzhinweise beachten.

## OreSat (Portland State Aerospace Society)

Quelle: https://github.com/oresat/oresat-structure — Lizenz: CERN-OHL-v2.
Professionelle SolidWorks-Fertigungszeichnungen (ASME Y14.5, Maße in mm)
mit passenden STEP-Modellen:

- supportBracket.pdf/.STEP (G10 Fiberglas)
- lensmount.pdf/.STEP (Kupfer C110)
- copperThermalMass.pdf/.STEP (Kupfer C110)
- thermalStrap.pdf/.STEP (Kupfer)
- CassegrainBase.pdf/.STEP (Aluminium 6061-T6)
- OreSat_InhibitPin.pdf/.STEP (Aluminium 6061-T6, eloxiert)
- OreSat_PushPlate.pdf/.STEP (Aluminium 6061-T6)

## ShapeOko / buildlog.net

Quelle: https://github.com/shapeoko/ShapeOko — Lizenz: CC BY-SA 3.0.
Inventor-Zeichnungen (Maße in mm):

- DW660_Mount.pdf/.stp (Fräsmotor-Halter, HDPE/UHMW)
- MSK01-03.pdf (Z-Achsen-Teil, ohne STEP)
- SM-S02.pdf (Front/Back Plate, ohne STEP)

## Nutzung

    python -m mockdata.inject_errors mockdata/echt_quellen <zielordner>

erzeugt daraus je Zeichnung ein unverändertes Referenzpaket und ein Paket
mit injizierten Fehlern (siehe MANIFEST.txt im Zielordner).
