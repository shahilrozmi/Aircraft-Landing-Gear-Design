"""
Landing_Gear_Design_Project
Phase 2D1 — Lower Piston Preliminary Structural Sizing

Purpose
-------
Size the lower sliding piston/tube using the frozen Phase 2C load envelope.

This is a PRELIMINARY static-strength and buckling screen.
It does not yet include:
- local bushing/contact stresses,
- lug/axle-root stress concentrations,
- surface treatment/plating effects,
- fatigue,
- fracture mechanics,
- detailed finite-element stresses.

Material baseline
-----------------
300M ultrahigh-strength steel, preliminary screening values:
    E      = 205 GPa
    G      = 80 GPa
    nu     = 0.28
    rho    = 7870 kg/m^3
    Sy     = 1517 MPa  (~220 ksi)
    Su     = 1862 MPa  (~270 ksi)

The strength values correspond to a conservative AMS 6417 heat-treated
screening basis from public typical-property data. Final design should use
approved aerospace allowables/specification data.

Load treatment
--------------
Limit loads are checked against yield strength.
Ultimate loads are checked against ultimate tensile strength as a preliminary
screen only.

For a circular hollow piston:
    A = pi/4  * (Do^2 - Di^2)
    I = pi/64 * (Do^4 - Di^4)
    J = pi/32 * (Do^4 - Di^4)

At a piston section h above the axle:
    Nc = Fz
    Vx = Fx
    Vy = Fy
    Mx = e*Fz + (rt + h)*Fy
    My = -(rt + h)*Fx
    Tz = -e*Fx
    Mb = sqrt(Mx^2 + My^2)

Critical outer-fiber normal stress:
    sigma = Nc/A + Mb*c/I

Torsional shear at the outer surface:
    tau_t = |T|*c/J

Preliminary von Mises screen:
    sigma_vm = sqrt(sigma^2 + 3*tau_t^2)

Transverse shear is checked separately using the deliberately conservative
screen:
    tau_v_screen = 2*V/A

Buckling
--------
The full-extension exposed piston segment is treated conservatively as a
cantilever column:
    K = 2.0

Johnson is used below the transition slenderness Cc, and Euler above it.
"""

import csv
import math
from pathlib import Path


# =============================================================================
# 1. MATERIAL — 300M STEEL PRELIMINARY SCREENING VALUES
# =============================================================================

E = 205e9                     # Pa
G = 80e9                      # Pa
nu = 0.28
rho = 7870.0                  # kg/m^3

Sy = 1517e6                   # Pa, ~220 ksi
Su = 1862e6                   # Pa, ~270 ksi

tau_y_allow = Sy / math.sqrt(3.0)
tau_u_allow = Su / math.sqrt(3.0)


# =============================================================================
# 2. LOCKED GEOMETRY FROM PHASE 2B
# =============================================================================

e = 0.120                     # m, strut-to-wheel lateral offset
rt = 0.175                    # m, static loaded tire radius

# Baseline OD screening:
# 58 mm matches the effective Phase 1 oleo piston diameter.
# This is NOT yet locked as the final structural outside diameter.
Do_baseline = 0.058           # m

# We have not yet frozen the lower-bushing / piston critical-section location.
# Therefore sweep plausible exposed-section distances instead of inventing one.
h_cases = [
    0.20,
    0.25,
    0.30,
    0.35,
]                             # m above axle

# Conservative preliminary buckling end condition.
K_buckling = 2.0

# Wall-thickness design sweep.
t_min_mm = 1.50
t_max_mm = 8.00
t_step_mm = 0.25


# =============================================================================
# 3. FIND PHASE 2C RESULT FILE
# =============================================================================

here = Path(__file__).resolve().parent

candidate_paths = [
    here / "phase2_internal_loads.csv",
    here.parent / "phase2_structures" / "phase2_internal_loads.csv",
]

phase2_csv = None

for path in candidate_paths:
    if path.exists():
        phase2_csv = path
        break

if phase2_csv is None:
    searched = "\n".join(str(p) for p in candidate_paths)
    raise FileNotFoundError(
        "Could not find phase2_internal_loads.csv.\n"
        "Run phase2_internal_loads.py first.\n"
        f"Searched:\n{searched}"
    )


