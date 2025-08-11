from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
import traceback

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
        # Keep references to open wizard windows so they aren't garbage-collected
        self._wizards = []

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
        self.run_all.back_requested.connect(lambda: self._goto(self.home))
        self.compare.back_requested.connect(lambda: self._goto(self.home))

    def _goto(self, w) -> None:
        self.stack.setCurrentWidget(w)

    def _open_wizard(self) -> None:
        try:
            wiz = WizardWindow()
            # Keep a strong reference so the window doesn't close immediately
            self._wizards.append(wiz)
            # Drop reference when the window is destroyed
            wiz.destroyed.connect(lambda *_: self._wizards.remove(wiz) if wiz in self._wizards else None)
            wiz.show()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Błąd", f"Nie udało się otworzyć kreatora:\n{e}")
