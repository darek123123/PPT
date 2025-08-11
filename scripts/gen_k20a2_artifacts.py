"""Headless artifact generator for K20A2 preset.

Usage (PowerShell example):
  $env:PYTHONPATH="$PWD\src"; $env:QT_QPA_PLATFORM="offscreen"; $env:MPLBACKEND="Agg"; .\.venv\Scripts\python.exe -u scripts\gen_k20a2_artifacts.py
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict


def _log(msg: str) -> None:
    print(f"[gen] {msg}")


def main() -> int:  # noqa: D401
    # Env for headless operation
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("MPLBACKEND", "Agg")

    # Ensure src/ on sys.path (repo root = parent of 'scripts')
    scripts_dir = Path(__file__).resolve().parent
    root = scripts_dir.parent
    src_path = root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    try:
        from iop_flow_gui.wizard.state import WizardState  # type: ignore
        from iop_flow.api import run_all  # type: ignore
        from iop_flow.io_json import write_session  # type: ignore
    except Exception as e:  # pragma: no cover
        _log(f"[ERR] import failed: {e}")
        return 2

    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    try:
        _log("start")
        state = WizardState()
        state.apply_defaults_preset()
        _log("preset OK")
        # Build session (use build_session_for_run_all for full data inc. CSA)
        session = state.build_session_for_run_all()
        _log("session OK")
        results: Dict[str, Any] = run_all(session)
        _log("run_all OK")
        # Write session
        session_path = artifacts_dir / "sample_session_k20a2.session.json"
        write_session(session_path, session)
        # Write results
        results_path = artifacts_dir / "results_k20a2.json"
        with results_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        # Optional CSVs (only if measurement points exist)
        intake_csv = artifacts_dir / "intake_k20a2.csv"
        exhaust_csv = artifacts_dir / "exhaust_k20a2.csv"
        wrote_csv = False
        if state.measure_intake or state.measure_exhaust:
            import csv

            if state.measure_intake:
                with intake_csv.open("w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
                    for row in state.measure_intake:
                        w.writerow(
                            [
                                row.get("lift_mm"),
                                row.get("q_cfm"),
                                row.get("dp_inH2O"),
                                row.get("swirl_rpm"),
                            ]
                        )
                    wrote_csv = True
            if state.measure_exhaust:
                with exhaust_csv.open("w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["lift_mm", "q_cfm", "dp_inH2O", "swirl_rpm"])
                    for row in state.measure_exhaust:
                        w.writerow(
                            [
                                row.get("lift_mm"),
                                row.get("q_cfm"),
                                row.get("dp_inH2O"),
                                row.get("swirl_rpm"),
                            ]
                        )
                    wrote_csv = True

        # Final report
        for p in [session_path, results_path] + ([intake_csv, exhaust_csv] if wrote_csv else []):
            try:
                _log(f"{p.name} {p.stat().st_size} B")
            except Exception:  # pragma: no cover
                _log(f"{p.name} <err>")
        _log("DONE")
        return 0
    except Exception as e:  # pragma: no cover
        _log(f"[ERR] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