# =============================================================================
# 4. READ FULL-PRECISION PHASE 2C FORCES
# =============================================================================

def read_force_cases(path):
    """
    phase2_internal_loads.csv contains one row for each case and load level.
    We read only the original Fx, Fy, Fz force components and recompute the
    resultants at arbitrary piston station h.
    """

    cases = {
        "limit": {},
        "ultimate": {},
    }

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            level = row["level"]
            case = row["case"]

            cases[level][case] = {
                "Fx_kN": float(row["Fx_kN"]),
                "Fy_kN": float(row["Fy_kN"]),
                "Fz_kN": float(row["Fz_kN"]),
            }

    return cases


loads = read_force_cases(
    phase2_csv
)


# =============================================================================
# 5. SECTION + LOAD FUNCTIONS
# =============================================================================

def section_properties(
    Do,
    wall,
):
    Di = Do - 2.0 * wall

    if Di <= 0.0:
        raise ValueError(
            "Wall thickness is too large for the selected OD."
        )

    A = math.pi / 4.0 * (
        Do**2 - Di**2
    )

    I = math.pi / 64.0 * (
        Do**4 - Di**4
    )

    J = math.pi / 32.0 * (
        Do**4 - Di**4
    )

    c = Do / 2.0

    radius_gyration = math.sqrt(
        I / A
    )

    mass_per_length = rho * A

    return {
        "Di_m": Di,
        "A_m2": A,
        "I_m4": I,
        "J_m4": J,
        "c_m": c,
        "r_g_m": radius_gyration,
        "mass_per_m_kg": mass_per_length,
    }


def piston_resultants(
    force,
    h,
):
    Fx = force["Fx_kN"]
    Fy = force["Fy_kN"]
    Fz = force["Fz_kN"]

    arm = rt + h

    Mx = (
        e * Fz
        + arm * Fy
    )

    My = (
        -arm * Fx
    )

    Tz = (
        -e * Fx
    )

    Mb = math.hypot(
        Mx,
        My,
    )

    V = math.hypot(
        Fx,
        Fy,
    )

    return {
        "Nc_kN": Fz,
        "V_kN": V,
        "Mx_kNm": Mx,
        "My_kNm": My,
        "Tz_kNm": Tz,
        "Mb_kNm": Mb,
    }


def stress_state(
    section,
    resultants,
):
    A = section["A_m2"]
    I = section["I_m4"]
    J = section["J_m4"]
    c = section["c_m"]

    N = abs(
        resultants["Nc_kN"]
    ) * 1e3

    V = abs(
        resultants["V_kN"]
    ) * 1e3

    Mb = abs(
        resultants["Mb_kNm"]
    ) * 1e3

    T = abs(
        resultants["Tz_kNm"]
    ) * 1e3

    sigma_axial = (
        N / A
    )

    sigma_bending = (
        Mb * c / I
    )

    # Worst compression-side magnitude.
    sigma_normal_worst = (
        sigma_axial
        + sigma_bending
    )

    tau_torsion = (
        T * c / J
    )

    sigma_vm = math.sqrt(
        sigma_normal_worst**2
        + 3.0 * tau_torsion**2
    )

    # Separate deliberately conservative transverse-shear screen.
    tau_transverse_screen = (
        2.0 * V / A
    )

    return {
        "sigma_axial_Pa": sigma_axial,
        "sigma_bending_Pa": sigma_bending,
        "sigma_normal_worst_Pa": sigma_normal_worst,
        "tau_torsion_Pa": tau_torsion,
        "sigma_vm_Pa": sigma_vm,
        "tau_transverse_screen_Pa": tau_transverse_screen,
    }


# =============================================================================
# 6. BUCKLING
# =============================================================================

