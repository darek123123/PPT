# Architecture

This repo is a small, typed Python core for flowbench/head-porting calculations. It favors
simple, explicit modules with strict typing and unit tests. All physics work in SI units; raw
bench inputs are normalized early.

- Modules and roles
  - formulas: Pure SI formulas. Conversions, geometry, Cd, velocities/Mach, swirl/tumble,
    engine coupling (RPM/CSA). Stateless and deterministic.
  - schemas: Frozen dataclasses that define input/output shapes. Validate ranges on init.
  - io_json: Serialize/deserialize a Session to/from JSON.
  - normalize: Convert raw bench data (CFM/"H2O/mm) to SI and reference (28" + chosen air).
  - compute_point: Per-point metrics at reference: areas, Cd, velocities, Mach, L/D, SR.
  - compute_series: Build series per side (intake/exhaust), align by lift, compute E/I.
  - engine_link: Tie series to engine context (RPM from head flow, RPM from CSA, Mach@minCSA).
  - compare: Align two series by lift, compute percent deltas, build overlays.
  - api: Thin glue: run_all (entire session) and run_compare (before/after).
  - cli: Batch runner over JSON (run / compare / schema example).

- Main data flow

  Raw bench JSON -> schemas.Session
      |
      v
  normalize (to SI + 28")
      |
      v
  compute_point / compute_series (A, Cd, V, Mach, SR)
      |
      v
  engine_link (RPM limits, Mach@minCSA)
      |
      v
  api.run_all / api.run_compare (JSON-ready results)

- Contracts and units
  - Inputs: raw LiftPoint use flowbench units (lift[mm], q[CFM], dp["H2O], swirl[RPM]).
  - Everything else is SI (m, m^2, m^3/s, Pa, K).
  - normalize converts and references flows to 28" H2O and chosen air conditions.
  - compute_series preserves series order and exposes reference metrics per lift.

- Stable API surface
  - api.run_all(session, ...) -> Dict[str, Any]
  - api.run_compare(before, after, ...) -> Dict[str, Any]
  - io_json.read_session(PathLike) -> Session / io_json.write_session(PathLike, Session)

- Error handling and validation
  - schemas enforce >0 / >=0 invariants; bad inputs raise ValueError early.
  - formulas raise on invalid domains (e.g., A<=0, dp<=0).
  - Higher layers assume validated inputs and keep ordering stable.

- Test strategy
  - Sanity tests for formulas
  - Roundtrips and validators for schemas/io
  - Normalization invariants and ordering
  - Per-series metrics and E/I
  - Engine coupling, comparisons, API, CLI smoke
