from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Literal, Optional, Tuple, List

from iop_flow.schemas import AirConditions, Engine, Geometry
from iop_flow.schemas import Session, FlowSeries, LiftPoint, CSAProfile
from iop_flow import formulas as F


DisplayUnits = Literal["workshop_pl"]
Mode = Literal["baseline", "after", "compare"]


def parse_float_pl(text: str) -> float:
    # Accept Polish comma decimal and ignore spaces (including NBSP) as thousand separators
    cleaned = text.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    return float(cleaned)


# Unit conversion helpers (workshop-friendly units)
def lift_m_to_mm(x_m: list[float]) -> list[float]:
    return [v * 1000.0 for v in x_m]


def q_m3s_to_cfm(x_m3s: list[float]) -> list[float]:
    return [F.m3s_to_cfm(v) for v in x_m3s]


@dataclass
class WizardState:
    meta: Dict[str, Any] = field(
        default_factory=lambda: {
            "project_name": "",
            "client": "",
            "date_iso": "",
            "mode": "baseline",
            "display_units": "workshop_pl",
            "notes": None,
        }
    )

    air_dp_ref_inH2O: float = 28.0
    air_dp_meas_inH2O: Optional[float] = None

    air: Optional[AirConditions] = None

    engine: Optional[Engine] = None
    engine_target_rpm: Optional[int] = None

    # Geometry (SI: meters, degrees, cc)
    geometry: Optional[Geometry] = None

    # Plan
    lifts_intake_mm: List[float] = field(default_factory=list)
    lifts_exhaust_mm: List[float] = field(default_factory=list)
    dp_per_point_inH2O: Dict[Tuple[str, float], float] = field(default_factory=dict)
    will_enter_swirl: bool = False

    # Measurements buffers (raw UI rows)
    measure_intake: List[Dict[str, Any]] = field(default_factory=list)
    measure_exhaust: List[Dict[str, Any]] = field(default_factory=list)

    # CSA (SI)
    csa_min_m2: Optional[float] = None
    csa_avg_m2: Optional[float] = None
    engine_v_target: Optional[float] = None  # [m/s]

    # Optional buffers for example points (not shown in UI)
    points_int: List[Dict[str, Any]] = field(default_factory=list)
    points_exh: List[Dict[str, Any]] = field(default_factory=list)

    # Aggregated results from steps (e.g., HP)
    results: Dict[str, Any] = field(default_factory=dict)

    # Optional tuning/export section (runners/plenum calculators)
    tuning: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.air, AirConditions):
            d["air"] = {"p_tot": self.air.p_tot, "T": self.air.T, "RH": self.air.RH}
        if isinstance(self.engine, Engine):
            d["engine"] = {
                "displ_L": self.engine.displ_L,
                "cylinders": self.engine.cylinders,
                "ve": self.engine.ve,
            }
        if isinstance(self.geometry, Geometry):
            d["geometry"] = {
                "bore_m": self.geometry.bore_m,
                "valve_int_m": self.geometry.valve_int_m,
                "valve_exh_m": self.geometry.valve_exh_m,
                "throat_m": self.geometry.throat_m,
                "stem_m": self.geometry.stem_m,
                "port_volume_cc": self.geometry.port_volume_cc,
                "port_length_m": self.geometry.port_length_m,
                "seat_angle_deg": self.geometry.seat_angle_deg,
                "seat_width_m": self.geometry.seat_width_m,
            }
        return d

    # Step 5/6 helpers as methods
    def plan_intake(self) -> List[float]:
        return list(self.lifts_intake_mm)

    def plan_exhaust(self) -> List[float]:
        return list(self.lifts_exhaust_mm)

    def dp_for_point(self, side: Literal["intake", "exhaust"], lift_mm: float) -> Optional[float]:
        return self.dp_per_point_inH2O.get((side, round(lift_mm, 3)))

    def build_session_from_wizard_for_compute(self) -> Session:
        """
        Build Session from current wizard state for live compute.
        Use measure_* as LiftPoints (dp None stays None). csa=None.
        """
        # Basic guards; raise if mandatory parts missing to catch earlier steps
        if self.air is None or self.engine is None or self.geometry is None:
            raise ValueError("Missing air/engine/geometry in wizard state")

        def to_points(rows: List[Dict[str, Any]]) -> List[LiftPoint]:
            # sort by lift and keep last for duplicates
            by_lift: Dict[float, Dict[str, Any]] = {}
            for r in rows:
                try:
                    lift_v = round(float(r.get("lift_mm", 0.0)), 3)
                    q_v = float(r.get("q_cfm", 0.0))
                except Exception:
                    continue
                dp_v = r.get("dp_inH2O")
                swirl_v = r.get("swirl_rpm")
                by_lift[lift_v] = {
                    "lift_mm": max(lift_v, 0.0),
                    "q_cfm": max(q_v, 0.0),
                    "dp_inH2O": (float(dp_v) if dp_v is not None else None),
                    "swirl_rpm": (float(swirl_v) if swirl_v is not None else None),
                }
            lifts_sorted = sorted(by_lift.keys())
            return [LiftPoint(**by_lift[lift]) for lift in lifts_sorted]

        series = FlowSeries(
            intake=to_points(self.measure_intake),
            exhaust=to_points(self.measure_exhaust),
        )

        mode_raw = str(self.meta.get("mode", "baseline")).lower()
        mode = "baseline" if mode_raw not in ("baseline", "after") else mode_raw

        return Session(
            meta=dict(self.meta),
            mode=mode,  # type: ignore[assignment]
            air=self.air,
            engine=self.engine,
            geom=self.geometry,
            lifts=series,
            csa=None,
        )

    def set_csa_from_ui(
        self,
        min_csa_mm2: Optional[float],
        avg_csa_mm2: Optional[float],
        v_target: Optional[float],
    ) -> None:
        """Accept mm^2 from UI; convert to m^2 and store along with engine_v_target."""
        self.csa_min_m2 = (
            (min_csa_mm2 / 1e6) if (min_csa_mm2 is not None and min_csa_mm2 > 0) else None
        )
        self.csa_avg_m2 = (
            (avg_csa_mm2 / 1e6) if (avg_csa_mm2 is not None and avg_csa_mm2 > 0) else None
        )
        self.engine_v_target = v_target if (v_target is not None and v_target > 0) else None

    def build_session_for_run_all(self) -> Session:
        """
        Build full Session with meta/mode, air, engine, geometry, FlowSeries (from measure_*),
        and CSAProfile if CSA values are available.
        """
        if self.air is None or self.engine is None or self.geometry is None:
            raise ValueError("Missing air/engine/geometry in wizard state")

        def to_points(rows: List[Dict[str, Any]]) -> List[LiftPoint]:
            by_lift: Dict[float, Dict[str, Any]] = {}
            for r in rows:
                try:
                    lift_v = round(float(r.get("lift_mm", 0.0)), 3)
                    q_v = float(r.get("q_cfm", 0.0))
                except Exception:
                    continue
                dp_v = r.get("dp_inH2O")
                swirl_v = r.get("swirl_rpm")
                by_lift[lift_v] = {
                    "lift_mm": max(lift_v, 0.0),
                    "q_cfm": max(q_v, 0.0),
                    "dp_inH2O": (float(dp_v) if dp_v is not None else None),
                    "swirl_rpm": (float(swirl_v) if swirl_v is not None else None),
                }
            lifts_sorted = sorted(by_lift.keys())
            return [LiftPoint(**by_lift[lift]) for lift in lifts_sorted]

        series = FlowSeries(
            intake=to_points(self.measure_intake),
            exhaust=to_points(self.measure_exhaust),
        )

        mode_raw = str(self.meta.get("mode", "baseline")).lower()
        mode = "baseline" if mode_raw not in ("baseline", "after") else mode_raw

        csa_profile = None
        if self.csa_min_m2 is not None or self.csa_avg_m2 is not None:
            csa_profile = CSAProfile(min_csa_m2=self.csa_min_m2, avg_csa_m2=self.csa_avg_m2)

        return Session(
            meta=dict(self.meta),
            mode=mode,  # type: ignore[assignment]
            air=self.air,
            engine=self.engine,
            geom=self.geometry,
            lifts=series,
            csa=csa_profile,
        )

    # Presets
    def apply_defaults_preset(self) -> None:
        """Populate wizard state with a realistic default configuration and data."""
        # Meta
        self.meta.update(
            {
                "project_name": "2.0L head (preset)",
                "client": "Example",
                "date_iso": "",
                "mode": "baseline",
                "display_units": "workshop_pl",
                "notes": None,
            }
        )
        # Bench & Air
        self.air_dp_ref_inH2O = 28.0
        self.air_dp_meas_inH2O = 28.0
        self.air = AirConditions(p_tot=101_325.0, T=F.C_to_K(20.0), RH=0.0)
        # Engine
        self.engine = Engine(displ_L=2.0, cylinders=4, ve=0.95)
        self.engine_target_rpm = 6500
        # Geometry (mm -> m)
        self.geometry = Geometry(
            bore_m=86.0 / 1000.0,
            valve_int_m=34.0 / 1000.0,
            valve_exh_m=29.0 / 1000.0,
            throat_m=27.0 / 1000.0,
            stem_m=7.0 / 1000.0,
            port_volume_cc=220.0,
            port_length_m=150.0 / 1000.0,
            seat_angle_deg=45.0,
            seat_width_m=1.5 / 1000.0,
        )
        # Plan lifty 1..9 mm, dp 28"
        self.lifts_intake_mm = [float(x) for x in range(1, 10)]
        self.lifts_exhaust_mm = [float(x) for x in range(1, 10)]
        self.dp_per_point_inH2O = {}
        for lift in self.lifts_intake_mm:
            self.dp_per_point_inH2O[("intake", round(lift, 3))] = 28.0
        for lift in self.lifts_exhaust_mm:
            self.dp_per_point_inH2O[("exhaust", round(lift, 3))] = 28.0
        self.will_enter_swirl = True
        # Measurements default example values (CFM @ 28"). Intake with swirl RPM; Exhaust = 0.78 * intake
        int_q = [22, 35, 48, 60, 70, 78, 84, 83, 82]
        int_sw = [200, 300, 400, 500, 600, 700, 820, 900, 950]
        self.points_int = [
            {"lift_mm": lift, "q_cfm": q, "dp_inH2O": 28.0, "swirl_rpm": s}
            for lift, q, s in zip(self.lifts_intake_mm, int_q, int_sw)
        ]
        exh_q = [int(round(q * 0.78)) for q in int_q]
        self.points_exh = [
            {"lift_mm": lift, "q_cfm": qx, "dp_inH2O": 28.0, "swirl_rpm": None}
            for lift, qx in zip(self.lifts_exhaust_mm, exh_q)
        ]
        # Apply into measurement buffers
        self.measure_intake = [dict(r) for r in self.points_int]
        self.measure_exhaust = [dict(r) for r in self.points_exh]
        # CSA and target velocity
        self.set_csa_from_ui(min_csa_mm2=520.0, avg_csa_mm2=600.0, v_target=100.0)


