# Formulas reference

The source of truth is `src/iop_flow/formulas.py`. Highlights:

- Conversions
  - CFM ↔ m³/s: cfm_to_m3s, m3s_to_cfm
  - inches H₂O ↔ Pa: in_h2o_to_pa, pa_to_in_h2o
  - °C/°F → K: C_to_K, F_to_K
- Referencing flow to conditions
  - flow_referenced: Q* = Q_meas * sqrt(dp*/dp_meas) * sqrt(rho_meas/rho*)
  - flow_to_28inH2O: convenience to 28" with AirState
- Geometry
  - area_curtain(d_valve, lift), area_throat(d_throat, d_stem), ld_ratio(lift, d_valve)
- Effective area
  - area_eff_smoothmin(a_curtain, a_throat, n=6)
  - area_eff_logistic(a_curtain, a_throat, ld, ld0=0.30, k=12)
- Cd and velocities
  - cd(q, a_ref, dp, rho), cd_SAE(...)
  - velocity_from_flow(q, area)
  - mach_from_velocity(v, T), speed_of_sound(T)
  - velocity_pitot(dp_pitot, rho, c_probe=1)
- Swirl/tumble
  - swirl_ratio_from_wheel_rpm(rpm_wheel, bore, q)
  - swirl_number_discrete(...), tumble_number_discrete(...)
- Engine coupling
  - engine_volumetric_flow(displ_L, rpm, ve)
  - rpm_limited_by_flow(q_head, displ_L, ve)
  - rpm_from_csa(A_avg, displ_L, ve, v_target)
  - mach_at_min_csa(q, a_min, T)

Assumptions and notes
- Flowbench regime assumed weakly compressible; Cd/velocity use SI.
- 28" H₂O referencing is standard; air density via simple humidity model.
- Use realistic ranges: 0.4 <= Cd <= ~1.2, Mach < ~0.7 for intake ports in typical cases.
