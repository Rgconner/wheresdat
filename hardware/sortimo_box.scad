// WheresDat — Parametric small-parts box, sized to drop into
// sortimo_tray.scad's pockets.
//
// Originally included a raised label platform in one top corner,
// inspired by a Sortimo T-Boxx 2018 insert box design. Removed: a
// platform floating above the rim is an overhang, which forces support
// material when the box is printed on its side (the practical
// orientation for an open-top box) — wasted filament, and supports
// touching what's supposed to be a clean label surface is a lose-lose.
// A label just goes directly on a flat wall or the top rim instead, no
// raised feature needed.
//
// Not yet rendered/validated (no OpenSCAD CLI in this environment) —
// open in the real app, and test-fit one box against a printed tray
// pocket before committing to a batch.

/* [Grid — must match sortimo_tray.scad] */
// Changed 2026-09-07: the tray moved from individually-walled per-cell
// pockets to open channels (one central divider, no interior walls
// within a channel — see sortimo_tray.scad). Box WIDTH is still bounded
// by real tray-cut walls (the outer wall on one side, the center divider
// on the other) so it keeps the old wall-based clearance formula, fixed
// at exactly one channel wide. Box LENGTH now runs free in whole units
// (1-4) with no tray wall between adjacent boxes in the same channel —
// several can sit end to end (1x1 + 1x1 + 2x1, or one 4x1, etc.).
module_size   = 52.3; // mm — keep this in sync with sortimo_tray.scad's module_size by hand; not auto-shared across files
units_x       = 1;    // length in grid modules (1-4): how many units long this box is
units_y       = 1;    // width in CHANNELS: 1 (normal, fits one channel) or 2 (wide — straddles
                       // both channels, needs the notch below to clear the center divider)

/* [Tray fit] */
// Width: same formula as before — the channel is still bounded by real
// printed walls on both long sides, so it needs the same wall-based
// clearance logic.
// Length: NOT bounded by a tray wall except at the very ends of a
// channel — an interior box just butts up against its neighbor, so this
// uses a small fixed allowance instead of the wall-based formula. Not a
// sourced value, just enough to keep several boxes from binding
// end-to-end — verify with a test run of e.g. a 1x1 + 3x1 pair before
// committing to a full batch.
tray_wall_thickness = 3;   // mm — copy of the tray file's wall_thickness, for computing channel width here
tray_fit_clearance  = 0.3; // mm — copy of the tray file's fit_clearance
tray_pocket_depth   = 8;   // mm — copy of the tray file's pocket_depth, so a units_y=2 box knows how tall the divider stands above the channel floor
box_fit_clearance   = 0.3; // mm, additional per-side width clearance so the box drops into the channel freely
length_clearance    = 0.2; // mm, per-side length allowance so end-to-end boxes don't bind

/* [Divider notch — only used when units_y = 2] */
// A units_y=2 box's outer footprint spans corner-to-corner across BOTH
// channels (bounded only by the tray's true outer walls), which means
// the tray's solid center divider sits physically inside that footprint
// — the box has to notch around it or it won't sit flat. The notch is
// full-depth (clears the divider's whole height above the channel
// floor) and runs the box's full length, centered on the divider.
// NOTE: this leaves the divider poking up into the box's interior as a
// ridge (it's taller than the box's own floor), splitting a wide box
// into two shallow sub-compartments rather than one flat-floored bin —
// reusing the tray's own structure instead of building a separate
// internal wall. If a continuous flat floor across the full width
// matters more than that, this needs a raised/stepped floor instead —
// flag it and it can be redone.
notch_fit_clearance = 0.3; // mm, per-side clearance so the notch doesn't bind on the divider
notch_depth_clearance = 0.3; // mm, extra depth so the notch fully clears the divider's top

/* [Box construction] */
box_height    = 25;  // mm — not a sourced spec, just a reasonable default for small parts; change freely
// Doubled 2 -> 4mm (2026-09-08): thin perimeters don't have enough
// cross-sectional bonding area between adjacent print paths and were
// separating during printing — confirmed on a real print, not a
// theoretical concern. 4mm gives real overlap between passes.
wall          = 4;   // mm
floor         = 2;   // mm

// ---------------------------------------------------------------------
// Derived geometry
// ---------------------------------------------------------------------

// units_y=1 uses the same per-channel formula as always. units_y=2 spans
// both channels as one continuous outer envelope (bounded only by the
// tray's true outer walls, same insets applied once at each far edge —
// see sortimo_tray.scad's pocket math, this mirrors it for a merged span).
box_y = units_y * module_size - 2 * (tray_wall_thickness / 2 + tray_fit_clearance) - 2 * box_fit_clearance;
box_x = units_x * module_size - 2 * length_clearance; // free-running — 1 to 4 units long

// Divider gap: the actual solid width of the tray's center wall as cut
// (wall_thickness plus the fit_clearance left over on each adjacent
// pocket) — must match sortimo_tray.scad's real geometry, not just its
// nominal wall_thickness.
divider_gap   = tray_wall_thickness + 2 * tray_fit_clearance;
notch_width   = divider_gap + 2 * notch_fit_clearance;
notch_depth   = tray_pocket_depth + notch_depth_clearance;

// 2 x 45s instead of 1 sharp 90 at each base corner touching the print
// bed — sharp corners are exactly where FDM prints concentrate cooling
// stress and curl/lift off the plate; this relieves the stress point
// rather than fighting it with more bed adhesion. Only affects the
// bottom chamfer_height of the part, not the functional geometry above
// it. "A couple mm," per Russ, not a structural taper.
chamfer_size   = 2; // mm, cut along each edge meeting at the corner
chamfer_height = 2; // mm, how far up from the base the cut runs

module base_chamfer_cut(width, depth, size, height) {
    corners = [[0, 0], [width, 0], [0, depth], [width, depth]];
    for (c = corners) {
        dx = (c[0] == 0) ? 1 : -1;
        dy = (c[1] == 0) ? 1 : -1;
        translate([c[0], c[1], -0.5])
            linear_extrude(height = height + 0.5)
                polygon([[0, 0], [dx * size, 0], [0, dy * size]]);
    }
}

module small_parts_box() {
    difference() {
        cube([box_x, box_y, box_height]);
        translate([wall, wall, floor])
            cube([box_x - 2 * wall, box_y - 2 * wall, box_height]); // open top, cut through

        // Divider notch — only when this box straddles both channels.
        // Centered on box_y (the divider sits at the midpoint of a
        // symmetric 2-channel span), cut from the bottom face up through
        // the divider's full height.
        if (units_y > 1) {
            translate([-0.5, box_y / 2 - notch_width / 2, -0.5])
                cube([box_x + 1, notch_width, notch_depth + 0.5]); // +1/+0.5 so cuts clear the faces cleanly
        }

        base_chamfer_cut(box_x, box_y, chamfer_size, chamfer_height);
    }
}

small_parts_box();
