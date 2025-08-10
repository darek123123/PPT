from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
)


ARefMode = Literal["eff", "throat", "curtain"]
EffMode = Literal["smoothmin", "logistic"]


@dataclass
class Prefs:
    a_ref_mode: ARefMode = "eff"
    eff_mode: EffMode = "smoothmin"
    dp_ref_inH2O: float = 28.0
    v_target: float = 100.0


SETTINGS_ORG = "iop_flow_gui"
SETTINGS_APP = "app"


def load_prefs() -> Prefs:
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    a_ref = str(s.value("prefs/a_ref_mode", "eff"))
    if a_ref not in ("eff", "throat", "curtain"):
        a_ref = "eff"
    eff = str(s.value("prefs/eff_mode", "smoothmin"))
    if eff not in ("smoothmin", "logistic"):
        eff = "smoothmin"
    try:
        dp = float(s.value("prefs/dp_ref_inH2O", 28.0))
    except Exception:
        dp = 28.0
    try:
        vt = float(s.value("prefs/v_target", 100.0))
    except Exception:
        vt = 100.0
    return Prefs(a_ref_mode=a_ref, eff_mode=eff, dp_ref_inH2O=dp, v_target=vt)


def save_prefs(p: Prefs) -> None:
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    s.setValue("prefs/a_ref_mode", p.a_ref_mode)
    s.setValue("prefs/eff_mode", p.eff_mode)
    s.setValue("prefs/dp_ref_inH2O", p.dp_ref_inH2O)
    s.setValue("prefs/v_target", p.v_target)


class PreferencesDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ustawienia")
        self._prefs = load_prefs()

        root = QVBoxLayout(self)

        # a_ref_mode
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("A_ref_mode:", self))
        self.cmb_a_ref = QComboBox(self)
        self.cmb_a_ref.addItems(["eff", "throat", "curtain"])
        self.cmb_a_ref.setCurrentText(self._prefs.a_ref_mode)
        row1.addWidget(self.cmb_a_ref)
        root.addLayout(row1)

        # eff_mode
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("eff_mode:", self))
        self.cmb_eff = QComboBox(self)
        self.cmb_eff.addItems(["smoothmin", "logistic"])
        self.cmb_eff.setCurrentText(self._prefs.eff_mode)
        row2.addWidget(self.cmb_eff)
        root.addLayout(row2)

        # dp_ref
        row3 = QHBoxLayout()
        row3.addWidget(QLabel('dp_ref ["H2O]:', self))
        self.ed_dp = QLineEdit(self)
        self.ed_dp.setText(f"{self._prefs.dp_ref_inH2O:.2f}")
        row3.addWidget(self.ed_dp)
        root.addLayout(row3)

        # v_target
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("v_target [m/s]:", self))
        self.ed_vt = QLineEdit(self)
        self.ed_vt.setText(f"{self._prefs.v_target:.1f}")
        row4.addWidget(self.ed_vt)
        root.addLayout(row4)

        # buttons
        btns = QHBoxLayout()
        self.btn_ok = QPushButton("Zapisz", self)
        self.btn_reset = QPushButton("Przywróć domyślne", self)
        self.btn_cancel = QPushButton("Anuluj", self)
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_reset)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)

        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_ok(self) -> None:
        # parse values with basic safety
        try:
            dp = float((self.ed_dp.text() or "").replace(",", "."))
        except Exception:
            dp = self._prefs.dp_ref_inH2O
        try:
            vt = float((self.ed_vt.text() or "").replace(",", "."))
        except Exception:
            vt = self._prefs.v_target
        p = Prefs(
            a_ref_mode=self.cmb_a_ref.currentText(),
            eff_mode=self.cmb_eff.currentText(),
            dp_ref_inH2O=max(dp, 0.1),
            v_target=max(vt, 0.1),
        )
        save_prefs(p)
        self.accept()

    def _on_reset(self) -> None:
        p = Prefs()
        save_prefs(p)
        # update widgets to defaults
        self.cmb_a_ref.setCurrentText(p.a_ref_mode)
        self.cmb_eff.setCurrentText(p.eff_mode)
        self.ed_dp.setText(f"{p.dp_ref_inH2O:.2f}")
        self.ed_vt.setText(f"{p.v_target:.1f}")
