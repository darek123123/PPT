from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QAbstractItemView,
)

from iop_flow.api import run_all
from iop_flow.schemas import Session

from .state import WizardState, parse_rows
from ..widgets.mpl_canvas import MplCanvas
from ..preferences import load_prefs


class _SideTable(QWidget):
    sig_changed = Signal()

    def __init__(self, state: WizardState, side: str) -> None:
        super().__init__()
        self.state = state
        self.side = side  # 'intake' | 'exhaust'

        lay = QVBoxLayout(self)
        btns = QHBoxLayout()
        lay.addLayout(btns)
        self.btn_autofill = QPushButton("Autouzupełnij lifty z planu", self)
        self.btn_copy_other = QPushButton("Skopiuj z drugiej zakładki", self)
        self.btn_clear = QPushButton("Wyczyść", self)
        btns.addWidget(self.btn_autofill)
        btns.addWidget(self.btn_copy_other)
        btns.addWidget(self.btn_clear)
        btns.addStretch(1)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        # Human-friendly headers and tooltips
        headers = [
            ("Lift [mm]", "Skok zaworu; wartości z planu"),
            ("Q [CFM] @ ΔP_meas", "Przepływ zmierzony; w CFM"),
            ("ΔP [\"H₂O]", "Depresja pomiarowa"),
            ("Swirl [RPM]", "Swirl obrotowy, jeśli mierzony"),
        ]
        from PySide6.QtWidgets import QTableWidgetItem as _QItem

        self.table.setHorizontalHeaderLabels([h for h, _ in headers])
        for c, (h, tip) in enumerate(headers):
            it = _QItem(h)
            it.setToolTip(tip)
            self.table.setHorizontalHeaderItem(c, it)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ContiguousSelection)
        lay.addWidget(self.table)

        counts = QHBoxLayout()
        self.lbl_counts = QLabel("—", self)
        counts.addWidget(self.lbl_counts)
        counts.addStretch(1)
        lay.addLayout(counts)

        self.btn_autofill.clicked.connect(self._autofill)
        self.btn_copy_other.clicked.connect(self._copy_other)
        self.btn_clear.clicked.connect(self._clear)
        self.table.itemChanged.connect(self._on_changed)
        self.table.viewport().installEventFilter(self)

        self._load_from_state()
        self._update_counts()

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.table.viewport() and event.type() == QEvent.KeyPress:
            ke: QKeyEvent = event  # type: ignore[assignment]
            if ke.matches(QKeySequence.Paste):
                self._paste_from_clipboard()
                return True
        return super().eventFilter(obj, event)

    def _load_from_state(self) -> None:
        rows = self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
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
                # reuse parse_rows logic: comma and dot accepted
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
            # keep last by lift
            if lift in seen:
                rows[seen[lift]] = row
            else:
                seen[lift] = len(rows)
                rows.append(row)
        rows.sort(key=lambda x: x["lift_mm"])  # sort increasing
        if self.side == "intake":
            self.state.measure_intake = rows
        else:
            self.state.measure_exhaust = rows

    def _apply_cell_validation(self) -> None:
        # Apply tooltip and background color on invalid cells
        def mark(item: Optional[QTableWidgetItem], good: bool, tip: str = "") -> None:
            if not item:
                return
            item.setToolTip("" if good else (tip or "Błędna wartość"))
            item.setBackground(Qt.white if good else Qt.red)  # type: ignore[arg-type]

        for r in range(self.table.rowCount()):
            it_l = self.table.item(r, 0)
            it_q = self.table.item(r, 1)
            it_dp = self.table.item(r, 2)
            it_sw = self.table.item(r, 3)

            def parse_opt(it: Optional[QTableWidgetItem]) -> Optional[float]:
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

            l_v = parse_opt(it_l)
            q_v = parse_opt(it_q)
            dp_v = parse_opt(it_dp)
            sw_v = parse_opt(it_sw)
            mark(it_l, l_v is not None and l_v >= 0, ">= 0")
            mark(it_q, q_v is not None and q_v >= 0, ">= 0")
            mark(it_dp, dp_v is None or dp_v > 0, "> 0 lub puste")
            mark(it_sw, sw_v is None or sw_v >= 0, ">= 0 lub puste")

    def _update_counts(self) -> None:
        rows = self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
        n = len(rows)
        m = sum(1 for r in rows if r.get("dp_inH2O") is not None)
        k = sum(1 for r in rows if r.get("swirl_rpm") is not None)
        self.lbl_counts.setText(f"n: {n}, z dp: {m}, ze swirl: {k}")

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self._save_to_state()
        self._apply_cell_validation()
        self._update_counts()
        self.sig_changed.emit()

    def _paste_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard().text()
        text = clipboard or ""
        rows = parse_rows(text)
        # Estimate bad rows: count non-empty logical lines with >=2 fields, then subtract parsed
        bad = 0
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = [
                p.strip()
                for p in (line.split(";") if ";" in line else line.replace("\t", " ").split())
                if p
            ]
            if len(parts) >= 2:
                # candidate line; if parse_rows didn't include it, count as bad
                # crude heuristic: will be overcounted if duplicates trimmed; acceptable for toast
                bad += 1
        bad = max(0, bad - len(rows))
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
        # Show non-blocking toast in status bar if some lines were skipped
        if bad > 0:
            try:
                win = self.window()
                if hasattr(win, "statusBar"):
                    sb = win.statusBar()
                    if sb is not None:
                        sb.showMessage(f"Pominięto {bad} błędnych wierszy", 2500)
            except Exception:
                pass

    def _autofill(self) -> None:
        plan = self.state.plan_intake() if self.side == "intake" else self.state.plan_exhaust()
        if not plan:
            QMessageBox.information(self, "Plan", "Brak planu dla tej strony.")
            return
        rows_map: Dict[float, Dict[str, Any]] = {
            (row.get("lift_mm") or 0.0): dict(row)
            for row in (
                self.state.measure_intake if self.side == "intake" else self.state.measure_exhaust
            )
        }
        for lift in plan:
            if lift not in rows_map:
                rows_map[lift] = {"lift_mm": lift}
        merged = [rows_map[k] for k in sorted(rows_map.keys())]
        if self.side == "intake":
            self.state.measure_intake = merged
        else:
            self.state.measure_exhaust = merged
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()

    def _copy_other(self) -> None:
        other = self.state.measure_exhaust if self.side == "intake" else self.state.measure_intake
        copied = [dict(r) for r in other]
        if self.side == "intake":
            self.state.measure_intake = copied
        else:
            self.state.measure_exhaust = copied
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()

    def _clear(self) -> None:
        if self.side == "intake":
            self.state.measure_intake = []
        else:
            self.state.measure_exhaust = []
        self._load_from_state()
        self._update_counts()
        self.sig_changed.emit()



