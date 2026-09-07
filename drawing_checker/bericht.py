"""Ausgabe: markiertes Bild, Excel-Rueckschrieb, HTML-Bericht.

Drei Ausgabewege auf dieselben Ergebnisse - deshalb ein Modul.
"""
from __future__ import annotations

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

from .kern import Finding, MaterialResult, Severity, SEVERITY_LABEL
from .zeichnung import RENDER_DPI, DrawingPdf

log = logging.getLogger(__name__)

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

from .kern import JobStatus, MaterialResult, RunConfig, Severity, SEVERITY_LABEL


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

from .kern import ( JobStatus, MaterialResult, RunConfig, Severity, SEVERITY_LABEL, )

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
