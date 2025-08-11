import importlib.util
import pathlib


def test_import_step_exhaust_smoke():
    p = pathlib.Path("src/iop_flow_gui/wizard/step_exhaust.py")
    assert p.exists()

    spec = importlib.util.spec_from_file_location("step_exhaust", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    # Class must exist; import must not print or block
    assert hasattr(mod, "StepExhaust")
