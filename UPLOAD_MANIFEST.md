# Upload Manifest

This is the curated upload set. The original local project archive remains untouched.

## Authoritative / latest code revisions

- `phase1_loads/phase1_loads.py`
- `phase1_loads/phase1_dynamics.py`
- `phase2_structures/phase2_traceability_audit_v04.py`
- `phase2_structures/phase2_traceability_v1_freeze_update.py`
- `phase2_structures/phase2e1_lower_end_architecture_v04.py`
- `phase2_structures/phase2e2_oleo_cavity_packaging_v03.py`
- `phase2_structures/phase2e2_metering_upper_head_layout_v04.py`
- `phase2_structures/phase2e2_metering_law_comparison_v03.py`
- `phase2_structures/phase2e2b_upper_head_closure_audit_v03.py`
- `phase2_structures/phase2e2c_fluid_continuity_closure_finalize_v01.py`
- `phase2_structures/phase2e2_v1_release_audit.py`
- `phase2_structures/phase2e3a_upper_attachment_source_audit_v01.py`
- `phase2_structures/phase2e3a2_upper_attachment_fbd_transport_v01.py`
- `phase2_structures/phase2e3b1_trunnion_centerline_trade_v01.py`
- `phase2_structures/phase2e3b2_trunnion_coupled_sizing_v01.py`
- `phase2_structures/phase2e3b3_trunnion_shortlist_head_integration_v01.py`
- `phase2_structures/phase2e3b4_cross_trunnion_head_interface_v01.py`
- `phase2_structures/phase2e3b5_local_head_interface_screen_v01.py`
- `phase2_structures/phase2e3b5a_barrel_material_upper_neck_audit_v01.py`
- `phase2_structures/phase2e3b5b_upper_barrel_reinforcement_profile_v01.py`
- `phase2_structures/phase2e3b6_head_span_recoupling_v01.py`
- `phase2_structures/phase2e3b6a_working_candidate_local_refresh_v02.py`
- `phase2_structures/phase2e3b7_transition_kt_budget_trade_v02.py`
- `phase2_structures/phase2e3b7a_expanded_transition_robustness_trade_v01.py`
- `phase2_structures/phase2e3b7b_transition_fea_handoff_v01.py`
- `phase2_structures/phase2e3b8_transition_fea_load_package_v01.py`
- `phase2_structures/phase2e3b9_fea_convergence_closeout_v01.py`
- `phase2_structures/phase2e3b9a_large_deflection_closeout_v01.py`
- `phase2_structures/phase2e3b10_upper_head_trunnion_integration.py`
- `phase2_structures/phase2e3b10a_retention_architecture_closeout.py`
- `phase2_structures/phase2e3b11_upper_head_local_screens.py`
- `phase2_structures/phase2e3b12_generate_integrated_model.py`
- `phase2_structures/current_design/phase2e3b13b_bushing_interface_sizing.py`
- `phase2_structures/current_design/phase2e3b13b_v02r1_interference_fit_min_ligament_correction.py`
- `phase2_structures/current_design/phase2e3b13b_v03_axial_thrust_flange_sizing.py`
- `phase2_structures/current_design/phase2e3b13b_v04_central_relief_trade.py`
- `phase2_structures/current_design/phase2e3b13c_build_geometry_portable_v2.py`

## Critical current records / CAD artifacts

- `phase1_loads/phase1_load_envelope.csv`
- `phase1_loads/phase1_dynamic_robustness.csv`
- `phase2_structures/phase2e2_v1_release_report.txt`
- `phase2_structures/phase2_traceability_register_v1.csv`
- `phase2_structures/phase2_open_validation_items_v1.csv`
- `phase2_structures/phase2_traceability_v1_summary.txt`
- `phase2_structures/phase2e3b9_closeout_summary.txt`
- `phase2_structures/phase2e3b9a_closeout_summary.txt`
- `phase2_structures/phase2e3b10_summary.txt`
- `phase2_structures/phase2e3b10a_retention_summary.txt`
- `phase2_structures/phase2e3b11_summary.txt`
- `phase2_structures/phase2e3b12_generation_summary.txt`
- `phase2_structures/phase2e3b12_integrated_head_trunnion.step`
- `phase2_structures/current_design/B13A_shaft_head_interface_trade.md`
- `phase2_structures/current_design/phase2e3b13b_summary.txt`
- `phase2_structures/current_design/phase2e3b13b_v02r1_summary.txt`
- `phase2_structures/current_design/phase2e3b13b_v03_summary.txt`
- `phase2_structures/current_design/phase2e3b13b_v04_summary.txt`
- `phase2_structures/current_design/phase2e3b13c_geometry_validation.txt`
- `phase2_structures/current_design/phase2e3b13c_bushed_head_trunnion.step`