# Validators


def is_valid_step_start(s: WizardState) -> bool:
    m = s.meta
    return bool(str(m.get("project_name", "")).strip()) and bool(str(m.get("client", "")).strip())


def is_valid_step_bench(s: WizardState) -> bool:
    if s.air_dp_ref_inH2O is None or s.air_dp_ref_inH2O <= 0:
        return False
    if s.air is None:
        return False
    return s.air.p_tot > 0 and 0.0 <= s.air.RH <= 1.0


def is_valid_step_engine(s: WizardState) -> bool:
    if s.engine is None:
        return False
    if s.engine.displ_L <= 0 or s.engine.cylinders <= 0:
        return False
    if s.engine.ve is not None and s.engine.ve < 0:
        return False
    if s.engine_target_rpm is not None and s.engine_target_rpm <= 0:
        return False
    return True


# Geometry helpers


def _sorted_unique(xs: List[float]) -> List[float]:
    seen: Dict[float, None] = {}
    out: List[float] = []
    for v in sorted(xs):
        if v in seen:
            continue
        seen[v] = None
        out.append(v)
    return out


def is_valid_step_geometry(s: WizardState) -> bool:
    g = s.geometry
    if g is None:
        return False
    if not (
        g.bore_m > 0 and g.valve_int_m > 0 and g.valve_exh_m > 0 and g.throat_m > 0 and g.stem_m > 0
    ):
        return False
    if not (g.stem_m < g.throat_m):
        return False
    if not (g.valve_int_m > g.throat_m and g.valve_exh_m > g.throat_m):
        return False
    if g.port_volume_cc is not None and g.port_volume_cc < 0:
        return False
    if g.port_length_m is not None and g.port_length_m <= 0:
        return False
    if g.seat_width_m is not None and g.seat_width_m < 0:
        return False
    return True


