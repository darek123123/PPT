from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .io_json import read_session, write_session
from .schemas import Session, AirConditions, Engine, Geometry, FlowSeries, LiftPoint
from .api import run_all, run_compare


def _cmd_run(args: argparse.Namespace) -> int:
    session = read_session(args.input)
    result = run_all(
        session,
        dp_ref_inH2O=args.dp_ref,
        a_ref_mode=args.a_ref_mode,
        eff_mode=args.eff_mode,
        logistic_ld0=args.ld0,
        logistic_k=args.k,
        engine_v_target=args.v_target,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[iop-flow] Saved results to {out}")
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    before = read_session(args.before)
    after = read_session(args.after)
    result = run_compare(
        before,
        after,
        keys=tuple(args.keys),
        dp_ref_inH2O=args.dp_ref,
        a_ref_mode=args.a_ref_mode,
        eff_mode=args.eff_mode,
        logistic_ld0=args.ld0,
        logistic_k=args.k,
        tol=args.tol,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[iop-flow] Saved diff to {out}")
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    # prosty przykład sesji (intake-only), zgodny z naszymi testami
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
        LiftPoint(lift_mm=3.0, q_cfm=220.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=4.0, q_cfm=260.0, dp_inH2O=28.0),
        LiftPoint(lift_mm=5.0, q_cfm=290.0, dp_inH2O=28.0),
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
    out = Path(args.output)
    write_session(out, s)
    print(f"[iop-flow] Wrote example session to {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="iop-flow", description="Head porting core computation CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Process a single session JSON")
    p_run.add_argument("--in", dest="input", required=True, help="input session.json")
    p_run.add_argument("--out", dest="output", required=True, help="output results.json")
    p_run.add_argument("--dp-ref", dest="dp_ref", type=float, default=28.0)
    p_run.add_argument("--a-ref-mode", choices=("throat", "curtain", "eff"), default="eff")
    p_run.add_argument("--eff-mode", choices=("smoothmin", "logistic"), default="smoothmin")
    p_run.add_argument("--ld0", type=float, default=0.30)
    p_run.add_argument("--k", type=float, default=12.0)
    p_run.add_argument("--v-target", type=float, default=100.0)
    p_run.set_defaults(func=_cmd_run)

    p_cmp = sub.add_parser("compare", help="Compare two sessions JSON")
    p_cmp.add_argument("--before", required=True)
    p_cmp.add_argument("--after", required=True)
    p_cmp.add_argument("--out", dest="output", required=True)
    p_cmp.add_argument("--keys", nargs="+", default=["q_m3s_ref", "Cd_ref", "V_ref", "Mach_ref"])
    p_cmp.add_argument("--dp-ref", dest="dp_ref", type=float, default=28.0)
    p_cmp.add_argument("--a-ref-mode", choices=("throat", "curtain", "eff"), default="eff")
    p_cmp.add_argument("--eff-mode", choices=("smoothmin", "logistic"), default="smoothmin")
    p_cmp.add_argument("--ld0", type=float, default=0.30)
    p_cmp.add_argument("--k", type=float, default=12.0)
    p_cmp.add_argument("--tol", type=float, default=5e-7)
    p_cmp.set_defaults(func=_cmd_compare)

    p_schema = sub.add_parser("schema", help="Write an example Session JSON")
    p_schema.add_argument("--out", dest="output", required=True)
    p_schema.set_defaults(func=_cmd_schema)

    args = p.parse_args(argv)
    rv = args.func(args)
    return int(rv)


if __name__ == "__main__":
    raise SystemExit(main())