def buckling_capacity(
    section,
    exposed_length,
):
    """
    Johnson / Euler transition.

    Slenderness:
        lambda = K L / r

    Transition:
        Cc = sqrt(2*pi^2*E/Sy)

    Johnson:
        sigma_cr = Sy * [
            1 - Sy/(4*pi^2*E) * lambda^2
        ]

    Euler:
        sigma_cr = pi^2*E/lambda^2
    """

    A = section["A_m2"]
    r_g = section["r_g_m"]

    slenderness = (
        K_buckling
        * exposed_length
        / r_g
    )

    Cc = math.sqrt(
        2.0
        * math.pi**2
        * E
        / Sy
    )

    if slenderness <= Cc:
        method = "JOHNSON"

        sigma_cr = (
            Sy
            * (
                1.0
                - (
                    Sy
                    * slenderness**2
                    / (
                        4.0
                        * math.pi**2
                        * E
                    )
                )
            )
        )

    else:
        method = "EULER"

        sigma_cr = (
            math.pi**2
            * E
            / slenderness**2
        )

    Pcr = (
        sigma_cr
        * A
    )

    return {
        "method": method,
        "slenderness": slenderness,
        "Cc": Cc,
        "sigma_cr_Pa": sigma_cr,
        "Pcr_N": Pcr,
    }


# =============================================================================
# 7. GEOMETRY EVALUATION
# =============================================================================

def evaluate_geometry(
    Do,
    wall,
    h,
):
    section = section_properties(
        Do,
        wall,
    )

    rows = []

    for level in (
        "limit",
        "ultimate",
    ):

        for case_name, force in loads[level].items():

            resultants = piston_resultants(
                force,
                h,
            )

            stress = stress_state(
                section,
                resultants,
            )

            rows.append({
                "level": level,
                "case": case_name,
                **resultants,
                **stress,
            })

    limit_rows = [
        row
        for row in rows
        if row["level"] == "limit"
    ]

    ultimate_rows = [
        row
        for row in rows
        if row["level"] == "ultimate"
    ]

    worst_limit_vm = max(
        limit_rows,
        key=lambda row: row["sigma_vm_Pa"],
    )

    worst_ultimate_vm = max(
        ultimate_rows,
        key=lambda row: row["sigma_vm_Pa"],
    )

    worst_limit_shear = max(
        limit_rows,
        key=lambda row: row[
            "tau_transverse_screen_Pa"
        ],
    )

    worst_ultimate_shear = max(
        ultimate_rows,
        key=lambda row: row[
            "tau_transverse_screen_Pa"
        ],
    )

    buckling = buckling_capacity(
        section,
        exposed_length=h,
    )

    max_ultimate_compression_N = max(
        abs(
            row["Nc_kN"]
        ) * 1e3
        for row in ultimate_rows
    )

    MS_yield_limit = (
        Sy
        / worst_limit_vm["sigma_vm_Pa"]
        - 1.0
    )

    MS_ultimate = (
        Su
        / worst_ultimate_vm["sigma_vm_Pa"]
        - 1.0
    )

    MS_shear_limit = (
        tau_y_allow
        / worst_limit_shear[
            "tau_transverse_screen_Pa"
        ]
        - 1.0
    )

    MS_shear_ultimate = (
        tau_u_allow
        / worst_ultimate_shear[
            "tau_transverse_screen_Pa"
        ]
        - 1.0
    )

    MS_buckling = (
        buckling["Pcr_N"]
        / max_ultimate_compression_N
        - 1.0
    )

    passes = all([
        MS_yield_limit >= 0.0,
        MS_ultimate >= 0.0,
        MS_shear_limit >= 0.0,
        MS_shear_ultimate >= 0.0,
        MS_buckling >= 0.0,
    ])

    return {
        "Do_mm": Do * 1000.0,
        "wall_mm": wall * 1000.0,
        "Di_mm": section["Di_m"] * 1000.0,
        "h_mm": h * 1000.0,
        "A_mm2": section["A_m2"] * 1e6,
        "I_mm4": section["I_m4"] * 1e12,
        "J_mm4": section["J_m4"] * 1e12,
        "mass_per_m_kg": section["mass_per_m_kg"],

        "limit_governing_case": worst_limit_vm["case"],
        "limit_vm_MPa": worst_limit_vm["sigma_vm_Pa"] / 1e6,
        "MS_yield_limit": MS_yield_limit,

        "ultimate_governing_case": worst_ultimate_vm["case"],
        "ultimate_vm_MPa": worst_ultimate_vm["sigma_vm_Pa"] / 1e6,
        "MS_ultimate": MS_ultimate,

        "limit_shear_case": worst_limit_shear["case"],
        "limit_tau_screen_MPa": (
            worst_limit_shear[
                "tau_transverse_screen_Pa"
            ]
            / 1e6
        ),
        "MS_shear_limit": MS_shear_limit,

        "ultimate_shear_case": worst_ultimate_shear["case"],
        "ultimate_tau_screen_MPa": (
            worst_ultimate_shear[
                "tau_transverse_screen_Pa"
            ]
            / 1e6
        ),
        "MS_shear_ultimate": MS_shear_ultimate,

        "buckling_method": buckling["method"],
        "slenderness": buckling["slenderness"],
        "Cc": buckling["Cc"],
        "Pcr_kN": buckling["Pcr_N"] / 1000.0,
        "MS_buckling": MS_buckling,

        "PASS": passes,
    }


