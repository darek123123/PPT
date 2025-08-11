from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QRadioButton,
    QLineEdit,
    QDoubleSpinBox,
)

import json
import io
import csv
import os
from pathlib import Path

from iop_flow.api import run_all
from iop_flow.io_json import write_session
from iop_flow import formulas as F
from iop_flow.hp import (
    hp_from_cfm,
    estimate_hp_curve_mode_b,
)

from .state import WizardState


class StepReport(QWidget):
    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self.settings = QSettings("iop-flow", "wizard")

        root = QVBoxLayout(self)
        self.lbl_stats = QLabel("—", self)
        root.addWidget(self.lbl_stats)

        # HP group
        hp_group = QGroupBox("Moc (HP)", self)
        hp_lay = QVBoxLayout(hp_group)

        # Mode selector
        mode_row = QHBoxLayout()
        self.rb_mode_a = QRadioButton("Tryb A – CFM/HP (ROT)", self)
        self.rb_mode_b = QRadioButton("Tryb B – BSFC/AFR (fizyczny)", self)
        self.rb_mode_a.setChecked(True)
        mode_row.addWidget(self.rb_mode_a)
        mode_row.addWidget(self.rb_mode_b)
        mode_row.addStretch(1)
        hp_lay.addLayout(mode_row)

        # Shared RPM range
        rng_row = QHBoxLayout()
        self.ed_rpm_start = QLineEdit(self)
        self.ed_rpm_stop = QLineEdit(self)
        self.ed_rpm_step = QLineEdit(self)
        self.ed_rpm_start.setPlaceholderText("RPM start (np. 1000)")
        self.ed_rpm_stop.setPlaceholderText("RPM stop (np. 9000)")
        self.ed_rpm_step.setPlaceholderText("Krok (np. 500)")
        self.ed_rpm_start.setText("1000")
        self.ed_rpm_stop.setText("9000")
        self.ed_rpm_step.setText("500")
        rng_row.addWidget(QLabel("Zakres RPM:", self))
        rng_row.addWidget(self.ed_rpm_start)
        rng_row.addWidget(self.ed_rpm_stop)
        rng_row.addWidget(self.ed_rpm_step)
        rng_row.addStretch(1)
        hp_lay.addLayout(rng_row)

        # Mode A params (CFM per HP)
        a_row = QHBoxLayout()
        self.ed_cfm_per_hp = QLineEdit(self)
        self.ed_cfm_per_hp.setPlaceholderText("CFM/HP (np. 1.67)")
        self.ed_cfm_per_hp.setToolTip("Reguła kciuka: CFM na 1 HP (np. 1.5–1.8)")
        self.ed_cfm_per_hp.setText("1.67")
        a_row.addWidget(QLabel("CFM/HP:", self))
        a_row.addWidget(self.ed_cfm_per_hp)
        a_row.addStretch(1)
        hp_lay.addLayout(a_row)

        # Mode B params
        b_row1 = QHBoxLayout()
        self.ed_afr = QLineEdit(self)
        self.ed_lambda = QLineEdit(self)
        self.ed_bsfc = QLineEdit(self)
        self.ed_afr.setPlaceholderText("AFR (np. 12.8)")
        self.ed_lambda.setPlaceholderText("λ (np. 1.00)")
        self.ed_bsfc.setPlaceholderText("BSFC [lb/HP·h] (np. 0.50)")
        self.ed_afr.setText("12.8")
        self.ed_lambda.setText("1.00")
        self.ed_bsfc.setText("0.50")
        b_row1.addWidget(QLabel("AFR:", self))
        b_row1.addWidget(self.ed_afr)
        b_row1.addWidget(QLabel("λ:", self))
        b_row1.addWidget(self.ed_lambda)
        b_row1.addWidget(QLabel("BSFC:", self))
        b_row1.addWidget(self.ed_bsfc)
        b_row1.addStretch(1)
        hp_lay.addLayout(b_row1)

        b_row2 = QHBoxLayout()
        self.rb_rho_bench = QRadioButton("ρ: z Bench", self)
        self.rb_rho_fixed = QRadioButton("ρ: 1.204 kg/m³", self)
        self.rb_rho_bench.setChecked(True)
        b_row2.addWidget(self.rb_rho_bench)
        b_row2.addWidget(self.rb_rho_fixed)
        b_row2.addStretch(1)
        hp_lay.addLayout(b_row2)

        # Shared loss factor
        loss_row = QHBoxLayout()
        self.ed_loss_pct = QLineEdit(self)
        self.ed_loss_pct.setPlaceholderText("Straty [%] (np. 10)")
        self.ed_loss_pct.setToolTip("Utrata między przepływem a mocą na wale (napęd osprzętu, pompa, tarcie)")
        self.ed_loss_pct.setText("0")
        loss_row.addWidget(QLabel("Straty:", self))
        loss_row.addWidget(self.ed_loss_pct)
        loss_row.addWidget(QLabel("%", self))
        loss_row.addStretch(1)
        hp_lay.addLayout(loss_row)

        # Plot and footer
        from ..widgets.mpl_canvas import MplCanvas
        from PySide6.QtWidgets import QToolButton

        self.plot_hp = MplCanvas()
        self.plot_hp.set_readout_units("RPM", "HP")
        hp_lay.addWidget(self.plot_hp)

        # top-right info button
        top_info_row = QHBoxLayout()
        top_info_row.addStretch(1)
        self.btn_info_hp = QToolButton(self)
        self.btn_info_hp.setText("i")
        self.btn_info_hp.setToolTip("Informacje o metodach szacowania mocy")
        self.btn_info_hp.clicked.connect(self._show_hp_info)
        top_info_row.addWidget(self.btn_info_hp)
        hp_lay.addLayout(top_info_row)

        self.lbl_hp_peak = QLabel("—", self)
        hp_lay.addWidget(self.lbl_hp_peak)

        root.addWidget(hp_group)


        # --- Tuning (expanded) ---
        from PySide6.QtWidgets import QComboBox
        tuning_box = QGroupBox("Tuning", self)
        tuning_lay = QVBoxLayout(tuning_box)

        # Prefill from state or defaults
        tdict = dict(self.state.tuning.get("intake_calc", {}))
        def _get_tuning(key, default):
            try:
                return type(default)(tdict.get(key, default))
            except Exception:
                return default

        # L_mm
        row_L = QHBoxLayout()
        self.spn_L_mm = QDoubleSpinBox(self)
        self.spn_L_mm.setRange(50.0, 800.0)
        self.spn_L_mm.setSingleStep(1.0)
        self.spn_L_mm.setDecimals(1)
        self.spn_L_mm.setToolTip("Długość kanału dolotowego (runner) L w mm.\nWartość zapisywana do sesji.\nUżywana w kalkulatorach ćwierćfali i Helmholtza.")
        self.spn_L_mm.setValue(_get_tuning("L_mm", 300.0))
        row_L.addWidget(QLabel("INT L [mm]:", self))
        row_L.addWidget(self.spn_L_mm)
        tuning_lay.addLayout(row_L)

        # D_mm
        row_D = QHBoxLayout()
        self.spn_D_mm = QDoubleSpinBox(self)
        self.spn_D_mm.setRange(50.0, 80.0)
        self.spn_D_mm.setSingleStep(0.1)
        self.spn_D_mm.setDecimals(1)
        self.spn_D_mm.setToolTip("Średnica kanału (runner) D w mm.\nUżywana w kalkulatorach.\nKorekcja końca: L_eff = L + 0.6·D.")
        self.spn_D_mm.setValue(_get_tuning("D_mm", 50.0))
        row_D.addWidget(QLabel("INT D [mm]:", self))
        row_D.addWidget(self.spn_D_mm)
        tuning_lay.addLayout(row_D)

        # V_plenum_cc
        row_V = QHBoxLayout()
        self.spn_V_plenum_cc = QDoubleSpinBox(self)
        self.spn_V_plenum_cc.setRange(1000.0, 8000.0)
        self.spn_V_plenum_cc.setSingleStep(10.0)
        self.spn_V_plenum_cc.setDecimals(0)
        self.spn_V_plenum_cc.setToolTip("Objętość plenum w cm³.\nUżywana w kalkulatorze Helmholtza.")
        self.spn_V_plenum_cc.setValue(_get_tuning("V_plenum_cc", 3500.0))
        row_V.addWidget(QLabel("Plenum [cc]:", self))
        row_V.addWidget(self.spn_V_plenum_cc)
        tuning_lay.addLayout(row_V)

        # n_harm
        row_n = QHBoxLayout()
        self.cmb_n_harm = QComboBox(self)
        self.cmb_n_harm.addItems(["1", "2", "3"])
        n_harm_val = int(_get_tuning("n_harm", 2))
        self.cmb_n_harm.setCurrentIndex(max(0, min(2, n_harm_val - 1)))
        self.cmb_n_harm.setToolTip("Harmoniczna ćwierćfali (n):\n1 = podst., 2 = 2. harmoniczna itd.\nPrzybliżenie akustyczne.")
        row_n.addWidget(QLabel("n_harm:", self))
        row_n.addWidget(self.cmb_n_harm)
        tuning_lay.addLayout(row_n)

        # afr (opcjonalnie)
        row_afr = QHBoxLayout()
        self.spn_afr = QDoubleSpinBox(self)
        self.spn_afr.setRange(8.0, 20.0)
        self.spn_afr.setSingleStep(0.1)
        self.spn_afr.setDecimals(2)
        self.spn_afr.setToolTip("AFR (Air-Fuel Ratio).\nTylko do zapisu w tuning, nie wpływa na HP.")
        self.spn_afr.setValue(_get_tuning("afr", 12.8))
        row_afr.addWidget(QLabel("AFR:", self))
        row_afr.addWidget(self.spn_afr)
        tuning_lay.addLayout(row_afr)

        # bsfc (opcjonalnie)
        row_bsfc = QHBoxLayout()
        self.spn_bsfc = QDoubleSpinBox(self)
        self.spn_bsfc.setRange(0.30, 0.80)
        self.spn_bsfc.setSingleStep(0.01)
        self.spn_bsfc.setDecimals(3)
        self.spn_bsfc.setToolTip("BSFC [lb/HP·h].\nTylko do zapisu w tuning, nie wpływa na HP.")
        self.spn_bsfc.setValue(_get_tuning("bsfc", 0.50))
        row_bsfc.addWidget(QLabel("BSFC:", self))
        row_bsfc.addWidget(self.spn_bsfc)
        tuning_lay.addLayout(row_bsfc)

        # Status line
        self.lbl_tuning_status = QLabel("", self)
        tuning_lay.addWidget(self.lbl_tuning_status)

        # --- Kalkulatory ---
        calc_box = QGroupBox("Kalkulatory", self)
        calc_lay = QVBoxLayout(calc_box)
        self.lbl_L_recommended = QLabel("—", self)
        self.lbl_rpm_for_L = QLabel("—", self)
        self.lbl_helmholtz_f = QLabel("—", self)
        self.lbl_helmholtz_rpm = QLabel("—", self)
        calc_lay.addWidget(QLabel("Ćwierćfala (L zalecane) [mm]:", self))
        calc_lay.addWidget(self.lbl_L_recommended)
        calc_lay.addWidget(QLabel("Ćwierćfala (rpm dla L_mm) [rpm]:", self))
        calc_lay.addWidget(self.lbl_rpm_for_L)
        calc_lay.addWidget(QLabel("Helmholtz f [Hz]:", self))
        calc_lay.addWidget(self.lbl_helmholtz_f)
        calc_lay.addWidget(QLabel("rpm≈ (wg f) [rpm]:", self))
        calc_lay.addWidget(self.lbl_helmholtz_rpm)

        tuning_lay.addWidget(calc_box)
        root.addWidget(tuning_box)

        actions = QHBoxLayout()
        self.btn_save_session = QPushButton("Zapisz Session JSON…", self)
        self.btn_save_results = QPushButton("Zapisz Results JSON…", self)
        self.btn_export_csv = QPushButton("Eksport CSV…", self)
        actions.addWidget(self.btn_save_session)
        actions.addWidget(self.btn_save_results)
        actions.addWidget(self.btn_export_csv)
        actions.addStretch(1)
        root.addLayout(actions)



        self.btn_save_session.clicked.connect(self._save_session)
        self.btn_save_results.clicked.connect(self._save_results)
        self.btn_export_csv.clicked.connect(self._export_csv)

        # --- All signal connections and initial sync at the end of __init__ ---
        self.spn_L_mm.valueChanged.connect(self._on_tuning_changed)
        self.spn_D_mm.valueChanged.connect(self._on_tuning_changed)
        self.spn_V_plenum_cc.valueChanged.connect(self._on_tuning_changed)
        self.cmb_n_harm.currentIndexChanged.connect(self._on_tuning_changed)
        self.spn_afr.valueChanged.connect(self._on_tuning_changed)
        self.spn_bsfc.valueChanged.connect(self._on_tuning_changed)

        for w in (
            self.rb_mode_a,
            self.rb_mode_b,
            self.ed_rpm_start,
            self.ed_rpm_stop,
            self.ed_rpm_step,
            self.ed_cfm_per_hp,
            self.ed_afr,
            self.ed_lambda,
            self.ed_bsfc,
            self.rb_rho_bench,
            self.rb_rho_fixed,
            self.ed_loss_pct,
        ):
            try:
                w.clicked.connect(self._refresh)  # type: ignore[attr-defined]
            except Exception:
                try:
                    w.textChanged.connect(self._refresh)  # type: ignore[attr-defined]
                except Exception:
                    pass

        self._sync_tuning_from_state()
        self._refresh()

        # --- All signal connections and initial sync at the end of __init__ ---
        self.spn_L_mm.valueChanged.connect(self._on_tuning_changed)
        self.spn_D_mm.valueChanged.connect(self._on_tuning_changed)
        self.spn_V_plenum_cc.valueChanged.connect(self._on_tuning_changed)
        self.cmb_n_harm.currentIndexChanged.connect(self._on_tuning_changed)
        self.spn_afr.valueChanged.connect(self._on_tuning_changed)
        self.spn_bsfc.valueChanged.connect(self._on_tuning_changed)

        for w in (
            self.rb_mode_a,
            self.rb_mode_b,
            self.ed_rpm_start,
            self.ed_rpm_stop,
            self.ed_rpm_step,
            self.ed_cfm_per_hp,
            self.ed_afr,
            self.ed_lambda,
            self.ed_bsfc,
            self.rb_rho_bench,
            self.rb_rho_fixed,
            self.ed_loss_pct,
        ):
            try:
                w.clicked.connect(self._refresh)  # type: ignore[attr-defined]
            except Exception:
                try:
                    w.textChanged.connect(self._refresh)  # type: ignore[attr-defined]
                except Exception:
                    pass

        self._sync_tuning_from_state()
        self._refresh()




    def _sync_tuning_from_state(self) -> None:
        """Load tuning values from state into widgets (no signal cascade)."""
        try:
            d = self.state.tuning.get("intake_calc", {})
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
                # V_plenum_cc
                V = d.get("V_plenum_cc")
                if V is not None:
                    self.spn_V_plenum_cc.blockSignals(True)
                    self.spn_V_plenum_cc.setValue(float(V))
                    self.spn_V_plenum_cc.blockSignals(False)
                # n_harm
                n = d.get("n_harm")
                if n is not None:
                    idx = max(0, min(2, int(n) - 1))
                    self.cmb_n_harm.blockSignals(True)
                    self.cmb_n_harm.setCurrentIndex(idx)
                    self.cmb_n_harm.blockSignals(False)
                # afr
                afr = d.get("afr")
                if afr is not None:
                    self.spn_afr.blockSignals(True)
                    self.spn_afr.setValue(float(afr))
                    self.spn_afr.blockSignals(False)
                # bsfc
                bsfc = d.get("bsfc")
                if bsfc is not None:
                    self.spn_bsfc.blockSignals(True)
                    self.spn_bsfc.setValue(float(bsfc))
                    self.spn_bsfc.blockSignals(False)
        except Exception:
            pass

    def _on_tuning_changed(self) -> None:
        try:
            curr = dict(self.state.tuning.get("intake_calc", {}))
            curr["L_mm"] = float(self.spn_L_mm.value())
            curr["D_mm"] = float(self.spn_D_mm.value())
            curr["V_plenum_cc"] = float(self.spn_V_plenum_cc.value())
            curr["n_harm"] = int(self.cmb_n_harm.currentText())
            curr["afr"] = float(self.spn_afr.value())
            curr["bsfc"] = float(self.spn_bsfc.value())
            self.state.tuning["intake_calc"] = curr
            self._recompute_tuning_calcs()
        except Exception:
            pass

    def _recompute_tuning_calcs(self) -> None:
        """Recompute and update tuning calculators and status line."""
        try:
            from iop_flow.tuning import quarter_wave_L_phys, quarter_wave_rpm_for_L, helmholtz_f_and_rpm
            # Gather inputs
            L_mm = float(self.spn_L_mm.value())
            D_mm = float(self.spn_D_mm.value())
            V_plenum_cc = float(self.spn_V_plenum_cc.value())
            n_harm = int(self.cmb_n_harm.currentText())
            # SI units
            L_m = L_mm / 1000.0
            D_m = D_mm / 1000.0
            V_plenum_m3 = V_plenum_cc * 1e-6
            # Get T_K from state (Bench & Air) or fallback
            T_K = 293.15
            try:
                if self.state.air and hasattr(self.state.air, "T"):
                    T_K = float(self.state.air.T)
            except Exception:
                pass
            # Get rpm_target from state (Silnik)
            rpm_target = 6500.0
            try:
                if self.state.engine_target_rpm:
                    rpm_target = float(self.state.engine_target_rpm)
            except Exception:
                pass
            # Compute
            L_recommended = quarter_wave_L_phys(rpm_target, n_harm, D_m, T_K)
            rpm_for_L = quarter_wave_rpm_for_L(L_m, n_harm, D_m, T_K)
            f_H, rpm_helm = helmholtz_f_and_rpm(D_m, L_m, V_plenum_m3, n_harm, T_K)
            # Display (rounded)
            self.lbl_L_recommended.setText(f"{L_recommended*1000:.0f}")
            self.lbl_rpm_for_L.setText(f"{round(rpm_for_L/10)*10:.0f}")
            self.lbl_helmholtz_f.setText(f"{f_H:.1f}")
            self.lbl_helmholtz_rpm.setText(f"{round(rpm_helm/10)*10:.0f}")
            # Status line
            from iop_flow import formulas as F
            a = F.speed_of_sound(T_K)
            self.lbl_tuning_status.setText(f"a(T)={a:.1f} m/s, n={n_harm}, rpm_target={rpm_target:.0f}")
        except Exception as e:
            self.lbl_L_recommended.setText("—")
            self.lbl_rpm_for_L.setText("—")
            self.lbl_helmholtz_f.setText("—")
            self.lbl_helmholtz_rpm.setText("—")
            self.lbl_tuning_status.setText(f"Błąd: {e}")

    def _status_ok(self, msg: str = "OK") -> None:
        try:
            win = self.window()
            if hasattr(win, "statusBar"):
                sb = win.statusBar()
                if sb is not None:
                    sb.showMessage(msg, 2000)
        except Exception:
            pass

    def _compute(self) -> Dict[str, Any]:
        session = self.state.build_session_for_run_all()
        out = run_all(
            session,
            dp_ref_inH2O=self.state.air_dp_ref_inH2O,
            engine_v_target=(self.state.engine_v_target or 100.0),
        )
        return {"session": session, "out": out}

    def _refresh(self) -> None:
        try:
            # Ensure UI reflects latest state.tuning if it changed elsewhere
            self._sync_tuning_from_state()
            self._recompute_tuning_calcs()
            data = self._compute()
            out = data["out"]
            series = out.get("series", {})
            ei = series.get("ei", [])
            vals = [e.get("EI") for e in ei if e.get("EI") is not None]
            rpm_flow_limit = out.get("engine", {}).get("rpm_flow_limit")
            txt = []
            if vals:
                avg = sum(vals) / len(vals)
                txt.append(f"E/I avg={avg:.3f}")
            if rpm_flow_limit:
                txt.append(f"RPM_flow_limit={rpm_flow_limit:,.0f}")
            self.lbl_stats.setText("; ".join(txt) if txt else "—")

            # HP compute and plot
            self._compute_and_plot_hp(data["session"], out)
        except Exception as e:
            self.lbl_stats.setText(f"Błąd obliczeń: {e}")

    def _save_session(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz Session JSON", last_dir, "JSON (*.json)"
        )
        if not path:
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        data = self._compute()["session"]
        try:
            write_session(Path(path), data)
            QMessageBox.information(self, "Zapis", f"Session zapisane: {path}")
            self._status_ok()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Błąd zapisu Session",
                f"Nie udało się zapisać pliku Session JSON.\n\n{e}",
            )

    def _save_results(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz Results JSON", last_dir, "JSON (*.json)"
        )
        if not path:
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        env = self._compute()
        out = env["out"]
        # Ensure HP section is included
        try:
            hp_section = self.state.results.get("hp")
            if hp_section:
                out = dict(out)
                out["hp"] = hp_section
        except Exception:
            pass
        # Attach tuning (intake/exhaust calc + sweeps) with optional sweep omission if large
        try:
            tdict = self.state.tuning
            tune_payload: dict[str, Any] = {}
            for key in ("intake_calc", "exhaust_calc"):
                v = tdict.get(key)
                if isinstance(v, dict):
                    tune_payload[key] = v
            # Sweeps: include only if length reasonable (<= 1000 points)
            for s_key in ("intake_sweep", "exhaust_sweep"):
                v = tdict.get(s_key)
                if isinstance(v, list):
                    try:
                        if len(v) <= 1000:
                            tune_payload[s_key] = v
                        else:
                            # Mark omission
                            tune_payload[s_key + "_omitted"] = {
                                "count": len(v),
                                "reason": ">1000 points omitted in Results (present in Session)",
                            }
                    except Exception:
                        pass
            if tune_payload:
                out = dict(out)
                out["tuning"] = tune_payload
        except Exception:
            pass
        try:
            self._write_json_pretty(path, out)
            QMessageBox.information(self, "Zapis", f"Wyniki zapisane: {path}")
            self._status_ok()
        except Exception as e:
            QMessageBox.critical(
                self, "Błąd zapisu wyników", f"Nie udało się zapisać wyników.\n\n{e}"
            )

    @staticmethod
    def _write_json_pretty(path: str, data: object) -> None:
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _export_csv(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        dir_path = QFileDialog.getExistingDirectory(self, "Wybierz katalog", last_dir)
        if not dir_path:
            return
        self.settings.setValue("last_dir", dir_path)
        data = self._compute()
        out = data["out"]
        series = out.get("series", {})
        for side in ("intake", "exhaust"):
            rows: List[Dict[str, Any]] = series.get(side, [])  # type: ignore[assignment]
            if not rows:
                continue
            csv_path = os.path.join(dir_path, f"{side}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                headers = ["lift_m", "q_m3s_ref", "A_ref_key", "Cd_ref", "V_ref", "Mach_ref", "SR"]
                writer.writerow(headers)
                for r in rows:
                    writer.writerow(
                        [
                            r.get("lift_m"),
                            r.get("q_m3s_ref"),
                            r.get("A_ref_key"),
                            r.get("Cd_ref"),
                            r.get("V_ref"),
                            r.get("Mach_ref"),
                            r.get("SR") if r.get("SR") is not None else "",
                        ]
                    )
        QMessageBox.information(self, "Eksport", f"Zapisano CSV do: {dir_path}")
        self._status_ok()

    # ----------------- HP helpers -----------------
    def _rpm_grid(self) -> list[float]:
        def _p(ed: QLineEdit, dv: float) -> float:
            s = (ed.text() or "").strip()
            try:
                return float(s.replace(",", "."))
            except Exception:
                return dv

        start = max(0.0, _p(self.ed_rpm_start, 1000.0))
        stop = max(start, _p(self.ed_rpm_stop, 9000.0))
        step = max(1.0, _p(self.ed_rpm_step, 500.0))
        vals: list[float] = []
        v = start
        while v <= stop + 1e-9:
            vals.append(round(v, 3))
            v += step
        return vals

    def _compute_and_plot_hp(self, session, out: dict) -> None:
        # Limits
        rpm_flow = (out.get("engine", {}) or {}).get("rpm_flow_limit")
        rpm_csa = (out.get("engine", {}) or {}).get("rpm_from_csa")
        # Mode
        mode = "A" if self.rb_mode_a.isChecked() else "B"
        xs: list[float] = []
        ys: list[float] = []
        peak_hp = 0.0
        peak_rpm = 0.0
        params: dict[str, Any] = {}

        # Bench context
        try:
            dp_ref = float(out.get("params", {}).get("dp_ref_inH2O", self.state.air_dp_ref_inH2O))
        except Exception:
            dp_ref = self.state.air_dp_ref_inH2O
        rho_ref = None
        try:
            rho_ref = F.air_density(F.AirState(self.state.air.p_tot, self.state.air.T, self.state.air.RH)) if self.state.air else None
        except Exception:
            rho_ref = None

        # Common loss factor
        def _loss_factor() -> float:
            try:
                p = float((self.ed_loss_pct.text() or "0").replace(",", "."))
                return max(0.0, min(0.99, p / 100.0))
            except Exception:
                return 0.0

        loss = _loss_factor()
        if mode == "A":
            # CFM/HP: take max intake q_m3s_ref per port, convert to CFM and multiply by cylinders
            try:
                intake = (out.get("series", {}) or {}).get("intake", [])
                q_m3s = [float(r.get("q_m3s_ref") or 0.0) for r in intake]
                # fallback to exhaust if intake missing
                if not any(q_m3s):
                    exhaust = (out.get("series", {}) or {}).get("exhaust", [])
                    q_m3s = [float(r.get("q_m3s_ref") or 0.0) for r in exhaust]
                q_peak_cfm = (max(q_m3s) if q_m3s else 0.0) * F.M3S_TO_CFM
                cyl = getattr(session.engine, "cylinders", 4) or 4
                cfm_total = q_peak_cfm * float(cyl)
                cfm_per_hp = float((self.ed_cfm_per_hp.text() or "1.67").replace(",", "."))
                hp_tot = hp_from_cfm(cfm_total, cfm_per_hp)
                hp_tot *= (1.0 - loss)
                xs = self._rpm_grid()
                ys = [hp_tot for _ in xs]
                peak_hp, peak_rpm = (hp_tot, xs[len(xs)//2] if xs else 0.0)
                params = {
                    "mode": "A",
                    "cfm_per_hp": cfm_per_hp,
                    "cfm_total": cfm_total,
                    "q_peak_cfm_per_port": q_peak_cfm,
                    "cylinders": cyl,
                    "loss_frac": loss,
                }
            except Exception:
                xs, ys = [], []
        else:
            # Physical model
            try:
                afr = float((self.ed_afr.text() or "12.8").replace(",", "."))
                lam = float((self.ed_lambda.text() or "1.0").replace(",", "."))
                bsfc = float((self.ed_bsfc.text() or "0.5").replace(",", "."))
                grid = self._rpm_grid()
                cap = None
                if grid:
                    cap = min(
                        [v for v in [rpm_flow or float("inf"), rpm_csa or float("inf"), max(grid)] if v is not None]
                    )
                rho_mode = "bench" if self.rb_rho_bench.isChecked() else "fixed"
                res = estimate_hp_curve_mode_b(
                    session,
                    rpm_grid=grid,
                    afr=afr,
                    lambda_corr=lam,
                    bsfc_lb_per_hp_h=bsfc,
                    rho_mode=("bench" if rho_mode == "bench" else "fixed"),
                    rho_fixed=1.204,
                    rpm_cap=cap,
                )
                xs = list(res["rpm"])
                ys = [v * (1.0 - loss) if (v == v) else v for v in res["hp"]]
                peak_hp, peak_rpm = res["peak"]
                params = {
                    "mode": "B",
                    "AFR": afr,
                    "lambda_corr": lam,
                    "BSFC": bsfc,
                    "rho_mode": rho_mode,
                    "loss_frac": loss,
                }
            except Exception:
                xs, ys = [], []

        # Plot
        self.plot_hp.clear()
        if xs and ys:
            self.plot_hp.plot_xy(xs, ys, label=("ROT" if mode == "A" else "BSFC/AFR"), xlabel="RPM", ylabel="HP [–]", title="Moc szacowana")
            # vertical limits
            try:
                ax = self.plot_hp.ax
                if rpm_flow:
                    ax.axvline(rpm_flow, color="#888", linestyle="--", linewidth=1.0)
                    ax.text(rpm_flow, ax.get_ylim()[1]*0.95, "limit z przepływu", rotation=90, va="top", ha="right", fontsize=8)
                if rpm_csa:
                    ax.axvline(rpm_csa, color="#444", linestyle=":", linewidth=1.0)
                    ax.text(rpm_csa, ax.get_ylim()[1]*0.90, "limit z CSA", rotation=90, va="top", ha="right", fontsize=8)
            except Exception:
                pass
        self.plot_hp.render()
        if peak_hp and peak_rpm:
            self.lbl_hp_peak.setText(f"Peak: {peak_hp:.0f} HP @ {peak_rpm:,.0f} RPM")
        else:
            self.lbl_hp_peak.setText("—")

        # Save to state results for JSON export
        try:
            hp_meta: dict[str, Any] = {
                "mode": ("A" if mode == "A" else "B"),
                "peak_hp": peak_hp,
                "rpm_at_peak": peak_rpm,
                "limits": {"flow": rpm_flow, "csa": rpm_csa},
                "params": params,
                "bench": {
                    "dp_ref_inH2O": dp_ref,
                    "rho_ref": rho_ref,
                },
            }
            # include curve if not too large
            if xs and ys and len(xs) <= 1000:
                hp_meta["curve"] = {"rpm": xs, "hp": ys}
            self.state.results["hp"] = hp_meta
        except Exception:
            pass

    def _show_hp_info(self) -> None:
        QMessageBox.information(
            self,
            "Szacowanie mocy",
            (
                "Tryb A – CFM/HP (ROT): HP ≈ CFM_total / (CFM/HP).\n"
                "CFM_total liczone z Q*@ΔP_ref (szczyt na jeden kanał × liczba cylindrów).\n"
                "Typowo 1.5–1.8 CFM/HP przy ΔP=28\" H₂O.\n\n"
                "Tryb B – BSFC/AFR (fizyczny): HP = (ṁ_paliwa [lb/h]) / BSFC,\n"
                "gdzie ṁ_paliwa = (ρ · Q_silnika · VE / AFR) / λ.\n"
                "ρ z ławy (Bench) lub stała 1.204 kg/m³.\n\n"
                "Straty [%] stosowane na końcu jako mnożnik (1−strata).\n"
            ),
        )
