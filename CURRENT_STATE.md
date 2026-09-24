# Landing Gear Design Project — Current Upload Snapshot

This repository contains the curated current working project state for continued development, reproducibility, and archival.
It intentionally removes large machine-specific Python environments and code revisions that were replaced by corrected/newer versions.

## Authoritative project state

### Phase 1 — frozen loads and landing dynamics

Use `phase1_loads/phase1_loads.py` and `phase1_loads/phase1_dynamics.py` as the authoritative Phase 1 sources.
The latter explicitly documents/reproduces the final validated 2-DOF tire/oleo landing model and includes both the nominal V0.4 and zero-lift V0.5b diagnostic.

`phase1_model_development/` is also retained as a non-authoritative history archive. It preserves the V0.3 -> V0.4 -> V0.5 -> V0.5b development chain, including tire-stiffness and combined-corner robustness studies that are not all duplicated in the frozen consolidated script. See its `README.md` before using those files.

Frozen load-envelope highlights from `phase1_load_envelope.csv`:
- LC1 / LC2 / LC3 vertical limit per detailed main: **25.02 kN**; ultimate **37.53 kN**.
- LC4 vertical limit per main: **11.0922 kN** with lateral **±8.34 kN**.
- LC5 limit: **Fx = -8.87376 kN**, **Fz = 11.0922 kN**; ultimate: **Fx = -13.31064 kN**, **Fz = 16.6383 kN**.

Landing-dynamics highlights from `phase1_dynamic_robustness.csv`:
- Nominal (30 kg unsprung): peak oleo stroke **206.338 mm**, tire deflection **44.961 mm**, ground reaction **23.800 kN**, strut force **23.038 kN**.
- Zero-lift virtual-stroke diagnostic: demanded oleo stroke **240.779 mm**, ground reaction **28.284 kN**, strut force **27.781 kN**.

### Phase 2E2 — released preliminary oleo architecture

`phase2_structures/phase2e2_v1_release_report.txt` is the authoritative E2 release record.
Release status: **PASS (22/22 checks)** at preliminary architecture / structural-screen level.

Released working geometry / hydraulic architecture:
- barrel: **64 mm ID / 74 mm OD**
- piston: **58 mm OD / 50 mm ID**
- physical stroke: **230 mm**
- smooth clamped-linear equivalent orifice: **10.301 -> 9.742 mm over 205 mm**
- fixed metering bore: **14 mm**
- preliminary E3 interface: **498.780 mm above U**

`phase2_traceability_register_v1.csv`, `phase2_open_validation_items_v1.csv`, and `phase2_traceability_v1_summary.txt` are the current pre-E3 traceability set. The pre-E3 disposition is **PASS**; remaining open items are intentionally retained for later-detail validation.

### Phase 2E3 — upper-head / trunnion development

The retained B1–B12 files document the design chain and supporting evidence. Important current milestones include:
- B9 mesh-converged local transition FEA: **PASS**; ultimate peak VM **469.18 MPa**, margin **+0.219**.
- B9A large-deflection sensitivity: preliminary static nonlinear sensitivity **passes**; retain B9 linear as conservative reference.
- B10 working trunnion integration: **150 mm span**, **38 mm 300M shaft**.
- B10A selected retention architecture removes the central keeper cross-hole concept from the main shaft/head region.
- B11 nominal upper-head static screen: **PASS**.
- B12 generated the 4-body integrated head/trunnion STEP baseline used as the source for B13 geometry development.

### Current design — Phase 2E3-B13C

Working architecture (`current_design/B13A_shaft_head_interface_trade.md`):

`7075-T6 head -> replaceable C63000 / AMS 4640 bronze bushings -> removable Ø38 mm 300M cross-pin -> external airframe bearings`

Current B13 working geometry after the corrected B13B trade and B13C CAD generation:
- 7075 upper-head outer boss: **Ø106 mm × 78 mm high**
- head passage: **Ø50 mm THROUGH**
- continuous 300M shaft: **Ø38 mm × 175 mm**
- each bronze sleeve: **Ø50 OD / Ø38 ID × 30 mm**
- each bronze flange: **Ø60 OD / Ø38 ID × 3 mm**
- shaft-to-7075 radial clearance in central relief: **6 mm**
- four separate physical bodies in the B13C STEP; validation reports zero solid intersection volume.

Important correction: the original B13B V0.2 interference-fit screen used the side ligament as the minimum ligament. It is intentionally omitted from this upload; **V0.2R1** is the corrected interference-fit screen and is the version to use.

## Current next engineering step

The project is positioned for **B13C nonlinear contact FEA** of the 7075 head, two bronze bushings, and continuous 300M shaft. The contact model should resolve actual bushing reaction distribution and local stresses, with interference/fit sensitivity cases. Production fit, running clearance, lubrication/wear/fretting, fatigue/fracture, final retention hardware, tolerances, corrosion protection, and certification mapping remain open.

## File-use rule

When two files appear to cover the same analysis, prefer the highest/current revision identified in `UPLOAD_MANIFEST.md`. Do not resurrect the removed development versions unless specifically doing a history/debug audit.
