import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_import_and_main_smoke() -> None:
    from iop_flow_gui.main import main

    assert main() == 0
