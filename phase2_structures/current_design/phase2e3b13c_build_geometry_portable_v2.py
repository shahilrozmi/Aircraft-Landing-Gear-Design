from pathlib import Path
import math
import cadquery as cq

# -------------------------------------------------------------------------
# PORTABLE FILE PATHS — V2
# -------------------------------------------------------------------------
# Usage options:
#
# 1) Put the source STEP next to this script and run normally, OR
# 2) Pass the full source STEP path as the first command-line argument:
#
#    .\cq_env\Scripts\python.exe .\phase2e3b13c_build_geometry_portable_v2.py "C:\full\path\source.step"
#
import sys

HERE = Path(__file__).resolve().parent

def find_source_step():
    # A. Explicit path supplied by the user
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1].strip('"')).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(
                "The STEP path supplied on the command line does not exist:\n"
                f"  {p}"
            )
        return p

    # B. Preferred exact filename beside the script
    preferred = HERE / "phase2e3b12_integrated_head_trunnion(1).step"
    if preferred.exists():
        return preferred

    # C. Search script folder + a few parent project folders
    search_roots = [HERE]
    p = HERE
    for _ in range(4):
        p = p.parent
        search_roots.append(p)

    patterns = [
        "phase2e3b12_integrated_head_trunnion*.step",
        "phase2e3b12_integrated_head_trunnion*.STEP",
    ]

    matches = []
    for root in search_roots:
        for pattern in patterns:
            matches.extend(root.glob(pattern))
            matches.extend(root.glob(f"**/{pattern}"))

    # Keep unique existing files
    unique = []
    seen = set()
    for m in matches:
        try:
            r = m.resolve()
        except Exception:
            continue
        if r.exists() and r not in seen:
            seen.add(r)
            unique.append(r)

    if unique:
        if len(unique) > 1:
            print("Multiple possible source STEP files found:")
            for i, m in enumerate(unique, start=1):
                print(f"  [{i}] {m}")
            print(f"Using the first match: {unique[0]}")
        return unique[0]

    raise FileNotFoundError(
        "Could not find the B12 source STEP automatically.\n\n"
        "Either:\n"
        "  1. Copy the STEP next to this script, or\n"
        "  2. Run this script with the full STEP path in quotes.\n\n"
        "Example:\n"
        r'  .\cq_env\Scripts\python.exe .\phase2e3b13c_build_geometry_portable_v2.py "C:\Users\Shahi\Downloads\phase2e3b12_integrated_head_trunnion(1).step"'
    )

SOURCE = find_source_step()

OUTPUT = HERE / "phase2e3b13c_bushed_head_trunnion.step"
REPORT = HERE / "phase2e3b13c_geometry_validation.txt"

print(f"Using source STEP: {SOURCE}")
print(f"Output STEP will be: {OUTPUT}")

# Current B12/B13 working geometry [mm]
SHAFT_AXIS_Z = 1012.78
HEAD_BOSS_RADIUS = 53.0       # Ø106 vertical cylindrical upper head
HEAD_BOSS_HEIGHT = 78.0       # z = 973.78 to 1051.78
SHAFT_D = 38.0
HEAD_PASSAGE_D = 50.0
BUSH_OD = 50.0
BUSH_ID = 38.0
BUSH_SLEEVE_L = 30.0
FLANGE_OD = 60.0
FLANGE_T = 3.0

# The flange is normal to X, but the existing head exterior is a Ø106 cylinder about Z.
# A Ø60 flange therefore needs a spotface/counterbore. The seat plane is placed at
# the tangent-safe X position for the full ±30 mm flange radius in Y:
#     x_seat = sqrt(R_head^2 - R_flange^2)
FLANGE_R = FLANGE_OD / 2.0
x_seat = math.sqrt(HEAD_BOSS_RADIUS**2 - FLANGE_R**2)
spotface_depth_at_y0 = HEAD_BOSS_RADIUS - x_seat
central_gap = 2.0 * (x_seat - BUSH_SLEEVE_L)

model = cq.importers.importStep(str(SOURCE))
solids = model.solids().vals()
if len(solids) != 4:
    raise RuntimeError(f'Expected 4 B12 solids, found {len(solids)}')

# Largest body is the 7075 head/barrel.
solids_sorted = sorted(solids, key=lambda s: s.Volume(), reverse=True)
head = solids_sorted[0]

