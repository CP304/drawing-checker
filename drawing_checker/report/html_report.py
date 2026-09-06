"""HTML-Übersichtsbericht je Prüflauf.

Eine einzelne, selbsterklärende HTML-Datei im Laufordner: Kennzahlen,
Mängel-Ranking und die komplette Ergebnistabelle mit Links auf die
annotierten Zeichnungsbilder (relative Pfade – der Ordner ist als Ganzes
teil-/archivierbar).
"""
from __future__ import annotations

import html
import time
from collections import Counter
from pathlib import Path

from ..core.models import (
    JobStatus, MaterialResult, RunConfig, Severity, SEVERITY_LABEL,
)

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
