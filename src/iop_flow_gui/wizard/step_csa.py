from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QToolButton,
    QMessageBox,
)

from .state import WizardState, parse_float_pl
from iop_flow.api import run_all
from iop_flow import formulas as F
from iop_flow_gui.widgets.mpl_canvas import MplCanvas


class StepCSA(QWidget):
    """CSA step: min/avg CSA inputs, auto-compute Mach@minCSA plot."""

    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:  # noqa: PLR0915
        super().__init__()
        self.state = state
        self._auto_done = False

        root = QHBoxLayout(self)
        left = QVBoxLayout()
        root.addLayout(left, 2)

        # Form inputs
        form = QVBoxLayout()
        self.ed_min = QLineEdit(self)
        self.ed_min.setPlaceholderText("min CSA [mm²]")
        self.ed_avg = QLineEdit(self)
        self.ed_avg.setPlaceholderText("avg CSA [mm²] (opcjonalne)")
        self.ed_vt = QLineEdit(self)
        self.ed_vt.setPlaceholderText("v_target [m/s]")
        form.addWidget(QLabel("Min CSA [mm²]", self))
        form.addWidget(self.ed_min)
        form.addWidget(QLabel("Avg CSA [mm²] (opcjonalne)", self))
        form.addWidget(self.ed_avg)
        form.addWidget(QLabel("Docelowa prędkość w porcie v_target [m/s]", self))
        form.addWidget(self.ed_vt)
        left.addLayout(form)

        # Actions
        actions = QHBoxLayout()
        self.btn_compute = QPushButton("Przelicz", self)
        actions.addWidget(self.btn_compute)
        actions.addStretch(1)
        left.addLayout(actions)

        # Right panel (plot + info)
        right = QVBoxLayout()
        root.addLayout(right, 3)
        self.plot_mach = MplCanvas()
        right.addWidget(self.plot_mach)
        info_row = QHBoxLayout()
        info_row.addStretch(1)
        self.btn_info = QToolButton(self)
        self.btn_info.setText("i")
        self.btn_info.setToolTip("Mach = V/a(T); V z Q i min-CSA")
        info_row.addWidget(self.btn_info)
        right.addLayout(info_row)
        self.lbl_nums = QLabel("—", self)
        self.lbl_alert = QLabel("", self)
        self.lbl_alert.setStyleSheet("color:red;font-weight:bold;")
        right.addWidget(self.lbl_nums)
        right.addWidget(self.lbl_alert)

        # Signals
        self.btn_compute.clicked.connect(self._compute)
        self.btn_info.clicked.connect(self._show_info)
        for ed in (self.ed_min, self.ed_avg, self.ed_vt):
            ed.textChanged.connect(self._on_changed)  # type: ignore[arg-type]

        # Prefill from state
        if self.state.csa_min_m2 is not None:
            self.ed_min.setText(f"{self.state.csa_min_m2 * 1e6:.1f}")
        if self.state.csa_avg_m2 is not None:
            self.ed_avg.setText(f"{self.state.csa_avg_m2 * 1e6:.1f}")
        if self.state.engine_v_target is not None:
            self.ed_vt.setText(f"{self.state.engine_v_target:.1f}")

        self._emit_valid()
        QTimer.singleShot(0, self._auto_compute_once)

    # ---- Auto compute pattern ----
    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        self._auto_compute_once()

    def _auto_compute_once(self) -> None:
        if self._auto_done:
            return
        self._auto_done = True
        try:
            if any(
                (
                    self.ed_min.text().strip(),
                    self.ed_avg.text().strip(),
                    self.ed_vt.text().strip(),
                )
            ):
                self._compute()
        except Exception:  # pragma: no cover
            pass
        self.sig_valid_changed.emit(True)

    # ---- Validation ----
    def _on_changed(self, *_: Any) -> None:
        self._apply_validation()
        self._emit_valid()

    def _apply_validation(self) -> None:
        def parse_opt(s: str) -> Optional[float]:
            s = s.strip()
            if not s:
                return None
            try:
                return parse_float_pl(s)
            except Exception:
                return None

        v_min = parse_opt(self.ed_min.text())
        v_avg = parse_opt(self.ed_avg.text())
        v_vt = parse_opt(self.ed_vt.text())

        def mark(w: QLineEdit, ok: bool, tip: str = "") -> None:
            w.setToolTip("" if ok else (tip or "Błędna wartość"))
            w.setStyleSheet("border:1px solid red;" if not ok else "")

        ok_min = (v_min is None) or (v_min > 0)
        ok_avg = (v_avg is None) or (v_avg > 0)
        ok_rel = True
        if v_min is not None and v_avg is not None:
            ok_rel = v_min <= v_avg
        ok_vt = (v_vt is None) or (v_vt > 0)
        mark(self.ed_min, ok_min, ">0 lub puste")
        mark(self.ed_avg, ok_avg, ">0 lub puste")
        mark(self.ed_vt, ok_vt, ">0 lub puste")
        if not ok_rel:
            self.ed_min.setToolTip("min_csa ≤ avg_csa")
            self.ed_min.setStyleSheet("border:1px solid red;")
            self.ed_avg.setStyleSheet("border:1px solid red;")

    def _emit_valid(self) -> None:
        self.sig_valid_changed.emit(True)

    # ---- Compute ----
    def _compute(self) -> None:
        def parse_opt(s: str) -> Optional[float]:
            s = s.strip()
            if not s:
                return None
            try:
                return parse_float_pl(s)
            except Exception:
                return None

        min_mm2 = parse_opt(self.ed_min.text())
        avg_mm2 = parse_opt(self.ed_avg.text())
        vt = parse_opt(self.ed_vt.text())
        self.state.set_csa_from_ui(min_mm2, avg_mm2, vt)
        try:
            session = self.state.build_session_for_run_all()
        except Exception:
            return
        # Preferences fallback (simple defaults if prefs module unavailable)
        class _Pref:
            dp_ref_inH2O = self.state.air_dp_ref_inH2O or 28.0
            a_ref_mode = "eff"
            eff_mode = "smoothmin"
            v_target = self.state.engine_v_target or 70.0
        prefs = _Pref()
        import time
        t0 = time.perf_counter()
        result = run_all(
            session,
            dp_ref_inH2O=prefs.dp_ref_inH2O,
            a_ref_mode=prefs.a_ref_mode,
            eff_mode=prefs.eff_mode,
            engine_v_target=(self.state.engine_v_target or prefs.v_target),
        )
        series = result.get("series", {})
        intake: List[Dict[str, Any]] = series.get("intake", [])  # type: ignore[assignment]
        engine = result.get("engine", {})
        self.plot_mach.clear()
        mach = engine.get("mach_min_csa")
        if mach and intake:
            lifts = [row.get("lift_m") for row in intake]
            if lifts and len(lifts) == len(mach):
                min_csa_mm2 = (self.state.csa_min_m2 or 0.0) * 1e6
                try:
                    a_T = F.speed_of_sound(self.state.air.T if self.state.air else 293.15)
                except Exception:
                    a_T = 0.0
                title = f"Mach@min-CSA min-CSA={min_csa_mm2:.0f} mm²; a(T)={a_T:.0f} m/s"
                lifts_mm = [float(v or 0.0) * 1000.0 for v in lifts]
                self.plot_mach.set_readout_units("mm", "-")
                self.plot_mach.plot_xy(lifts_mm, mach, label="Mach@minCSA", xlabel="Lift [mm]", ylabel="Mach (-)", title=title)
        self.plot_mach.render()
        rpm_flow = engine.get("rpm_flow_limit")
        rpm_csa = engine.get("rpm_from_csa")
        nums = []
        if rpm_flow:
            nums.append(f"RPM_flow_limit={rpm_flow:,.0f}")
        if rpm_csa:
            nums.append(f"RPM_from_CSA={rpm_csa:,.0f}")
        if not intake and self.state.csa_min_m2 is not None:
            nums.append("Brak serii Intake — brak Mach@minCSA")
        if self.state.csa_avg_m2 is not None and self.state.engine is None:
            nums.append("Brak parametrów silnika — RPM_from_CSA wymaga displ i VE")
        self.lbl_nums.setText("; ".join(nums) if nums else "—")
        alert_txt = ""
        if mach:
            try:
                if any((m is not None and float(m) > 0.60) for m in mach):
                    alert_txt = "ALERT: Wysoki Mach w min-CSA (>0.60)"
            except Exception:
                pass
        self.lbl_alert.setText(alert_txt)
        try:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            win = self.window()
            if hasattr(win, "statusBar"):
                sb = win.statusBar()
                if sb is not None:
                    sb.showMessage(f"OK ({dt_ms} ms)", 2000)
        except Exception:
            pass

    def _show_info(self) -> None:
        QMessageBox.information(
            self,
            "Informacje",
            "Mach = V/a(T); V liczone z Q oraz min-CSA (prędkość w minimum przekroju)",
        )
