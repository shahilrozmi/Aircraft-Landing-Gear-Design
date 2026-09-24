from pathlib import Path
import cadquery as cq

LOWER_OD_MM = 74.0
UPPER_OD_MM = 106.0
ID_MM = 64.0

FULL_TAPER_START_A_MM = 275.0
FULL_TAPER_END_A_MM = 973.780357

MODEL_BOTTOM_A_MM = 50.0
MODEL_TOP_A_MM = 700.0

OUTPUT_STEP = Path(__file__).resolve().parent / "phase2e3b9_primary106_submodel.step"


def smoothstep(s):
    s = max(0.0, min(1.0, float(s)))
    return 3.0*s**2 - 2.0*s**3


def outer_diameter_mm(z_a_mm):
    if z_a_mm <= FULL_TAPER_START_A_MM:
        return LOWER_OD_MM

    if z_a_mm >= FULL_TAPER_END_A_MM:
        return UPPER_OD_MM

    s = (
        (z_a_mm - FULL_TAPER_START_A_MM)
        / (FULL_TAPER_END_A_MM - FULL_TAPER_START_A_MM)
    )

    return (
        LOWER_OD_MM
        + (UPPER_OD_MM - LOWER_OD_MM)
        * smoothstep(s)
    )


z_values = []
z = MODEL_BOTTOM_A_MM

while z < MODEL_TOP_A_MM - 1e-12:
    z_values.append(z)
    z += 2.0

z_values.append(MODEL_TOP_A_MM)

outer_points = [
    (
        outer_diameter_mm(z_a) / 2.0,
        z_a,
    )
    for z_a in z_values
]

ri = ID_MM / 2.0

profile = (
    cq.Workplane("XZ")
    .moveTo(
        outer_points[0][0],
        outer_points[0][1],
    )
    .spline(
        outer_points[1:],
        includeCurrent=True,
    )
    .lineTo(
        ri,
        MODEL_TOP_A_MM,
    )
    .lineTo(
        ri,
        MODEL_BOTTOM_A_MM,
    )
    .close()
)

solid = profile.revolve(
    360.0,
    (0.0, 0.0),
    (0.0, 1.0),
)

cq.exporters.export(
    solid,
    str(OUTPUT_STEP),
)

print(f"Created: {OUTPUT_STEP}")
