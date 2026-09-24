# Landing_Gear_Design_Project — Phase 2 Preliminary Design Baseline V1

**Review outcome:** PRELIMINARY BASELINE READY — OPEN DETAIL/PACKAGING ITEMS REMAIN

This report is generated from the Phase 1 / Phase 2 CSV calculation chain. Calculated stresses, reactions, and margins are not transcribed from chat.

## Status summary

| Status | Count |
|---|---:|
| FROZEN | 11 |
| LOCK_PRELIMINARY | 22 |
| KEEP_PARAMETRIC | 8 |
| DEFER_DETAIL_FEA | 2 |

## Baseline

| Subsystem | Parameter | Value | Unit | Status | Source |
|---|---|---:|---|---|---|
| Project / frozen input | Aircraft mass | 1700.0 | kg | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Screening weight used in Phase 1 | 16.68 | kN | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Wheelbase | 2.35 | m | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Main-gear track | 3.2 | m | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Wheel/strut lateral offset e | 120.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Static loaded tire radius | 175.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Physical oleo stroke | 230.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Static oleo sag | 50.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Full-extension U-to-A length | 525.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Static U-to-A length | 475.0 | mm | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Project / frozen input | Ultimate factor | 1.5 | - | FROZEN | Phase 0 / Phase 1 / Phase 2B |
| Lower piston | Structural OD | 58.0 | mm | LOCK_PRELIMINARY | phase2_piston_sizing.csv |
| Lower piston | Wall thickness | 4.0 | mm | LOCK_PRELIMINARY | phase2_piston_sizing.csv |
| Outer barrel | Bore / ID | 64.0 | mm | LOCK_PRELIMINARY | phase2_barrel_sizing.csv |
| Outer barrel | Smooth wall thickness | 5.0 | mm | LOCK_PRELIMINARY | phase2_barrel_sizing.csv |
| Outer barrel | Smooth OD | 74.0 | mm | LOCK_PRELIMINARY | phase2_barrel_sizing.csv |
| Guide system | Lower bushing static station h_L | 250.0 | mm above axle | LOCK_PRELIMINARY | phase2_packaging_overlap.csv |
| Guide system | Bushing spacing | 150.0 | mm | LOCK_PRELIMINARY | phase2_packaging_overlap.csv |
| Guide system | Upper bushing static station h_U | 400.0 | mm above axle | LOCK_PRELIMINARY | phase2_packaging_overlap.csv |
| Guide system | Bushing axial length | 30.0 | mm | LOCK_PRELIMINARY | phase2_bushing_material_gland_requirements.csv |
| Guide system | Bushing material | C63000 / AMS 4640 Ni-Al bronze |  | LOCK_PRELIMINARY | phase2_bushing_material_gland_requirements.csv |
| Guide system | Bushing radial wall | 3.0 | mm | LOCK_PRELIMINARY | phase2_bushing_material_gland_requirements.csv |
| Guide / packaging | Top guide-surface overrun | 20.0 | mm | KEEP_PARAMETRIC | phase2_packaging_overlap.csv |
| Guide / packaging | Required piston guide-surface length | 485.0 | mm | KEEP_PARAMETRIC | phase2_packaging_overlap.csv |
| Gland | Architecture | Integral shoulder + bronze guide/seal carrier + threaded gland nut |  | LOCK_PRELIMINARY | phase2_gland_retainer_sizing.csv |
| Gland | Thread envelope | M70 x 2 equivalent 60-deg envelope |  | KEEP_PARAMETRIC | phase2_gland_retainer_sizing.csv |
| Gland | Thread engagement | 12.0 | mm | KEEP_PARAMETRIC | phase2_gland_retainer_sizing.csv |
| Lower barrel boss | Local boss OD | 84.0 | mm | LOCK_PRELIMINARY | phase2_gland_retainer_sizing.csv |
| Lower barrel boss | Boss-to-smooth-barrel transition land | 15.0 | mm | KEEP_PARAMETRIC | phase2_lower_barrel_boss_sizing.csv |
| Lower barrel boss | Actual fillet radius / local Kt | OPEN |  | DEFER_DETAIL_FEA | phase2_lower_barrel_boss_sizing.csv |
| Axle / spindle | Smooth root OD | 50.0 | mm | LOCK_PRELIMINARY | phase2_axle_sizing.csv |
| Axle / spindle | Smooth root wall | 8.0 | mm | LOCK_PRELIMINARY | phase2_axle_sizing.csv |
| Axle / spindle | Axle-to-piston local transition | OPEN |  | DEFER_DETAIL_FEA | phase2_axle_sizing.csv |
| Upper attachment | Trunnion architecture | Two bearings on +x axis + independent Mx brace path |  | LOCK_PRELIMINARY | phase2_upper_trunnion_sizing.csv |
| Upper attachment | Trunnion journal diameter | 32.0 | mm | LOCK_PRELIMINARY | phase2_upper_trunnion_sizing.csv |
| Upper attachment | Trunnion bearing width | 25.0 | mm | LOCK_PRELIMINARY | phase2_upper_trunnion_sizing.csv |
| Upper attachment | Trunnion support span | 120.0 | mm | KEEP_PARAMETRIC | phase2_upper_trunnion_sizing.csv |
| Upper brace | Tube OD | 25.0 | mm | LOCK_PRELIMINARY | phase2_upper_brace_sizing.csv |
| Upper brace | Tube wall | 3.0 | mm | LOCK_PRELIMINARY | phase2_upper_brace_sizing.csv |
| Upper brace | Pin diameter | 18.0 | mm | LOCK_PRELIMINARY | phase2_upper_brace_sizing.csv |
| Upper brace | Pin-bushing projected width | 20.0 | mm | LOCK_PRELIMINARY | phase2_upper_brace_sizing.csv |
| Upper brace | Effective perpendicular moment arm | 250.0 | mm | KEEP_PARAMETRIC | phase2_upper_brace_sizing.csv |
| Upper brace | Pin-to-pin free length | 350.0 | mm | KEEP_PARAMETRIC | phase2_upper_brace_sizing.csv |

