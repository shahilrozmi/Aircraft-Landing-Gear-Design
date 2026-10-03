B13F-2C — Left Bushing Inner-Edge Relief R2.0 mm

Base geometry: B13F-1B D44 reinforced 7075 head.
Modification: LEFT C63000/AMS4640 bushing only.
A 2.0 mm tangent circular fillet is applied to the inboard Ø50 OD edge.
Purpose: continue unloading the same inboard edge band after the validated R1.5 run reduced bronze VM to 618.94 MPa while the pressure peak remained on the same relieved-edge band.

Unchanged: Ø38 shaft bore, 30 mm sleeve nominal length, Ø60×3 flange, collar interfaces, right bushing, shaft, collars, and B13F-1B D44 head reinforcement.
Material removed from left bushing relative to unrelieved B13F-1B: 132.429 mm^3.
Approx. radial wall remaining at the extreme relieved end: 4.000 mm.
CAD validation: six valid solids on STEP re-import; no unintended positive-volume intersections.

ANSYS: delete any auto-generated Contact Regions; verify all 10 named contacts, especially CT_SHAFT_BUSH_L, CT_BUSH_HEAD_L, and CT_FLANGE_HEAD_L because left-bushing topology changed.
Recommended comparison mesh: B13F head transition 0.75 mm and active left-contact sizing 1.5 mm, subject to Student numerical limit.
Primary outputs: left-bushing VM max/location, CT_BUSH_HEAD_L pressure max/average/location, head VM max, total deformation.
Comparison targets from R1.5: 618.94 MPa bushing VM; 742.82 MPa contact-pressure max; 440.81 MPa head VM; 3.9567 mm total deformation.
