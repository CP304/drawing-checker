"""OCR-Fallback für gescannte Zeichnungen ohne Textlayer.

Technische Zeichnungen sind für OCR ein Sonderfall: Der Text steht nicht in
Absätzen, sondern verstreut zwischen Linien, ist teilweise um 90° gedreht
(Maße an senkrechten Maßlinien) und besteht überwiegend aus Codes
(„1.4301", „M12x1,5", „⌀20 H7"), die kein Wörterbuch kennt. Die
Standardeinstellungen von Tesseract sind darauf nicht ausgelegt.

Der Pfad hier bündelt, was sich in freien OCR-Pipelines (OCRmyPDF,
tesseract-Rezepte) als wirksam erwiesen hat, zugeschnitten auf Zeichnungen:

  1. Hohe Renderauflösung (Standard 400 dpi) in Graustufen.
  2. Binarisierung nach Otsu – entfernt Scan-Rauschen und Grauschleier.
  3. Optionale Schräglagenkorrektur über das Projektionsprofil.
  4. Seitensegmentierung „sparse text" (PSM 11) statt Absatzlayout.
  5. Zweiter Durchgang auf dem um 90° gedrehten Bild; die Fundstellen
     werden zurückgerechnet. Erst das findet die gedrehten Maßtexte.
  6. Wörterbücher aus – sonst „korrigiert" Tesseract Codes kaputt.
  7. Nachkorrektur der typischen Verwechslungen (O/0, l/1, Ø-Varianten).

Alle Stellschrauben lassen sich ohne Codeänderung über Umgebungsvariablen
setzen (DRAWING_CHECKER_OCR_*), damit die Einstellung am Zielrechner
nachjustiert werden kann – siehe `OcrSettings`.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pymupdf

from ..core.models import BBox

if TYPE_CHECKING:
    from .pdfdoc import Word

log = logging.getLogger(__name__)


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

    from .pdfdoc import Word          # Laufzeitimport, zyklusfrei

    words: list[Word] = []
    todo = pages if pages is not None else range(doc.page_count)
    for pno in todo:
        page = doc[pno]
        img = _render(page, cfg, Image)
        angle = _skew_angle(img, cfg) if cfg.deskew else 0.0
        if angle:
            log.info("OCR Seite %d: Schräglage %.1f° korrigiert", pno + 1, angle)
            img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
        page_words = _ocr_page(img, pno, cfg, pytesseract, Image, Word)
        words.extend(page_words)
    words = _dedupe(words)
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
    return Image.fromarray(((arr > threshold) * 255).astype("uint8"))


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
        out.extend(_pass(rotated, pno, cfg,
                         cfg.min_conf + cfg.rotation_conf_bonus, angle, scale,
                         img.height, pytesseract, Word))
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


def _dedupe(words: "list[Word]") -> "list[Word]":
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
