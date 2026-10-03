# Landing Gear Design Project — Current Repository State

This repository is a curated engineering snapshot for continued development, reproducibility, and traceability. Large machine-specific Python environments, caches, and superseded artifacts are intentionally excluded.

## Authoritative project state

### Phase 1 — frozen loads and landing dynamics

Use `phase1_loads/phase1_loads.py` and `phase1_loads/phase1_dynamics.py` as the authoritative Phase 1 sources.

Frozen load-envelope highlights:

- LC1 / LC2 / LC3 vertical limit per detailed main: **25.02 kN**; ultimate **37.53 kN**
- LC4 vertical limit per main: **11.0922 kN** with lateral **±8.34 kN**
- LC5 limit: **Fx = -8.87376 kN**, **Fz = 11.0922 kN**
- LC5 ultimate: **Fx = -13.31064 kN**, **Fz = 16.6383 kN**

Landing-dynamics highlights:

- Nominal peak oleo stroke: **206.338 mm**
- Nominal peak tire deflection: **44.961 mm**
- Nominal peak ground reaction: **23.800 kN**
- Nominal peak strut force: **23.038 kN**
- Zero-lift virtual-stroke demand: **240.779 mm**
- Zero-lift peak ground reaction: **28.284 kN**
- Zero-lift peak strut force: **27.781 kN**

`phase1_model_development/` remains a non-authoritative development-history archive.

### Phase 2E2 — released preliminary oleo architecture

`phase2_structures/phase2e2_v1_release_report.txt` remains the authoritative E2 release record.

Release status: **PASS (22/22 checks)** at preliminary architecture / structural-screen level.

Released working geometry / hydraulic architecture:

- barrel: **64 mm ID / 74 mm OD**
- piston: **58 mm OD / 50 mm ID**
- physical stroke: **230 mm**
- smooth clamped-linear equivalent orifice: **10.301 → 9.742 mm over 205 mm**
- fixed metering bore: **14 mm**
- preliminary E3 interface: **498.780 mm above U**

### Phase 2E3 — upper-head / trunnion evolution

B1–B12 remain the retained design history leading to the B13 family.

The previous GitHub snapshot stopped at the **B13C** four-body geometry. That geometry is now historical rather than the active CAD parent.

#### Current retained parent — B13F-3C

The validated parent for the later B14 horn/clevis work is:

`phase2_structures/phase2e3_b13f_3c_d44_r1p5_t3p5_left_collar_partial_relief.step`

Key geometry:

- 7075-T6 upper-head boss: **Ø106 × 78 mm**
- continuous 300M shaft: **Ø38 × 175 mm**
- head side passage: **Ø50 mm**
- central passage: **Ø44 mm** over the retained center region
- minimum shaft/head radial gap: **3 mm**
- right bronze sleeve: **Ø50/Ø38 × 30 mm**
- left bronze flange: **Ø60/Ø38 × 3.5 mm**
- separate left/right 300M thrust collars
- physical bodies: **6**
- validation: **54 PASS / 0 FAIL**

The validation record explicitly supersedes the old B13C model as the current parent for B14B-9.

## B14 physical-brace / horn-clevis development

### B14A — source-connected ANSYS reaction record

`phase2e3b14a_freeze_record.csv` is the load-source handoff for later B14B work.

Combined brace reaction:

- **Mx = -16.856 kN·m**
- force + moment + pressure superposition residual: **0.001260%**

### B14B — physical brace

The physical brace architecture converts the frozen B14A moment reaction into an axial two-force member.

Working values:

- effective Mx arm: **250 mm**
- pin-to-pin length: **350 mm**
- ultimate brace force: **67.424 kN**
- tube working section: **25 mm OD × 3 mm wall**

### B14B-9 — physical horn / clevis CAD

`phase2e3b14b9_head_horn_clevis_v01.step` adds the source-connected horn/clevis to the validated B13F-3C parent.

- equivalent root section entering the horn: **85 × 95 mm**
- pin bore: **Ø18 mm**
- geometry validation: **62 PASS / 0 FAIL**
- gate: `PASS_B14B9_GEOMETRY_FOR_LOCAL_FEA`

### B14B-10 — physical-brace FEA closeout

B14B-10 is **closed for global physical-brace load-path validation and large-deflection sensitivity**.

The large-deflection sensitivity showed only small changes in global response, including approximately:

- brace-force magnitude: **-0.0283%**
- maximum deformation: **+0.1484%**
- maximum von Mises stress: **+0.0144%**

The sharp horn/head root remained the governing local hotspot, so the next work moved to local transition refinement rather than treating the B14B-10 local maximum as final.

## B14B-11 — horn/head root transition refinement

### R6 development reference

The R6 local root-mesh sequence reached:

- 3.0 mm: **411.23 MPa**
- 2.5 mm: **408.46 MPa**
- 2.0 mm: **407.52 MPa**

The 2.5 → 2.0 mm change was **0.230%**, so R6 was considered converged enough for that design stage.

### R8 local submodel

Later targeted refinement showed that the raw full-model root maximum was not a reliable converged local stress. A quadratic local-submodel workflow was therefore created.

Retained R8 convergence sequence:

- 1.50 mm: **442.62 MPa**
- 1.00 mm: **697.48 MPa**
- 0.75 mm: **732.45 MPa**

At 0.75 mm:

- nodes/elements: **19,081 / 11,045**
- fillet-average VM: **91.817 MPa**
- maximum total deformation: **0.73252 mm**
- 1.00 → 0.75 mm peak change: **+5.014%**

Disposition:

- treat **732.45 MPa** as the current conservative R8 local design-screen peak
- describe it as **near-converged / mesh-stabilized**, not strictly converged
- the generic 7075 project static screen is exceeded
- the R8 geometry therefore requires redesign or a later allowable-based justification before any final design freeze

## Current design-response checkpoint — B14B-11F

Two reinforced-root concepts were generated from the R8 response target.

### F2_BALANCED

- root section: **95 × 115 mm**
- nominal blend: **R12 mm**
- added mass vs R8 head: approximately **0.615 kg**

1.0 mm local-screen result:

- mesh: **24,801 nodes / 14,487 elements**
- maximum deformation: **0.73252 mm**
- fillet-average VM: **77.072 MPa**
- fillet peak VM: **1995.7 MPa**
- peak location: approximately **(40.753, 37.334, 994.066) mm**

The average stress decreased by about **16.1%** from the retained R8 result while the local peak rose dramatically. The peak sits at/near the termination of the redesigned blend, identifying a local transition problem rather than a global section-load increase.

### Current disposition

**F2 V1 is rejected as-is.**

The **95 × 115 mm reinforced-root concept is retained** because the section response is promising, but the abrupt constant-radius blend termination must be replaced.

## Immediate next engineering step

**Design F2B**:

1. retain the **95 × 115 mm** root concept
2. replace the abrupt constant-radius blend termination with a smoother/tangent transition
3. preserve the established local-submodel cut/mapping convention
4. rerun the candidate at **1.0 mm quadratic local sizing**
5. inspect peak location, peak/average behavior, displacement consistency, and geometry credibility
6. only proceed to **0.75 mm** refinement after the 1.0 mm screen is physically credible
7. after local acceptance, update the full six-body parent and run the parent confirmation solve

F3 remains a fallback concept; it has not superseded the retained F2 section concept at this checkpoint.

## File-use rule

When multiple files cover the same analysis, prefer the highest/current revision identified in `UPLOAD_MANIFEST.md` and the explicit closeout/final-assessment records. Do not restore superseded development versions merely because they exist in an older local archive.
