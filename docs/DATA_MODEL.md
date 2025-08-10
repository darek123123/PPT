# Data Model (schemas.py)

All data classes are frozen and validated on creation. Unless noted, units are SI.

- AirConditions
  - p_tot [Pa] > 0, T [K] > 0, RH [0..1]
- Engine
  - displ_L [L] > 0, cylinders > 0, ve (optional, >=0)
- Geometry
  - bore_m, valve_int_m, valve_exh_m, throat_m > 0
  - stem_m >= 0 and < throat_m
  - port_volume_cc (optional, > 0)
  - port_length_m (optional, > 0)
  - seat_width_m (optional, > 0)
- LiftPoint (raw bench input, flowbench units)
  - lift_mm >= 0, q_cfm >= 0
  - dp_inH2O optional, if present > 0
  - swirl_rpm optional, >= 0
- FlowSeries
  - intake/exhaust: lists of LiftPoint; ordering is preserved
- CSAProfile (engine coupling)
  - min_csa_m2 optional > 0
  - avg_csa_m2 optional > 0
- Session
  - meta: Dict[str, Any], free-form
  - mode: Literal["baseline","after"]
  - air: AirConditions
  - engine: Engine
  - geom: Geometry
  - lifts: FlowSeries
  - csa: Optional[CSAProfile]

Conventions
- Geometry is in meters; port volume is in cubic centimeters (cc).
- Raw bench inputs: lift [mm], flow Q [CFM], depression ΔP [inches H2O], swirl [RPM].
- Everything computed uses SI internally.

Example JSON (short)
```json
{
  "meta": {"project": "example"},
  "mode": "baseline",
  "air": {"p_tot": 101325.0, "T": 293.15, "RH": 0.0},
  "engine": {"displ_L": 2.0, "cylinders": 4, "ve": 0.95},
  "geom": {
    "bore_m": 0.086, "valve_int_m": 0.046, "valve_exh_m": 0.040,
    "throat_m": 0.034, "stem_m": 0.007,
    "port_volume_cc": 180.0, "port_length_m": 0.110,
    "seat_angle_deg": 45.0, "seat_width_m": 0.0015
  },
  "lifts": {"intake": [
    {"lift_mm": 1.0, "q_cfm": 120.0, "dp_inH2O": 28.0},
    {"lift_mm": 2.0, "q_cfm": 175.0, "dp_inH2O": 28.0}
  ], "exhaust": []},
  "csa": {"min_csa_m2": 0.00095, "avg_csa_m2": 0.00120}
}
```
