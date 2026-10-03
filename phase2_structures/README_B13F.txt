B13F — Upper Trunnion Head Geometry Refinement
Source: phase2e3b13g1_bushed_head_trunnion_with_thrust_collars.step

All B13G1 external hardware and validated axial-thrust path are unchanged:
  Ø106 7075 head external envelope (unchanged)
  Ø38 300M shaft (unchanged)
  Ø50×Ø38×30 bronze bushings and Ø60×3 flanges (unchanged)
  left/right 300M thrust collars (unchanged)

Refinement: add 7075 material only in the otherwise-open central Ø50 passage between the two bushing sleeves.
A 1 mm axial gap is retained from each bushing inner end; a 4 mm smooth taper transitions from Ø50 to the reduced central relief.
This preserves external packaging and prevents the new 7075 web from becoming a bushing axial stop.

B13F_1A_D46: central relief Ø46 mm; shaft radial clearance 4.0 mm; added 7075 volume 6466.1 mm^3.
B13F_1B_D44: central relief Ø44 mm; shaft radial clearance 3.0 mm; added 7075 volume 9510.2 mm^3.
B13F_1C_D42: central relief Ø42 mm; shaft radial clearance 2.0 mm; added 7075 volume 12428.3 mm^3.

Recommended first ANSYS run: B13F_1B_D44. It is the middle case (3 mm radial shaft clearance).
Use exactly the B13G combined ultimate load/contact setup and compare head VM max/hotspot location against 676.11 MPa.
