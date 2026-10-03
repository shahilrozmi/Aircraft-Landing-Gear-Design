B13F-3B — Left Bronze Thrust-Flange Thickening (3.5 mm)

WHY THIS REVISION
B13F-3A's annular-only collar seat reduced bronze VM but the solved CT_COLLAR_FLANGE_L pressure went to essentially zero and the left collar VM went to essentially zero, proving the axial thrust path unloaded. B13F-3B therefore abandons annular-only loading and restores the validated full annular collar-to-flange interface.

GEOMETRY
Base: B13F-2B R1.5 left-bushing relief.
Head: D44 reinforced 7075 head unchanged.
Left bushing: R1.5 OD relief retained. Bronze thrust flange thickened from 3.0 mm to 3.5 mm by adding 0.50 mm on the collar-facing/outboard side. Head-side thrust-seat plane is unchanged.
Left collar: original full annular contact face retained (r=19..29 mm); entire collar translated 0.50 mm outward (-X) so the collar face remains coincident with the new bronze flange face.
Shaft/right bushing/right collar unchanged.
Package growth on left side: 0.50 mm.

LOAD-PATH INTENT
Preserve the validated shaft -> left collar -> bronze flange -> 7075 head thrust stack while increasing bronze flange section thickness to reduce bending/shear near the bore, where the R1.5 hotspot remained.

ANSYS IMPORTANT
Branch from the validated B13F-2B R1.5 .wbpj. Replace geometry with this STEP. Delete any auto-generated generic Contact Regions. Because both the left bushing flange and left collar moved/changed topology, recheck CT_COLLAR_FLANGE_L, CT_COLLAR_SHAFT_L, CT_FLANGE_HEAD_L, CT_BUSH_HEAD_L and CT_SHAFT_BUSH_L. CT_COLLAR_FLANGE_L should use the ORIGINAL FULL annular collar face against the full bronze flange face; do not use the B13F-3A narrow outer ring scoping.

Recommended mesh: keep the accepted 0.75 mm head-transition refinement and 1.5 mm left-contact refinement if within Student limits.
Primary outputs: left bronze VM, CT_COLLAR_FLANGE_L pressure, CT_BUSH_HEAD_L pressure, left collar VM, 7075 head VM, total deformation.

Reference R1.5 values before thrust-path experiments: bronze VM 618.94 MPa; CT_BUSH_HEAD_L pressure 742.82 MPa; head VM 440.81 MPa; deformation 3.9567 mm.
