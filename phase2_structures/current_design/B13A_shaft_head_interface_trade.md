# Phase 2E3-B13A — Shaft / Head Interface Architecture Trade

## Working architecture

**Selected working concept:** removable Ø38 mm 300M cross-pin running in two replaceable
C63000 / AMS 4640 nickel-aluminum-bronze head bushings.

Load path:

`7075-T6 head -> bronze bushings -> 300M shaft -> external airframe bearings`

The independent brace / lock-link remains the reaction path for `Mx`.

## Why B13 exists

B12/B12C showed that the extreme local head stress was controlled by the termination of the
idealized bonded shaft/head interface. A head-only path offset approximately 0.5 mm from that
termination dropped to roughly 191–238 MPa, while the exact interface edge remained far higher.
The bonded model is therefore retained only as historical sensitivity evidence, not as the final
physical interface.

## Concept trade

| Concept | Benefit | Main drawback | B13 disposition |
|---|---|---|---|
| Direct 300M-to-7075 interference fit | simple, rigid | adds fit stress directly to 7075; poorer serviceability | not preferred |
| Replaceable bronze bushings + removable pin | replaceable wear surface; realistic pin joint | needs fit/contact analysis | **working selection** |
| Split/clamped boss | removable and rigidizable | more parts, preload and package complexity | reserve option |

## Freeze boundary

B13A freezes the *architecture*, not final dimensions.

Working starting dimensions for B13B:
- shaft nominal diameter: 38 mm
- current CAD head OD input: 106 mm
- bushing material: C63000 / AMS 4640 nickel-aluminum bronze
- initial practical candidate explored: 50 mm OD × 30 mm length per side

Still open:
- bronze-to-7075 interference/retention fit
- shaft running clearance
- lubrication/wear/fretting
- final bushing OD and length
- 7075 local bearing/net-section/shear-out
- nonlinear contact FEA
