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

        # React to any HP param changes
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

        self._refresh()

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