## Intentionally retained supporting analyses

- `phase1_model_development/` is retained as a clearly labeled **historical archive**. Its V0.3/V0.4/V0.5/V0.5b scripts all execute successfully and preserve useful development evidence that is not fully duplicated by the consolidated frozen script (especially the tire-stiffness sweep, selected robustness corners, and the 1.10 Vd zero-lift virtual-stroke case). `phase1_loads/phase1_dynamics.py` remains authoritative.
- Unique B1–B12 trade, audit, sizing, FEA-handoff and convergence files are retained even when they are not the final design, because they provide traceability for why the current design changed.
- CSV/TXT outputs belonging to retained analyses are included so results can be reviewed without rerunning every script.

## Intentionally excluded

- `phase2_structures/phase2_traceability_audit_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2_traceability_audit_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2_traceability_audit_v03.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e1_lower_end_architecture.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e1_lower_end_architecture_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e1_lower_end_architecture_v03.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_metering_law_comparison_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_metering_law_comparison_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_metering_upper_head_layout_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_metering_upper_head_layout_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_metering_upper_head_layout_v03.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_oleo_cavity_packaging_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2_oleo_cavity_packaging_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2b_upper_head_closure_audit_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e2b_upper_head_closure_audit_v02.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e3b6a_working_candidate_local_refresh_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e3b7_transition_kt_budget_trade_v01.py` — Superseded by a later revision of the same analysis.
- `phase2_structures/phase2e3b6a_candidate_comparison.csv` — Superseded by corrected Phase 2E3-B6A V0.2 contact/local-head outputs.
- `phase2_structures/phase2e3b6a_contact_distribution.csv` — Superseded by corrected Phase 2E3-B6A V0.2 contact/local-head outputs.
- `phase2_structures/phase2e3b6a_summary.txt` — Superseded by corrected Phase 2E3-B6A V0.2 contact/local-head outputs.
- `phase2_structures/phase2e3b6a_thrust_requirement.csv` — Superseded by corrected Phase 2E3-B6A V0.2 contact/local-head outputs.
- `phase2_structures/phase2e3b6a_working_local_head_screen.csv` — Superseded by corrected Phase 2E3-B6A V0.2 contact/local-head outputs.
- `phase2_structures/phase2e3b7a_working_profile.csv` — Empty artifact from a trade with no passing working profile.
- `phase2_structures/phase2_traceability_register.csv` — Pre-V1 traceability output superseded by *_v1 current register/open-items/summary.
- `phase2_structures/phase2_open_validation_items.csv` — Pre-V1 traceability output superseded by *_v1 current register/open-items/summary.
- `phase2_structures/phase2_traceability_summary.txt` — Pre-V1 traceability output superseded by *_v1 current register/open-items/summary.
- `phase2_structures/current_design/phase2e3b13b_v02_interference_fit_screen.py` — Superseded by V0.2R1 minimum-ligament correction.
- `phase2_structures/current_design/phase2e3b13b_v02_interference_sweep.csv` — Superseded by V0.2R1 minimum-ligament correction.
- `phase2_structures/current_design/phase2e3b13b_v02_summary.txt` — Superseded by V0.2R1 minimum-ligament correction.
- `phase2_structures/current_design/phase2e3b13c_build_geometry.py` — Superseded by portable_v2 geometry builder.
- `phase2_structures/current_design/phase2e3b13c_build_geometry_portable.py` — Superseded by portable_v2 geometry builder.
- `phase2_structures/current_design/phase2e3b12_integrated_head_trunnion(1).step` — Byte-identical duplicate of phase2_structures/phase2e3b12_integrated_head_trunnion.step.

## Major size reduction

- `phase2_structures/current_design/cq_env/` is **not included**. It was a Windows virtual environment with thousands of third-party files and accounted for essentially all of the ~1.2 GB original archive size. Recreate dependencies from `requirements.txt` instead.
- Python caches / compiled bytecode are excluded.

## Recommended reading order for continuation

1. `CURRENT_STATE.md`
2. `phase1_loads/phase1_load_envelope.csv` and `phase1_loads/phase1_dynamic_robustness.csv`
3. `phase1_model_development/README.md` only when reviewing Phase 1 design evolution; do not treat the archived scripts as authoritative.
4. `phase2_structures/phase2e2_v1_release_report.txt`
5. `phase2_structures/phase2_traceability_v1_summary.txt`
6. `phase2_structures/phase2e3b9_closeout_summary.txt` through `phase2e3b12_generation_summary.txt`
7. `phase2_structures/current_design/B13A_shaft_head_interface_trade.md`
8. current-design B13B corrected summaries and `phase2e3b13c_geometry_validation.txt`
9. `phase2_structures/current_design/phase2e3b13c_build_geometry_portable_v2.py` for the current CAD-generation implementation.