# =============================================================================
# 8. RUN DESIGN SWEEP
# =============================================================================

designs = []

n_steps = int(
    round(
        (t_max_mm - t_min_mm)
        / t_step_mm
    )
) + 1

wall_values_mm = [
    t_min_mm
    + i * t_step_mm
    for i in range(n_steps)
]

for h in h_cases:

    for wall_mm in wall_values_mm:

        design = evaluate_geometry(
            Do=Do_baseline,
            wall=wall_mm / 1000.0,
            h=h,
        )

        designs.append(
            design
        )


# =============================================================================
# 9. REGRESSION CHECK — 58 x 4 mm, h = 350 mm
# =============================================================================

def find_design(
    h_mm,
    wall_mm,
):
    for row in designs:

        if (
            abs(
                row["h_mm"]
                - h_mm
            ) < 1e-9
            and abs(
                row["wall_mm"]
                - wall_mm
            ) < 1e-9
        ):
            return row

    raise KeyError(
        "Requested design not found."
    )


working_candidate = find_design(
    h_mm=350.0,
    wall_mm=4.0,
)


def assert_close(
    label,
    calculated,
    reference,
    tolerance,
):
    error = abs(
        calculated
        - reference
    )

    assert error <= tolerance, (
        f"{label} regression failed: "
        f"calculated={calculated:.6f}, "
        f"reference={reference:.6f}, "
        f"error={error:.6f}"
    )


assert_close(
    "58x4 h=350 limit VM [MPa]",
    working_candidate["limit_vm_MPa"],
    682.114746,
    1e-3,
)

assert_close(
    "58x4 h=350 ultimate VM [MPa]",
    working_candidate["ultimate_vm_MPa"],
    1023.172119,
    1e-3,
)

assert_close(
    "58x4 h=350 buckling [kN]",
    working_candidate["Pcr_kN"],
    771.433581,
    1e-3,
)


# =============================================================================
# 10. WRITE CSV
# =============================================================================

output_csv = (
    here
    / "phase2_piston_sizing.csv"
)

with output_csv.open(
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=list(
            designs[0].keys()
        ),
    )

    writer.writeheader()
    writer.writerows(
        designs
    )


# =============================================================================
# 11. CONSOLE REPORT
# =============================================================================

print()
print("=" * 90)
print(
    " PHASE 2D1 — LOWER PISTON "
    "PRELIMINARY STRUCTURAL SIZING"
)
print("=" * 90)

print()
print("--- INPUT CONNECTION ---")
print(
    f"Phase 2C result file:             "
    f"{phase2_csv}"
)

print()
print("--- MATERIAL BASELINE: 300M STEEL ---")
print(
    f"E:                               "
    f"{E/1e9:.1f} GPa"
)
print(
    f"G:                               "
    f"{G/1e9:.1f} GPa"
)
print(
    f"Poisson ratio:                    "
    f"{nu:.2f}"
)
print(
    f"Density:                          "
    f"{rho:.0f} kg/m^3"
)
print(
    f"Yield screening strength:         "
    f"{Sy/1e6:.0f} MPa"
)
print(
    f"Ultimate screening strength:      "
    f"{Su/1e6:.0f} MPa"
)

print()
print("--- GEOMETRY SCREEN ---")
print(
    f"Baseline OD:                      "
    f"{Do_baseline*1000:.1f} mm"
)
print(
    f"Critical-section h sweep:         "
    f"{', '.join(f'{h*1000:.0f}' for h in h_cases)} mm"
)
print(
    f"Wall sweep:                       "
    f"{t_min_mm:.2f} to "
    f"{t_max_mm:.2f} mm"
)
print(
    f"Buckling K:                       "
    f"{K_buckling:.1f} "
    f"(cantilever screening)"
)