## Compatibility / structural review

| Check | Result | Detail | Severity |
|---|---|---|---|
| Piston OD matches D5 bearing interface | PASS | piston OD = 58.0 mm | REQUIRED |
| Bushing OD matches barrel bore | PASS | bushing OD = 64.0 mm, barrel ID = 64.0 mm | REQUIRED |
| Bushing radial stack is self-consistent | PASS | (barrel ID - piston OD)/2 = 3.0 mm, D5 bushing wall = 3.0 mm | REQUIRED |
| Full lower-bushing engagement at physical stroke | PASS | reserve = +55.0 mm | REQUIRED |
| Full lower-bushing engagement in V0.5b diagnostic | PASS | reserve = +44.2 mm | DIAGNOSTIC |
| Local gland boss is thicker than smooth barrel | PASS | boss OD = 84.0 mm, smooth barrel OD = 74.0 mm | REQUIRED |
| Gland boss retains positive thread-root wall | PASS | boss root wall = 7.00 mm | REQUIRED |
| Gland nut retains positive root wall over through-bore | PASS | gland root wall = 4.27 mm | REQUIRED |
| Piston preliminary structural screen | PASS | ultimate VM = 1023.2 MPa, MS = +0.820 | REQUIRED |
| Barrel preliminary structural/pressure screen | PASS | ultimate VM = 595.2 MPa, MS = +2.128 | REQUIRED |
| Lower boss transition at review Kt | PASS | Kt = 2.0, ultimate VM = 230.1 MPa, MS = +7.091 | REQUIRED |
| Axle root preliminary screen | PASS | ultimate VM = 481.2 MPa, MS = +2.870 | REQUIRED |
| Upper trunnion preliminary screen | PASS | ultimate VM = 460.0 MPa, bearing p = 101.9 MPa | REQUIRED |
| Upper brace tube preliminary screen | PASS | MS ultimate = +8.530, MS buckling = +3.871 | REQUIRED |
| Upper brace pin/bushing preliminary screen | PASS | pin shear MS = +12.505, bearing MS = +2.676 | REQUIRED |
| Upper Mx load path exists | PASS | brace effective arm = 250 mm; calculated ultimate brace force = 40.51 kN | REQUIRED |
| Axle-to-piston local root geometry resolved | OPEN | smooth piston ID = 50.0 mm and axle OD = 50.0 mm; this is not a through-fit requirement, but the forged/welded/local axle-to-piston transition has not yet been defined | OPEN_DETAIL |
| Physical upper-barrel/cavity package above U resolved | OPEN | current packaging model requires 190.0 mm piston-top intrusion above equivalent datum U at physical stroke | OPEN_PACKAGING |
| Actual trunnion/brace airframe fitting geometry resolved | OPEN | journal spacing and brace arm/free length remain preliminary until airframe fitting CAD is established | OPEN_PACKAGING |

## Open items

| Priority | Item | Resolution gate |
|---|---|---|
| HIGH | Axle-to-piston lower-end architecture | Detailed lower-strut CAD + local stress/FEA |
| HIGH | Upper barrel / piston cavity above equivalent datum U | Full strut packaging CAD |
| HIGH | Physical trunnion / brace airframe fitting coordinates | Airframe-interface CAD / structural arrangement |
| MEDIUM | Gland production thread / lock / seal definition | Detailed gland design |
| MEDIUM | Actual fillet radii and stress concentrations | Detailed CAD + FEA/fatigue |
| MEDIUM | Wheel bearing seats / brake flange / wheel-retention spindle detail | Wheel/brake interface design |
| MEDIUM | Brace clevis/lug/pin bending details | Detailed upper-joint design |
| LATER | Fatigue / fracture / fretting / corrosion / surface treatment | Later structural substantiation phase |
| LATER | Retraction mechanism | Optional later extension |

## Baseline rule

Items marked **LOCK_PRELIMINARY** are now the Phase 2 baseline and should be used by downstream analyses unless a deliberate design-change decision reopens them. **KEEP_PARAMETRIC** items remain active packaging variables. **DEFER_DETAIL_FEA** items are intentionally unresolved until the appropriate detailed-design stage.