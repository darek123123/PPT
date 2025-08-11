from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Literal

import typer

from iop_flow_core import (  # type: ignore[attr-defined]
    read_session,
    write_session,
    run_all,
    run_compare,
    load_preset_json,
    AirConditions,
    Engine,
    Geometry,
    FlowSeries,
    LiftPoint,
    Session,
)

app = typer.Typer(help="Head porting core CLI (Typer)")


@app.command()
def run(
    input: Path = typer.Option(..., "--in", help="Input session.json"),
    out: Path = typer.Option(..., "--out", help="Output results.json"),
    dp_ref: float = typer.Option(28.0, "--dp-ref"),
    a_ref_mode: Literal["throat", "curtain", "eff"] = typer.Option(
        "eff", "--a-ref-mode", help="throat|curtain|eff"
    ),
    eff_mode: Literal["smoothmin", "logistic"] = typer.Option(
        "smoothmin", "--eff-mode", help="smoothmin|logistic"
    ),
    ld0: float = typer.Option(0.30, "--ld0"),
    k: float = typer.Option(12.0, "--k"),
    v_target: Optional[float] = typer.Option(None, "--v-target"),
) -> None:
    """Process a single session JSON and write results."""
    s = read_session(str(input))
    res = run_all(
        s,
        dp_ref_inH2O=dp_ref,
        a_ref_mode=a_ref_mode,
        eff_mode=eff_mode,
        logistic_ld0=ld0,
        logistic_k=k,
        engine_v_target=(v_target if v_target is not None else 100.0),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"[iop-flow] Saved results to {out}")


@app.command()
def compare(
    before: Path = typer.Option(..., "--before"),
    after: Path = typer.Option(..., "--after"),
    out: Path = typer.Option(..., "--out"),
    keys: list[str] = typer.Option(["q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref"], "--keys"),
    dp_ref: float = typer.Option(28.0, "--dp-ref"),
    a_ref_mode: Literal["throat", "curtain", "eff"] = typer.Option("eff", "--a-ref-mode"),
    eff_mode: Literal["smoothmin", "logistic"] = typer.Option("smoothmin", "--eff-mode"),
    ld0: float = typer.Option(0.30, "--ld0"),
    k: float = typer.Option(12.0, "--k"),
    tol: float = typer.Option(5e-7, "--tol"),
) -> None:
    """Compare two sessions and write a diff JSON."""
    s_before = read_session(str(before))
    s_after = read_session(str(after))
    res = run_compare(
        s_before,
        s_after,
        keys=tuple(keys),
        dp_ref_inH2O=dp_ref,
        a_ref_mode=a_ref_mode,
        eff_mode=eff_mode,
        logistic_ld0=ld0,
        logistic_k=k,
        tol=tol,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"[iop-flow] Saved diff to {out}")


@app.command()
def schema(out: Path = typer.Option(..., "--out")) -> None:
    """Write an example Session JSON."""
    air = AirConditions(p_tot=101325.0, T=293.15, RH=0.0)
    eng = Engine(displ_L=2.0, cylinders=4, ve=0.95)
    geom = Geometry(
        bore_m=0.086,
        valve_int_m=0.046,
        valve_exh_m=0.040,
        throat_m=0.034,
        stem_m=0.007,
        port_volume_cc=180.0,
        port_length_m=0.110,
        seat_angle_deg=45.0,
        seat_width_m=0.0015,
    )
    intake = [
        LiftPoint(lift_mm=1.0, q_cfm=120.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=2.0, q_cfm=175.0, dp_inH2O=28.0),
    ]
    fs = FlowSeries(intake=intake, exhaust=[])
    s = Session(
        meta={"project": "example"},
        mode="baseline",
        air=air,
        engine=eng,
        geom=geom,
        lifts=fs,
        csa=None,
    )
    write_session(out, s)
    typer.echo(f"[iop-flow] Wrote example session to {out}")


@app.command()
def preset(name: str = typer.Argument("k20a2")) -> None:
    """Print a builtin preset JSON to stdout."""
    data = load_preset_json(name)
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
