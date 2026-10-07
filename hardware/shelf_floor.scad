// WheresDat — Shelf floor, split out from the original fused
// floor+3-walls design in shelf.scad. See shelf_side.scad for the full
// rationale — a separate flat plate has no tall walls rising off it to
// drive uneven cooling, so it should print much flatter on its own.
//
// Same footprint as the old fused floor. A raised tongue runs along the
// left/right/back edges (front stays free, same as before - open front,
// no wall there), rising from this plate's top surface into the matching
// groove cut into the bottom of shelf_side.scad / shelf_back.scad, and
// gets glued there. This is a separate 4mm-tall feature sitting on top
// of the 4mm floor slab - it does not change floor_thickness or require
// any change to the walls' wall_height, since the groove is already cut
// starting right where the wall's own bottom meets the floor's top, not
// into the floor's own body.
//
// Supersedes shelf.scad. Not yet rendered/validated - open in the app
// and test-fit against a printed side/back piece before committing to a
// full run of 8.

/* [Printer] */
max_footprint = 280; // mm

/* [Post geometry — must match shelf_side.scad and shelf_back.scad] */
post_size      = 6;
post_clearance = 0.3;

/* [Footprint — must match shelf_side.scad and shelf_back.scad] */
post_spacing_x = 241.2;
post_spacing_y = 245.8;

/* [Floor construction] */
// wall_thickness here only sizes the floor to match the wall pieces'
// footprint — must match shelf_side.scad / shelf_back.scad.
min_wall        = 3;
wall_thickness  = post_size + min_wall; // 9mm
floor_thickness = 4; // mm — must match shelf_side.scad / shelf_back.scad's rabbet_height calc

/* [Edge tongue — must fit shelf_side.scad / shelf_back.scad's groove:
   tongue_height + tongue_clearance must equal their rabbet_height] */
tongue_height    = 4;   // mm, rises from this plate's own top surface
tongue_clearance = 0.3; // mm, so the tongue seats without binding
// Same horizontal reach as the wall pieces' rabbet_depth — must match.
tongue_depth = 7; // mm, inward from the wall's inner face

/* [Base chamfer — relieves corner curling on the print bed] */
chamfer_size   = 3; // mm
chamfer_height = floor_thickness;

// ---------------------------------------------------------------------
// Derived geometry
// ---------------------------------------------------------------------

floor_x = post_spacing_x + 2 * wall_thickness;
floor_y = post_spacing_y + 2 * wall_thickness;

assert(floor_x <= max_footprint,
    str("Shelf floor X (", floor_x, "mm) exceeds max_footprint (", max_footprint, "mm)"));
assert(floor_y <= max_footprint,
    str("Shelf floor Y (", floor_y, "mm) exceeds max_footprint (", max_footprint, "mm)"));

module post_socket(x, y) {
    translate([x, y, floor_thickness / 2])
        cube([post_size + 2 * post_clearance, post_size + 2 * post_clearance, floor_thickness + 1], center = true);
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

// Tongue strips along the straight runs only (front-corner to where the
// back corner's diagonal cut starts / post_spacing_x corner-to-corner for
// the back edge) — same simplification shelf_side.scad / shelf_back.scad
// make for their groove, skipping the small diagonal-corner triangle.
module edge_tongues() {
    run_y = floor_y - wall_thickness; // front to the back diagonal's start

    // Left
    translate([-post_spacing_x / 2 - tongue_depth, -floor_y / 2, floor_thickness / 2])
        cube([tongue_depth, run_y, tongue_height]);
    // Right
    translate([post_spacing_x / 2, -floor_y / 2, floor_thickness / 2])
        cube([tongue_depth, run_y, tongue_height]);
    // Back
    translate([-post_spacing_x / 2, post_spacing_y / 2, floor_thickness / 2])
        cube([post_spacing_x, tongue_depth, tongue_height]);
}

module shelf_floor() {
    union() {
        difference() {
            cube([floor_x, floor_y, floor_thickness], center = true);

            post_socket(-post_spacing_x / 2, -post_spacing_y / 2);
            post_socket(post_spacing_x / 2, -post_spacing_y / 2);
            post_socket(-post_spacing_x / 2, post_spacing_y / 2);
            post_socket(post_spacing_x / 2, post_spacing_y / 2);

            translate([-floor_x / 2, -floor_y / 2, -floor_thickness / 2])
                base_chamfer_cut(floor_x, floor_y, chamfer_size, chamfer_height);
        }
        edge_tongues();
    }
}

shelf_floor();
