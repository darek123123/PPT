from __future__ import annotations

from typing import Optional, Any, List, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from iop_flow.api import run_all
from ..widgets.mpl_canvas import MplCanvas
from .state import WizardState, parse_float_pl
from ..preferences import load_prefs


class StepCSA(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

        root = QHBoxLayout(self)

        # Left panel: inputs and actions
        left = QVBoxLayout()
        form = QVBoxLayout()

        self.ed_min = QLineEdit(self)
        self.ed_avg = QLineEdit(self)
        self.ed_vt = QLineEdit(self)
        self.ed_min.setPlaceholderText("Min CSA [mm²]")
        self.ed_avg.setPlaceholderText("Avg CSA [mm²]")
        self.ed_vt.setPlaceholderText("Docelowa prędkość v_target [m/s] (np. 100)")

        form.addWidget(QLabel("Min CSA [mm²] (opcjonalne)", self))
        form.addWidget(self.ed_min)
        form.addWidget(QLabel("Avg CSA [mm²] (opcjonalne)", self))
        form.addWidget(self.ed_avg)
        form.addWidget(QLabel("Docelowa prędkość w porcie v_target [m/s]", self))
        form.addWidget(self.ed_vt)

        left.addLayout(form)

        actions = QHBoxLayout()
        self.btn_compute = QPushButton("Przelicz", self)
        actions.addWidget(self.btn_compute)
        actions.addStretch(1)
        left.addLayout(actions)

        root.addLayout(left, 2)

        # Right panel: plots and numbers
        right = QVBoxLayout()
        right.addWidget(QLabel("Mach@minCSA vs lift_m", self))
        self.plot_mach = MplCanvas()
        right.addWidget(self.plot_mach)

        self.lbl_nums = QLabel("—", self)
        self.lbl_alert = QLabel("", self)
        self.lbl_alert.setStyleSheet("color: red; font-weight: bold;")
        right.addWidget(self.lbl_nums)
        right.addWidget(self.lbl_alert)

        root.addLayout(right, 3)

        # Wire
        self.btn_compute.clicked.connect(self._compute)
        for ed in (self.ed_min, self.ed_avg, self.ed_vt):
            ed.textChanged.connect(self._on_changed)  # type: ignore[arg-type]

        # Preload from state if present
        if self.state.csa_min_m2 is not None:
            self.ed_min.setText(f"{self.state.csa_min_m2 * 1e6:.1f}")
        if self.state.csa_avg_m2 is not None:
            self.ed_avg.setText(f"{self.state.csa_avg_m2 * 1e6:.1f}")
        if self.state.engine_v_target is not None:
            self.ed_vt.setText(f"{self.state.engine_v_target:.1f}")

        self._emit_valid()
        # If we have prefilled values, compute immediately to render charts
        try:
            if any(
                (
                    bool(self.ed_min.text().strip()),
                    bool(self.ed_avg.text().strip()),
                    bool(self.ed_vt.text().strip()),
                )
            ):
                self._compute()
        except Exception:
            pass

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        # Live-validate fields (basic)
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

        def mark(widget: QLineEdit, ok: bool, tip: str = "") -> None:
            widget.setToolTip("" if ok else (tip or "Błędna wartość"))
            widget.setStyleSheet("border: 1px solid red;" if not ok else "")

        ok_min = (v_min is None) or (v_min > 0)
        ok_avg = (v_avg is None) or (v_avg > 0)
        ok_rel = True
        if v_min is not None and v_avg is not None:
            ok_rel = v_min <= v_avg
        ok_vt = (v_vt is None) or (v_vt > 0)

        mark(self.ed_min, ok_min, "> 0 lub puste")
        mark(self.ed_avg, ok_avg, "> 0 lub puste")
        mark(self.ed_vt, ok_vt, "> 0 lub puste")
        if not ok_rel:
            self.ed_min.setToolTip("min_csa ≤ avg_csa")
            self.ed_min.setStyleSheet("border: 1px solid red;")
            self.ed_avg.setStyleSheet("border: 1px solid red;")

    def _emit_valid(self) -> None:
        # CSA optional: always allow Next
        self.sig_valid_changed.emit(True)

    def _compute(self) -> None:
        # Save CSA to state
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

        # Build session and compute
        try:
            session = self.state.build_session_for_run_all()
        except Exception:
            # Missing mandatory inputs from earlier steps
            return

        prefs = load_prefs()
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

        # Plot Mach@minCSA if available
        self.plot_mach.clear()
        mach = engine.get("mach_min_csa")
        if mach and intake:
            lifts = [row.get("lift_m") for row in intake]
            if lifts and len(lifts) == len(mach):
                self.plot_mach.plot_xy(lifts, mach, label="Mach@minCSA")
        self.plot_mach.render()

        # Numbers and alert
        rpm_flow = engine.get("rpm_flow_limit")
        rpm_csa = engine.get("rpm_from_csa")
        nums = []
        if rpm_flow:
            nums.append(f"RPM_flow_limit={rpm_flow:,.0f}")
        if rpm_csa:
            nums.append(f"RPM_from_CSA={rpm_csa:,.0f}")
        if not intake and self.state.csa_min_m2 is not None:
            nums.append("Brak serii Intake — nie można policzyć Mach@minCSA")
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
        # status OK with timing
        try:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            win = self.window()
            if hasattr(win, "statusBar"):
                sb = win.statusBar()
                if sb is not None:
                    sb.showMessage(f"OK ({dt_ms} ms)", 2000)
        except Exception:
            pass
