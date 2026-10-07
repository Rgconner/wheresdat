// WheresDat — Shelf unit end caps (top + bottom), carbon-rod corner posts
//
// Structural approach (see SPEC.md, "Irregular-size kit boxes get open
// shelves"): 4x solid carbon fiber square rod corner posts, real sourced
// size 6x6x420mm. Caps consume 10mm of post length at each end (420mm -
// 10 - 10 = 400mm usable post span left for shelves to slide on).
// One cap design serves both top and bottom — no differentiation
// requested yet.
//
// Not yet rendered/validated (no OpenSCAD CLI in this environment) —
// open in the actual app before printing, same caveat as
// hardware/sortimo_tray.scad.

/* [Printer] */
// Real printer bed is 300x300mm (see sortimo_tray.scad), but the target
// here is 280mm, not 300 — large flat prints like this need a brim for
// bed adhesion (corners lift otherwise), and a brim needs room outside
// the part's own footprint. Designing to the raw bed limit would leave
// no space for one.
max_footprint = 280; // mm

/* [Post geometry — real, sourced] */
post_size       = 6;   // mm, square cross-section (6x6x420mm carbon rod)
post_clearance  = 0.3; // mm, per-side fit clearance so the post slides/press-fits into its socket
cap_thickness   = 10;  // mm — "sacrifice 10mm top and bottom for the caps"

/* [Footprint — sized to hold 2 stacked 2x4 sortimo_tray.scad trays] */
// Derived 2026-09-07 from the tray's real dimensions (tray_x=219.2mm,
// tray_y=114.6mm at current defaults) for the "one shelf holds 2 trays,
// deep enough" layout: two trays stacked FRONT-TO-BACK (doubling the
// 114.6mm depth axis), not side-by-side left-right (doubling the 219.2mm
// axis instead) — the left-right layout would need a ~438mm-wide cap
// plate, well past the 280mm max_footprint above, so it's not printable
// as one piece. If side-by-side is actually what's wanted, this needs a
// split-cap design instead (same idea as sortimo_tray.scad's two-piece
// tray), not just different numbers here.
//
// First pass at this (post_spacing 230x240) still didn't actually fit
// two real trays laid over it — two things drove that: the fit
// clearance was razor-thin (2mm/side, near zero margin for print
// variance), and it didn't budget any depth at all for the front
// stopper rod below, which eats into the same Y axis the trays sit in.
// Widened for real here rather than nudged, since there was ~20mm of
// unused headroom under max_footprint going to waste anyway. Still not
// test-fit against a real print — two misses in a row on this number is
// reason enough to actually verify before committing to the full cap.
side_edge_clearance = 8;      // mm, per side (left/right, X axis) — general drop-in margin, not rod-related
back_edge_clearance = 8;      // mm, back side (Y axis) — general drop-in margin
front_rod_size      = 2;      // mm, the 2mm square carbon rod glued across the front
front_rod_clearance = 0.6;    // mm, total (0.3/side) so the rod seats without binding
// front_rod_depth is space reserved on the front (Y axis) for the rod to
// sit as a stopper right at the tray's front edge — the actual socket/
// groove that holds it is a feature of the shelf panel (not yet built),
// this just makes sure the overall footprint has room for it.
front_rod_depth     = front_rod_size + front_rod_clearance;

post_spacing_x = 219.2 + post_size + 2 * side_edge_clearance; // one tray's width + margin both sides
post_spacing_y = 2 * 114.6 + post_size + back_edge_clearance + front_rod_depth; // 2 stacked trays' depth + back margin + front rod allowance

/* [Frame + X-girder — replaces the old honeycomb lattice] */
// The honeycomb produced a lot of small print-path corners (every hex
// cell is 6 of them) — slow and a lot of direction-change stress points
// for not much structural benefit. Solid frame around the perimeter plus
// two diagonal beams crossing in the center is far simpler to print and
// still ties the whole plate together.
min_wall     = 3;  // mm — the one hard constraint: "at least 3mm thick for support"
frame_width  = 20; // mm, solid border width measured in from the plate's outer edge
girder_width = 15; // mm, width of each diagonal beam

/* [Full-height corner chamfer] */
// 2026-09-08 revision: full vertical edge top to bottom, not just a
// base-relief cut — different from the tray/box treatment on purpose.
chamfer_size   = 3; // mm, cut along each edge meeting at the corner
chamfer_height = cap_thickness; // mm — the whole plate thickness, not just the base

// ---------------------------------------------------------------------
// Derived geometry
// ---------------------------------------------------------------------

// Keeps the post sockets clear of the plate's own outer edge — driven by
// min_wall, not picked independently.
edge_margin = min_wall + post_size / 2 + post_clearance;

plate_x = post_spacing_x + post_size + 2 * edge_margin;
plate_y = post_spacing_y + post_size + 2 * edge_margin;

assert(plate_x <= max_footprint,
    str("Cap X (", plate_x, "mm) exceeds max_footprint (", max_footprint, "mm) — leaves no room for a brim; trim post_spacing_x"));
assert(plate_y <= max_footprint,
    str("Cap Y (", plate_y, "mm) exceeds max_footprint (", max_footprint, "mm) — leaves no room for a brim; trim post_spacing_y"));

module post_socket(x, y) {
    // Through-slot, not a blind pocket — "10mm tall slots"
    translate([x, y, 0])
        cube([post_size + 2 * post_clearance, post_size + 2 * post_clearance, cap_thickness + 1], center = true);
}

// A single straight beam of constant width from p1 to p2, in the XY
// plane — used to build each diagonal of the X girder as an exact
// rectangle rather than a hull/approximation.
module beam(p1, p2, width) {
    dir = p2 - p1;
    len = norm(dir);
    unit = dir / len;
    perp = [-unit[1], unit[0]] * width / 2;
    polygon([p1 + perp, p2 + perp, p2 - perp, p1 - perp]);
}

module x_girder(width, height) {
    linear_extrude(height = cap_thickness + 1, center = true) {
        beam([-width / 2, -height / 2], [width / 2, height / 2], girder_width);
        beam([-width / 2, height / 2], [width / 2, -height / 2], girder_width);
    }
}

// Everything inside the frame gets removed except the X girder, which
// spans corner-to-corner of the interior rectangle and so ties directly
// into the solid frame at both ends of each beam.
module frame_interior_cut(width, height) {
    difference() {
        cube([width, height, cap_thickness + 1], center = true);
        x_girder(width, height);
    }
}

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

module end_cap() {
    difference() {
        cube([plate_x, plate_y, cap_thickness], center = true);

        frame_interior_cut(plate_x - 2 * frame_width, plate_y - 2 * frame_width);

        for (x = [-post_spacing_x / 2, post_spacing_x / 2])
            for (y = [-post_spacing_y / 2, post_spacing_y / 2])
                post_socket(x, y);

        // Same corner-relief cut as the other hardware files — this
        // module works in a 0,0-origin local frame, so shift into the
        // centered plate's coordinate space rather than changing it.
        translate([-plate_x / 2, -plate_y / 2, -cap_thickness / 2])
            base_chamfer_cut(plate_x, plate_y, chamfer_size, chamfer_height);
    }
}

end_cap();
