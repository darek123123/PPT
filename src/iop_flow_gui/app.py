from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStackedWidget

from .views.home import HomeView
from .views.run_all import RunAllView
from .views.compare import CompareView
from .wizard.wizard import WizardWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("iop-flow GUI")
        self.stack = QStackedWidget(self)
        self.setCentralWidget(self.stack)

        self.home = HomeView()
        self.run_all = RunAllView()
        self.compare = CompareView()

        self.stack.addWidget(self.home)
        self.stack.addWidget(self.run_all)
        self.stack.addWidget(self.compare)

        # wiring
        self.home.sig_open_run_all.connect(lambda: self._goto(self.run_all))
        self.home.sig_open_compare.connect(lambda: self._goto(self.compare))
        self.home.sig_open_wizard.connect(self._open_wizard)

    def _goto(self, w) -> None:
        self.stack.setCurrentWidget(w)

    def _open_wizard(self) -> None:
        wiz = WizardWindow()
        wiz.show()
