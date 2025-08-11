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
from .state import WizardState, parse_rows
from iop_flow import formulas as F
from iop_flow_gui.widgets.mpl_canvas import MplCanvas


class StepExhaust(QWidget):
    """Wizard step for exhaust measurements & tuning panel.

    All UI is created lazily in __init__ so import is side‑effect free.
    """

    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:  # noqa: PLR0915 (long but structured)
        super().__init__()
        self.state = state

        # Root layout with two columns
        root = QHBoxLayout(self)

        # ==== LEFT (exhaust measurement table + tuning inputs) ====
        left = QVBoxLayout()
        root.addLayout(left, 2)

        # Row of buttons for measurement table
        btns = QHBoxLayout()
        self.btn_autofill = QPushButton("Autouzupełnij lifty z planu EXH", self)
        self.btn_copy_from_int = QPushButton("Skopiuj INT → EXH (tylko lift)", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        for b in (self.btn_autofill, self.btn_copy_from_int, self.btn_clear):
            btns.addWidget(b)
        btns.addStretch(1)
        left.addLayout(btns)

        # Table for exhaust measurements
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
        from PySide6.QtWidgets import QAbstractItemView  # local import
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.table.viewport().installEventFilter(self)
        left.addWidget(self.table)

        counts = QHBoxLayout()
        self.lbl_counts = QLabel("—", self)
        counts.addWidget(self.lbl_counts)
        counts.addStretch(1)
        left.addLayout(counts)

        # ---- Tuning panel ----
        from PySide6.QtWidgets import QDoubleSpinBox, QComboBox, QToolButton
        tuning_box = QGroupBox("Tuning — Wydech", self)
        tuning_lay = QVBoxLayout(tuning_box)
        left.addWidget(tuning_box)

        # Load current dict (non-destructive merge behavior on updates)
        tdict = dict(self.state.tuning.get("exhaust_calc", {}))
        def _pref(key: str, default: float | int) -> float | int:
            try:
                v = tdict.get(key, default)
                return type(default)(v)  # type: ignore[call-arg]
            except Exception:
                return default

        # L_mm
        row_L = QHBoxLayout(); tuning_lay.addLayout(row_L)
        self.spn_L_mm = QDoubleSpinBox(self); self.spn_L_mm.setRange(100, 1200); self.spn_L_mm.setSingleStep(1); self.spn_L_mm.setDecimals(1)
        self.spn_L_mm.setToolTip("Długość runnera L (mm). Model ćwierćfali.")
        self.spn_L_mm.setValue(float(_pref("L_mm", 450.0)))
        row_L.addWidget(QLabel("L [mm]:", self)); row_L.addWidget(self.spn_L_mm)

        # D_mm
        row_D = QHBoxLayout(); tuning_lay.addLayout(row_D)
        self.spn_D_mm = QDoubleSpinBox(self); self.spn_D_mm.setRange(10, 80); self.spn_D_mm.setSingleStep(0.5); self.spn_D_mm.setDecimals(1)
        self.spn_D_mm.setToolTip("Średnica rury D (mm). Używana do korekcji długości.")
        self.spn_D_mm.setValue(float(_pref("D_mm", 38.0)))
        row_D.addWidget(QLabel("D [mm]:", self)); row_D.addWidget(self.spn_D_mm)

        # n_harm (1,2,3 -> odd 1,3,5 conceptually)
        row_n = QHBoxLayout(); tuning_lay.addLayout(row_n)
        self.cmb_n_harm = QComboBox(self)
        self.cmb_n_harm.addItems(["1", "2", "3"])
        self.cmb_n_harm.setToolTip("Nieparzyste harmoniczne 1/3/5. 1⇒1., 2⇒3., 3⇒5. (model ćwierćfali)")
        n_saved = int(_pref("n_harm", 2))
        self.cmb_n_harm.setCurrentIndex(max(0, min(2, n_saved - 1)))
        row_n.addWidget(QLabel("n_harm:", self)); row_n.addWidget(self.cmb_n_harm)

        # T_exh_K
        row_T = QHBoxLayout(); tuning_lay.addLayout(row_T)
        self.spn_T_exh_K = QDoubleSpinBox(self); self.spn_T_exh_K.setRange(400, 1200); self.spn_T_exh_K.setSingleStep(10); self.spn_T_exh_K.setDecimals(0)
        self.spn_T_exh_K.setToolTip("Szacowana temp. spalin w K. a(T) rośnie z T ⇒ krótsze L dla tej samej harmoniki.")
        self.spn_T_exh_K.setValue(float(_pref("T_exh_K", 700.0)))
        row_T.addWidget(QLabel("T_exh [K]:", self)); row_T.addWidget(self.spn_T_exh_K)

        # v_target_ms
        row_v = QHBoxLayout(); tuning_lay.addLayout(row_v)
        self.spn_v_target = QDoubleSpinBox(self); self.spn_v_target.setRange(20, 120); self.spn_v_target.setSingleStep(1); self.spn_v_target.setDecimals(0)
        self.spn_v_target.setToolTip("Docelowa średnia prędkość w kolektorze wydechu dla doboru CSA.")
        self.spn_v_target.setValue(float(_pref("v_target_ms", 70.0)))
        row_v.addWidget(QLabel("v_target [m/s]:", self)); row_v.addWidget(self.spn_v_target)

        # Output labels
        self.lbl_rpm_for_L = QLabel("rpm dla L: —", self)
        self.lbl_L_rec = QLabel("L_rec: — mm", self); self.lbl_L_rec.setToolTip("Długość runnera dla RPM target (ćwierćfala).")
        self.lbl_CSA = QLabel("CSA: — mm²", self); self.lbl_CSA.setToolTip("Wymagane CSA kolektora przy Q_exh_peak i v_target.")
        self.lbl_d_eq = QLabel("d_eq: — mm", self)
        for w in (self.lbl_rpm_for_L, self.lbl_L_rec, self.lbl_CSA, self.lbl_d_eq):
            tuning_lay.addWidget(w)

        # Status + corner notice
        self.lbl_tuning_status = QLabel("", self)
        self.lbl_corner_notice = QLabel("", self)
        self.lbl_corner_notice.setStyleSheet("color:#aa8800;font-style:italic;")
        tuning_lay.addWidget(self.lbl_tuning_status)
        tuning_lay.addWidget(self.lbl_corner_notice)

        # Primary length helper (simple)
        helper = QGroupBox("Długość primary (1D)", self)
        helper.setToolTip("Szacunek z modelu ćwierćfali czasu fazy spalin.")
        hl = QHBoxLayout(helper)
        self.ed_phi_exh = QLineEdit(self); self.ed_phi_exh.setPlaceholderText("phi [deg]"); self.ed_phi_exh.setText("90")
        self.ed_harm_exh = QLineEdit(self); self.ed_harm_exh.setPlaceholderText("harm"); self.ed_harm_exh.setText("1")
        self.ed_rpm_exh = QLineEdit(self); self.ed_rpm_exh.setPlaceholderText("RPM cel");
        if self.state.engine_target_rpm: self.ed_rpm_exh.setText(str(self.state.engine_target_rpm))
        self.lbl_len_exh = QLabel("L ≈ — mm; a(T)=— m/s", self)
        for lab, w in (("phi:", self.ed_phi_exh),("harm:", self.ed_harm_exh),("RPM:", self.ed_rpm_exh)):
            hl.addWidget(QLabel(lab, self)); hl.addWidget(w)
        hl.addWidget(self.lbl_len_exh); hl.addStretch(1)
        tuning_lay.addWidget(helper)

        # Buttons below tuning / table (compute etc.)
        actions = QHBoxLayout(); left.addLayout(actions)
        self.btn_compute = QPushButton("Przelicz", self)
        actions.addWidget(self.btn_compute); actions.addStretch(1)

        # ==== RIGHT (E/I plot & CSA quick calc) ====
        right = QVBoxLayout(); root.addLayout(right, 3)
        self.plot_ei = MplCanvas(); self.plot_ei.set_readout_units("mm", "-"); right.addWidget(self.plot_ei)
        self.lbl_ei = QLabel("—", self); self.lbl_alert = QLabel("", self); self.lbl_alert.setStyleSheet("color:red;font-weight:bold;")
        self.lbl_corner = QLabel("", self); self.lbl_corner.setStyleSheet("color:#666;font-style:italic;")
        for w in (self.lbl_ei, self.lbl_alert, self.lbl_corner): right.addWidget(w)

        # Collector CSA quick box (separate from tuning required CSA)
        csa_box = QGroupBox("Primary/Collector CSA", self); csa_l = QHBoxLayout(csa_box)
        self.ed_v_exh = QLineEdit(self); self.ed_v_exh.setPlaceholderText("v_target [m/s]"); self.ed_v_exh.setText("70")
        self.lbl_A_req = QLabel("A_req = — mm²", self); self.lbl_d_eq2 = QLabel("d_eq = — mm", self)
        csa_l.addWidget(QLabel("v_target:", self)); csa_l.addWidget(self.ed_v_exh); csa_l.addWidget(self.lbl_A_req); csa_l.addWidget(self.lbl_d_eq2); csa_l.addStretch(1)
        right.addWidget(csa_box)

        # --- Helper closures ---
        def save_field(key: str, value: float | int) -> None:
            d = dict(self.state.tuning.get("exhaust_calc", {}))
            d[key] = value
            self.state.tuning["exhaust_calc"] = d

        def compute_primary_length() -> None:
            try:
                from iop_flow.formulas import primary_length_exhaust_quarterwave
                phi = float((self.ed_phi_exh.text() or "90").replace(",", "."))
                harm = int(float((self.ed_harm_exh.text() or "1").replace(",", ".")))
                rpm = float((self.ed_rpm_exh.text() or str(self.state.engine_target_rpm or 6500)).replace(",", "."))
                T = float(self.state.air.T if self.state.air else 293.15)
                a_T = F.speed_of_sound(T)
                L_m = primary_length_exhaust_quarterwave(rpm, T, phi_deg=phi, harmonic=harm)
                self.lbl_len_exh.setText(f"L ≈ {L_m*1000:.0f} mm; a(T)={a_T:.0f} m/s")
            except Exception:
                self.lbl_len_exh.setText("L ≈ — mm; a(T)=— m/s")

        def estimate_q_peaks() -> tuple[float, str]:
            """Return (q_exh_peak_m3s, notice)."""
            # Try run_all if possible
            try:
                session = self.state.build_session_for_run_all()
                result = run_all(session, dp_ref_inH2O=self.state.air_dp_ref_inH2O or 28.0, engine_v_target=(self.state.engine_v_target or 100.0))
                ex = (result.get("series", {}).get("exhaust", []) or [])  # type: ignore[index]
                if ex:
                    return max(float(r.get("q_m3s_ref") or 0.0) for r in ex), ""
                # fallback via intake series
                intake = (result.get("series", {}).get("intake", []) or [])  # type: ignore[index]
                if intake:
                    q_int = max(float(r.get("q_m3s_ref") or 0.0) for r in intake)
                    return 0.78 * q_int, "Brak danych EXH – użyto szacunku 0.78×INT"
            except Exception:
                pass
            # Fallback: derive from raw measurement rows (CFM → m3/s)
            try:
                meas_exh = [float(r.get("q_cfm")) for r in self.state.measure_exhaust if r.get("q_cfm") is not None]
                if meas_exh:
                    q_exh = max(F.cfm_to_m3s(q) for q in meas_exh)  # type: ignore[attr-defined]
                    return q_exh, "Szacunek z tabeli EXH (bez korekcji)"
                meas_int = [float(r.get("q_cfm")) for r in self.state.measure_intake if r.get("q_cfm") is not None]
                if meas_int:
                    q_int = max(F.cfm_to_m3s(q) for q in meas_int)  # type: ignore[attr-defined]
                    return 0.78 * q_int, "Brak danych EXH – użyto 0.78×INT (tabela)"
            except Exception:
                pass
            return 0.0, "Brak danych INT/EXH — CSA pominięte"

        def recompute() -> None:
            from iop_flow.tuning import exhaust_quarter_wave_rpm_for_L, exhaust_quarter_wave_L_phys, collector_csa_from_q
            L_mm = float(self.spn_L_mm.value()); D_mm = float(self.spn_D_mm.value()); n_harm = int(self.cmb_n_harm.currentText()); T_exh = float(self.spn_T_exh_K.value()); v_target = float(self.spn_v_target.value())
            D_m = D_mm / 1000.0
            # RPM for given L
            try:
                rpm_for_L = exhaust_quarter_wave_rpm_for_L(L_mm, n_harm, D_m, T_exh)
            except Exception:
                rpm_for_L = None
            # Recommended L for target rpm
            L_rec_mm = None
            target_rpm = self.state.engine_target_rpm
            if target_rpm:
                try:
                    L_rec_mm = exhaust_quarter_wave_L_phys(float(target_rpm), n_harm, D_m, T_exh) * 1000.0
                except Exception:
                    L_rec_mm = None
            q_peak, notice = estimate_q_peaks()
            csa_mm2 = None; d_eq_mm = None
            if q_peak > 0 and v_target > 0:
                try:
                    csa_m2, csa_mm2_val = collector_csa_from_q(q_peak, v_target)
                    csa_mm2 = csa_mm2_val
                    d_eq_mm = (4.0 * csa_m2 / 3.141592653589793) ** 0.5 * 1000.0
                except Exception:
                    pass
            elif notice == "":
                notice = "Brak danych – pominięto CSA"
            self.lbl_rpm_for_L.setText(f"rpm dla L: {rpm_for_L:.0f}" if rpm_for_L else "rpm dla L: —")
            self.lbl_L_rec.setText(f"L_rec: {L_rec_mm:.0f} mm" if L_rec_mm else "L_rec: — mm")
            self.lbl_CSA.setText(f"CSA: {csa_mm2:.0f} mm²" if csa_mm2 else "CSA: — mm²")
            self.lbl_d_eq.setText(f"d_eq: {d_eq_mm:.1f} mm" if d_eq_mm else "d_eq: — mm")
            a_exh = None
            try: a_exh = F.speed_of_sound(T_exh)
            except Exception: pass
            q_cfm = F.m3s_to_cfm(q_peak) if q_peak > 0 else None
            self.lbl_tuning_status.setText(
                f"a_exh(T)={(a_exh or 0):.1f} m/s · Q_exh_peak={(q_cfm or 0):.1f} CFM · CSA={(csa_mm2 or 0):.0f} mm² · d_eq={(d_eq_mm or 0):.1f} mm"
                if a_exh and q_cfm is not None else "a_exh(T)=— m/s · Q_exh_peak=— CFM · CSA=— mm² · d_eq=— mm"
            )
            self.lbl_corner_notice.setText(notice)
            # Persist computed values (merge)
            d = dict(self.state.tuning.get("exhaust_calc", {}))
            d.update({"L_mm": L_mm, "D_mm": D_mm, "n_harm": n_harm, "T_exh_K": T_exh, "v_target_ms": v_target})
            if rpm_for_L: d["rpm_for_L"] = rpm_for_L
            if L_rec_mm: d["L_rec_mm"] = L_rec_mm
            if csa_mm2: d["CSA_req_mm2"] = csa_mm2
            if d_eq_mm: d["d_eq_mm"] = d_eq_mm
            if notice: d["notice"] = notice
            self.state.tuning["exhaust_calc"] = d

        # --- Wire signals ---
        def on_any_change():
            for key, widget in ("L_mm", self.spn_L_mm), ("D_mm", self.spn_D_mm), ("T_exh_K", self.spn_T_exh_K), ("v_target_ms", self.spn_v_target):
                try: save_field(key, float(widget.value()))
                except Exception: pass
            try: save_field("n_harm", int(self.cmb_n_harm.currentText()))
            except Exception: pass
            recompute(); compute_primary_length()

        self.spn_L_mm.valueChanged.connect(lambda *_: on_any_change())
        self.spn_D_mm.valueChanged.connect(lambda *_: on_any_change())
        self.cmb_n_harm.currentIndexChanged.connect(lambda *_: on_any_change())
        self.spn_T_exh_K.valueChanged.connect(lambda *_: on_any_change())
        self.spn_v_target.valueChanged.connect(lambda *_: on_any_change())
        self.ed_v_exh.textChanged.connect(lambda *_: self._update_csa_numbers())  # existing CSA quick calc
        for ed in (self.ed_phi_exh, self.ed_harm_exh, self.ed_rpm_exh): ed.textChanged.connect(lambda *_: compute_primary_length())
        self.btn_compute.clicked.connect(lambda *_: self._compute())
        self.btn_autofill.clicked.connect(self._autofill)
        self.btn_copy_from_int.clicked.connect(self._copy_intake_lifts)
        self.btn_clear.clicked.connect(self._clear)
        self.table.itemChanged.connect(self._on_changed)

        # Initial load of measurement table
        self._load_from_state(); self._update_counts(); self._emit_valid()
        # Initial recompute for tuning panel
        recompute(); compute_primary_length(); self._update_csa_numbers()

    # ----------------- Legacy methods kept (refactored) -----------------

    def _load_from_state(self) -> None:  # type: ignore[override]
        rows = self.state.measure_exhaust
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"]):
                val = row.get(key)
                self.table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.table.blockSignals(False)
        
    # (other methods unchanged below; cleaned duplicates)

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
            from iop_flow.tuning import (
                exhaust_quarter_wave_rpm_for_L,
                exhaust_quarter_wave_L_phys,
                collector_csa_from_q,
            )
            # Inputs
            L_mm = float(self.spn_L_mm.value())
            D_mm = float(self.spn_D_mm.value())
            n_harm = int(self.cmb_n_harm.currentText())
            T_exh_K = float(self.spn_T_exh_K.value())
            v_target = float(self.spn_v_target.value())
            D_m = D_mm / 1000.0
            rpm_target = float(getattr(self.state, "engine_target_rpm", 6500.0) or 6500.0)
            # Estimate Q_exh_peak
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
                    intake = (result or {}).get("series", {}).get("intake", [])
                    if intake:
                        Q_intake_peak = max(float(r.get("q_m3s_ref") or 0.0) for r in intake)
                        Q_exh_peak = 0.78 * Q_intake_peak
            except Exception:
                Q_hint = "Brak pomiarów – użyto szacunku"
            rpm_for_L = exhaust_quarter_wave_rpm_for_L(L_mm, n_harm, D_m, T_exh_K)
            L_rec = exhaust_quarter_wave_L_phys(rpm_target, n_harm, D_m, T_exh_K)
            csa_mm2 = 0.0
            d_eq = 0.0
            if Q_exh_peak > 0.0 and v_target > 0.0:
                csa_m2, csa_mm2 = collector_csa_from_q(Q_exh_peak, v_target)
                d_eq = (4.0 * csa_m2 / 3.141592653589793) ** 0.5 * 1000.0
            self.lbl_rpm_for_L.setText(f"rpm dla L: {rpm_for_L:.0f}")
            self.lbl_L_rec.setText(f"L zalecane: {L_rec*1000:.0f} mm")
            self.lbl_CSA.setText(f"CSA: {csa_mm2:.0f} mm²")
            self.lbl_d_eq.setText(f"d_eq: {d_eq:.1f} mm")
            a_exh = F.speed_of_sound(T_exh_K)
            Q_cfm = Q_exh_peak * F.M3S_TO_CFM if Q_exh_peak > 0 else 0.0
            self.lbl_tuning_status.setText(
                f"a_exh(T)={a_exh:.1f} m/s; Q_exh_peak={Q_cfm:.1f} CFM; CSA={csa_mm2:.0f} mm²; d_eq={d_eq:.1f} mm"
            )
            if Q_hint:
                self.lbl_corner.setText(Q_hint)
        except Exception as e:  # pragma: no cover - defensive
            self.lbl_rpm_for_L.setText("rpm dla L: —")
            self.lbl_L_rec.setText("L zalecane: — mm")
            self.lbl_CSA.setText("CSA: — mm²")
            self.lbl_d_eq.setText("d_eq: — mm")
            self.lbl_tuning_status.setText(f"Błąd: {e}")

    # (removed duplicate initial compute/state block)

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
                self.lbl_d_eq2.setText(f"d_eq = {d_eq:.1f} mm")
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
