"""Wizard step for Exhaust measurements and helpers.

This module must be import-safe: no top-level widget creation, QApplication,
or prints. All UI is constructed inside StepExhaust.__init__.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal, QEvent, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QGroupBox,
    QLineEdit,
)

from iop_flow.api import run_all
try:
    from .state import WizardState, parse_rows
    from ..widgets.mpl_canvas import MplCanvas
except ImportError:  # allow direct file import in tests
    from iop_flow_gui.wizard.state import WizardState, parse_rows  # type: ignore[no-redef]
    from iop_flow_gui.widgets.mpl_canvas import MplCanvas  # type: ignore[no-redef]
from iop_flow import formulas as F


class StepExhaust(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state


        # Root layout
        root = QHBoxLayout(self)

        # Left: controls, table, and tuning panel
        left = QVBoxLayout()
        btns = QHBoxLayout()
        self.btn_autofill = QPushButton("Autouzupełnij lifty z planu EXH", self)
        self.btn_copy_from_int = QPushButton("Skopiuj INT → EXH (tylko lift)", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        btns.addWidget(self.btn_autofill)
        btns.addWidget(self.btn_copy_from_int)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)
        left.addLayout(btns)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
        from PySide6.QtWidgets import QAbstractItemView  # local import
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.table.viewport().installEventFilter(self)
        left.addWidget(self.table)

        # --- Tuning — Wydech panel ---
        from PySide6.QtWidgets import QDoubleSpinBox, QComboBox
        tuning_box = QGroupBox("Tuning — Wydech", self)
        tuning_lay = QVBoxLayout(tuning_box)
        # Prefill from state or defaults
        tdict = dict(self.state.tuning.get("exhaust_calc", {}))
        def _get_tuning(key, default):
            try:
                return type(default)(tdict.get(key, default))
            except Exception:
                return default

        # L_mm
        row_L = QHBoxLayout()
        self.spn_L_mm = QDoubleSpinBox(self)
        self.spn_L_mm.setRange(100.0, 1200.0)
        self.spn_L_mm.setSingleStep(1.0)
        self.spn_L_mm.setDecimals(1)
        self.spn_L_mm.setToolTip("Długość runnera wydechu L w mm.\nModel ćwierćfali.")
        self.spn_L_mm.setValue(_get_tuning("L_mm", 450.0))
        row_L.addWidget(QLabel("L [mm]:", self))
        row_L.addWidget(self.spn_L_mm)
        tuning_lay.addLayout(row_L)

        # D_mm
        row_D = QHBoxLayout()
        self.spn_D_mm = QDoubleSpinBox(self)
        self.spn_D_mm.setRange(10.0, 80.0)
        self.spn_D_mm.setSingleStep(0.1)
        self.spn_D_mm.setDecimals(1)
        self.spn_D_mm.setToolTip("Średnica rury wydechowej D w mm.")
        self.spn_D_mm.setValue(_get_tuning("D_mm", 38.0))
        row_D.addWidget(QLabel("D [mm]:", self))
        row_D.addWidget(self.spn_D_mm)
        tuning_lay.addLayout(row_D)

        # n_harm
        row_n = QHBoxLayout()
        self.cmb_n_harm = QComboBox(self)
        self.cmb_n_harm.addItems(["1", "2", "3"])
        n_harm_val = int(_get_tuning("n_harm", 2))
        self.cmb_n_harm.setCurrentIndex(max(0, min(2, n_harm_val - 1)))
        self.cmb_n_harm.setToolTip("Harmoniczna ćwierćfali (1/3/5…).\nWybierz n=1,2,3.")
        row_n.addWidget(QLabel("n_harm:", self))
        row_n.addWidget(self.cmb_n_harm)
        tuning_lay.addLayout(row_n)

        # T_exh_K
        row_T = QHBoxLayout()
        self.spn_T_exh_K = QDoubleSpinBox(self)
        self.spn_T_exh_K.setRange(400.0, 1200.0)
        self.spn_T_exh_K.setSingleStep(10.0)
        self.spn_T_exh_K.setDecimals(1)
        self.spn_T_exh_K.setToolTip("Temperatura spalin T [K].\na(T) rośnie z temperaturą.")
        self.spn_T_exh_K.setValue(_get_tuning("T_exh_K", 700.0))
        row_T.addWidget(QLabel("T_exh [K]:", self))
        row_T.addWidget(self.spn_T_exh_K)
        tuning_lay.addLayout(row_T)

        # v_target_ms
        row_v = QHBoxLayout()
        self.spn_v_target = QDoubleSpinBox(self)
        self.spn_v_target.setRange(20.0, 120.0)
        self.spn_v_target.setSingleStep(1.0)
        self.spn_v_target.setDecimals(1)
        self.spn_v_target.setToolTip("Docelowa prędkość gazów w kolektorze [m/s].")
        self.spn_v_target.setValue(_get_tuning("v_target_ms", 70.0))
        row_v.addWidget(QLabel("v_target [m/s]:", self))
        row_v.addWidget(self.spn_v_target)
        tuning_lay.addLayout(row_v)

        # Outputs (read-only)
        self.lbl_rpm_for_L = QLabel("rpm dla L: —", self)
        self.lbl_L_rec = QLabel("L zalecane: — mm", self)
        self.lbl_CSA = QLabel("CSA: — mm²", self)
        self.lbl_d_eq = QLabel("d_eq: — mm", self)
        tuning_lay.addWidget(self.lbl_rpm_for_L)
        tuning_lay.addWidget(self.lbl_L_rec)
        tuning_lay.addWidget(self.lbl_CSA)
        tuning_lay.addWidget(self.lbl_d_eq)

        # Status line
        self.lbl_tuning_status = QLabel("", self)
        tuning_lay.addWidget(self.lbl_tuning_status)

        left.addWidget(tuning_box)


    actions = QHBoxLayout()
    self.btn_compute = QPushButton("Przelicz", self)
    self.btn_back = QPushButton("Wstecz", self)
    self.btn_next = QPushButton("Dalej", self)
    actions.addWidget(self.btn_compute)
    actions.addStretch(1)
    actions.addWidget(self.btn_back)
    actions.addWidget(self.btn_next)
    left.addLayout(actions)

    # Wire up tuning field changes
    self.spn_L_mm.valueChanged.connect(self._on_tuning_changed)
    self.spn_D_mm.valueChanged.connect(self._on_tuning_changed)
    self.cmb_n_harm.currentIndexChanged.connect(self._on_tuning_changed)
    self.spn_T_exh_K.valueChanged.connect(self._on_tuning_changed)
    self.spn_v_target.valueChanged.connect(self._on_tuning_changed)

    # Initial compute
    self._sync_tuning_from_state()
    self._recompute_tuning_exhaust()
    def _sync_tuning_from_state(self) -> None:
        """Load exhaust tuning values from state into widgets (no signal cascade)."""
        try:
            d = self.state.tuning.get("exhaust_calc", {})
            if isinstance(d, dict):
                # L_mm
                L = d.get("L_mm")
                if L is not None:
                    self.spn_L_mm.blockSignals(True)
                    self.spn_L_mm.setValue(float(L))
                    self.spn_L_mm.blockSignals(False)
                # D_mm
                D = d.get("D_mm")
                if D is not None:
                    self.spn_D_mm.blockSignals(True)
                    self.spn_D_mm.setValue(float(D))
                    self.spn_D_mm.blockSignals(False)
                # n_harm
                n = d.get("n_harm")
                if n is not None:
                    idx = max(0, min(2, int(n) - 1))
                    self.cmb_n_harm.blockSignals(True)
                    self.cmb_n_harm.setCurrentIndex(idx)
                    self.cmb_n_harm.blockSignals(False)
                # T_exh_K
                T = d.get("T_exh_K")
                if T is not None:
                    self.spn_T_exh_K.blockSignals(True)
                    self.spn_T_exh_K.setValue(float(T))
                    self.spn_T_exh_K.blockSignals(False)
                # v_target_ms
                v = d.get("v_target_ms")
                if v is not None:
                    self.spn_v_target.blockSignals(True)
                    self.spn_v_target.setValue(float(v))
                    self.spn_v_target.blockSignals(False)
        except Exception:
            pass

    def _on_tuning_changed(self) -> None:
        try:
            curr = dict(self.state.tuning.get("exhaust_calc", {}))
            curr["L_mm"] = float(self.spn_L_mm.value())
            curr["D_mm"] = float(self.spn_D_mm.value())
            curr["n_harm"] = int(self.cmb_n_harm.currentText())
            curr["T_exh_K"] = float(self.spn_T_exh_K.value())
            curr["v_target_ms"] = float(self.spn_v_target.value())
            self.state.tuning["exhaust_calc"] = curr
            self._recompute_tuning_exhaust()
        except Exception:
            pass

    def _recompute_tuning_exhaust(self) -> None:
        """Recompute exhaust tuning outputs and status line."""
        try:
            from iop_flow.tuning import exhaust_quarter_wave_rpm_for_L, exhaust_quarter_wave_L_phys, collector_csa_from_q
            from iop_flow import formulas as F
            # Inputs
            L_mm = float(self.spn_L_mm.value())
            D_mm = float(self.spn_D_mm.value())
            n_harm = int(self.cmb_n_harm.currentText())
            T_exh_K = float(self.spn_T_exh_K.value())
            v_target = float(self.spn_v_target.value())
            # SI
            L_m = L_mm / 1000.0
            D_m = D_mm / 1000.0
            # Target RPM
            rpm_target = float(getattr(self.state, "engine_target_rpm", 6500.0) or 6500.0)
            # Q_exh_peak (m3/s): from results if available, else 0.78*Q_intake_peak
            Q_exh_peak = 0.0
            Q_hint = ""
            try:
                session = self.state.build_session_for_run_all()
                result = run_all(
                    session,
                    dp_ref_inH2O=self.state.air_dp_ref_inH2O or 28.0,
                    a_ref_mode="eff",
                    eff_mode="smoothmin",
                    engine_v_target=(self.state.engine_target_rpm or 100.0),
                )
                ex = (result or {}).get("series", {}).get("exhaust", [])
                if ex:
                    Q_exh_peak = max(float(r.get("q_m3s_ref") or 0.0) for r in ex)
                else:
                    Q_hint = "Brak pomiarów – użyto szacunku"
                    # Try intake
                    intake = (result or {}).get("series", {}).get("intake", [])
                    if intake:
                        Q_intake_peak = max(float(r.get("q_m3s_ref") or 0.0) for r in intake)
                        Q_exh_peak = 0.78 * Q_intake_peak
            except Exception:
                Q_hint = "Brak pomiarów – użyto szacunku"
            # Outputs
            rpm_for_L = exhaust_quarter_wave_rpm_for_L(L_mm, n_harm, D_m, T_exh_K)
            L_rec = exhaust_quarter_wave_L_phys(rpm_target, n_harm, D_m, T_exh_K)
            csa_m2, csa_mm2 = (0.0, 0.0)
            d_eq = 0.0
            if Q_exh_peak > 0.0 and v_target > 0.0:
                csa_m2, csa_mm2 = collector_csa_from_q(Q_exh_peak, v_target)
                d_eq = (4.0 * csa_m2 / 3.141592653589793) ** 0.5 * 1000.0
            # Set outputs
            self.lbl_rpm_for_L.setText(f"rpm dla L: {rpm_for_L:.0f}")
            self.lbl_L_rec.setText(f"L zalecane: {L_rec*1000:.0f} mm")
            self.lbl_CSA.setText(f"CSA: {csa_mm2:.0f} mm²")
            self.lbl_d_eq.setText(f"d_eq: {d_eq:.1f} mm")
            # Status line
            a_exh = F.speed_of_sound(T_exh_K)
            Q_cfm = Q_exh_peak * F.M3S_TO_CFM if Q_exh_peak > 0 else 0.0
            self.lbl_tuning_status.setText(f"a_exh(T)={a_exh:.1f} m/s; Q_exh_peak={Q_cfm:.1f} CFM; CSA={csa_mm2:.0f} mm²; d_eq={d_eq:.1f} mm")
            # Hint if no data
            if Q_hint:
                self.lbl_corner.setText(Q_hint)
            else:
                self.lbl_corner.setText("")
        except Exception as e:
            self.lbl_rpm_for_L.setText("rpm dla L: —")
            self.lbl_L_rec.setText("L zalecane: — mm")
            self.lbl_CSA.setText("CSA: — mm²")
            self.lbl_d_eq.setText("d_eq: — mm")
            self.lbl_tuning_status.setText(f"Błąd: {e}")

        root.addLayout(left, 2)

        # Right: E/I results and CSA
        right = QVBoxLayout()
        # Info row with corner notice
        info_row = QHBoxLayout()
        info_row.addStretch(1)
        from PySide6.QtWidgets import QToolButton

        self.btn_info = QToolButton(self)
        self.btn_info.setText("i")
        self.btn_info.setToolTip("Informacje o wskaźniku E/I")
        self.btn_info.clicked.connect(self._show_info)
        info_row.addWidget(self.btn_info)
        right.addLayout(info_row)

        self.plot_ei = MplCanvas()
        self.plot_ei.set_readout_units("mm", "-")
        right.addWidget(self.plot_ei)
        self.lbl_ei = QLabel("—", self)
        self.lbl_alert = QLabel("", self)
        self.lbl_alert.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_corner = QLabel("", self)
        self.lbl_corner.setStyleSheet("color: #666; font-style: italic;")
        self.lbl_corner.setAlignment(Qt.AlignRight)
        right.addWidget(self.lbl_ei)
        right.addWidget(self.lbl_alert)
        right.addWidget(self.lbl_corner)

        # CSA selection group
        csa_box = QGroupBox("Primary/Collector CSA", self)
        csa_box.setToolTip("A_req = Q_exh_peak / v_target; Q_exh_peak z EXH (max z Q* @ ref)")
        csa_layout = QVBoxLayout(csa_box)
        row = QHBoxLayout()
        self.ed_v_exh = QLineEdit(self)
        self.ed_v_exh.setPlaceholderText("v_exh_target [m/s] (np. 70)")
        self.ed_v_exh.setText("70")
        row.addWidget(QLabel("v_target:", self))
        row.addWidget(self.ed_v_exh)
        row.addStretch(1)
        csa_layout.addLayout(row)
        row2 = QHBoxLayout()
        self.lbl_A_req = QLabel("A_req = — mm²", self)
        self.lbl_d_eq = QLabel("d_eq = — mm", self)
        row2.addWidget(self.lbl_A_req)
        row2.addWidget(self.lbl_d_eq)
        row2.addStretch(1)
        csa_layout.addLayout(row2)
        right.addWidget(csa_box)

        # Primary length (1D, quarter-wave) helper
        length_box = QGroupBox("Długość primary (1D)", self)
        length_box.setToolTip(
            "Szacowanie L z modelu 1D (ćwierć-fala): 2L ≈ a(T) · Δt / harmonic.\n"
            "Mierz do pierwszej istotnej zmiany przekroju (stożek/zbieracz)."
        )
        length_layout = QVBoxLayout(length_box)
        row_len = QHBoxLayout()
        self.ed_phi_exh = QLineEdit(self)
        self.ed_phi_exh.setPlaceholderText("phi [deg] (np. 90)")
        self.ed_phi_exh.setText("90")
        self.ed_harm_exh = QLineEdit(self)
        self.ed_harm_exh.setPlaceholderText("harmonic (1..)")
        self.ed_harm_exh.setText("1")
        self.ed_rpm_exh = QLineEdit(self)
        self.ed_rpm_exh.setPlaceholderText("RPM (np. cel)")
        if state.engine_target_rpm:
            self.ed_rpm_exh.setText(str(state.engine_target_rpm))
        row_len.addWidget(QLabel("phi:", self))
        row_len.addWidget(self.ed_phi_exh)
        row_len.addWidget(QLabel("harm:", self))
        row_len.addWidget(self.ed_harm_exh)
        row_len.addWidget(QLabel("RPM:", self))
        row_len.addWidget(self.ed_rpm_exh)
        row_len.addStretch(1)
        length_layout.addLayout(row_len)
        row_len2 = QHBoxLayout()
        self.lbl_len_exh = QLabel("L ≈ — mm; a(T)=— m/s", self)
        row_len2.addWidget(self.lbl_len_exh)
        row_len2.addStretch(1)
        length_layout.addLayout(row_len2)
        right.addWidget(length_box)

        root.addLayout(right, 3)

        # Wire
        self.btn_autofill.clicked.connect(self._autofill)
        self.btn_copy_from_int.clicked.connect(self._copy_intake_lifts)
        self.btn_clear.clicked.connect(self._clear)
        self.table.itemChanged.connect(self._on_changed)
        self.btn_compute.clicked.connect(self._compute)
        self.ed_v_exh.textChanged.connect(lambda *_: self._update_csa_numbers())
        for ed in (self.ed_phi_exh, self.ed_harm_exh, self.ed_rpm_exh):
            ed.textChanged.connect(lambda *_: self._update_primary_length())

        # Init
        self._load_from_state()
        self._update_counts()
        self._emit_valid()
        self._update_primary_length()

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.table.viewport() and event.type() == QEvent.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            if ke.matches(QKeySequence.Paste):
                self._paste_from_clipboard()
                return True
        return super().eventFilter(obj, event)

    def _load_from_state(self) -> None:
        rows = self.state.measure_exhaust
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"]):
                val = row.get(key)
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table.blockSignals(False)

    def _save_to_state(self) -> None:
        def parse_item(it: Optional[QTableWidgetItem]) -> Optional[float]:
            if it is None:
                return None
            s = (it.text() or "").strip()
            if s == "":
                return None
            try:
                from .state import parse_float_pl

                return parse_float_pl(s)
            except Exception:
                return None

        rows: List[Dict[str, Any]] = []
        seen: Dict[float, int] = {}
        for r in range(self.table.rowCount()):
            lift = parse_item(self.table.item(r, 0))
            q = parse_item(self.table.item(r, 1))
            dp = parse_item(self.table.item(r, 2))
            swirl = parse_item(self.table.item(r, 3))
            if lift is None or q is None:
                continue
            lift = round(max(lift, 0.0), 3)
            row: Dict[str, Any] = {"lift_mm": lift, "q_cfm": max(q, 0.0)}
            if dp is not None and dp > 0:
                row["dp_inH2O"] = dp
            if swirl is not None and swirl >= 0:
                row["swirl_rpm"] = swirl
            if lift in seen:
                rows[seen[lift]] = row
            else:
                seen[lift] = len(rows)
                rows.append(row)
        rows.sort(key=lambda x: x["lift_mm"])  # sort increasing
        self.state.measure_exhaust = rows

    def _update_counts(self) -> None:
        rows = self.state.measure_exhaust
        n = len(rows)
        m = sum(1 for r in rows if r.get("dp_inH2O") is not None)
        k = sum(1 for r in rows if r.get("swirl_rpm") is not None)
        self.lbl_counts.setText(f"n: {n}, z dp: {m}, ze swirl: {k}")

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self._save_to_state()
        self._update_counts()
        self._emit_valid()

    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard().text()
        rows = parse_rows(clipboard or "")
        if not rows:
            return
        start = self.table.rowCount()
        self.table.setRowCount(start + len(rows))
        for i, (lift, q, dp, swirl) in enumerate(rows):
            r = start + i
            vals = [lift, q, dp if dp is not None else "", swirl if swirl is not None else ""]
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(v)))
        self._on_changed()

    def _autofill(self) -> None:
        plan = list(self.state.plan_exhaust())
        if not plan:
            QMessageBox.information(self, "Plan EXH", "Brak planu dla EXH.")
            return
        rows_map: Dict[float, Dict[str, Any]] = {
            (row.get("lift_mm") or 0.0): dict(row) for row in self.state.measure_exhaust
        }
        for lift in plan:
            if lift not in rows_map:
                rows_map[lift] = {"lift_mm": lift}
        self.state.measure_exhaust = [rows_map[k] for k in sorted(rows_map.keys())]
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _copy_intake_lifts(self) -> None:
        rows_int = self.state.measure_intake
        lifts = sorted({round(float(r.get("lift_mm", 0.0)), 3) for r in rows_int})
        mapped = [{"lift_mm": lift_val} for lift_val in lifts]
        self.state.measure_exhaust = mapped
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _clear(self) -> None:
        self.state.measure_exhaust = []
        self._load_from_state()
        self._update_counts()
        self._emit_valid()

    def _emit_valid(self) -> None:
        # Allow Next even if exhaust empty (user can skip)
        self.sig_valid_changed.emit(True)

    def _compute(self) -> None:
        try:
            session = self.state.build_session_for_run_all()
        except Exception:
            return
        result = run_all(
            session,
            dp_ref_inH2O=self.state.air_dp_ref_inH2O or 28.0,
            a_ref_mode="eff",
            eff_mode="smoothmin",
            engine_v_target=(self.state.engine_v_target or 100.0),
        )
        series = result.get("series", {})
        intake: List[Dict[str, Any]] = series.get("intake", [])  # type: ignore[assignment]
        exhaust: List[Dict[str, Any]] = series.get("exhaust", [])  # type: ignore[assignment]
        ei = series.get("ei", [])

        # Plot E/I vs lift for matched lifts only
        self.plot_ei.clear()
        if ei:
            lifts_m = [float(row.get("lift_m") or 0.0) for row in ei]
            lifts_mm = [v * 1000.0 for v in lifts_m]
            vals = [row.get("EI") for row in ei]
            valid_vals = [float(v) for v in vals if v is not None]
            title_extra = f" · mean={sum(valid_vals)/len(valid_vals):.3f}" if valid_vals else ""
            if lifts_mm and any(v is not None for v in vals):
                self.plot_ei.plot_xy(
                    lifts_mm,
                    [float(v) if v is not None else 0.0 for v in vals],
                    label="E/I",
                    xlabel="Lift [mm]",
                    ylabel="E/I [–]",
                    title=f"E/I vs Lift{title_extra}",
                )
        self.plot_ei.render()

        # Summary and alerts
        txt = ""
        if intake and exhaust:
            txt = f"INT={len(intake)} EXH={len(exhaust)} dopasowane={len(ei)}"
            if ei:
                valid = [x.get("EI") for x in ei if x.get("EI") is not None]
                if valid:
                    avg = sum(valid) / len(valid)
                    txt += f"; mean(E/I)={avg:.3f}"
                    if avg < 0.70 or avg > 0.85:
                        self.lbl_alert.setText("ALERT: E/I poza zakresem 0.70–0.85")
                    else:
                        self.lbl_alert.setText("")
                else:
                    self.lbl_alert.setText("")
            self.lbl_corner.setText("")
        else:
            txt = "Brak danych exhaust — E/I będzie puste"
            self.lbl_alert.setText("")
            self.lbl_corner.setText("Brak danych wydechu — wykres niedostępny (INFO)")

        # Show summary text
        self.lbl_ei.setText(txt)
        # Update CSA numbers when we have fresh series
        self._update_csa_numbers(result)
        # Update primary length readout (depends on T and RPM input)
        self._update_primary_length()

    def _show_info(self) -> None:
        QMessageBox.information(
            self,
            "E/I — co to jest?",
            (
                "E/I to stosunek przepływu wydechu do ssania dla tych samych liftów.\n"
                "Wykres pokazuje E/I w funkcji liftu [mm].\n\n"
                "Uwaga: jeśli brak danych EXH, wykres jest niedostępny."
            ),
        )

    def _update_csa_numbers(self, result: Optional[Dict[str, Any]] = None) -> None:
        try:
            v_txt = (self.ed_v_exh.text() or "70").replace(",", ".")
            v_target = float(v_txt)
            if v_target <= 0:
                raise ValueError
        except Exception:
            self.lbl_A_req.setText("A_req = — mm²")
            self.lbl_d_eq.setText("d_eq = — mm")
            return
        if result is None:
            try:
                session = self.state.build_session_for_run_all()
                result = run_all(
                    session,
                    dp_ref_inH2O=self.state.air_dp_ref_inH2O or 28.0,
                    a_ref_mode="eff",
                    eff_mode="smoothmin",
                    engine_v_target=(self.state.engine_v_target or 100.0),
                )
            except Exception:
                result = None
        q_peak = 0.0
        try:
            ex = (result or {}).get("series", {}).get("exhaust", [])  # type: ignore[union-attr]
            if ex:
                q_peak = max(float(r.get("q_m3s_ref") or 0.0) for r in ex)
        except Exception:
            q_peak = 0.0
        if q_peak > 0.0:
            try:
                A_req = F.header_csa_required(q_peak, v_target)
                A_mm2 = A_req * 1e6
                d_eq = (4.0 * A_req / 3.141592653589793) ** 0.5 * 1000.0
                self.lbl_A_req.setText(f"A_req = {A_mm2:.0f} mm²")
                self.lbl_d_eq.setText(f"d_eq = {d_eq:.1f} mm")
            except Exception:
                self.lbl_A_req.setText("A_req = — mm²")
                self.lbl_d_eq.setText("d_eq = — mm")
        else:
            self.lbl_A_req.setText("A_req = — mm²")
            self.lbl_d_eq.setText("d_eq = — mm")

    def _update_primary_length(self) -> None:
        # Compute simple primary length estimate from RPM/phi/harm and air T
        try:
            phi = float((self.ed_phi_exh.text() or "90").replace(",", "."))
            harm = int(float((self.ed_harm_exh.text() or "1").replace(",", ".")))
            rpm = float((self.ed_rpm_exh.text() or "6500").replace(",", "."))
            T = float(self.state.air.T if self.state.air is not None else 293.15)
            a_T = F.speed_of_sound(T)
            L_m = F.primary_length_exhaust_quarterwave(rpm, T, phi_deg=phi, harmonic=harm)
            self.lbl_len_exh.setText(f"L ≈ {L_m*1000.0:.0f} mm; a(T)={a_T:.0f} m/s")
        except Exception:
            self.lbl_len_exh.setText("L ≈ — mm; a(T)=— m/s")


__all__ = ["StepExhaust"]

if __name__ == "__main__":
    # No GUI startup here. Manual testing can be added by the developer,
    # but importing this module must remain side-effect free.
    pass
