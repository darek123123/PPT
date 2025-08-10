from __future__ import annotations

from typing import Any, List, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QStyle,
)

from iop_flow.api import run_all
from iop_flow.engine_link import mach_at_min_csa_for_series

from .state import WizardState


class StepValidate(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)

        self.lbl_info = QLabel("Walidacja i diagnostyka", self)
        root.addWidget(self.lbl_info)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Poziom", "Opis"])
        root.addWidget(self.tree)

        actions = QHBoxLayout()
        self.btn_recompute = QPushButton("Przelicz i odśwież", self)
        actions.addWidget(self.btn_recompute)
        actions.addStretch(1)
        root.addLayout(actions)

        self.btn_recompute.clicked.connect(self._recompute)
        self._recompute()

    def _add_item(self, level: str, text: str) -> None:
        icon = self.style().standardIcon(
            {
                "INFO": QStyle.SP_MessageBoxInformation,
                "WARN": QStyle.SP_MessageBoxWarning,
                "ERROR": QStyle.SP_MessageBoxCritical,
            }.get(level, QStyle.SP_MessageBoxInformation)
        )
        it = QTreeWidgetItem([level, text])
        it.setIcon(0, icon)
        self.tree.addTopLevelItem(it)

    def _recompute(self) -> None:
        self.tree.clear()
        # Try building session and running compute
        session = None
        out: Optional[Dict[str, Any]] = None
        try:
            session = self.state.build_session_for_run_all()
            out = run_all(
                session,
                dp_ref_inH2O=self.state.air_dp_ref_inH2O,
                engine_v_target=(self.state.engine_v_target or 100.0),
            )
        except Exception as e:
            self._add_item("ERROR", f"Nie udało się przeliczyć: {e}")
            self.sig_valid_changed.emit(False)
            return

        # Basic checks
        if self.state.air and not (0.0 <= self.state.air.RH <= 1.0):
            self._add_item("WARN", "Wilgotność RH poza zakresem [0,1]")

        g = self.state.geometry
        if g is not None:
            if g.stem_m >= g.throat_m:
                self._add_item("ERROR", "Średnica trzonka (stem) ≥ throat")
            if not (g.valve_int_m > g.throat_m and g.valve_exh_m > g.throat_m):
                self._add_item("ERROR", "Throat nie jest mniejszy od średnic zaworów")

        # Missing dp hints
        for side_name, rows in (
            ("intake", self.state.measure_intake),
            ("exhaust", self.state.measure_exhaust),
        ):
            if rows:
                missing = sum(1 for r in rows if r.get("dp_inH2O") in (None, ""))
                if missing:
                    self._add_item(
                        "INFO", f"{side_name}: brak dp_inH2O w {missing} punktach — przyjęto dp_ref"
                    )

        # Mach@minCSA if available
        try:
            if not self.state.csa_min_m2:
                self._add_item("INFO", "Brak min_CSA — Mach@minCSA pominięty")
            elif out is not None:
                series_intake: List[Dict[str, Any]] = out.get("series", {}).get("intake", [])  # type: ignore[assignment]
                if series_intake:
                    mach = mach_at_min_csa_for_series(
                        series_intake, self.state.csa_min_m2, session.air
                    )  # type: ignore[arg-type]
                    # Alert only if strictly above 0.60
                    if any((m is not None and float(m) > 0.60) for m in mach):
                        self._add_item("WARN", "Wysoki Mach w min-CSA (>0.60)")
                else:
                    self._add_item("INFO", "Brak serii Intake — Mach@minCSA pominięty")
        except Exception:
            self._add_item("WARN", "Nie udało się policzyć Mach@minCSA")

        # E/I range if both series
        series = (out or {}).get("series", {}) if out else {}
        ei = series.get("ei", [])
        if ei:
            vals = [e.get("EI") for e in ei if e.get("EI") is not None]
            if vals:
                avg = sum(vals) / len(vals)
                # Alert only if strictly outside bounds
                if avg < 0.70 or avg > 0.85:
                    self._add_item("WARN", "E/I poza zakresem 0.70–0.85")
        else:
            # If there is no exhaust data, inform that EI is skipped
            rows_exh = self.state.measure_exhaust
            if not rows_exh:
                self._add_item("INFO", "Brak danych exhaust — E/I pominięte")

        self.sig_valid_changed.emit(True)
