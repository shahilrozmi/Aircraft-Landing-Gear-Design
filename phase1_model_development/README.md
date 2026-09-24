# Phase 1 Model Development Archive

These scripts are retained as **historical engineering evidence**, not as the current source of truth.

For current/frozen Phase 1 results, use:

- `../phase1_loads/phase1_loads.py`
- `../phase1_loads/phase1_dynamics.py`
- `../phase1_loads/phase1_load_envelope.csv`
- `../phase1_loads/phase1_dynamic_robustness.csv`

The archived scripts all execute successfully in the current audit environment, but they represent the model-development chain that led to the frozen consolidated model.

## What each archived script shows

- `landing_dynamic_v1.py` — V0.3 predecessor: 1-DOF energy-equivalent oleo model, hand-analysis targets, gas sizing, and smooth hydraulic metering. Useful for showing how the 205 mm target stroke and 10.301 -> 9.742 mm metering schedule were established. Superseded by the 2-DOF model for final landing loads.
- `landing_dynamic_v04_2dof.py` — V0.4 2-DOF sprung/unsprung tire-oleo model. Reproduces the accepted nominal result (206.338 mm stroke, 23.800 kN ground reaction, 23.038 kN strut force), extension-stop release, energy balance, and 20/30/40 kg unsprung-mass sensitivity.
- `landing_dynamic_v05_robustness.py` — V0.5 robustness study. Contains the unsprung-mass, sink-speed, **tire-stiffness**, and retained-lift sweeps plus selected combined robustness corners. The tire-stiffness sweep and combined corner studies are useful development evidence and are not all duplicated in the consolidated `phase1_dynamics.py`.
- `landing_dynamic_v05b_virtual_stroke.py` — V0.5b zero-lift virtual-stroke diagnostic. Reproduces the accepted 3.048 m/s zero-lift demand (240.779 mm stroke, 28.284 kN ground reaction, 27.781 kN strut force) and also evaluates the 1.10 Vd zero-lift case (248.258 mm demanded stroke).

## Interpretation rule

If an archived development result differs in framing or screening status from the frozen Phase 1 sources, the files in `phase1_loads/` govern. Do not use this archive to retune the frozen model unless the project is deliberately reopened.
