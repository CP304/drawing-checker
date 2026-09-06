"""Nachbau einer SAP-GUI-Scripting-Session für Tests und Trockenläufe.

Bildet die Teile der COM-API nach, die der Adapter nutzt (FindById, Text,
Press, SendVKey, Busy, sbar …). Damit lässt sich der komplette Ablauf –
Ablaufabspielen, Popup-Behandlung, Fehlerpfade, Download-Erkennung – ohne
SAP-Installation prüfen. Wird ausschließlich in Tests und im Trockenlauf
(`--sap-dry-run`) verwendet.
"""
from __future__ import annotations

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
