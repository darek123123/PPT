import pytest

from iop_flow_gui.wizard.state import (
    WizardState,
    parse_float_pl,
    gen_grid,
    set_geometry_from_ui,
    is_valid_step_geometry,
)


def test_gen_grid_basic() -> None:
    grid = gen_grid(1.0, 5.0, 0.5)
    # rounded to 3 decimals; inclusive bounds
    assert grid[0] == 1.0
    assert grid[-1] == 5.0
    assert 3.0 in grid
    assert len(grid) == 9  # 1.0,1.5,2.0,...,5.0


def test_geometry_validator_stem_vs_throat() -> None:
    s = WizardState()
    # set geometry with stem >= throat should be invalid
    set_geometry_from_ui(
        s,
        bore_mm=86.0,
        valve_int_mm=32.0,
        valve_exh_mm=28.0,
        throat_mm=7.0,
        stem_mm=7.0,  # equal -> invalid per spec
        seat_angle_deg=45.0,
        seat_width_mm=2.0,
        port_volume_cc=180.0,
        port_length_mm=100.0,
    )
    assert not is_valid_step_geometry(s)


def test_parse_float_pl_commas() -> None:
    assert parse_float_pl("2,50") == 2.5
    assert parse_float_pl(" 1 234,5 ") == pytest.approx(1234.5)
