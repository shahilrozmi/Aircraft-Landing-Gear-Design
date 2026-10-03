"""
Landing_Gear_Design_Project
PHASE 2E3-B14B-8 V0.1 — PHYSICAL CLEVIS FRAME / EAR-ROOT TRADE / CAD HANDOFF

PURPOSE
-------
Turn the B14B-7 saddle-root envelope into an explicit, buildable gear-side horn +
clevis geometry suitable for a first CAD model and later physical-brace ANSYS model.

SOURCE CONNECTION
-----------------
Reads:
    phase2e3b14a_freeze_record.csv
    phase2e3b14b_working_geometry.csv
    phase2e3b14b7_reference_candidate.csv

No governing loads are pasted from chat.

LOCAL JOINT FRAME
-----------------
The physical brace direction is u_b (from B14B).

The horn radial direction is:
    e_h = global +Y

Choose the clevis pin axis as:
    e_p = normalize(e_h x u_b)

Therefore:
    e_p is perpendicular to BOTH the horn radial direction and the brace axis.

This gives a mechanically coherent fork:
    - horn extends along e_h
    - brace load acts along u_b
    - pin runs along e_p

The ear plates lie in the e_h-u_b plane.

WORKING / TRADED GEOMETRY
-------------------------
Brace eye retained:
    OD = 44 mm
    width along pin axis = 20 mm

Side clearance:
    1 mm per side

Pin:
    18 mm 300M

Candidate clevis:
    ear thickness t          = 10, 12, 14, 16 mm
    local plate width w      = 50, 55, 60, 65, 70 mm along u_b
    root-to-pin lever L      = 25, 30, 35, 40 mm along e_h
    outboard free extension  = 30 mm along e_h

The fork throat is at:
    y_throat = y_pin - L

The two ears extend from y_throat to:
    y_free = y_pin + 30 mm

The taper/solid-horn body is represented as a loft from:
    B14B-7 saddle root section at y_root
to:
    the full clevis-base envelope at y_throat.

STRENGTH SCREEN
---------------
Ear root:
    each ear carries F/2 along u_b
    M_root = (F/2) L
    rectangular section t x w
    Kt = 3.0 on bending
    rectangular shear = 1.5 V/A
    von Mises combination

Pin:
    retained B14B distributed-bearing pin-bending model
    plus conservative concentrated-contact bound.

Lug:
    nominal net-section and shear-out generic 7075-T6 material screens.
    Projected bearing demand is reported but remains OPEN because no
    product-form-specific lug bearing allowable has been frozen.

SELECTION RULE
--------------
Candidate is eligible when:
    - clevis-base rotated bounding box fits inside B14B-7 85 x 95 root
      with >= 5 mm margin per side in both global X and Z
    - root-side clearance from 44 mm brace-eye OD >= 3 mm
    - outboard clearance from 44 mm brace-eye OD >= 5 mm
    - load-direction hole ligament >= 18 mm
    - ear-root MS_limit >= +0.20
    - ear-root MS_ultimate >= +0.20
    - nominal lug net/shear generic screens >= +0.20
    - 300M pin conservative-bound limit/ultimate MS >= +0.20

Bearing allowable remains OPEN and does not become falsely "passed."

Among eligible candidates, select minimum ear-pair solid volume proxy, then
minimum thickness, then minimum width, then minimum root-to-pin lever.

OUTPUTS
-------
phase2e3b14b8_joint_frame.csv
phase2e3b14b8_clevis_trade.csv
phase2e3b14b8_reference_geometry.csv
phase2e3b14b8_cad_handoff.csv
phase2e3b14b8_open_items.csv
phase2e3b14b8_summary.txt
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent

B14A_FREEZE = HERE / "phase2e3b14a_freeze_record.csv"
B14B_GEOM = HERE / "phase2e3b14b_working_geometry.csv"
B14B7_REF = HERE / "phase2e3b14b7_reference_candidate.csv"

OUT_FRAME = HERE / "phase2e3b14b8_joint_frame.csv"
OUT_TRADE = HERE / "phase2e3b14b8_clevis_trade.csv"
OUT_REFERENCE = HERE / "phase2e3b14b8_reference_geometry.csv"
OUT_HANDOFF = HERE / "phase2e3b14b8_cad_handoff.csv"
OUT_OPEN = HERE / "phase2e3b14b8_open_items.csv"
OUT_SUMMARY = HERE / "phase2e3b14b8_summary.txt"


# =============================================================================
# 1. MATERIAL / JOINT INPUTS
# =============================================================================

ULTIMATE_FACTOR = 1.5

# Generic 7075-T6 material screens.
SY_7075_T6_MPA = 505.0
SU_7075_T6_MPA = 570.0
TAU_Y_7075_VM_MPA = SY_7075_T6_MPA / math.sqrt(3.0)
TAU_U_7075_VM_MPA = SU_7075_T6_MPA / math.sqrt(3.0)

# 300M project screens.
SY_300M_MPA = 1517.0
SU_300M_MPA = 1862.0
TAU_Y_300M_MPA = 875.840
TAU_U_300M_MPA = 1075.026

PIN_D_MM = 18.0

EYE_OD_MM = 44.0
EYE_WIDTH_PIN_AXIS_MM = 20.0
SIDE_CLEARANCE_MM = 1.0

EAR_T_VALUES_MM = [10.0, 12.0, 14.0, 16.0]
PLATE_W_VALUES_MM = [50.0, 55.0, 60.0, 65.0, 70.0]
ROOT_TO_PIN_VALUES_MM = [25.0, 30.0, 35.0, 40.0]

OUTBOARD_FREE_EXTENSION_MM = 30.0

KT_EAR_ROOT = 3.0

MIN_ROOT_PACKAGING_MARGIN_X_MM = 5.0
MIN_ROOT_PACKAGING_MARGIN_Z_MM = 5.0
MIN_ROOT_SIDE_EYE_CLEARANCE_MM = 3.0
MIN_OUTBOARD_EYE_CLEARANCE_MM = 5.0
MIN_LOAD_DIRECTION_HOLE_LIGAMENT_MM = 18.0

MIN_MS_LIMIT = 0.20
MIN_MS_ULT = 0.20


# =============================================================================
# 2. HELPERS
# =============================================================================

def read_one(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required source: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f"{path.name}: expected one row, got {len(rows)}")
    return rows[0]


def write_csv(path: Path, rows):
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def norm(v):
    return math.sqrt(dot(v, v))


def unit(v):
    n = norm(v)
    return (v[0]/n, v[1]/n, v[2]/n)


def add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def scale(v, s):
    return (v[0]*s, v[1]*s, v[2]*s)


def ms(allowable, demand):
    return allowable/demand - 1.0


# =============================================================================
# 3. SOURCE CONNECTION
# =============================================================================

b14a = read_one(B14A_FREEZE)
geom = read_one(B14B_GEOM)
root = read_one(B14B7_REF)

if str(b14a["superposition_pass"]).strip().lower() not in {
    "true", "1", "yes", "pass"
}:
    raise RuntimeError("B14A superposition gate is not PASS.")

Mx_ult_kNm = float(b14a["combined_Mx_kNm"])

a_perp_m = float(geom["effective_arm_mm"]) / 1000.0

u_b = unit((
    float(geom["u_x"]),
    float(geom["u_y"]),
    float(geom["u_z"]),
))

e_h = (0.0, 1.0, 0.0)

# Clevis pin axis perpendicular to both horn radial direction and brace axis.
e_p = unit(cross(e_h, u_b))

# Orthogonality checks.
orth_h_b = dot(e_h, u_b)
orth_h_p = dot(e_h, e_p)
orth_b_p = dot(u_b, e_p)

if max(abs(orth_h_b), abs(orth_h_p), abs(orth_b_p)) > 1e-10:
    raise RuntimeError("Local clevis frame is not orthogonal.")

B = (
    float(geom["B_x_mm"]),
    float(geom["B_y_mm"]),
    float(geom["B_z_mm"]),
)

ROOT_BX_MM = float(root["bx_mm"])
ROOT_HZ_MM = float(root["hz_mm"])
ROOT_Y_MM = float(root["root_plane_y_mm"])

Fbrace_ult_kN = Mx_ult_kNm / a_perp_m
Fbrace_abs_ult_N = abs(Fbrace_ult_kN) * 1000.0
Fbrace_abs_lim_N = Fbrace_abs_ult_N / ULTIMATE_FACTOR

F_ear_ult_N = Fbrace_abs_ult_N / 2.0
F_ear_lim_N = Fbrace_abs_lim_N / 2.0


# =============================================================================
# 4. FRAME RECORD
# =============================================================================

frame_rows = [
    {
        "axis": "horn_radial_e_h",
        "x": e_h[0], "y": e_h[1], "z": e_h[2],
        "meaning": "horn centerline / root-to-pin direction",
    },
    {
        "axis": "brace_axis_u_b",
        "x": u_b[0], "y": u_b[1], "z": u_b[2],
        "meaning": "two-force member axial-load direction",
    },
    {
        "axis": "pin_axis_e_p",
        "x": e_p[0], "y": e_p[1], "z": e_p[2],
        "meaning": "clevis pin axis = normalize(e_h x u_b)",
    },
]

write_csv(OUT_FRAME, frame_rows)


# =============================================================================
# 5. CLEVIS / EAR / PIN TRADE
# =============================================================================

rows = []

pin_area_mm2 = math.pi * PIN_D_MM**2 / 4.0

tau_pin_lim_MPa = (
    Fbrace_abs_lim_N / (2.0*pin_area_mm2)
)
tau_pin_ult_MPa = (
    Fbrace_abs_ult_N / (2.0*pin_area_mm2)
)

for t in EAR_T_VALUES_MM:

    # Pin stack geometry.
    grip_mm = (
        2.0*t
        + EYE_WIDTH_PIN_AXIS_MM
        + 2.0*SIDE_CLEARANCE_MM
    )

    inner_ear_face_offset_mm = (
        EYE_WIDTH_PIN_AXIS_MM/2.0
        + SIDE_CLEARANCE_MM
    )

    outer_ear_face_offset_mm = (
        inner_ear_face_offset_mm
        + t
    )

    # B14B pin bending models updated with actual ear thickness.
    distributed_pin_lever_mm = (
        EYE_WIDTH_PIN_AXIS_MM/4.0
        + SIDE_CLEARANCE_MM
        + t/2.0
    )

    concentrated_pin_lever_mm = (
        EYE_WIDTH_PIN_AXIS_MM/2.0
        + SIDE_CLEARANCE_MM
        + t/2.0
    )

    Mpin_dist_lim_Nmm = (
        Fbrace_abs_lim_N/2.0
        * distributed_pin_lever_mm
    )
    Mpin_dist_ult_Nmm = (
        Fbrace_abs_ult_N/2.0
        * distributed_pin_lever_mm
    )

    Mpin_bound_lim_Nmm = (
        Fbrace_abs_lim_N/2.0
        * concentrated_pin_lever_mm
    )
    Mpin_bound_ult_Nmm = (
        Fbrace_abs_ult_N/2.0
        * concentrated_pin_lever_mm
    )

    def pin_vm(M_Nmm, tau_MPa):
        sig_b = (
            32.0*M_Nmm
            / (math.pi*PIN_D_MM**3)
        )
        return math.sqrt(
            sig_b**2
            + 3.0*tau_MPa**2
        )

    vm_pin_dist_lim = pin_vm(
        Mpin_dist_lim_Nmm,
        tau_pin_lim_MPa,
    )
    vm_pin_dist_ult = pin_vm(
        Mpin_dist_ult_Nmm,
        tau_pin_ult_MPa,
    )

    vm_pin_bound_lim = pin_vm(
        Mpin_bound_lim_Nmm,
        tau_pin_lim_MPa,
    )
    vm_pin_bound_ult = pin_vm(
        Mpin_bound_ult_Nmm,
        tau_pin_ult_MPa,
    )

    ms_pin_bound_lim = ms(
        SY_300M_MPA,
        vm_pin_bound_lim,
    )
    ms_pin_bound_ult = ms(
        SU_300M_MPA,
        vm_pin_bound_ult,
    )

    for w in PLATE_W_VALUES_MM:

        # Full clevis-base envelope in the x-z plane:
        # width w along brace axis u_b,
        # total grip along pin axis e_p.
        bbox_x_mm = (
            w*abs(u_b[0])
            + grip_mm*abs(e_p[0])
        )
        bbox_z_mm = (
            w*abs(u_b[2])
            + grip_mm*abs(e_p[2])
        )

        root_margin_x_each_mm = (
            ROOT_BX_MM - bbox_x_mm
        ) / 2.0

        root_margin_z_each_mm = (
            ROOT_HZ_MM - bbox_z_mm
        ) / 2.0

        packaging_pass = (
            root_margin_x_each_mm
            >= MIN_ROOT_PACKAGING_MARGIN_X_MM
            and root_margin_z_each_mm
            >= MIN_ROOT_PACKAGING_MARGIN_Z_MM
        )

        # Hole ligament in load direction u_b.
        load_dir_edge_distance_mm = (
            w/2.0
        )
        load_dir_hole_ligament_mm = (
            load_dir_edge_distance_mm
            - PIN_D_MM/2.0
        )

        load_dir_ligament_pass = (
            load_dir_hole_ligament_mm
            >= MIN_LOAD_DIRECTION_HOLE_LIGAMENT_MM
        )

        # Nominal lug shear-out area in brace-load direction.
        lug_shearout_area_mm2 = (
            2.0*t
            * load_dir_hole_ligament_mm
        )

        tau_lug_lim_MPa = (
            F_ear_lim_N
            / lug_shearout_area_mm2
        )
        tau_lug_ult_MPa = (
            F_ear_ult_N
            / lug_shearout_area_mm2
        )

        ms_lug_so_lim = ms(
            TAU_Y_7075_VM_MPA,
            tau_lug_lim_MPa,
        )
        ms_lug_so_ult = ms(
            TAU_U_7075_VM_MPA,
            tau_lug_ult_MPa,
        )

        # Bearing demand only.
        p_bearing_lim_MPa = (
            F_ear_lim_N
            / (PIN_D_MM*t)
        )
        p_bearing_ult_MPa = (
            F_ear_ult_N
            / (PIN_D_MM*t)
        )

        for L in ROOT_TO_PIN_VALUES_MM:

            root_side_eye_clearance_mm = (
                L - EYE_OD_MM/2.0
            )

            outboard_eye_clearance_mm = (
                OUTBOARD_FREE_EXTENSION_MM
                - EYE_OD_MM/2.0
            )

            eye_clearance_pass = (
                root_side_eye_clearance_mm
                >= MIN_ROOT_SIDE_EYE_CLEARANCE_MM
                and outboard_eye_clearance_mm
                >= MIN_OUTBOARD_EYE_CLEARANCE_MM
            )

            throat_y_mm = (
                B[1] - L
            )

            free_y_mm = (
                B[1]
                + OUTBOARD_FREE_EXTENSION_MM
            )

            taper_length_mm = (
                throat_y_mm
                - ROOT_Y_MM
            )

            if taper_length_mm <= 0.0:
                continue

            # Ear-root in-plane cantilever bending.
            Mear_lim_Nmm = (
                F_ear_lim_N * L
            )
            Mear_ult_Nmm = (
                F_ear_ult_N * L
            )

            Zear_mm3 = (
                t*w**2 / 6.0
            )

            sigma_ear_b_lim_MPa = (
                KT_EAR_ROOT
                * Mear_lim_Nmm
                / Zear_mm3
            )

            sigma_ear_b_ult_MPa = (
                KT_EAR_ROOT
                * Mear_ult_Nmm
                / Zear_mm3
            )

            tau_ear_root_lim_MPa = (
                1.5*F_ear_lim_N
                / (t*w)
            )

            tau_ear_root_ult_MPa = (
                1.5*F_ear_ult_N
                / (t*w)
            )

            vm_ear_root_lim_MPa = math.sqrt(
                sigma_ear_b_lim_MPa**2
                + 3.0*tau_ear_root_lim_MPa**2
            )

            vm_ear_root_ult_MPa = math.sqrt(
                sigma_ear_b_ult_MPa**2
                + 3.0*tau_ear_root_ult_MPa**2
            )

            ms_ear_root_lim = ms(
                SY_7075_T6_MPA,
                vm_ear_root_lim_MPa,
            )

            ms_ear_root_ult = ms(
                SU_7075_T6_MPA,
                vm_ear_root_ult_MPa,
            )

            # Pin-hole nominal net section under load along u_b.
            ear_length_y_mm = (
                L
                + OUTBOARD_FREE_EXTENSION_MM
            )

            net_height_y_mm = (
                ear_length_y_mm
                - PIN_D_MM
            )

            net_area_mm2 = (
                t * net_height_y_mm
            )

            sigma_net_lim_MPa = (
                F_ear_lim_N / net_area_mm2
            )

            sigma_net_ult_MPa = (
                F_ear_ult_N / net_area_mm2
            )

            ms_net_lim = ms(
                SY_7075_T6_MPA,
                sigma_net_lim_MPa,
            )

            ms_net_ult = ms(
                SU_7075_T6_MPA,
                sigma_net_ult_MPa,
            )

            strength_pass = all([
                ms_ear_root_lim >= MIN_MS_LIMIT,
                ms_ear_root_ult >= MIN_MS_ULT,
                ms_net_lim >= MIN_MS_LIMIT,
                ms_net_ult >= MIN_MS_ULT,
                ms_lug_so_lim >= MIN_MS_LIMIT,
                ms_lug_so_ult >= MIN_MS_ULT,
                ms_pin_bound_lim >= MIN_MS_LIMIT,
                ms_pin_bound_ult >= MIN_MS_ULT,
            ])

            eligible = all([
                packaging_pass,
                load_dir_ligament_pass,
                eye_clearance_pass,
                strength_pass,
            ])

            # Solid-volume proxy for the ear pair before holes/fillets.
            ear_pair_volume_proxy_mm3 = (
                2.0
                * t
                * w
                * ear_length_y_mm
            )

            rows.append({
                "ear_t_mm": t,
                "plate_width_along_brace_axis_mm": w,
                "root_to_pin_lever_mm": L,
                "outboard_free_extension_mm": OUTBOARD_FREE_EXTENSION_MM,
                "ear_length_y_mm": ear_length_y_mm,

                "structural_pin_grip_mm": grip_mm,
                "eye_width_pin_axis_mm": EYE_WIDTH_PIN_AXIS_MM,
                "side_clearance_each_mm": SIDE_CLEARANCE_MM,

                "clevis_base_bbox_x_mm": bbox_x_mm,
                "clevis_base_bbox_z_mm": bbox_z_mm,
                "root_margin_x_each_mm": root_margin_x_each_mm,
                "root_margin_z_each_mm": root_margin_z_each_mm,
                "packaging_pass": packaging_pass,

                "load_dir_edge_distance_mm": load_dir_edge_distance_mm,
                "load_dir_hole_ligament_mm": load_dir_hole_ligament_mm,
                "load_dir_ligament_pass": load_dir_ligament_pass,

                "root_side_eye_clearance_mm": root_side_eye_clearance_mm,
                "outboard_eye_clearance_mm": outboard_eye_clearance_mm,
                "eye_clearance_pass": eye_clearance_pass,

                "throat_y_mm": throat_y_mm,
                "free_y_mm": free_y_mm,
                "taper_length_from_saddle_root_mm": taper_length_mm,

                "Kt_ear_root": KT_EAR_ROOT,
                "ear_root_VM_limit_MPa": vm_ear_root_lim_MPa,
                "ear_root_MS_limit": ms_ear_root_lim,
                "ear_root_VM_ultimate_MPa": vm_ear_root_ult_MPa,
                "ear_root_MS_ultimate": ms_ear_root_ult,

                "lug_net_sigma_limit_MPa": sigma_net_lim_MPa,
                "lug_net_MS_limit": ms_net_lim,
                "lug_net_sigma_ultimate_MPa": sigma_net_ult_MPa,
                "lug_net_MS_ultimate": ms_net_ult,

                "lug_shearout_tau_limit_MPa": tau_lug_lim_MPa,
                "lug_shearout_MS_limit": ms_lug_so_lim,
                "lug_shearout_tau_ultimate_MPa": tau_lug_ult_MPa,
                "lug_shearout_MS_ultimate": ms_lug_so_ult,

                "lug_bearing_demand_limit_MPa": p_bearing_lim_MPa,
                "lug_bearing_demand_ultimate_MPa": p_bearing_ult_MPa,
                "lug_bearing_status": "OPEN_ALLOWABLE",

                "pin_VM_distributed_limit_MPa": vm_pin_dist_lim,
                "pin_VM_distributed_ultimate_MPa": vm_pin_dist_ult,
                "pin_VM_bound_limit_MPa": vm_pin_bound_lim,
                "pin_MS_bound_limit": ms_pin_bound_lim,
                "pin_VM_bound_ultimate_MPa": vm_pin_bound_ult,
                "pin_MS_bound_ultimate": ms_pin_bound_ult,

                "ear_pair_volume_proxy_mm3": ear_pair_volume_proxy_mm3,

                "strength_pass_except_bearing": strength_pass,
                "eligible_reference": eligible,

                "note": (
                    "Bearing allowable remains open. "
                    "Actual lug contour, fillets, contact and 3D root load transfer require FEA."
                ),
            })


write_csv(OUT_TRADE, rows)


# =============================================================================
# 6. REFERENCE SELECTION
# =============================================================================

eligible_rows = [
    r for r in rows
    if r["eligible_reference"]
]

if not eligible_rows:
    raise RuntimeError(
        "No physical clevis candidate satisfies the working selection rules."
    )

reference = min(
    eligible_rows,
    key=lambda r: (
        r["ear_pair_volume_proxy_mm3"],
        r["ear_t_mm"],
        r["plate_width_along_brace_axis_mm"],
        r["root_to_pin_lever_mm"],
    ),
)

reference_row = {
    **reference,
    "selection_status": "WORKING_CAD_FEA_REFERENCE_NOT_FROZEN",
    "selection_note": (
        "Minimum ear-pair solid-volume proxy among candidates satisfying "
        "packaging, eye-clearance, generic 7075 root/net/shear screens and "
        "conservative 300M pin bound. Lug bearing allowable remains open."
    ),
}

write_csv(OUT_REFERENCE, [reference_row])


# =============================================================================
# 7. GLOBAL CAD / ANSYS HANDOFF
# =============================================================================

t_ref = reference["ear_t_mm"]
w_ref = reference["plate_width_along_brace_axis_mm"]
L_ref = reference["root_to_pin_lever_mm"]

grip_ref = reference["structural_pin_grip_mm"]
half_grip_ref = grip_ref/2.0

throat_y = reference["throat_y_mm"]
free_y = reference["free_y_mm"]

# Pin axis endpoints for structural grip.
pin_end_minus = add(
    B,
    scale(e_p, -half_grip_ref),
)

pin_end_plus = add(
    B,
    scale(e_p, +half_grip_ref),
)

# Inner / outer ear face offsets along pin axis.
inner_face = (
    EYE_WIDTH_PIN_AXIS_MM/2.0
    + SIDE_CLEARANCE_MM
)
outer_face = inner_face + t_ref

# Clevis-base center at throat plane.
throat_center = (
    B[0],
    throat_y,
    B[2],
)

# Saddle-root center.
saddle_center = (
    0.0,
    ROOT_Y_MM,
    0.0,
)

handoff = [
    {
        "parameter": "horn_axis_e_h",
        "x": e_h[0], "y": e_h[1], "z": e_h[2],
        "value": "", "units": "-",
        "classification": "DERIVED_LOCAL_FRAME",
    },
    {
        "parameter": "brace_axis_u_b",
        "x": u_b[0], "y": u_b[1], "z": u_b[2],
        "value": "", "units": "-",
        "classification": "SOURCE_B14B",
    },
    {
        "parameter": "pin_axis_e_p",
        "x": e_p[0], "y": e_p[1], "z": e_p[2],
        "value": "", "units": "-",
        "classification": "DERIVED_LOCAL_FRAME",
    },
    {
        "parameter": "saddle_root_center",
        "x": saddle_center[0], "y": saddle_center[1], "z": saddle_center[2],
        "value": "", "units": "mm",
        "classification": "SOURCE_B14B7",
    },
    {
        "parameter": "saddle_root_section",
        "x": "", "y": "", "z": "",
        "value": f"{ROOT_BX_MM:.3f} x {ROOT_HZ_MM:.3f}",
        "units": "mm",
        "classification": "SOURCE_B14B7",
    },
    {
        "parameter": "clevis_throat_center",
        "x": throat_center[0], "y": throat_center[1], "z": throat_center[2],
        "value": "", "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "clevis_base_local_width_along_brace",
        "x": "", "y": "", "z": "",
        "value": w_ref,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "clevis_base_total_grip_along_pin_axis",
        "x": "", "y": "", "z": "",
        "value": grip_ref,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "ear_thickness",
        "x": "", "y": "", "z": "",
        "value": t_ref,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "central_slot_width_along_pin_axis",
        "x": "", "y": "", "z": "",
        "value": EYE_WIDTH_PIN_AXIS_MM + 2.0*SIDE_CLEARANCE_MM,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "pin_center",
        "x": B[0], "y": B[1], "z": B[2],
        "value": "", "units": "mm",
        "classification": "SOURCE_B14B",
    },
    {
        "parameter": "pin_axis_minus_endpoint",
        "x": pin_end_minus[0], "y": pin_end_minus[1], "z": pin_end_minus[2],
        "value": "", "units": "mm",
        "classification": "DERIVED",
    },
    {
        "parameter": "pin_axis_plus_endpoint",
        "x": pin_end_plus[0], "y": pin_end_plus[1], "z": pin_end_plus[2],
        "value": "", "units": "mm",
        "classification": "DERIVED",
    },
    {
        "parameter": "pin_diameter",
        "x": "", "y": "", "z": "",
        "value": PIN_D_MM,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "brace_eye_OD",
        "x": "", "y": "", "z": "",
        "value": EYE_OD_MM,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "brace_eye_width_along_pin_axis",
        "x": "", "y": "", "z": "",
        "value": EYE_WIDTH_PIN_AXIS_MM,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "fork_free_end_y",
        "x": "", "y": "", "z": "",
        "value": free_y,
        "units": "mm",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "taper_length_saddle_to_clevis_throat",
        "x": "", "y": "", "z": "",
        "value": reference["taper_length_from_saddle_root_mm"],
        "units": "mm",
        "classification": "DERIVED",
    },
    {
        "parameter": "negative_ear_pin_axis_offsets",
        "x": "", "y": "", "z": "",
        "value": f"{-outer_face:.3f} to {-inner_face:.3f}",
        "units": "mm along e_p",
        "classification": "WORKING_NOT_FROZEN",
    },
    {
        "parameter": "positive_ear_pin_axis_offsets",
        "x": "", "y": "", "z": "",
        "value": f"{inner_face:.3f} to {outer_face:.3f}",
        "units": "mm along e_p",
        "classification": "WORKING_NOT_FROZEN",
    },
]

write_csv(OUT_HANDOFF, handoff)


# =============================================================================
# 8. OPEN ITEMS
# =============================================================================

open_items = [
    {
        "item": "LUG_BEARING_ALLOWABLE",
        "status": "OPEN",
        "reason": (
            "Projected bearing demand is computed, but no valid product-form-specific "
            "7075 lug bearing allowable has been frozen."
        ),
    },
    {
        "item": "CLEVIS_SLOT_ROOT_FILLET",
        "status": "OPEN",
        "reason": (
            "The 22 mm central slot must terminate with a generous radiused root. "
            "Final radius/shape should be set in CAD and checked by local FEA."
        ),
    },
    {
        "item": "SADDLE_TO_CLEVIS_TAPER",
        "status": "OPEN",
        "reason": (
            "B14B-8 defines the two end sections and their separation. "
            "Actual loft/taper contour and fillets remain CAD/FEA variables."
        ),
    },
    {
        "item": "BRACE_EYE_END_FITTING",
        "status": "OPEN",
        "reason": (
            "Gear-side joint geometry is now explicit, but the 44 mm eye to 25x3 tube "
            "joining method remains to be detailed."
        ),
    },
    {
        "item": "AIRFRAME_SIDE_JOINT",
        "status": "OPEN",
        "reason": (
            "The opposite brace-end fitting and aircraft structural attachment are "
            "not defined by the landing-gear head geometry."
        ),
    },
    {
        "item": "PHYSICAL_ANSYS_REPLACEMENT",
        "status": "OPEN",
        "reason": (
            "After CAD geometry exists, remove SUP_BRACE_RX and model the actual "
            "pin-ended brace. Re-solve journal reactions and local head stresses."
        ),
    },
]

write_csv(OUT_OPEN, open_items)


# =============================================================================
# 9. SUMMARY
# =============================================================================

lines = []
emit = lines.append

emit("=" * 132)
emit(" PHASE 2E3-B14B-8 V0.1 — PHYSICAL CLEVIS FRAME / EAR-ROOT TRADE / CAD HANDOFF")
emit("=" * 132)
emit("")
emit("SOURCE CONNECTION")
emit("-" * 132)
emit(f"B14A freeze:   {B14A_FREEZE}")
emit(f"B14B geometry: {B14B_GEOM}")
emit(f"B14B-7 root:   {B14B7_REF}")
emit("")
emit("LOCAL ORTHONORMAL JOINT FRAME")
emit("-" * 132)
emit(f"e_h horn/radial: [{e_h[0]:+.9f}, {e_h[1]:+.9f}, {e_h[2]:+.9f}]")
emit(f"u_b brace axis:  [{u_b[0]:+.9f}, {u_b[1]:+.9f}, {u_b[2]:+.9f}]")
emit(f"e_p pin axis:    [{e_p[0]:+.9f}, {e_p[1]:+.9f}, {e_p[2]:+.9f}]")
emit(f"dot(e_h,u_b):    {orth_h_b:+.3e}")
emit(f"dot(e_h,e_p):    {orth_h_p:+.3e}")
emit(f"dot(u_b,e_p):    {orth_b_p:+.3e}")
emit("")
emit("WORKING PHYSICAL CLEVIS REFERENCE — NOT FROZEN")
emit("-" * 132)
emit(f"Ear thickness:                    {reference['ear_t_mm']:.3f} mm each")
emit(f"Plate width along brace axis:     {reference['plate_width_along_brace_axis_mm']:.3f} mm")
emit(f"Root-to-pin lever:                {reference['root_to_pin_lever_mm']:.3f} mm")
emit(f"Outboard free extension:          {reference['outboard_free_extension_mm']:.3f} mm")
emit(f"Total structural pin grip:        {reference['structural_pin_grip_mm']:.3f} mm")
emit(f"Central slot / eye package:       {EYE_WIDTH_PIN_AXIS_MM + 2*SIDE_CLEARANCE_MM:.3f} mm")
emit(f"Clevis throat y:                  {reference['throat_y_mm']:.3f} mm")
emit(f"Pin center y:                     {B[1]:.3f} mm")
emit(f"Fork free end y:                  {reference['free_y_mm']:.3f} mm")
emit(f"Saddle-root to throat taper:      {reference['taper_length_from_saddle_root_mm']:.3f} mm")
emit("")
emit("PACKAGING AGAINST B14B-7 ROOT")
emit("-" * 132)
emit(f"Saddle root:                      {ROOT_BX_MM:.3f} x {ROOT_HZ_MM:.3f} mm")
emit(f"Rotated clevis-base bbox X:       {reference['clevis_base_bbox_x_mm']:.3f} mm")
emit(f"Rotated clevis-base bbox Z:       {reference['clevis_base_bbox_z_mm']:.3f} mm")
emit(f"Root X margin each side:          {reference['root_margin_x_each_mm']:.3f} mm")
emit(f"Root Z margin each side:          {reference['root_margin_z_each_mm']:.3f} mm")
emit("")
emit("EYE / HOLE CLEARANCE")
emit("-" * 132)
emit(f"Root-side clearance to eye OD:    {reference['root_side_eye_clearance_mm']:.3f} mm")
emit(f"Outboard clearance to eye OD:     {reference['outboard_eye_clearance_mm']:.3f} mm")
emit(f"Load-direction hole ligament:     {reference['load_dir_hole_ligament_mm']:.3f} mm")
emit("")
emit("EAR-ROOT SCREEN, Kt=3.0")
emit("-" * 132)
emit(f"VM limit:                         {reference['ear_root_VM_limit_MPa']:.3f} MPa")
emit(f"MS limit:                         {reference['ear_root_MS_limit']:+.3f}")
emit(f"VM ultimate:                      {reference['ear_root_VM_ultimate_MPa']:.3f} MPa")
emit(f"MS ultimate:                      {reference['ear_root_MS_ultimate']:+.3f}")
emit("")
emit("NOMINAL LUG SCREENS")
emit("-" * 132)
emit(f"Net-section ultimate demand:      {reference['lug_net_sigma_ultimate_MPa']:.3f} MPa")
emit(f"Net-section ultimate MS:          {reference['lug_net_MS_ultimate']:+.3f}")
emit(f"Shear-out ultimate demand:        {reference['lug_shearout_tau_ultimate_MPa']:.3f} MPa")
emit(f"Shear-out ultimate MS:            {reference['lug_shearout_MS_ultimate']:+.3f}")
emit(f"Projected bearing ultimate:       {reference['lug_bearing_demand_ultimate_MPa']:.3f} MPa [ALLOWABLE OPEN]")
emit("")
emit("300M PIN")
emit("-" * 132)
emit(f"Distributed pin VM ultimate:      {reference['pin_VM_distributed_ultimate_MPa']:.3f} MPa")
emit(f"Conservative-bound VM limit:      {reference['pin_VM_bound_limit_MPa']:.3f} MPa")
emit(f"Conservative-bound MS limit:      {reference['pin_MS_bound_limit']:+.3f}")
emit(f"Conservative-bound VM ultimate:   {reference['pin_VM_bound_ultimate_MPa']:.3f} MPa")
emit(f"Conservative-bound MS ultimate:   {reference['pin_MS_bound_ultimate']:+.3f}")
emit("")
emit("PIN AXIS GLOBAL GEOMETRY")
emit("-" * 132)
emit(f"Pin center B:                     [{B[0]:+.3f}, {B[1]:+.3f}, {B[2]:+.3f}] mm")
emit(f"Pin-axis minus grip endpoint:     [{pin_end_minus[0]:+.3f}, {pin_end_minus[1]:+.3f}, {pin_end_minus[2]:+.3f}] mm")
emit(f"Pin-axis plus grip endpoint:      [{pin_end_plus[0]:+.3f}, {pin_end_plus[1]:+.3f}, {pin_end_plus[2]:+.3f}] mm")
emit("")
emit("DISPOSITION")
emit("-" * 132)
emit("The B14B gear-side joint now has an explicit orthogonal pin orientation, fork stack, throat station and tapered-horn endpoints.")
emit("This is sufficiently defined for a first CAD/FEA geometry build, but it remains WORKING_NOT_FROZEN.")
emit("Lug bearing allowable, slot-root fillet, taper contour, brace-eye tube joint and airframe-side joint remain open.")
emit("Next: build/verify the physical horn + clevis CAD geometry, then replace SUP_BRACE_RX with the physical brace in ANSYS.")
emit("")
emit("OUTPUTS")
emit("-" * 132)
for p in [OUT_FRAME, OUT_TRADE, OUT_REFERENCE, OUT_HANDOFF, OUT_OPEN, OUT_SUMMARY]:
    emit(str(p))
emit("=" * 132)

report = "\n".join(lines)
OUT_SUMMARY.write_text(report, encoding="utf-8")
print(report)
