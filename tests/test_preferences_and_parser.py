from __future__ import annotations


def test_preferences_roundtrip_qsettings() -> None:
    from iop_flow_gui.preferences import Prefs, save_prefs, load_prefs

    # Save custom prefs
    p = Prefs(a_ref_mode="throat", eff_mode="logistic", dp_ref_inH2O=30.5, v_target=95.0)
    save_prefs(p)
    # Load and verify
    p2 = load_prefs()
    assert p2.a_ref_mode == "throat"
    assert p2.eff_mode == "logistic"
    assert abs(p2.dp_ref_inH2O - 30.5) < 1e-9
    assert abs(p2.v_target - 95.0) < 1e-9


def test_parse_rows_accepts_commas_semicolons_tabs() -> None:
    from iop_flow_gui.wizard.state import parse_rows

    text = (
        "1,0;100,0;28,0\n"  # semicolons, comma decimals
        "2.0\t160.0\t28.0\n"  # tabs, dot decimals
        "3,0 200,0 28,0 800\n"  # spaces
        "bad;row;here\n"  # bad row
    )
    rows = parse_rows(text)
    # Should parse 3 valid rows, skipping the bad one
    assert len(rows) == 3
    # Check numeric parsing correctness
    assert rows[0][0] == 1.0 and rows[0][1] == 100.0 and rows[0][2] == 28.0
    assert rows[1][0] == 2.0 and rows[1][1] == 160.0 and rows[1][2] == 28.0
    assert rows[2][0] == 3.0 and rows[2][1] == 200.0 and rows[2][2] == 28.0 and rows[2][3] == 800.0
