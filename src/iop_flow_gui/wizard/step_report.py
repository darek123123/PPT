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
)

import json
import io
import csv
import os

from iop_flow.api import run_all
from iop_flow.io_json import write_session

from .state import WizardState


class StepReport(QWidget):
    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self.settings = QSettings("iop-flow", "wizard")

        root = QVBoxLayout(self)
        self.lbl_stats = QLabel("—", self)
        root.addWidget(self.lbl_stats)

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
        except Exception as e:
            self.lbl_stats.setText(f"Błąd obliczeń: {e}")

    def _save_session(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz Session", last_dir, "JSON (*.json)")
        if not path:
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        data = self._compute()["session"]
        try:
            write_session(data, path)
            QMessageBox.information(self, "Zapis", f"Session zapisane: {path}")
            self._status_ok()
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie udało się zapisać: {e}")

    def _save_results(self) -> None:
        last_dir = self.settings.value("last_dir", "", type=str) or ""
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz Results", last_dir, "JSON (*.json)")
        if not path:
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        out = self._compute()["out"]
        try:
            self._write_json_pretty(path, out)
            QMessageBox.information(self, "Zapis", f"Wyniki zapisane: {path}")
            self._status_ok()
        except Exception as e:
            QMessageBox.warning(self, "Błąd", f"Nie udało się zapisać: {e}")

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
