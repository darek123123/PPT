from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
    QTextEdit,
)

from iop_flow import formulas as F
from iop_flow.schemas import AirConditions

from .state import WizardState, parse_float_pl, is_valid_step_bench


class StepBench(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self._auto_done = False
        lay = QVBoxLayout(self)
        form = QFormLayout()
        lay.addLayout(form)

        self.ed_dp_ref = QLineEdit(self)
        self.ed_dp_ref.setText("28.0")
        self.ed_dp_meas = QLineEdit(self)
        self.ed_dp_meas.setText("28.0")
        self.ed_T_C = QLineEdit(self)
        self.ed_T_C.setText("20.0")
        self.ed_p_pa = QLineEdit(self)
        self.ed_p_pa.setText("101325")
        self.ed_rh = QLineEdit(self)
        self.ed_rh.setText("0.0")
        self.ed_notes = QTextEdit(self)

        form.addRow('ΔP ref ["H₂O]', self.ed_dp_ref)
        form.addRow('ΔP meas ["H₂O]', self.ed_dp_meas)
        form.addRow("T [°C]", self.ed_T_C)
        form.addRow("p_tot [Pa]", self.ed_p_pa)
        form.addRow("RH [0..1]", self.ed_rh)
        form.addRow("Kalibracja/notatki", self.ed_notes)

        # live preview
        self.lbl_rho = QLabel("ρ: —", self)
        self.lbl_a = QLabel("a(T): —", self)
        lay.addWidget(self.lbl_rho)
        lay.addWidget(self.lbl_a)

        # wiring
        for w in (self.ed_dp_ref, self.ed_dp_meas, self.ed_T_C, self.ed_p_pa, self.ed_rh):
            w.textChanged.connect(self._on_changed)

        self._on_changed()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._auto_compute_once)

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._auto_compute_once()

    def _auto_compute_once(self) -> None:
        if self._auto_done:
            return
        self._auto_done = True
        self._on_changed()

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        try:
            dp_ref = parse_float_pl(self.ed_dp_ref.text())
        except Exception:
            dp_ref = -1.0
        try:
            dp_meas = self.ed_dp_meas.text().strip()
            dp_meas_v = parse_float_pl(dp_meas) if dp_meas else None
        except Exception:
            dp_meas_v = None
        try:
            T_K = F.C_to_K(parse_float_pl(self.ed_T_C.text()))
        except Exception:
            T_K = -1.0
        try:
            p_pa = parse_float_pl(self.ed_p_pa.text())
        except Exception:
            p_pa = -1.0
        try:
            rh = parse_float_pl(self.ed_rh.text())
        except Exception:
            rh = -1.0

        if p_pa > 0 and T_K > 0 and 0.0 <= rh <= 1.0:
            rho = F.air_density(F.AirState(p_pa, T_K, rh))
            a = F.speed_of_sound(T_K)
            self.lbl_rho.setText(f"ρ: {rho:.4f} kg/m³")
            self.lbl_a.setText(f"a(T): {a:.2f} m/s")
            # live preview confirmed via labels
        else:
            self.lbl_rho.setText("ρ: —")
            self.lbl_a.setText("a(T): —")

        self.state.air_dp_ref_inH2O = dp_ref
        self.state.air_dp_meas_inH2O = dp_meas_v
        self.state.air = AirConditions(
            p_tot=max(p_pa, 0.0), T=max(T_K, 0.0), RH=max(min(rh, 1.0), 0.0)
        )

        ok = is_valid_step_bench(self.state)
        self._apply_field_styles()
        self.sig_valid_changed.emit(ok)

    def _apply_field_styles(self) -> None:
        def mark(widget, good: bool, tip: str = "Błąd wartości") -> None:
            widget.setStyleSheet("" if good else "border: 1px solid red")
            widget.setToolTip("" if good else tip)

        mark(self.ed_dp_ref, (self.state.air_dp_ref_inH2O or 0) > 0, "> 0")
        air = self.state.air
        ok_T = bool(air and air.T > 0)
        ok_p = bool(air and air.p_tot > 0)
        ok_rh = bool(air and 0 <= air.RH <= 1)
        mark(self.ed_T_C, ok_T)
        mark(self.ed_p_pa, ok_p)
        mark(self.ed_rh, ok_rh, "0..1")
