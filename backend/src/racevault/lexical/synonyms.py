"""Motorsport vocabulary equivalences for search-time lexical expansion.

BM25 matches surface forms. Motorsport documents in one corpus are written by
regulators, a manufacturer, and component suppliers across several regions, so
the same component is named differently from document to document: Australian
regulations say "tyre" where North American ones say "tire", a supplier writes
"shock absorber" where a manual writes "damper", and acronyms stand in for full
names throughout.

Rules
-----
Only genuine naming equivalences belong here. Two entries never share a term
unless they mean the same thing in every context, because a graph synonym pulls
its whole group into every query that touches it. Units are grouped only when
the same quantity has several spellings ("nm", "newton metre"); never when the
values differ ("psi", "bar"), which would make numeric answers wrong. Terms that
regulations use to separate obligation from advice ("shall", "should", "may")
are left untouched for the same reason.

The list is applied as a search-time `synonym_graph` filter, so it can be
extended without reindexing the corpus.
"""

from __future__ import annotations

MOTORSPORT_SYNONYMS: tuple[str, ...] = (
    # Regulations legislate about the "Automobile"; people ask about the "car".
    "automobile, car, vehicle",
    "weight, weigh, mass",
    # Regional spelling
    "tyre, tire",
    "kerb, curb",
    "tyre wall, tire wall",
    "litre, liter",
    "metre, meter",
    "centre, center",
    "stabiliser, stabilizer",
    "aluminium, aluminum",
    # Chassis and suspension
    "damper, shock absorber, shock",
    "anti-roll bar, antiroll bar, roll bar, sway bar, stabiliser bar, arb",
    "ride height, ground clearance",
    "wishbone, control arm, a-arm",
    "upright, hub carrier, knuckle",
    "spring rate, spring stiffness",
    "bump stop, bumpstop, packer",
    "corner weight, corner weighting",
    # Wheels and tyres
    "rim, wheel rim",
    "et, wheel offset, offset",
    "rolling circumference, circumference",
    "tyre pressure, inflation pressure, cold pressure",
    "wheel nut, wheel bolt, lug nut",
    # Braking
    "abs, anti-lock braking system, antilock braking system, anti lock brake",
    "brake bias, brake balance, brake distribution",
    "brake disc, brake rotor, disc rotor",
    "brake pad, friction pad",
    "brake caliper, caliper",
    # Drivetrain
    "gearbox, transmission",
    "differential, diff",
    "lsd, limited slip differential",
    "driveshaft, drive shaft, halfshaft, half shaft",
    "clutch pack, clutch plate",
    "final drive, crown wheel and pinion",
    # Engine and electronics
    "ecu, engine control unit, engine management",
    "tc, traction control",
    "engine map, calibration map, fuel map",
    "lambda, air fuel ratio, afr",
    "knock, detonation, pinking",
    "rpm, engine speed, revs",
    "bhp, hp, horsepower",
    "nm, newton metre, newton meter",
    "wiring loom, wiring harness, cable loom",
    "telemetry, data logging, datalogging",
    "dashboard, dash display, steering wheel display",
    "coolant temperature, water temperature",
    # Aerodynamics and bodywork
    "aero, aerodynamic",
    "undertray, floor, underbody",
    "splitter, front splitter, front lip",
    "rear wing, rear aerofoil, rear airfoil",
    "diffuser, rear diffuser",
    "bodywork, panel work",
    # Safety equipment
    "roll cage, rollcage, safety cage",
    "safety harness, seat belt, seatbelt, six point harness",
    "hans, head and neck restraint, frhd",
    "fuel cell, fuel bladder, fuel tank",
    "fire extinguisher, fire suppression, extinguisher system",
    "window net, window netting",
    "seat insert, seat padding",
    # Sporting procedure
    "scrutineering, technical inspection, tech inspection, eligibility check",
    "parc ferme, parc ferme conditions, impound",
    "safety car, pace car",
    "formation lap, warm up lap, warmup lap, parade lap",
    "qualifying, qualification, quali",
    "free practice, practice session",
    "pit lane, pitlane, pits",
    "pit stop, pitstop",
    "track limits, circuit limits",
    "grid, starting grid",
    "minimum weight, weight limit",
    "homologation, homologated specification",
    "ballast, weight ballast",
    "driving standards, on track conduct",
    # Vehicle naming
    "gt3 cup, cup car",
    "carrera cup, pcc",
    "supercup, psc",
)
