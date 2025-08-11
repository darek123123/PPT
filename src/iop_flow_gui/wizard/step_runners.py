from __future__ import annotations

 

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox, QRadioButton
)

from iop_flow import formulas as F
from iop_flow.tuning import (
    quarter_wave_length,
    event_freq_from_rpm,
    csa_from_flow_and_velocity,
    diameter_from_csa,
    helmholtz_plenum_volume_for_freq,
    grid_search_runner,
    RunnerBounds,
)

from .state import WizardState
from ..widgets.mpl_canvas import MplCanvas


class StepRunnersPlenum(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)

        # Intake group
        gi = QGroupBox("Intake (runner)", self)
        gli = QVBoxLayout(gi)
        rowi = QHBoxLayout()
        gli.addLayout(rowi)
        self.ed_rpm_i = QLineEdit(self)
        self.ed_rpm_i.setPlaceholderText("RPM target (np. 6500)")
        self.ed_vi = QLineEdit(self)
        self.ed_vi.setPlaceholderText("v_target [m/s] (np. 55)")
        self.ed_vi.setText("55")
        self.ed_Li_min = QLineEdit(self)
        self.ed_Li_min.setPlaceholderText("L_min [mm]")
        self.ed_Li_max = QLineEdit(self)
        self.ed_Li_max.setPlaceholderText("L_max [mm]")
        self.ed_di_min = QLineEdit(self)
        self.ed_di_min.setPlaceholderText("d_min [mm]")
        self.ed_di_max = QLineEdit(self)
        self.ed_di_max.setPlaceholderText("d_max [mm]")
        rowi.addWidget(QLabel("RPM:", self))
        rowi.addWidget(self.ed_rpm_i)
        rowi.addWidget(QLabel("v_target:", self))
        rowi.addWidget(self.ed_vi)
        rowi2 = QHBoxLayout()
        gli.addLayout(rowi2)
        rowi2.addWidget(QLabel("L[min,max] [mm]:", self))
        rowi2.addWidget(self.ed_Li_min)
        rowi2.addWidget(self.ed_Li_max)
        rowi2.addWidget(QLabel("d[min,max] [mm]:", self))
        rowi2.addWidget(self.ed_di_min)
        rowi2.addWidget(self.ed_di_max)
        rowi3 = QHBoxLayout()
        gli.addLayout(rowi3)
        self.rb_i_o1 = QRadioButton("harm 1", self)
        self.rb_i_o3 = QRadioButton("harm 3", self)
        self.rb_i_o5 = QRadioButton("harm 5", self)
        self.rb_i_o1.setChecked(True)
        rowi3.addWidget(self.rb_i_o1)
        rowi3.addWidget(self.rb_i_o3)
        rowi3.addWidget(self.rb_i_o5)
        rowi3.addStretch(1)
        self.btn_calc_i = QPushButton("Policz (INT)", self)
        self.btn_scan_i = QPushButton("Skanuj (grid)", self)
        gli.addWidget(self.btn_calc_i)
        gli.addWidget(self.btn_scan_i)
        self.lbl_out_i = QLabel("—", self)
        gli.addWidget(self.lbl_out_i)
        root.addWidget(gi)

        # Exhaust group
        ge = QGroupBox("Exhaust (primary)", self)
        gle = QVBoxLayout(ge)
        rowe = QHBoxLayout()
        gle.addLayout(rowe)
        self.ed_rpm_e = QLineEdit(self)
        self.ed_rpm_e.setPlaceholderText("RPM target (np. 6500)")
        self.ed_Te = QLineEdit(self)
        self.ed_Te.setPlaceholderText("T_exh [K] (np. 700)")
        self.ed_Te.setText("700")
        self.ed_ve = QLineEdit(self)
        self.ed_ve.setPlaceholderText("v_target [m/s] (np. 65)")
        self.ed_ve.setText("65")
        self.ed_Le_min = QLineEdit(self)
        self.ed_Le_min.setPlaceholderText("L_min [mm]")
        self.ed_Le_max = QLineEdit(self)
        self.ed_Le_max.setPlaceholderText("L_max [mm]")
        self.ed_de_min = QLineEdit(self)
        self.ed_de_min.setPlaceholderText("d_min [mm]")
        self.ed_de_max = QLineEdit(self)
        self.ed_de_max.setPlaceholderText("d_max [mm]")
        rowe.addWidget(QLabel("RPM:", self))
        rowe.addWidget(self.ed_rpm_e)
        rowe.addWidget(QLabel("T_exh:", self))
        rowe.addWidget(self.ed_Te)
        rowe.addWidget(QLabel("v_target:", self))
        rowe.addWidget(self.ed_ve)
        rowe2 = QHBoxLayout()
        gle.addLayout(rowe2)
        rowe2.addWidget(QLabel("L[min,max] [mm]:", self))
        rowe2.addWidget(self.ed_Le_min)
        rowe2.addWidget(self.ed_Le_max)
        rowe2.addWidget(QLabel("d[min,max] [mm]:", self))
        rowe2.addWidget(self.ed_de_min)
        rowe2.addWidget(self.ed_de_max)
        rowe3 = QHBoxLayout()
        gle.addLayout(rowe3)
        self.rb_e_o1 = QRadioButton("harm 1", self)
        self.rb_e_o3 = QRadioButton("harm 3", self)
        self.rb_e_o5 = QRadioButton("harm 5", self)
        self.rb_e_o1.setChecked(True)
        rowe3.addWidget(self.rb_e_o1)
        rowe3.addWidget(self.rb_e_o3)
        rowe3.addWidget(self.rb_e_o5)
        rowe3.addStretch(1)
        self.btn_calc_e = QPushButton("Policz (EXH)", self)
        self.btn_scan_e = QPushButton("Skanuj (grid)", self)
        gle.addWidget(self.btn_calc_e)
        gle.addWidget(self.btn_scan_e)
        self.lbl_out_e = QLabel("—", self)
        gle.addWidget(self.lbl_out_e)
        root.addWidget(ge)

        # Plenum group (intake)
        gp = QGroupBox("Plenum (Helmholtz)", self)
        glp = QVBoxLayout(gp)
        rowp = QHBoxLayout()
        glp.addLayout(rowp)
        self.ed_use_plenum = QRadioButton("Użyj plenum", self)
        self.ed_use_plenum.setChecked(True)
        self.ed_Aneck_mm2 = QLineEdit(self)
        self.ed_Aneck_mm2.setPlaceholderText("A_neck [mm²]")
        self.ed_Lneck_mm = QLineEdit(self)
        self.ed_Lneck_mm.setPlaceholderText("L_neck [mm]")
        self.ed_f_Hz = QLineEdit(self)
        self.ed_f_Hz.setPlaceholderText("f_Hz (lub rpm target)")
        self.ed_rpm_pl = QLineEdit(self)
        self.ed_rpm_pl.setPlaceholderText("rpm target (opc.)")
        rowp.addWidget(self.ed_use_plenum)
        rowp.addWidget(QLabel("A:", self))
        rowp.addWidget(self.ed_Aneck_mm2)
        rowp.addWidget(QLabel("L:", self))
        rowp.addWidget(self.ed_Lneck_mm)
        rowp.addWidget(QLabel("f:", self))
        rowp.addWidget(self.ed_f_Hz)
        rowp.addWidget(QLabel("RPM:", self))
        rowp.addWidget(self.ed_rpm_pl)
        self.btn_calc_p = QPushButton("Policz V_plenum", self)
        glp.addWidget(self.btn_calc_p)
        self.lbl_out_p = QLabel("—", self)
        glp.addWidget(self.lbl_out_p)
        root.addWidget(gp)

        # Plot area (optional score plot)
        self.plot = MplCanvas()
        self.plot.set_readout_units("RPM", "score")
        root.addWidget(self.plot)

        # Wire
        self.btn_calc_i.clicked.connect(self._calc_intake)
        self.btn_scan_i.clicked.connect(self._scan_intake)
        self.btn_calc_e.clicked.connect(self._calc_exhaust)
        self.btn_scan_e.clicked.connect(self._scan_exhaust)
        self.btn_calc_p.clicked.connect(self._calc_plenum)

        self._prefill()
        self.sig_valid_changed.emit(True)

    def _prefill(self) -> None:
        try:
            if self.state.engine_target_rpm:
                self.ed_rpm_i.setText(str(self.state.engine_target_rpm))
                self.ed_rpm_e.setText(str(self.state.engine_target_rpm))
        except Exception:
            pass

    def _calc_intake(self) -> None:
        try:
            rpm = float((self.ed_rpm_i.text() or "6500").replace(",", "."))
            v_target = float((self.ed_vi.text() or "55").replace(",", "."))
            f = event_freq_from_rpm(rpm)
            T = float(self.state.air.T if self.state.air else F.C_to_K(20.0))
            a = F.speed_of_sound(T)
            order = 1 if self.rb_i_o1.isChecked() else (3 if self.rb_i_o3.isChecked() else 5)
            # Rough q_peak based on engine flow
            q_eng = F.engine_volumetric_flow(self.state.engine.displ_L if self.state.engine else 2.0, rpm, (self.state.engine.ve if self.state.engine and self.state.engine.ve else 1.0))
            A = csa_from_flow_and_velocity(q_eng, v_target)
            d = diameter_from_csa(A)
            L = quarter_wave_length(a, f, order=order, r_m=d*0.5)
            self.lbl_out_i.setText(f"L≈{L*1000:.0f} mm, d≈{d*1000:.1f} mm, A≈{A*1e6:.0f} mm², harm={order}")
            # persist to state
            self.state.tuning["intake_calc"] = {
                "rpm": rpm,
                "v_target": v_target,
                "order": order,
                "L_mm": round(L * 1000.0, 1),
                "d_mm": round(d * 1000.0, 2),
                "A_mm2": round(A * 1e6, 0),
            }
        except Exception:
            self.lbl_out_i.setText("—")

    def _scan_intake(self) -> None:
        try:
            rpm = float((self.ed_rpm_i.text() or "6500").replace(",", "."))
            v_target = float((self.ed_vi.text() or "55").replace(",", "."))
            T = float(self.state.air.T if self.state.air else F.C_to_K(20.0))
            a = F.speed_of_sound(T)
            # Estimate q_peak from engine requirement at RPM
            q_eng = F.engine_volumetric_flow(self.state.engine.displ_L if self.state.engine else 2.0, rpm, (self.state.engine.ve if self.state.engine and self.state.engine.ve else 1.0))
            bounds = RunnerBounds(
                L_min_m=max(0.05, float((self.ed_Li_min.text() or "200").replace(",", ".")) / 1000.0),
                L_max_m=float((self.ed_Li_max.text() or "600").replace(",", ".")) / 1000.0,
                d_min_m=max(0.02, float((self.ed_di_min.text() or "30").replace(",", ".")) / 1000.0),
                d_max_m=float((self.ed_di_max.text() or "55").replace(",", ".")) / 1000.0,
            )
            best, score = grid_search_runner(a, rpm, q_eng, v_target, bounds)
            self.lbl_out_i.setText(f"BEST INT: L={best.L_m*1000:.0f} mm d={best.d_m*1000:.1f} mm A={best.A_m2*1e6:.0f} mm² harm={best.order}; score={score:.0f}; {best.note}")
            self.state.tuning["intake_best"] = {
                "rpm": rpm,
                "v_target": v_target,
                "L_mm": round(best.L_m * 1000.0, 1),
                "d_mm": round(best.d_m * 1000.0, 2),
                "A_mm2": round(best.A_m2 * 1e6, 0),
                "order": int(best.order),
                "score": round(float(score), 2),
                "note": best.note,
            }
        except Exception:
            self.lbl_out_i.setText("—")

    def _calc_exhaust(self) -> None:
        try:
            rpm = float((self.ed_rpm_e.text() or "6500").replace(",", "."))
            T = float((self.ed_Te.text() or "700").replace(",", "."))
            v_target = float((self.ed_ve.text() or "65").replace(",", "."))
            a = F.speed_of_sound(T)
            order = 1 if self.rb_e_o1.isChecked() else (3 if self.rb_e_o3.isChecked() else 5)
            # Assume q_peak similar to intake engine requirement; adjust by typical EXH factor ~1.1
            q_eng = F.engine_volumetric_flow(self.state.engine.displ_L if self.state.engine else 2.0, rpm, (self.state.engine.ve if self.state.engine and self.state.engine.ve else 1.0)) * 1.1
            A = csa_from_flow_and_velocity(q_eng, v_target)
            d = diameter_from_csa(A)
            f = event_freq_from_rpm(rpm)
            L = quarter_wave_length(a, f, order=order, r_m=d*0.5)
            self.lbl_out_e.setText(f"L≈{L*1000:.0f} mm, d≈{d*1000:.1f} mm, A≈{A*1e6:.0f} mm², harm={order}; a(T)={a:.0f} m/s")
            self.state.tuning["exhaust_calc"] = {
                "rpm": rpm,
                "T_K": T,
                "v_target": v_target,
                "order": order,
                "L_mm": round(L * 1000.0, 1),
                "d_mm": round(d * 1000.0, 2),
                "A_mm2": round(A * 1e6, 0),
                "a_mps": round(a, 1),
            }
        except Exception:
            self.lbl_out_e.setText("—")

    def _scan_exhaust(self) -> None:
        try:
            rpm = float((self.ed_rpm_e.text() or "6500").replace(",", "."))
            T = float((self.ed_Te.text() or "700").replace(",", "."))
            v_target = float((self.ed_ve.text() or "65").replace(",", "."))
            a = F.speed_of_sound(T)
            q_eng = F.engine_volumetric_flow(self.state.engine.displ_L if self.state.engine else 2.0, rpm, (self.state.engine.ve if self.state.engine and self.state.engine.ve else 1.0)) * 1.1
            bounds = RunnerBounds(
                L_min_m=max(0.10, float((self.ed_Le_min.text() or "200").replace(",", ".")) / 1000.0),
                L_max_m=float((self.ed_Le_max.text() or "500").replace(",", ".")) / 1000.0,
                d_min_m=max(0.025, float((self.ed_de_min.text() or "28").replace(",", ".")) / 1000.0),
                d_max_m=float((self.ed_de_max.text() or "50").replace(",", ".")) / 1000.0,
            )
            best, score = grid_search_runner(a, rpm, q_eng, v_target, bounds)
            self.lbl_out_e.setText(f"BEST EXH: L={best.L_m*1000:.0f} mm d={best.d_m*1000:.1f} mm A={best.A_m2*1e6:.0f} mm² harm={best.order}; score={score:.0f}; {best.note}")
            self.state.tuning["exhaust_best"] = {
                "rpm": rpm,
                "T_K": T,
                "v_target": v_target,
                "L_mm": round(best.L_m * 1000.0, 1),
                "d_mm": round(best.d_m * 1000.0, 2),
                "A_mm2": round(best.A_m2 * 1e6, 0),
                "order": int(best.order),
                "score": round(float(score), 2),
                "note": best.note,
            }
        except Exception:
            self.lbl_out_e.setText("—")

    def _calc_plenum(self) -> None:
        try:
            if not self.ed_use_plenum.isChecked():
                self.lbl_out_p.setText("—")
                return
            A_mm2 = float((self.ed_Aneck_mm2.text() or "1200").replace(",", "."))
            L_mm = float((self.ed_Lneck_mm.text() or "80").replace(",", "."))
            f_Hz = float((self.ed_f_Hz.text() or "" ).replace(",", ".")) if self.ed_f_Hz.text() else None
            rpm_pl = float((self.ed_rpm_pl.text() or "" ).replace(",", ".")) if self.ed_rpm_pl.text() else None
            if f_Hz is None and rpm_pl is None:
                # fall back to engine target rpm
                rpm_pl = float(self.state.engine_target_rpm or 6000)
            if f_Hz is None and rpm_pl is not None:
                f_Hz = rpm_pl / 120.0
            T = float(self.state.air.T if self.state.air else F.C_to_K(20.0))
            a = F.speed_of_sound(T)
            A = A_mm2 / 1e6
            L = L_mm / 1000.0
            V = helmholtz_plenum_volume_for_freq(a, A, L, float(f_Hz))
            self.lbl_out_p.setText(f"V_plenum≈{V*1000:.1f} L (a={a:.0f} m/s, f={f_Hz:.1f} Hz)")
            self.state.tuning["plenum"] = {
                "A_neck_mm2": A_mm2,
                "L_neck_mm": L_mm,
                "f_Hz": float(f_Hz),
                "rpm": float(rpm_pl) if rpm_pl is not None else None,
                "a_mps": round(a, 1),
                "V_L": round(V * 1000.0, 2),
            }
        except Exception:
            self.lbl_out_p.setText("—")
