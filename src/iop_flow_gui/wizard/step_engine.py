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

        # Prefill from state if present; else sensible defaults
        if self.state.engine:
            e = self.state.engine
            if e.displ_L:
                self.ed_displ.setText(f"{e.displ_L:.3g}")
            if e.cylinders:
                self.ed_cyl.setText(str(int(e.cylinders)))
            if e.ve is not None:
                self.ed_ve.setText(f"{e.ve:.3g}")
        if self.state.engine_target_rpm:
            self.ed_rpm.setText(str(int(self.state.engine_target_rpm)))
        if not self.ed_displ.text().strip():
            self.ed_displ.setText("2.0")
        if not self.ed_cyl.text().strip():
            self.ed_cyl.setText("4")
        if not self.ed_ve.text().strip():
            self.ed_ve.setText("0.95")
        if not self.ed_rpm.text().strip():
            self.ed_rpm.setText("6500")

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
        # draw Q_eng vs RPM with guards
        self.canvas.clear()
        e = self.state.engine
        ve = e.ve if (e and (e.ve or 0) > 0) else 0.95
        displ = e.displ_L if (e and e.displ_L and e.displ_L > 0) else None
        if not displ:
            # show hint when displacement invalid
            try:
                self.canvas.ax.clear()
                self.canvas.ax.text(0.5, 0.5, "Uzupełnij silnik (L > 0)", ha="center", va="center")
                self.canvas.render()
            except Exception:
                pass
            return
        rpms = list(range(1000, 9001, 500))
        try:
            q = [F.engine_volumetric_flow(displ, r, ve) for r in rpms]
        except ValueError:
            # fallback if any calc fails
            try:
                self.canvas.ax.clear()
                self.canvas.ax.text(0.5, 0.5, "Błąd obliczeń Q_eng", ha="center", va="center")
                self.canvas.render()
            except Exception:
                pass
            return
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
