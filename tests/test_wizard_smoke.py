import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_wizard_importable() -> None:
    from iop_flow_gui.wizard.wizard import WizardWindow  # noqa: F401
