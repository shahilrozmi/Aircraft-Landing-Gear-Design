B13F-3A — Left Thrust-Collar Annular Load-Path Alignment

WHY THIS CANDIDATE
The exact R2.0 bronze VM maximum was at X=-45.595315, Y=5.530394, Z=993.707803 mm.
For the CAD geometry, the bronze thrust flange spans X=-46.6921 to -43.6921 mm and the Ø38 bore radius is 19 mm. The hotspot radius is ~19.858 mm, placing it inside the flange and only ~0.86 mm from the bore. Thus the governing bronze hotspot is a thrust-flange/bore load-transfer problem, not the inboard OD relief itself.

DESIGN
Base: B13F-2B R1.5 bushing relief (the best simple-radius bronze VM result).
Head: B13F-1B D44 reinforced head unchanged.
Left bushing: unchanged R1.5 relief.
Left 300M thrust collar: bushing-facing inner annulus recessed 0.50 mm. Full-depth recess extends to r=24.5 mm, then a 1.0 mm radial taper returns to the original face at r=25.5 mm. The remaining flat thrust-contact ring is r=25.5..29.0 mm.

LOAD-PATH INTENT
Existing collar thrust face spans r=19..29 mm, while the bronze flange is supported by the head only outside the Ø50 head bore, approximately r=25..30 mm. B13F-3A moves collar-to-flange thrust entry outward so axial force enters the bronze flange much closer to the head-supported annulus, reducing radial bending/shear through the flange near the bore.
For LC5 ultimate Fx=13.31064 kN, ideal uniform pressure on the remaining r=25.5..29 mm ring is only ~22.21 MPa, so the reduced flat area remains ample as a preliminary contact footprint.

ANSYS IMPORTANT
Delete auto-generated Contact Regions. Verify all 10 named contacts. CT_COLLAR_FLANGE_L MUST be rescoped to the NEW FLAT OUTER ANNULAR COLLAR FACE ONLY (r≈25.5..29 mm) against the bronze flange face. Do not scope the recessed inner annulus or taper. CT_COLLAR_SHAFT_L may also need face remapping because the collar topology changed. Other left bushing contacts should retain the validated R1.5 setup.
Recommended mesh: head transition 0.75 mm, active left-contact sizing 1.5 mm, subject to Student numerical limit.
Primary outputs: left bronze VM, CT_COLLAR_FLANGE_L pressure, CT_BUSH_HEAD_L pressure, 300M left-collar VM, 7075 head VM, total deformation.
Reference R1.5 values: bronze VM 618.94 MPa; CT_BUSH_HEAD_L pressure 742.82 MPa; head VM 440.81 MPa; deformation 3.9567 mm.