print()
print("--- MINIMUM PASSING WALL AT EACH h ---")
print(
    f"{'h (mm)':>8}"
    f"{'t_min (mm)':>12}"
    f"{'Limit VM':>12}"
    f"{'Ult VM':>12}"
    f"{'Pcr kN':>12}"
    f"{'Gov LC':>10}"
)
print("-" * 66)

for h in h_cases:

    subset = [
        row
        for row in designs
        if (
            abs(
                row["h_mm"]
                - h * 1000.0
            ) < 1e-9
            and row["PASS"]
        )
    ]

    if subset:

        first = min(
            subset,
            key=lambda row: row["wall_mm"],
        )

        print(
            f"{first['h_mm']:>8.0f}"
            f"{first['wall_mm']:>12.2f}"
            f"{first['limit_vm_MPa']:>12.1f}"
            f"{first['ultimate_vm_MPa']:>12.1f}"
            f"{first['Pcr_kN']:>12.1f}"
            f"{first['ultimate_governing_case']:>10}"
        )

    else:

        print(
            f"{h*1000:>8.0f}"
            f"{'NO PASS':>12}"
        )

print()
print("--- WORKING CANDIDATE: 58 mm OD x 4 mm WALL ---")
print(
    f"Critical-section distance h:      "
    f"{working_candidate['h_mm']:.0f} mm"
)
print(
    f"Inner diameter:                   "
    f"{working_candidate['Di_mm']:.1f} mm"
)
print(
    f"Area:                             "
    f"{working_candidate['A_mm2']:.1f} mm^2"
)
print(
    f"I:                                "
    f"{working_candidate['I_mm4']:.0f} mm^4"
)
print(
    f"J:                                "
    f"{working_candidate['J_mm4']:.0f} mm^4"
)
print(
    f"Mass per metre:                   "
    f"{working_candidate['mass_per_m_kg']:.3f} kg/m"
)

print()
print(
    f"Limit governing case:             "
    f"{working_candidate['limit_governing_case']}"
)
print(
    f"Limit von Mises stress:           "
    f"{working_candidate['limit_vm_MPa']:.1f} MPa"
)
print(
    f"Limit yield margin:               "
    f"{working_candidate['MS_yield_limit']:+.3f}"
)

print()
print(
    f"Ultimate governing case:          "
    f"{working_candidate['ultimate_governing_case']}"
)
print(
    f"Ultimate VM screening stress:     "
    f"{working_candidate['ultimate_vm_MPa']:.1f} MPa"
)
print(
    f"Ultimate strength margin:         "
    f"{working_candidate['MS_ultimate']:+.3f}"
)

print()
print(
    f"Transverse shear screen, limit:   "
    f"{working_candidate['limit_tau_screen_MPa']:.1f} MPa"
)
print(
    f"Transverse shear screen, ult:     "
    f"{working_candidate['ultimate_tau_screen_MPa']:.1f} MPa"
)

print()
print(
    f"Buckling method:                  "
    f"{working_candidate['buckling_method']}"
)
print(
    f"Slenderness KL/r:                 "
    f"{working_candidate['slenderness']:.2f}"
)
print(
    f"Transition Cc:                    "
    f"{working_candidate['Cc']:.2f}"
)
print(
    f"Critical buckling load:           "
    f"{working_candidate['Pcr_kN']:.1f} kN"
)
print(
    f"Buckling margin:                  "
    f"{working_candidate['MS_buckling']:+.3f}"
)

print()
print(
    f"Preliminary screen:               "
    f"{'PASS' if working_candidate['PASS'] else 'FAIL'}"
)
print()
print(
    "NOTE: 4 mm is a working preliminary wall, "
    "not a frozen final thickness."
)
print(
    "Local bushing loads, stress concentrations, "
    "fatigue, and fracture checks come later."
)

print()
print("Regression checks:                PASS")
print(
    f"CSV written to:                   "
    f"{output_csv.name}"
)
print("=" * 90)