# -----------------------------------------------------------------------------
# 1) Enlarge/rebuild the horizontal shaft passage to Ø50 through the head.
# This completely removes the old Ø38 bore and its B12C mouth chamfers.
# -----------------------------------------------------------------------------
through = cq.Solid.makeCylinder(
    HEAD_PASSAGE_D / 2.0,
    220.0,
    cq.Vector(-110.0, 0.0, SHAFT_AXIS_Z),
    cq.Vector(1.0, 0.0, 0.0),
)
head_b13 = head.cut(through)

# -----------------------------------------------------------------------------
# 2) Create left/right Ø60 spotfaces on the curved Ø106 head exterior.
# These are required so the flanged bushings have real planar thrust seats.
# -----------------------------------------------------------------------------
left_spotface = cq.Solid.makeCylinder(
    FLANGE_R,
    110.0 - x_seat,
    cq.Vector(-110.0, 0.0, SHAFT_AXIS_Z),
    cq.Vector(1.0, 0.0, 0.0),
)
right_spotface = cq.Solid.makeCylinder(
    FLANGE_R,
    110.0 - x_seat,
    cq.Vector(x_seat, 0.0, SHAFT_AXIS_Z),
    cq.Vector(1.0, 0.0, 0.0),
)
head_b13 = head_b13.cut(left_spotface).cut(right_spotface)

# -----------------------------------------------------------------------------
# 3) Replace the old 3-piece Ø38 shaft surrogate with one continuous 300M shaft.
# Original imported extents were X = -87.5 ... +87.5 mm.
# -----------------------------------------------------------------------------
shaft = cq.Solid.makeCylinder(
    SHAFT_D / 2.0,
    175.0,
    cq.Vector(-87.5, 0.0, SHAFT_AXIS_Z),
    cq.Vector(1.0, 0.0, 0.0),
)

# -----------------------------------------------------------------------------
# 4) Two separate flanged AMS 4640 bushings.
# Sleeve is Ø50/Ø38 x 30 mm; flange is Ø60/Ø38 x 3 mm.
# -----------------------------------------------------------------------------
def annular_cylinder(od, id_, length, start_x):
    outer = cq.Solid.makeCylinder(
        od / 2.0, length,
        cq.Vector(start_x, 0.0, SHAFT_AXIS_Z),
        cq.Vector(1.0, 0.0, 0.0),
    )
    inner = cq.Solid.makeCylinder(
        id_ / 2.0, length + 0.2,
        cq.Vector(start_x - 0.1, 0.0, SHAFT_AXIS_Z),
        cq.Vector(1.0, 0.0, 0.0),
    )
    return outer.cut(inner)

# Left: flange outside (more negative X), sleeve inward (+X)
left_sleeve = annular_cylinder(BUSH_OD, BUSH_ID, BUSH_SLEEVE_L, -x_seat)
left_flange = annular_cylinder(FLANGE_OD, BUSH_ID, FLANGE_T, -x_seat - FLANGE_T)
left_bushing = left_sleeve.fuse(left_flange)

# Right: sleeve inward from x = x_seat - L to x = x_seat; flange outside (+X)
right_sleeve = annular_cylinder(BUSH_OD, BUSH_ID, BUSH_SLEEVE_L, x_seat - BUSH_SLEEVE_L)
right_flange = annular_cylinder(FLANGE_OD, BUSH_ID, FLANGE_T, x_seat)
right_bushing = right_sleeve.fuse(right_flange)

# -----------------------------------------------------------------------------
# 5) Validate solids / overlaps.
# -----------------------------------------------------------------------------
parts = {
    'HEAD_BARREL_7075': head_b13,
    'SHAFT_300M_CONTINUOUS': shaft,
    'BUSHING_LEFT_AMS4640': left_bushing,
    'BUSHING_RIGHT_AMS4640': right_bushing,
}

for name, shp in parts.items():
    if not shp.isValid():
        raise RuntimeError(f'{name} is not a valid solid')

pairs = [
    ('head-shaft', head_b13, shaft),
    ('head-left_bushing', head_b13, left_bushing),
    ('head-right_bushing', head_b13, right_bushing),
    ('shaft-left_bushing', shaft, left_bushing),
    ('shaft-right_bushing', shaft, right_bushing),
    ('left-right_bushing', left_bushing, right_bushing),
]

overlap_rows = []
for label, a, b in pairs:
    try:
        common = a.intersect(b)
        v = common.Volume() if not common.isNull() else 0.0
    except Exception:
        v = float('nan')
    overlap_rows.append((label, v))

