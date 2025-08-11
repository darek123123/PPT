from __future__ import annotations

from datetime import date
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QTextEdit,
)

from .state import WizardState, is_valid_step_start


class StepStart(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self._auto_done = False

        lay = QVBoxLayout(self)
        form = QFormLayout()
        lay.addLayout(form)

        self.ed_project = QLineEdit(self)
        self.ed_client = QLineEdit(self)
        self.ed_date = QLineEdit(self)
        self.ed_date.setText(date.today().isoformat())

        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(["baseline", "after", "compare"])

        self.cmb_units = QComboBox(self)
        self.cmb_units.addItems(['Warsztat (mm, CFM, "H₂O, °C)'])

        self.ed_notes = QTextEdit(self)

        form.addRow("Nazwa projektu", self.ed_project)
        form.addRow("Klient", self.ed_client)
        form.addRow("Data (ISO)", self.ed_date)
        form.addRow("Tryb", self.cmb_mode)
        form.addRow("Jednostki", self.cmb_units)
        form.addRow("Notatki", self.ed_notes)

        # Prefill from state if present
        m = self.state.meta
        if m.get("project_name"):
            self.ed_project.setText(str(m.get("project_name")))
        if m.get("client"):
            self.ed_client.setText(str(m.get("client")))
        if m.get("mode"):
            mode = str(m.get("mode"))
            idx = max(0, self.cmb_mode.findText(mode))
            self.cmb_mode.setCurrentIndex(idx)
        # Keep date as today (existing logic) unless meta has a date
        if m.get("date_iso"):
            self.ed_date.setText(str(m.get("date_iso")))

        for w in (self.ed_project, self.ed_client, self.ed_date):
            w.textChanged.connect(self._on_changed)
        self.cmb_mode.currentIndexChanged.connect(self._on_changed)

        self._on_changed()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._auto_compute_once)

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._auto_compute_once()

    def _auto_compute_once(self) -> None:
        if getattr(self, "_auto_done", False):
            return
        self._auto_done = True
        self._on_changed()

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self.state.meta.update(
            {
                "project_name": self.ed_project.text().strip(),
                "client": self.ed_client.text().strip(),
                "date_iso": self.ed_date.text().strip(),
                "mode": self.cmb_mode.currentText(),
                "display_units": "workshop_pl",
                "notes": self.ed_notes.toPlainText() or None,
            }
        )
        ok = is_valid_step_start(self.state)
        self._apply_field_styles()
        self.sig_valid_changed.emit(ok)

    def _apply_field_styles(self) -> None:
        def mark(widget, good: bool) -> None:
            widget.setStyleSheet("" if good else "border: 1px solid red")
            if good:
                widget.setToolTip("")
            else:
                widget.setToolTip("Pole wymagane")

        mark(self.ed_project, bool(self.state.meta.get("project_name")))
        mark(self.ed_client, bool(self.state.meta.get("client")))
