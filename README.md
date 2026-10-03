# Aircraft Landing Gear Design

Preliminary design and structural analysis of an **oleo-pneumatic main landing gear** for a generic 4–6 seat light aircraft. The project combines aircraft load-case definition, nonlinear landing-dynamics simulation, structural sizing, CAD/STEP geometry generation, and progressively refined FEA-oriented structural development using Python-based engineering tools.

## Project Overview

The design focuses on one single-wheel main landing gear leg for a generic low-wing tricycle aircraft.

### Baseline aircraft and landing-gear definition

- Aircraft mass: **1700 kg**
- Wheelbase: **2.35 m**
- Main-gear track: **3.20 m**
- Detailed main-gear wheel lateral offset: **120 mm**
- Static loaded tire radius: **175 mm**
- Physical oleo stroke: **230 mm**
- Static oleo sag: **50 mm**
- Structural ultimate factor: **1.5**

The project is developed progressively from aircraft-level loads and landing energy to component sizing, physical upper-attachment architecture, CAD geometry, FEA load-path validation, local mesh refinement, and geometry redesign.

## Engineering Workflow

### Phase 1 — Aircraft Loads and Landing Dynamics

The authoritative Phase 1 implementation is contained in:

- `phase1_loads/phase1_loads.py`
- `phase1_loads/phase1_dynamics.py`

The landing model uses a **2-DOF tire/oleo representation** with gas-spring and hydraulic-damping behavior.

Selected results:

| Quantity | Result |
|---|---:|
| Nominal peak oleo compression | **206.338 mm** |
| Nominal peak tire deflection | **44.961 mm** |
| Nominal peak ground reaction | **23.800 kN** |
| Nominal peak strut force | **23.038 kN** |
| Zero-lift demanded oleo stroke | **240.779 mm** |
| Zero-lift peak ground reaction | **28.284 kN** |
| Zero-lift peak strut force | **27.781 kN** |

`phase1_model_development/` preserves the development history and robustness studies. Those files are retained for traceability but are **not** the authoritative frozen Phase 1 model.

### Phase 2 — Structural Design and Oleo Architecture

Released preliminary oleo geometry includes:

- Outer barrel: **64 mm ID / 74 mm OD**
- Lower piston: **58 mm OD / 50 mm ID**
- Physical stroke: **230 mm**
- Equivalent orifice schedule: **10.301 → 9.742 mm**
- Fixed metering bore: **14 mm**

Phase 2 includes piston, barrel, bushing/gland, boss, axle, trunnion, brace, overlap/packaging, and traceability work. The repository retains the analytical scripts and associated CSV/TXT engineering records used to develop the architecture.

### Phase 2E3 — Upper Attachment, Physical Brace, and Horn/Clevis Development

The upper attachment evolved beyond the earlier B13C four-body baseline. The validated **B13F-3C** parent is now the retained source geometry for the later physical horn/clevis work.

Current B13F-3C parent highlights:

- 7075-T6 upper-head outer boss: **Ø106 mm × 78 mm**
- Continuous 300M shaft: **Ø38 mm × 175 mm**
- Head side passage: **Ø50 mm**
- Central passage: **Ø44 mm** over the retained center region
- Minimum shaft/head radial gap in the central relief: **3 mm**
- C63000 / AMS 4640 bronze bushings
- Separate 300M thrust collars
- **6 physical bodies** in the validated STEP parent
- Current-parent validation: **54 PASS / 0 FAIL**

The B14 work then physicalized the brace load path and added the source-connected horn/clevis geometry.

Selected B14 milestones:

- B14A source-connected combined brace reaction: **Mx = -16.856 kN·m**
- B14B preliminary physical-brace ultimate force: **67.424 kN**
- B14B-9 physical head/horn/clevis CAD: **62 PASS / 0 FAIL** geometry checks
- B14B-10 global physical-brace FEA load path: **closed** for global reaction/load-path validation and large-deflection sensitivity
- B14B-11: horn/head root transition and local-stress refinement

## Current Root-Transition / FEA Status

The current detailed work is the **B14B-11 root transition**.

### R6 development reference

