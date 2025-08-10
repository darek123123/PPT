from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
)

from iop_flow import formulas as F
from iop_flow.schemas import Engine

from ..widgets.mpl_canvas import MplCanvas
from .state import WizardState, parse_float_pl, is_valid_step_engine


class StepEngine(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._update_plot)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        lay.addLayout(form)

        self.ed_displ = QLineEdit(self)
        self.ed_cyl = QLineEdit(self)
        self.ed_ve = QLineEdit(self)
        self.ed_rpm = QLineEdit(self)
        form.addRow("Displacement [L]", self.ed_displ)
        form.addRow("Cylindry", self.ed_cyl)
        form.addRow("VE (opc.)", self.ed_ve)
        form.addRow("Target RPM (opc.)", self.ed_rpm)

        self.lbl_hint = QLabel("Podpowiedź VE: 0.95–1.00", self)
        lay.addWidget(self.lbl_hint)

        self.canvas = MplCanvas()
        lay.addWidget(self.canvas)

        for w in (self.ed_displ, self.ed_cyl, self.ed_ve, self.ed_rpm):
            w.textChanged.connect(self._on_changed)

        self._on_changed()

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        # parse
        displ = self._parse_float_opt(self.ed_displ.text())
        cyl = self._parse_int_opt(self.ed_cyl.text())
        ve = self._parse_float_opt(self.ed_ve.text())
        rpm = self._parse_int_opt(self.ed_rpm.text())

        # update state
        self.state.engine = (
            Engine(displ_L=displ or 0.0, cylinders=cyl or 0, ve=ve if (ve is not None) else None)
            if displ and cyl
            else None
        )
        self.state.engine_target_rpm = rpm if rpm else None

        # debounce plot
        self._timer.start()

        ok = is_valid_step_engine(self.state)
        self._apply_field_styles()
        self.sig_valid_changed.emit(ok)

    def _update_plot(self) -> None:
        # draw Q_eng vs RPM
        self.canvas.clear()
        displ = (self.state.engine.displ_L if self.state.engine else None) or 0.0
        ve = (
            self.state.engine.ve
            if (self.state.engine and self.state.engine.ve is not None)
            else 0.95
        )
        rpms = list(range(1000, 9001, 500))
        q = [F.engine_volumetric_flow(displ, r, ve) for r in rpms]
        self.canvas.plot_xy(rpms, q, label="Q_eng [m³/s]")
        self.canvas.render()

    def _parse_float_opt(self, text: str) -> Optional[float]:
        t = text.strip()
        if not t:
            return None
        try:
            return parse_float_pl(t)
        except Exception:
            return None

    def _parse_int_opt(self, text: str) -> Optional[int]:
        t = text.strip()
        if not t:
            return None
        try:
            return int(float(parse_float_pl(t)))
        except Exception:
            return None

    def _apply_field_styles(self) -> None:
        def mark(widget, good: bool, tip: str = "Błąd wartości") -> None:
            widget.setStyleSheet("" if good else "border: 1px solid red")
            widget.setToolTip("" if good else tip)

        e = self.state.engine
        mark(self.ed_displ, bool(e and e.displ_L > 0), "> 0")
        mark(self.ed_cyl, bool(e and e.cylinders > 0), "> 0")
        ve_ok = True if (e is None or e.ve is None) else (e.ve >= 0)
        mark(self.ed_ve, ve_ok, ">= 0")
        rpm = self.state.engine_target_rpm
        mark(self.ed_rpm, True if rpm is None else rpm > 0, "> 0")
