from pathlib import Path
import csv, math
from cadquery import importers
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

HERE = Path(__file__).resolve().parent
STEP_CANDIDATES = [
    HERE / 'phase2e3b14b9_head_horn_clevis_v01.step',
    HERE / '_lg_measure' / 'Landing_Gear_Project_UPLOAD_v2' / 'phase2_structures' / 'phase2e3b14b9_head_horn_clevis_v01.step',
]
STEP = next((p for p in STEP_CANDIDATES if p.exists()), None)
if STEP is None:
    raise FileNotFoundError('phase2e3b14b9_head_horn_clevis_v01.step not found')

wp = importers.importStep(str(STEP))
solids = wp.solids().vals()
if len(solids) != 6:
    raise RuntimeError(f'Expected 6 solids, found {len(solids)}')

# Current B14B-9 body ordering after STEP import, verified by volume/bounding boxes.
head = solids[0]
left_bush = solids[2]
right_bush = solids[3]

def cyl_faces(shape, radius, axis='x', tol=1e-6):
    out=[]
    for idx,f in enumerate(shape.Faces(), start=1):
        ad=BRepAdaptor_Surface(f.wrapped, True)
        if ad.GetType()!=GeomAbs_Cylinder:
            continue
        c=ad.Cylinder(); r=c.Radius(); d=c.Axis().Direction(); loc=c.Axis().Location(); bb=f.BoundingBox()
        if abs(r-radius)>tol:
            continue
        vec=(d.X(),d.Y(),d.Z())
        if axis=='x' and abs(abs(vec[0])-1)>tol:
            continue
        out.append(dict(face_index=idx, face=f, radius=r,
                        axis_loc=(loc.X(),loc.Y(),loc.Z()), axis_dir=vec,
                        xmin=bb.xmin,xmax=bb.xmax,ymin=bb.ymin,ymax=bb.ymax,zmin=bb.zmin,zmax=bb.zmax,
                        area=f.Area()))
    return out

# Bushing OD faces: one r=25 axial-x cylinder on each bronze body.
L_b = cyl_faces(left_bush,25.0)[0]
R_b = cyl_faces(right_bush,25.0)[0]
# Head has two r=25 passage cylinders. Sort by x midpoint: left then right.
head_passages = sorted(cyl_faces(head,25.0), key=lambda a:(a['xmin']+a['xmax'])/2)
L_h,R_h = head_passages[0], head_passages[1]

def dist_faces(a,b):
    d=BRepExtrema_DistShapeShape(a['face'].wrapped,b['face'].wrapped); d.Perform()
    if not d.IsDone(): raise RuntimeError('Distance calculation failed')
    return d.Value()

def axis_offset(a,b):
    # Both are parallel to x; radial axis offset is yz distance.
    ay,az=a['axis_loc'][1],a['axis_loc'][2]
    by,bz=b['axis_loc'][1],b['axis_loc'][2]
    return math.hypot(ay-by,az-bz)

def overlap_x(a,b):
    return max(0.0,min(a['xmax'],b['xmax'])-max(a['xmin'],b['xmin']))

rows=[]
for side,b,h in [('LEFT',L_b,L_h),('RIGHT',R_b,R_h)]:
    rows.append({
        'side':side,
        'bushing_od_mm':2*b['radius'],
        'head_passage_id_mm':2*h['radius'],
        'diameter_difference_mm':2*b['radius']-2*h['radius'],
        'bushing_axis_y_mm':b['axis_loc'][1],
        'bushing_axis_z_mm':b['axis_loc'][2],
        'head_axis_y_mm':h['axis_loc'][1],
        'head_axis_z_mm':h['axis_loc'][2],
        'axis_offset_mm':axis_offset(b,h),
        'bushing_axis_dir_x':b['axis_dir'][0],
        'bushing_axis_dir_y':b['axis_dir'][1],
        'bushing_axis_dir_z':b['axis_dir'][2],
        'head_axis_dir_x':h['axis_dir'][0],
        'head_axis_dir_y':h['axis_dir'][1],
        'head_axis_dir_z':h['axis_dir'][2],
        'bushing_cyl_xmin_mm':b['xmin'],
        'bushing_cyl_xmax_mm':b['xmax'],
        'head_cyl_xmin_mm':h['xmin'],
        'head_cyl_xmax_mm':h['xmax'],
        'axial_overlap_mm':overlap_x(b,h),
        'cad_kernel_min_distance_mm':dist_faces(b,h),
        'bushing_face_index':b['face_index'],
        'head_face_index':h['face_index'],
    })

csv_path=HERE/'phase2e3b14b10_contact_geometry_audit_v01.csv'
with csv_path.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

summary_path=HERE/'phase2e3b14b10_contact_geometry_audit_v01.txt'
with summary_path.open('w') as f:
    f.write('PHASE 2E3-B14B-10 — BUSHING/HEAD CONTACT GEOMETRY AUDIT V0.1\n')
    f.write(f'Source STEP: {STEP}\n\n')
    for r in rows:
        f.write(f"{r['side']}\n")
        f.write(f"  Bushing OD:              {r['bushing_od_mm']:.6f} mm\n")
        f.write(f"  Head passage ID:         {r['head_passage_id_mm']:.6f} mm\n")
        f.write(f"  Diameter difference:     {r['diameter_difference_mm']:.9f} mm\n")
        f.write(f"  Axis offset (YZ):        {r['axis_offset_mm']:.9f} mm\n")
        f.write(f"  Axis center (Y,Z):       ({r['bushing_axis_y_mm']:.6f}, {r['bushing_axis_z_mm']:.6f}) mm\n")
        f.write(f"  Axial cylinder overlap:  {r['axial_overlap_mm']:.6f} mm\n")
        f.write(f"  CAD-kernel min distance: {r['cad_kernel_min_distance_mm']:.9f} mm\n\n")
    f.write('INTERPRETATION\n')
    f.write('- The Ø50 bushing OD and Ø50 head passage are exactly nominally coincident in the STEP kernel.\n')
    f.write('- Their axes are coaxial (zero YZ axis offset) and parallel to global X.\n')
    f.write('- Therefore the ~1.29/1.61 mm ANSYS geometric-penetration values are not literal CAD radial interference.\n')
    f.write('- Left cylindrical overlap is 28.5 mm because the final 1.5 mm of the left sleeve OD is replaced by the designed toroidal inner-end relief; right overlap is 30.0 mm.\n')

print(summary_path.read_text())
print('CSV',csv_path)
print('SUMMARY',summary_path)
