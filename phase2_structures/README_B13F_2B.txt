B13F-2B — Left Bushing Inner-Edge Relief R1.5 mm

Base geometry: B13F-1B D44 reinforced 7075 head.
Modification: LEFT C63000/AMS4640 bushing only.
A 1.5 mm tangent circular fillet is applied to the inboard Ø50 OD edge.
Purpose: further unload the same inboard edge band that remained at ~685 MPa bronze VM and ~719 MPa contact pressure in the validated B13F-2A R1.0 run.

Unchanged: Ø38 shaft bore, 30 mm sleeve nominal length, Ø60×3 flange, collar interfaces, right bushing, shaft, collars, and B13F-1B D44 head reinforcement.
Material removed from left bushing relative to unrelieved B13F-1B: 74.830 mm^3.
Approx. radial wall remaining at the extreme relieved end: 4.500 mm.
CAD validation: six valid solids on STEP re-import; no unintended positive-volume intersections.

ANSYS: delete any auto-generated Contact Regions; then verify the 10 named contacts, especially CT_SHAFT_BUSH_L and CT_BUSH_HEAD_L because left-bushing topology changed.
Recommended comparison mesh: B13F head transition 0.75 mm and active left-contact sizing 1.5 mm, subject to Student numerical limit.
Primary outputs: left-bushing VM max/location, CT_BUSH_HEAD_L pressure max/average, head VM max, total deformation.
