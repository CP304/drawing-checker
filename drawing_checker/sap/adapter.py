"""Adapter-Interface zur SAP-Beschaffung der YMATDOCS-Pakete.

Der Orchestrator kennt nur dieses Interface. Implementierungen:
  * SapGuiAdapter (sap/session.py): echtes SAP GUI Scripting (nur Windows).
  * MockSapAdapter (sap/mock.py): liefert ZIPs aus einem Ordner – für
    Entwicklung/Tests ohne SAP und für die Mockdaten-Läufe.
"""
from __future__ import annotations

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