A local R6 root-mesh sequence reached a design-stage result of **407.52 MPa** at 2.0 mm local sizing with stable global response. This was used as an intermediate reference while the radius trade continued.

### R8 local submodel

A later quadratic local-submodel study showed that the R8 peak was substantially more severe than the earlier coarse full-model screens suggested.

Retained R8 local result:

- 1.50 mm: **442.62 MPa**
- 1.00 mm: **697.48 MPa**
- 0.75 mm: **732.45 MPa**
- 1.00 → 0.75 mm peak change: **+5.014%**
- 0.75 mm fillet-average VM: **91.817 MPa**
- Maximum deformation: **0.73252 mm**

The 0.75 mm solution is treated as **near-converged / mesh-stabilized**, not as strictly mathematically converged. Under the generic project 7075 static screen, the **732.45 MPa** local peak is unacceptable and requires a geometry response.

### F2 reinforced-root redesign

The first B14B-11F redesign retained the basic root architecture but enlarged the section:

- **F2_BALANCED:** **95 × 115 mm** root section, **R12** blend
- Added mass versus the R8 head: approximately **0.615 kg**

A 1.0 mm local submodel gave:

- **24,801 nodes / 14,487 elements**
- Maximum deformation: **0.73252 mm**
- Fillet-average VM: **77.072 MPa** (**16.1% lower** than the retained R8 average)
- Fillet-scoped peak VM: **1995.7 MPa**

The extreme peak occurs at the termination of the new blend. Therefore **F2 is rejected as-is**, while the **95 × 115 mm reinforced-section concept is retained**.

## Current Next Step

**B14B-11F / F2B root redesign**:

- retain the **95 × 115 mm** reinforced root concept
- replace the abrupt constant-radius blend termination with a smoother/tangent transition
- rerun the **1.0 mm quadratic local screen**
- only refine to **0.75 mm** after the local peak becomes physically credible and the transition geometry is accepted
- update the full six-body parent only after the local redesign passes the screening gate

## Repository Structure

```text
Aircraft-Landing-Gear-Design/
├── README.md
├── CURRENT_STATE.md
├── UPLOAD_MANIFEST.md
├── FILE_INVENTORY.csv
├── requirements.txt
│
├── phase1_loads/
│   ├── phase1_loads.py
│   ├── phase1_dynamics.py
│   └── frozen CSV outputs
│
├── phase1_model_development/
│   ├── README.md
│   └── historical Phase 1 model revisions
│
└── phase2_structures/
    ├── preliminary component sizing / architecture
    ├── E2 release and traceability records
    ├── B13 / B13F upper-head and trunnion development
    ├── B14 physical-brace / horn-clevis development
    ├── B14B-10 FEA handoff and closeout records
    ├── B14B-11 radius trade / local-submodel / convergence work
    ├── B14B-11F redesign candidates
    └── current_design/
        └── retained B13-era interface sizing records
```

## Running the Python Analyses

Create a virtual environment and install the retained dependencies:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Principal Phase 1 analyses:

```bash
python phase1_loads/phase1_loads.py
python phase1_loads/phase1_dynamics.py
```

Phase 2 contains multiple design-stage scripts rather than one monolithic program. See `CURRENT_STATE.md` and `UPLOAD_MANIFEST.md` for the current analysis chain and authoritative revisions.

## Remaining Work

Major later-stage items include:

- F2B root-transition redesign and local FEA screen
- final horn/head root geometry selection and full-parent confirmation solve
- local stress convergence of the accepted geometry
- production fit and running-clearance definition
- lubrication, wear, and fretting assessment
- fatigue and fracture analysis
- final shaft-retention hardware
- detailed tolerances and surface finishes
- corrosion protection
- complete airframe attachment definition
- certification / regulatory load mapping
- finalized landing-gear assembly and detailed component geometry in CATIA V5
- optional retraction-mechanism development

## Project Notes

`CURRENT_STATE.md` is the recommended starting point for the latest engineering status.

`UPLOAD_MANIFEST.md` identifies the retained/current analysis chain and explains the curation rules used for GitHub.

This repository represents an **educational preliminary engineering design project**, not a certified aircraft component design.