def is_valid_step_plan(s: WizardState) -> bool:
    def _is_increasing(xs: List[float]) -> bool:
        return all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))

    if not s.lifts_intake_mm:
        return False
    if not _is_increasing(sorted(s.lifts_intake_mm)):
        return False
    if s.lifts_exhaust_mm and not _is_increasing(sorted(s.lifts_exhaust_mm)):
        return False
    for (side, lift), dp in s.dp_per_point_inH2O.items():
        if dp is not None and dp <= 0:
            return False
    return True


def gen_grid(start_mm: float, stop_mm: float, step_mm: float) -> List[float]:
    if step_mm <= 0:
        return []
    if stop_mm < start_mm:
        start_mm, stop_mm = stop_mm, start_mm
    vals: List[float] = []
    v = start_mm
    # include stop with rounding to 3 decimals
    while v <= stop_mm + 1e-9:
        vals.append(round(v, 3))
        v += step_mm
    return _sorted_unique(vals)


def parse_rows(text: str) -> List[Tuple[float, float, Optional[float], Optional[float]]]:
    """
    Accept 2-4 columns per row (tab/semicolon/whitespace separated):
    - 2 cols: lift_mm, q_cfm
    - 3 cols: lift_mm, q_cfm, dp_inH2O
    - 4 cols: lift_mm, q_cfm, dp_inH2O, swirl_rpm
    Skip empty lines; validate: lift>=0, q>=0, dp>0(if given), swirl>=0(if given).
    """
    out: List[Tuple[float, float, Optional[float], Optional[float]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Preserve empty columns when semicolons are used; otherwise split on whitespace
        if ";" in line:
            parts = [p.strip() for p in line.split(";")]
        else:
            tmp = line.replace("\t", " ")
            parts = [p for p in tmp.split() if p]
        # Limit to at most 4 columns
        if len(parts) > 4:
            parts = parts[:4]
        if len(parts) < 2:
            continue
        try:
            # parse_float_pl accepts both ',' and '.' decimals and ignores spaces/nbsp
            lift = parse_float_pl(parts[0])
            q = parse_float_pl(parts[1])
            dp = parse_float_pl(parts[2]) if len(parts) >= 3 and parts[2].strip() != "" else None
            swirl = parse_float_pl(parts[3]) if len(parts) >= 4 and parts[3].strip() != "" else None
        except Exception:
            continue
        if lift < 0 or q < 0:
            continue
        if dp is not None and dp <= 0:
            continue
        if swirl is not None and swirl < 0:
            continue
        out.append((round(lift, 3), q, dp, swirl))
    return out


def set_geometry_from_ui(
    s: WizardState,
    *,
    bore_mm: float,
    valve_int_mm: float,
    valve_exh_mm: float,
    throat_mm: float,
    stem_mm: float,
    seat_angle_deg: Optional[float] = None,
    seat_width_mm: Optional[float] = None,
    port_volume_cc: Optional[float] = None,
    port_length_mm: Optional[float] = None,
) -> None:
    try:
        s.geometry = Geometry(
            bore_m=bore_mm / 1000.0,
            valve_int_m=valve_int_mm / 1000.0,
            valve_exh_m=valve_exh_mm / 1000.0,
            throat_m=throat_mm / 1000.0,
            stem_m=stem_mm / 1000.0,
            port_volume_cc=port_volume_cc if port_volume_cc is not None else None,
            port_length_m=port_length_mm / 1000.0 if port_length_mm is not None else None,
            seat_angle_deg=seat_angle_deg if seat_angle_deg is not None else 45.0,
            seat_width_m=seat_width_mm / 1000.0 if seat_width_mm is not None else None,
        )
    except Exception:
        # Keep invalid inputs in state as None so validators can reflect failure
        s.geometry = None


def set_plan_from_ui(
    s: WizardState,
    *,
    intake: List[float],
    exhaust: List[float],
    dp_map: Dict[Tuple[str, float], float],
    will_swirl: bool,
) -> None:
    s.lifts_intake_mm = _sorted_unique([round(x, 3) for x in intake])
    s.lifts_exhaust_mm = _sorted_unique([round(x, 3) for x in exhaust])
    # keep only keys that match lifts
    new_dp: Dict[Tuple[str, float], float] = {}
    for k, v in dp_map.items():
        side, lift = k
        if side not in ("intake", "exhaust"):
            continue
        if side == "intake" and lift in s.lifts_intake_mm and v is not None:
            new_dp[(side, lift)] = v
        if side == "exhaust" and lift in s.lifts_exhaust_mm and v is not None:
            new_dp[(side, lift)] = v
    s.dp_per_point_inH2O = new_dp
    s.will_enter_swirl = bool(will_swirl)
