from __future__ import annotations

from iop_flow_gui.wizard.state import WizardState

if __name__ == "__main__":
    s = WizardState()
    s.apply_defaults_preset()
    s.tuning = {"intake_calc": {"L_mm": 300.0}}
    d = s.to_dict()
    print("has_tuning:", "tuning" in d, d.get("tuning"))