class StepMeasurements(QWidget):
    sig_valid_changed = Signal(bool)

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self._debounce = QTimer(self)
        self._debounce.setInterval(150)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._recompute)

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        self.tabs = QTabWidget(self)
        self.tab_intake = _SideTable(state, "intake")
        self.tab_exhaust = _SideTable(state, "exhaust")
        self.tab_intake.sig_changed.connect(self._on_changed)
        self.tab_exhaust.sig_changed.connect(self._on_changed)
        self.tabs.addTab(self.tab_intake, "INTAKE")
        self.tabs.addTab(self.tab_exhaust, "EXHAUST")

        # Iterator tab (L sweep → RPM)
        from PySide6.QtWidgets import QGroupBox, QDoubleSpinBox, QComboBox

        self.tab_iterator = QWidget(self)
        iter_lay = QVBoxLayout(self.tab_iterator)
        box = QGroupBox("Iterator L→RPM", self.tab_iterator)
        box_lay = QVBoxLayout(box)
        # Row inputs
        row1_iter = QHBoxLayout()
        box_lay.addLayout(row1_iter)
        self.spn_L_min = QDoubleSpinBox(self)
        self.spn_L_min.setRange(50, 1200)
        self.spn_L_min.setValue(250)
        self.spn_L_max = QDoubleSpinBox(self)
        self.spn_L_max.setRange(50, 1200)
        self.spn_L_max.setValue(600)
        self.spn_L_step = QDoubleSpinBox(self)
        self.spn_L_step.setRange(1, 200)
        self.spn_L_step.setValue(10)
        for w in (self.spn_L_min, self.spn_L_max, self.spn_L_step):
            w.setDecimals(0)
        row1_iter.addWidget(QLabel("L_min", self))
        row1_iter.addWidget(self.spn_L_min)
        row1_iter.addWidget(QLabel("L_max", self))
        row1_iter.addWidget(self.spn_L_max)
        row1_iter.addWidget(QLabel("step", self))
        row1_iter.addWidget(self.spn_L_step)
        row1_iter.addStretch(1)
        # Row 2: n_harm, D_mm, T_int, T_exh
        row2_iter = QHBoxLayout()
        box_lay.addLayout(row2_iter)
        self.cmb_iter_n = QComboBox(self)
        self.cmb_iter_n.addItems(["1", "2", "3"])
        self.cmb_iter_n.setCurrentIndex(1)
        self.spn_iter_D = QDoubleSpinBox(self)
        self.spn_iter_D.setRange(10, 120)
        self.spn_iter_D.setValue(50)
        self.spn_iter_D.setDecimals(1)
        self.spn_iter_D.setSingleStep(0.5)
        self.spn_iter_T_int = QDoubleSpinBox(self)
        self.spn_iter_T_int.setRange(250, 500)
        self.spn_iter_T_int.setValue(293)
        self.spn_iter_T_int.setDecimals(0)
        self.spn_iter_T_exh = QDoubleSpinBox(self)
        self.spn_iter_T_exh.setRange(400, 1200)
        self.spn_iter_T_exh.setValue(700)
        self.spn_iter_T_exh.setDecimals(0)
        row2_iter.addWidget(QLabel("n_harm", self))
        row2_iter.addWidget(self.cmb_iter_n)
        row2_iter.addWidget(QLabel("D_mm", self))
        row2_iter.addWidget(self.spn_iter_D)
        row2_iter.addWidget(QLabel("T_int[K]", self))
        row2_iter.addWidget(self.spn_iter_T_int)
        row2_iter.addWidget(QLabel("T_exh[K]", self))
        row2_iter.addWidget(self.spn_iter_T_exh)
        row2_iter.addStretch(1)
        # Buttons
        row_btn = QHBoxLayout()
        box_lay.addLayout(row_btn)
        self.btn_scan_intake = QPushButton("Skanuj INT", self)
        self.btn_scan_exhaust = QPushButton("Skanuj EXH", self)
        row_btn.addWidget(self.btn_scan_intake)
        row_btn.addWidget(self.btn_scan_exhaust)
        row_btn.addStretch(1)
        # Plot canvas
        self.plot_iter = MplCanvas()
        self.plot_iter.set_readout_units("L_mm", "RPM")
        box_lay.addWidget(self.plot_iter)
        iter_lay.addWidget(box)
        self.tabs.addTab(self.tab_iterator, "Iterator")
        self.tabs.currentChanged.connect(lambda _: self._recompute())
        left.addWidget(self.tabs)

        # Action buttons
        actions = QHBoxLayout()
        self.btn_compute = QPushButton("Przelicz", self)
        self.btn_back = QPushButton("Wstecz", self)
        self.btn_next = QPushButton("Dalej", self)
        actions.addWidget(self.btn_compute)
        actions.addStretch(1)
        actions.addWidget(self.btn_back)
        actions.addWidget(self.btn_next)
        left.addLayout(actions)

        # Right side plots/info
        right = QVBoxLayout()
        self.plot_cd = MplCanvas()
        self.plot_q = MplCanvas()
        info_row = QHBoxLayout()
        info_row.addStretch(1)
        from PySide6.QtWidgets import QToolButton

        self.btn_info = QToolButton(self)
        self.btn_info.setText("i")
        self.btn_info.setToolTip("Informacje o Cd i Q*")
        self.btn_info.clicked.connect(self._show_info)
        info_row.addWidget(self.btn_info)
        right.addLayout(info_row)
        right.addWidget(self.plot_cd)
        right.addWidget(self.plot_q)
        self.lbl_params = QLabel("—", self)
        right.addWidget(self.lbl_params)
        self.lbl_ei = QLabel("", self)
        right.addWidget(self.lbl_ei)

        # Pitot mini-panel
        from PySide6.QtWidgets import QLineEdit, QGroupBox

        pit_row = QVBoxLayout()
        gb = QGroupBox("Pitot (lokalna prędkość)", self)
        gb_l = QVBoxLayout(gb)
        row1_p = QHBoxLayout()
        self.ed_pit_dp = QLineEdit(self)
        self.ed_pit_T = QLineEdit(self)
        self.ed_pit_C = QLineEdit(self)
        self.ed_pit_dp.setPlaceholderText("ΔP [inH₂O] (np. 28.0)")
        self.ed_pit_T.setPlaceholderText("T [°C] (np. 20.0)")
        self.ed_pit_C.setPlaceholderText("C_probe (np. 1.00)")
        self.ed_pit_dp.setToolTip("Różnica ciśnień Pitota (statyczne–całkowite)")
        self.ed_pit_C.setToolTip("Współczynnik kalibracyjny sondy")
        # defaults
        self.ed_pit_dp.setText("28.0")
        try:
            tC = 20.0
            if self.state.air is not None:
                tC = float(self.state.air.T - 273.15)
            self.ed_pit_T.setText(f"{tC:.1f}")
        except Exception:
            self.ed_pit_T.setText("20.0")
        self.ed_pit_C.setText("1.00")
        row1_p.addWidget(QLabel("ΔP:", self))
        row1_p.addWidget(self.ed_pit_dp)
        row1_p.addWidget(QLabel("T:", self))
        row1_p.addWidget(self.ed_pit_T)
        row1_p.addWidget(QLabel("C_probe:", self))
        row1_p.addWidget(self.ed_pit_C)
        gb_l.addLayout(row1_p)
        row2_p = QHBoxLayout()
        self.lbl_pit_V = QLabel("V = — m/s", self)
        self.lbl_pit_Mach = QLabel("Mach = —", self)
        self.btn_pit_calc = QPushButton("Oblicz", self)
        row2_p.addWidget(self.lbl_pit_V)
        row2_p.addWidget(self.lbl_pit_Mach)
        row2_p.addStretch(1)
        row2_p.addWidget(self.btn_pit_calc)
        gb_l.addLayout(row2_p)
        pit_row.addWidget(gb)
        right.addLayout(pit_row)

        root.addLayout(left, 2)
        root.addLayout(right, 3)

        # Connections
        self.btn_compute.clicked.connect(self._recompute)
        self.btn_pit_calc.clicked.connect(self._compute_pitot)
        self.btn_scan_intake.clicked.connect(lambda: self._run_iterator(side="intake"))
        self.btn_scan_exhaust.clicked.connect(lambda: self._run_iterator(side="exhaust"))
        # Mirror wizard navigation
        self.btn_back.clicked.connect(lambda: getattr(self.window(), "_go_back", lambda: None)())
        self.btn_next.clicked.connect(lambda: getattr(self.window(), "_go_next", lambda: None)())
        self._on_changed()
        QTimer.singleShot(0, self._recompute)

    def _on_changed(self, *args: Any) -> None:  # noqa: ARG002
        self.btn_compute.setEnabled(True)
        self._debounce.start()
        self._emit_valid()

    def _run_iterator(self, side: str) -> None:
        try:
            from iop_flow.tuning import sweep_intake_L, sweep_exhaust_L
            L_min = float(self.spn_L_min.value()); L_max = float(self.spn_L_max.value()); step = float(self.spn_L_step.value())
            n = int(self.cmb_iter_n.currentText()); D_m = float(self.spn_iter_D.value())/1000.0
            T_int = float(self.spn_iter_T_int.value()); T_exh = float(self.spn_iter_T_exh.value())
            rpm_target = float(self.state.engine_target_rpm or 6500)
            if L_min >= L_max or step <= 0: return
            if side == "intake":
                data = sweep_intake_L(L_min, L_max, step, n, D_m, T_int, rpm_target)
                self.state.tuning["intake_sweep"] = data
            else:
                data = sweep_exhaust_L(L_min, L_max, step, n, D_m, T_exh, rpm_target)
                self.state.tuning["exhaust_sweep"] = data
            xs = [p[0] for p in data]; ys = [p[1] for p in data]
            self.plot_iter.clear();
            label = "INT" if side=="intake" else "EXH"
            if xs and ys:
                self.plot_iter.plot_xy(xs, ys, label=label, xlabel="L [mm]", ylabel="RPM", title=f"{label} rpm_for_L")
            self.plot_iter.render()
        except Exception:
            try:
                self.plot_iter.clear(); self.plot_iter.render()
            except Exception:
                pass

    def _emit_valid(self) -> None:
        ok_prev = self._prev_steps_ok()
        ok_data = (len(self.state.measure_intake) > 0) or (len(self.state.measure_exhaust) > 0)
        self.sig_valid_changed.emit(bool(ok_prev and ok_data))

    def _prev_steps_ok(self) -> bool:
        from .state import is_valid_step_bench, is_valid_step_geometry

        return is_valid_step_bench(self.state) and is_valid_step_geometry(self.state)

    def _recompute(self) -> None:
        if not self._prev_steps_ok():
            return
        if not (self.state.measure_intake or self.state.measure_exhaust):
            try:
                self.plot_cd.clear()
                self.plot_q.clear()
                self.plot_cd.render()
                self.plot_q.render()
                self.lbl_params.setText("—")
                self.lbl_ei.setText("")
            except Exception:
                pass
            return
        try:
            session: Session = self.state.build_session_from_wizard_for_compute()
        except Exception:
            return
        prefs = load_prefs()
        import time

        t0 = time.perf_counter()
        try:
            result = run_all(
                session,
                dp_ref_inH2O=(prefs.dp_ref_inH2O or 28.0),
                a_ref_mode=prefs.a_ref_mode,
                eff_mode=prefs.eff_mode,
            )
        except Exception:
            try:
                self.plot_cd.clear()
                self.plot_q.clear()
                self.plot_cd.render()
                self.plot_q.render()
                self.lbl_params.setText("—")
                self.lbl_ei.setText("")
                win = self.window()
                if hasattr(win, "statusBar"):
                    sb = win.statusBar()
                    if sb is not None:
                        sb.showMessage("Błąd obliczeń (pomiń do czasu uzupełnienia danych)", 2500)
            except Exception:
                pass
            return
        series = result.get("series", {})
        active_idx = self.tabs.currentIndex()
        side = "intake" if active_idx == 0 else "exhaust"
        data: List[Dict[str, Any]] = series.get(side, [])  # type: ignore[assignment]

        self.plot_cd.clear()
        self.plot_q.clear()
        lifts_m = [float(d.get("lift_m") or 0.0) for d in data]
        lifts_mm = [v * 1000.0 for v in lifts_m]
        cd = [float(d.get("Cd_ref") or 0.0) for d in data]
        q_cfm = [float(d.get("q_m3s_ref") or 0.0) * 2118.8800032893 for d in data]
        a_key = (result.get("params", {}).get("A_ref_key") or "eff") if isinstance(result, dict) else "eff"
        try:
            dp_ref = float(result.get("params", {}).get("dp_ref_inH2O", 28.0))  # type: ignore[assignment]
        except Exception:
            dp_ref = 28.0
        side_prefix = "INT" if side == "intake" else "EXH"
        title_cd = f"{side_prefix} · Cd @ {a_key} ΔP={dp_ref:.0f}\" H₂O"
        title_q = f"{side_prefix} · Q* @ {a_key} ΔP={dp_ref:.0f}\" H₂O"
        self.plot_cd.set_readout_units("mm", "-")
        self.plot_q.set_readout_units("mm", "CFM")
        if lifts_mm and any(v != 0.0 for v in cd):
            self.plot_cd.plot_xy(lifts_mm, cd, label=f"{side_prefix}", xlabel="Lift [mm]", ylabel="Cd (-)", title=title_cd)
        if lifts_mm and any(v != 0.0 for v in q_cfm):
            self.plot_q.plot_xy(lifts_mm, q_cfm, label=f"{side_prefix}", xlabel="Lift [mm]", ylabel="Q* [CFM]", title=title_q)
        self.plot_cd.render()
        self.plot_q.render()

        rho_ref = None
        try:
            from iop_flow import formulas as F

            rho_ref = (
                F.air_density(F.AirState(self.state.air.p_tot, self.state.air.T, self.state.air.RH))
                if self.state.air
                else None
            )
        except Exception:
            rho_ref = None
        params_txt = (
            f'dp_ref={self.state.air_dp_ref_inH2O:.1f}"H₂O, '
            f"ρ_ref={rho_ref:.4f} kg/m³, A_ref_mode=eff, eff_mode=smoothmin"
            if rho_ref is not None
            else f'dp_ref={self.state.air_dp_ref_inH2O:.1f}"H₂O, A_ref_mode=eff, eff_mode=smoothmin'
        )
        self.lbl_params.setText(params_txt)

        ei_text = ""
        if series.get("ei"):
            ei = series["ei"]
            if ei:
                vals = [e.get("EI") for e in ei if e.get("EI") is not None]
                if vals:
                    ei_text = f"E/I avg={sum(vals) / len(vals):.3f} min={min(vals):.3f} max={max(vals):.3f}"
        self.lbl_ei.setText(ei_text)

        try:
            sr_vals = [d.get("SR") for d in data if d.get("SR") is not None]
            sr_txt = f"{sum(sr_vals) / len(sr_vals):.0f} rpm" if sr_vals else "—"
            self.lbl_params.setText(self.lbl_params.text() + f", SR_avg={sr_txt}")
        except Exception:
            pass
        self.btn_compute.setEnabled(False)
        try:
            dt_ms = int((time.perf_counter() - t0) * 1000)
            win = self.window()
            if hasattr(win, "statusBar"):
                sb = win.statusBar()
                if sb is not None:
                    sb.showMessage(f"OK ({dt_ms} ms)", 2000)
        except Exception:
            pass
        self._emit_valid()

    def _show_info(self) -> None:
        QMessageBox.information(
            self,
            "Co to jest?",
            (
                "Cd (-) – Cd = Q / (A·√(2ΔP/ρ)) przy ΔP_ref.\n"
                "Q [CFM]* – Przepływ przeliczony do ΔP_ref; wykres w CFM dla czytelności."
            ),
        )

    def _compute_pitot(self) -> None:
        from iop_flow import formulas as F
        try:
            dp_in = float((self.ed_pit_dp.text() or "28.0").replace(",", "."))
            tC = float((self.ed_pit_T.text() or "20.0").replace(",", "."))
            C = float((self.ed_pit_C.text() or "1.0").replace(",", "."))
            dp_pa = F.in_h2o_to_pa(dp_in)
            rho = F.air_density(F.AirState(self.state.air.p_tot, self.state.air.T, self.state.air.RH)) if self.state.air else 1.204
            V = F.velocity_pitot(dp_pa, rho, C)
            Mach = V / F.speed_of_sound(F.C_to_K(tC))
            self.lbl_pit_V.setText(f"V = {V:.1f} m/s")
            self.lbl_pit_Mach.setText(f"Mach = {Mach:.3f}")
        except Exception:
            self.lbl_pit_V.setText("V = — m/s")
            self.lbl_pit_Mach.setText("Mach = —")
