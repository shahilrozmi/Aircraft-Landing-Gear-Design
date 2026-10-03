B13F-3C — Mild Partial Inner Relief of Left 300M Thrust Collar

BASE
B13F-3B geometry: D44 reinforced 7075 head; left C63000 bushing with R1.5 OD relief and 3.5 mm bronze thrust flange; original validated collar/flange architecture restored.

CHANGE
Only the left 300M collar thrust face is modified.
- r=19..22 mm: recessed 0.12 mm from the original thrust datum.
- r=22..23 mm: smooth linear/conical transition back to the original datum.
- r=23..29 mm: broad flat thrust-contact annulus retained at the ORIGINAL axial datum.
- retained flat contact area: 980.18 mm^2.
- ideal uniform pressure under LC5 ultimate Fx=13.31064 kN: 13.58 MPa.

WHY
B13F-3B preserved the thrust path but the remaining bronze VM hotspot (609.75 MPa) sat only about 1.5 mm outside the Ø38 bore, indicating local flange bending/shear from inward thrust application. B13F-3C mildly biases the collar thrust load outward without the aggressive 0.5 mm / r25.5 annular-only seat used in failed B13F-3A.

ANSYS
Branch from the validated B13F-3B .wbpj. Replace geometry with this STEP. Delete any automatically generated generic contacts. Recheck CT_COLLAR_FLANGE_L and CT_COLLAR_SHAFT_L because the collar topology changed. For CT_COLLAR_FLANGE_L, scope the CONTACT side to ONLY the retained outer flat collar annulus r=23..29 mm; do not include the recessed r19..22 face or the r22..23 taper. The bronze flange target remains its flat collar-facing annulus.

Keep the accepted 0.75 mm head-transition and 1.5 mm left-contact mesh controls if within Student limits.

Primary acceptance checks:
1) CT_COLLAR_FLANGE_L remains engaged through full load (nonzero pressure at t=1 s).
2) left collar 300M VM is nonzero and reasonable.
3) bronze VM improves from B13F-3B 609.75 MPa toward/below the working 568.5 MPa ultimate-equivalent target.
4) head VM remains near ~442 MPa and total deformation near ~4.0 mm.
