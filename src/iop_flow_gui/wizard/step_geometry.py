from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QDoubleSpinBox,
)

from iop_flow import formulas as F

from ..widgets.mpl_canvas import MplCanvas
from .state import WizardState, parse_float_pl, is_valid_step_geometry, set_geometry_from_ui


class StepGeometry(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QHBoxLayout(self)

        # left form
        form_wrap = QWidget(self)
        form = QFormLayout(form_wrap)
        root.addWidget(form_wrap, 1)

        self.ed_bore = QLineEdit(self)
        self.ed_valve_i = QLineEdit(self)
        self.ed_valve_e = QLineEdit(self)
        self.ed_throat = QLineEdit(self)
        self.ed_stem = QLineEdit(self)
        self.ed_seat_angle = QLineEdit(self)
        self.ed_seat_width = QLineEdit(self)
        self.ed_port_vol = QLineEdit(self)
        self.ed_port_len = QLineEdit(self)

        form.addRow("Adapter/Bore [mm]", self.ed_bore)
        form.addRow("Valve INT [mm]", self.ed_valve_i)
        form.addRow("Valve EXH [mm]", self.ed_valve_e)
        form.addRow("Throat [mm]", self.ed_throat)
        form.addRow("Stem [mm]", self.ed_stem)
        form.addRow("Seat angle [deg] (opc.)", self.ed_seat_angle)
        form.addRow("Seat width [mm] (opc.)", self.ed_seat_width)
        form.addRow("Port volume [cc] (opc.)", self.ed_port_vol)
        form.addRow("Port length [mm] (opc.)", self.ed_port_len)

        # right preview
        right_wrap = QWidget(self)
        right = QVBoxLayout(right_wrap)
        root.addWidget(right_wrap, 1)

        self.lbl_Ath = QLabel("A_throat: — mm²", self)
        right.addWidget(self.lbl_Ath)
        self.preview = MplCanvas()
        right.addWidget(self.preview)
        self.spin_lift = QDoubleSpinBox(self)
        self.spin_lift.setRange(0.0, 50.0)
        self.spin_lift.setDecimals(3)
        self.spin_lift.setSingleStep(0.1)
        self.spin_lift.setValue(5.0)
        right.addWidget(self.spin_lift)

        for w in (
            self.ed_bore,
            self.ed_valve_i,
            self.ed_valve_e,
            self.ed_throat,
            self.ed_stem,
            self.ed_seat_angle,
            self.ed_seat_width,
            self.ed_port_vol,
            self.ed_port_len,
        ):
            w.textChanged.connect(self._on_changed)
        self.spin_lift.valueChanged.connect(self._on_changed)

        self._on_changed()

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        def f(ed: QLineEdit) -> Optional[float]:
            t = ed.text().strip()
            if not t:
                return None
            try:
                return parse_float_pl(t)
            except Exception:
                return None

        bore = f(self.ed_bore)
        vi = f(self.ed_valve_i)
        ve = f(self.ed_valve_e)
        th = f(self.ed_throat)
        st = f(self.ed_stem)
        ang = f(self.ed_seat_angle)
        sw = f(self.ed_seat_width)
        pv = f(self.ed_port_vol)
        pl = f(self.ed_port_len)

        if all(x is not None for x in (bore, vi, ve, th, st)):
            set_geometry_from_ui(
                self.state,
                bore_mm=bore or 0.0,
                valve_int_mm=vi or 0.0,
                valve_exh_mm=ve or 0.0,
                throat_mm=th or 0.0,
                stem_mm=st or 0.0,
                seat_angle_deg=ang,
                seat_width_mm=sw,
                port_volume_cc=pv,
                port_length_mm=pl,
            )
        else:
            self.state.geometry = None

        # preview: A_throat and L/D lines
        g = self.state.geometry
        if g:
            Ath_mm2 = F.area_throat(g.throat_m, g.stem_m) * 1e6
            self.lbl_Ath.setText(f"A_throat: {Ath_mm2:.2f} mm²")
            # L/D vs lift for INT and EXH
            lifts = [i / 10.0 for i in range(0, 501)]  # 0..50 mm step 0.1
            x = lifts
            ld_i = [(lift / 1000.0) / g.valve_int_m for lift in lifts]
            ld_e = [(lift / 1000.0) / g.valve_exh_m for lift in lifts]
            self.preview.clear()
            self.preview.plot_xy(x, ld_i, label="L/D INT")
            self.preview.plot_xy(x, ld_e, label="L/D EXH")
            self.preview.render()
        else:
            self.lbl_Ath.setText("A_throat: — mm²")
            self.preview.clear()
            self.preview.render()

        ok = is_valid_step_geometry(self.state)
        self._apply_styles(ok)
        self.sig_valid_changed.emit(ok)

    def _apply_styles(self, ok: bool) -> None:
        def mark(ed: QLineEdit, good: bool, tip: str = "Błąd wartości") -> None:
            ed.setStyleSheet("" if good else "border: 1px solid red")
            ed.setToolTip("" if good else tip)

        g = self.state.geometry
        req = [self.ed_bore, self.ed_valve_i, self.ed_valve_e, self.ed_throat, self.ed_stem]
        for ed in req:
            mark(ed, g is not None)
        # relations if geometry present
        if g:
            mark(self.ed_stem, g.stem_m < g.throat_m, "stem < throat")
            mark(self.ed_valve_i, g.valve_int_m > g.throat_m, "> throat")
            mark(self.ed_valve_e, g.valve_exh_m > g.throat_m, "> throat")
