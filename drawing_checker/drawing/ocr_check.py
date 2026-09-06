"""Werkzeug: OCR-Fähigkeit prüfen und an einer Datei ausprobieren.

    drawing-checker --ocr-check                  # nur Installation prüfen
    drawing-checker --ocr-check zeichnung.pdf    # Datei durch die OCR jagen

Zeigt, ob Tesseract und die Sprachpakete vorhanden sind, wie die aktuellen
Einstellungen lauten und – mit Datei – was die Erkennung liefert. Damit
lässt sich am Zielrechner in einem Schritt klären, ob ein Scan überhaupt
auswertbar ist, statt es am Prüfergebnis zu raten.
"""
from __future__ import annotations

from pathlib import Path


def ocr_check(pdf_path: Path | None = None) -> int:
    from .ocr import OcrSettings, _tesseract

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
    from .dimensions import extract_dimensions
    from .pdfdoc import DrawingPdf

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
