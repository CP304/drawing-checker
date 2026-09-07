# Herkunft der echten Testzeichnungen

Reale, frei lizenzierte Fertigungszeichnungen (mit passenden STEP-Modellen,
wo verfügbar) zur Kalibrierung des Checkers. Nur für interne Test- und
Entwicklungszwecke; Lizenzhinweise beachten.

**Stand: 84 Zeichnungen, davon 28 mit STEP-Modell.**

Die Dateien selbst liegen als **ein** Archiv `mockdata/echt_quellen.zip`
neben diesem Ordner – als über hundert Einzeldateien haben sie jede
Dateiliste zugemüllt. Auspacken (einmalig, nach `mockdata/.echt_quellen/`,
nicht im Repository):

```bash
python -m mockdata.quellen
```

Die Werkzeuge unten packen bei Bedarf von selbst aus.

Der Satz ist bewusst breit: Frästeile, Blechteile, Wellen/Shims, Guss- und
Baugruppenzeichnungen, in Millimeter und in Zoll, ISO- und ASME-Bemaßung,
sauber und schlampig bemaßt. Genau daran zeigt sich, ob eine Regel trägt
oder nur auf der eigenen Mustervorlage funktioniert.

## OreSat / PSAS (Portland State Aerospace Society) — 56 Zeichnungen

Quelle: https://github.com/oresat/oresat-structure — Lizenz: **CERN-OHL-S v2**.
Professionelle SolidWorks-Fertigungszeichnungen (ASME Y14.5, überwiegend in
Millimeter) mit STEP-Modellen. Enthalten sind unter anderem:

- Rahmen der Satellitenstruktur (1U/1.5U/2U/3U, jeweils ±X und Y)
- Kartenkeile in mehreren Varianten (CardWedge*)
- Kamera- und Optikteile (CassegrainBase, lensmount, Shims, Baffle)
- Thermik (copperThermalMass, thermalStrap, thermalClamp)
- Reaktionsräder (MountingBeam, MotorBracket, RWWeight, MagnetHolder)
- Vibrationsprüfvorrichtungen, Montagejigs, Endkarten

Dateien tragen das Präfix `oresat_`; die sieben zuerst aufgenommenen
Zeichnungen behielten ihre ursprünglichen Namen (CassegrainBase.pdf,
lensmount.pdf, copperThermalMass.pdf, thermalStrap.pdf, supportBracket.pdf,
OreSat_InhibitPin.pdf, OreSat_PushPlate.pdf).

## ShapeOko / buildlog.net — 28 Zeichnungen

Quelle: https://github.com/shapeoko/ShapeOko — Lizenz: **CC BY-SA 3.0**.
Inventor-/SolidWorks-Zeichnungen einer offenen CNC-Fräse: Blechteile,
Aluminiumprofile, Platten, Baugruppen. Teilweise in Zoll bemaßt und mit
unvollständigen Schriftfeldern – wertvoll, weil genau solche Zeichnungen im
Einkauf auftauchen.

Dateien tragen das Präfix `shapeoko_`; drei Zeichnungen der ersten Runde
heißen weiterhin DW660_Mount.pdf, MSK01-03.pdf und SM-S02.pdf.

## Bewusst NICHT aufgenommen

- **Katalogblätter von Händlern** (McMaster-Carr u. Ä.): keine
  Fertigungszeichnungen, sondern Referenzblätter zugekaufter Normteile.
  Sie verfälschen die Fehlalarm-Statistik.
- **Zeichnungen unter NC-Lizenz** (z. B. Ultimaker-Teilezeichnungen,
  CC BY-NC): technisch hervorragend, aber die Lizenz erlaubt keine
  kommerzielle Nutzung – für ein Firmenwerkzeug ungeeignet.
- **Leiterplatten-Fertigungsunterlagen**: anderer Zeichnungstyp, andere
  Regeln.

## Nutzung

```bash
python -m mockdata.inject_errors mockdata/echt_quellen <zielordner>
python -m drawing_checker.app --headless --mock <zielordner> \
    --excel <zielordner>/Materialliste_Echt.xlsx --column C
python -m tools.kalibrier_auswertung <zielordner>
```

Der erste Aufruf erzeugt je Zeichnung ein unverändertes **Referenzpaket**
und ein Paket mit **injizierten Fehlern** (MANIFEST.txt dokumentiert, was
wo eingebaut wurde). Die Auswertung stellt beides gegenüber: Was auf den
unveränderten Zeichnungen als „Fehler" gemeldet wird, ist Fehlalarm-Verdacht;
was nur auf den Fehlerpaketen anschlägt, ist echte Trefferleistung.
