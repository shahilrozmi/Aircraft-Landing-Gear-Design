# Aircraft Landing Gear Design

Preliminary design and structural analysis of an **oleo-pneumatic main landing gear** for a generic 4–6 seat light aircraft. The project combines aircraft load-case definition, nonlinear landing-dynamics simulation, structural sizing, analytical stress checks, CAD/STEP geometry generation, and FEA preparation using Python-based engineering tools.

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

The project is being developed progressively from aircraft-level loads to component-level structural sizing and detailed upper-head/trunnion design.

## Engineering Workflow

### Phase 1 — Aircraft Loads and Landing Dynamics

Phase 1 establishes the design loads and landing-energy model.

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

The `phase1_model_development/` directory preserves the model-development history and robustness studies. These files are retained for traceability but are **not** the authoritative frozen Phase 1 model.

### Phase 2 — Structural Design and Oleo Architecture

Phase 2 develops the preliminary structural architecture of the landing gear using the frozen Phase 1 loads.

Released preliminary oleo geometry includes:

- Outer barrel: **64 mm ID / 74 mm OD**
- Lower piston: **58 mm OD / 50 mm ID**
- Physical stroke: **230 mm**
- Equivalent orifice schedule: **10.301 → 9.742 mm**
- Fixed metering bore: **14 mm**

The structural work includes:

- piston sizing and buckling
- barrel pressure and combined-stress sizing
- bushing and gland load transfer
- gland/retainer architecture
- lower barrel boss sizing
- axle/spindle sizing
- upper trunnion sizing
- upper brace/link sizing
- packaging and overlap checks
- traceability and design-freeze audits

### Phase 2E3 — Upper Head and Trunnion Development

The current detailed design work focuses on the upper attachment and shaft/head interface.

Current architecture:

**7075-T6 upper head → C63000 / AMS 4640 bronze bushings → removable Ø38 mm 300M cross-pin → external airframe bearings**

Current B13 geometry:

- 7075 upper-head outer boss: **Ø106 mm × 78 mm**
- Head passage: **Ø50 mm THROUGH**
- Continuous 300M shaft: **Ø38 mm × 175 mm**
- Bronze sleeves: **Ø50 OD / Ø38 ID × 30 mm**
- Bronze flange: **Ø60 OD / Ø38 ID × 3 mm**
- Shaft-to-head radial clearance through the central relief: **6 mm**

The generated B13C STEP model contains **four separate physical bodies** and has been checked for zero solid interference.

## Structural Analysis Highlights

Selected current structural results include:

- Phase 2E2 preliminary architecture release: **PASS — 22/22 checks**
- B9 mesh-converged local transition FEA: **PASS**
- B9 ultimate peak von Mises stress: **469.18 MPa**
- B9 reported margin: **+0.219**
- B9A large-deflection sensitivity: preliminary nonlinear static sensitivity passed
- Current integrated trunnion working point: **150 mm span, Ø38 mm 300M shaft**
- B11 nominal upper-head static screen: **PASS**

These are preliminary engineering results and remain subject to later detailed validation, fatigue/fracture substantiation, production tolerancing, and certification-level analysis.

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
    ├── structural sizing and audit scripts
    ├── CSV/TXT engineering outputs
    ├── STEP geometry
    └── current_design/
        ├── B13 trade and sizing records
        ├── corrected interface analyses
        └── current B13C geometry generator and STEP model
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

The principal Phase 1 analyses can then be run from the repository root:

```bash
python phase1_loads/phase1_loads.py
python phase1_loads/phase1_dynamics.py
```

Phase 2 contains multiple design-stage scripts rather than one monolithic program. See `CURRENT_STATE.md` and `UPLOAD_MANIFEST.md` for the current analysis chain and authoritative revisions.

## Current Status

The project has completed:

- aircraft-level landing-gear load cases
- nonlinear tire/oleo landing dynamics
- preliminary oleo architecture
- component-level structural sizing
- preliminary upper-attachment structural design
- local transition FEA and convergence work
- current upper-head / bronze-bushing / 300M-shaft CAD generation

### Current next step

**B13C nonlinear contact FEA** of the:

- 7075-T6 upper head
- two C63000 bronze bushings
- continuous 300M shaft

The next analysis will refine bushing reaction distribution, local contact stresses, and interface behavior including fit/interference sensitivity.

## Remaining Work

Major later-stage items include:

- nonlinear contact FEA
- production fit and running-clearance definition
- lubrication, wear, and fretting assessment
- fatigue and fracture analysis
- final shaft-retention hardware
- detailed tolerances and surface finishes
- corrosion protection
- complete airframe attachment definition
- certification / regulatory load mapping
- Develop the finalized landing-gear assembly and detailed component geometry in CATIA V5
- optional retraction-mechanism development

## Project Notes

`CURRENT_STATE.md` is the recommended starting point for the latest engineering status.

`UPLOAD_MANIFEST.md` identifies the authoritative code revisions and explains which superseded development files were intentionally excluded.

This repository represents an **educational preliminary engineering design project**, not a certified aircraft component design.
