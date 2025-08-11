import importlib.util
import os
import sys
import time
import pathlib


def test_gen_k20a2_artifacts_headless(tmp_path):  # noqa: D103
    root = pathlib.Path(__file__).resolve().parents[1]
    script_path = root / 'scripts' / 'gen_k20a2_artifacts.py'
    assert script_path.exists(), 'generator script missing'
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['MPLBACKEND'] = 'Agg'
    # Ensure src on path
    src_path = root / 'src'
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    spec = importlib.util.spec_from_file_location('gen_k20a2_artifacts', script_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    t0 = time.time()
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    rc = mod.main()  # type: ignore[attr-defined]
    dt = time.time() - t0
    assert rc == 0, 'main() exit code non-zero'
    assert dt < 5.0, 'artifact generation too slow'
    art = root / 'artifacts'
    session = art / 'sample_session_k20a2.session.json'
    results = art / 'results_k20a2.json'
    assert session.exists() and session.stat().st_size > 0
    assert results.exists() and results.stat().st_size > 0
    # Optional CSVs
    for name in ('intake_k20a2.csv', 'exhaust_k20a2.csv'):
        p = art / name
        if p.exists():
            assert p.stat().st_size > 0
