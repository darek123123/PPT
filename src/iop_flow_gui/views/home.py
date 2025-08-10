from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class HomeView(QWidget):
    sig_open_run_all = Signal()
    sig_open_compare = Signal()
    sig_open_wizard = Signal()

    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        btn_run = QPushButton("Analiza sesji", self)
        btn_cmp = QPushButton("Porównanie Before/After", self)
        btn_wizard = QPushButton("Nowa sesja (kreator)", self)
        lay.addWidget(btn_run)
        lay.addWidget(btn_cmp)
        lay.addWidget(btn_wizard)
        btn_run.clicked.connect(self.sig_open_run_all)
        btn_cmp.clicked.connect(self.sig_open_compare)
        btn_wizard.clicked.connect(self.sig_open_wizard)