# -----------------------------------------------------------------------------
# 6) Export named 4-body STEP assembly.
# -----------------------------------------------------------------------------
assy = cq.Assembly(name='B13C_UPPER_HEAD_BUSHED_TRUNNION')
assy.add(head_b13, name='HEAD_BARREL_7075')
assy.add(shaft, name='SHAFT_300M_CONTINUOUS')
assy.add(left_bushing, name='BUSHING_LEFT_AMS4640')
assy.add(right_bushing, name='BUSHING_RIGHT_AMS4640')

assy.export(str(OUTPUT), exportType='STEP', mode='default')

# Re-import exported file to verify actual delivered body count.
check = cq.importers.importStep(str(OUTPUT))
check_solids = check.solids().vals()

# -----------------------------------------------------------------------------
# 7) Report.
# -----------------------------------------------------------------------------
lines = []
def emit(s=''):
    print(s)
    lines.append(s)

emit('=' * 108)
emit(' PHASE 2E3-B13C — GENERATED BUSHED UPPER-HEAD GEOMETRY VALIDATION')
emit('=' * 108)
emit(f'Source STEP:                         {SOURCE.name}')
emit(f'Output STEP:                         {OUTPUT.name}')
emit(f'Imported B12 solid count:            {len(solids)}')
emit(f'Exported/re-imported solid count:    {len(check_solids)}')
emit()
emit('--- WORKING GEOMETRY ---')
emit(f'Upper-head outer boss:               Ø{2*HEAD_BOSS_RADIUS:.3f} mm x {HEAD_BOSS_HEIGHT:.3f} mm high')
emit(f'Head passage:                        Ø{HEAD_PASSAGE_D:.3f} mm THROUGH')
emit(f'Continuous 300M shaft:               Ø{SHAFT_D:.3f} mm x 175.000 mm')
emit(f'Bronze sleeve, each side:            Ø{BUSH_OD:.3f}/Ø{BUSH_ID:.3f} x {BUSH_SLEEVE_L:.3f} mm')
emit(f'Bronze flange, each side:            Ø{FLANGE_OD:.3f}/Ø{BUSH_ID:.3f} x {FLANGE_T:.3f} mm')
emit()
emit('--- CURVED-HEAD FLANGE SEAT CORRECTION ---')
emit('The source head exterior at the trunnion is a Ø106 cylinder about global Z,')
emit('not a planar ±X face. A real flange therefore needs planar spotfaces.')
emit(f'Full-Ø60 tangent-safe spotface plane: X = ±{x_seat:.6f} mm')
emit(f'Spotface depth at Y=0 from Ø106 tangent: {spotface_depth_at_y0:.6f} mm')
emit(f'Bushing sleeve inner ends:            X = ±{x_seat-BUSH_SLEEVE_L:.6f} mm')
emit(f'Unoccupied central Ø50 passage:       {central_gap:.6f} mm')
emit(f'Shaft-to-7075 radial clearance there: {(HEAD_PASSAGE_D-SHAFT_D)/2:.3f} mm')
emit()
emit('--- BODY BOUNDING BOXES / VOLUMES ---')
for name, shp in parts.items():
    bb = shp.BoundingBox()
    emit(
        f'{name:28s}  V={shp.Volume():12.3f} mm^3  '
        f'X[{bb.xmin:9.3f},{bb.xmax:9.3f}] '
        f'Y[{bb.ymin:9.3f},{bb.ymax:9.3f}] '
        f'Z[{bb.zmin:9.3f},{bb.zmax:9.3f}]'
    )
emit()
emit('--- INTERSECTION VOLUME CHECK ---')
for label, v in overlap_rows:
    emit(f'{label:28s}: {v:.9f} mm^3')
emit()
emit('INTERPRETATION')
emit('- Four separate physical bodies are delivered: 7075 head, one 300M shaft, two bronze bushings.')
emit('- Ø50 through-cut supersedes the B12C Ø38 bore and its 1.5 mm diagnostic mouth chamfers.')
emit('- Shaft/head direct contact is geometrically impossible in the central relief region (6 mm radial gap).')
emit('- Bronze/head OD and bronze/shaft ID are nominally coincident surfaces for contact definition in ANSYS.')
emit('- The Ø60 flanges now seat on explicit planar Ø60 spotfaces cut into the curved Ø106 head exterior.')
emit('- Spotface root/edge detail is intentionally sharp and remains a local FEA/detail-design sensitivity.')
emit('=' * 108)

REPORT.write_text('\n'.join(lines), encoding='utf-8')
