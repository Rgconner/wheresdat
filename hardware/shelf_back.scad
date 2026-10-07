// WheresDat — Shelf back wall, split out from the original fused
// floor+3-walls design in shelf.scad. See shelf_side.scad for the full
// rationale (large flat floor fused to tall walls was warping).
//
// Diagonal-cut at both ends, matching shelf_side.scad's back corner cut
// exactly — each cut runs through the post socket's center, not through
// solid material, so this piece and the two side pieces recombine into
// the full post sockets at both back corners once assembled, pinned by
// the corner post itself.
//
// Same bottom-inner groove as shelf_side.scad: this wall's own bottom
// sits flush on the floor's top surface, and the groove is cut straight
// up into it from there (not into the floor's body) for a raised tongue
// on shelf_floor.scad's edge to glue into.
//
// Supersedes shelf.scad. Not yet rendered/validated — open in the app
// and test-fit both corners before committing to a full run of 8.

/* [Printer] */
max_footprint = 280; // mm

/* [Post geometry — must match shelf_floor.scad and shelf_side.scad] */
post_size      = 6;
post_clearance = 0.3;

/* [Footprint — must match shelf_floor.scad and shelf_side.scad] */
post_spacing_x = 241.2;
post_spacing_y = 245.8;

/* [Wall construction — must match shelf_side.scad] */
min_wall       = 3;
wall_thickness = post_size + min_wall; // 9mm
wall_height    = 50;

/* [Floor tongue groove — must match shelf_side.scad; rabbet_height must
   equal shelf_floor.scad's tongue_height + tongue_clearance, not
   floor_thickness — see shelf_side.scad for the full explanation] */
floor_thickness  = 4; // mm — reference only, not used to size the groove
rabbet_clearance = 0.3; // mm — the tongue's clearance
rabbet_depth     = 7; // see shelf_side.scad for why this was bumped from 6mm
rabbet_height    = 4.3; // tongue_height (4) + tongue_clearance (0.3)

assert(rabbet_depth < wall_thickness,
    str("rabbet_depth (", rabbet_depth, "mm) must leave solid wall material outward of the notch (wall_thickness = ", wall_thickness, "mm)"));

// ---------------------------------------------------------------------
// Derived geometry
// ---------------------------------------------------------------------

floor_x = post_spacing_x + 2 * wall_thickness;
floor_y = post_spacing_y + 2 * wall_thickness;

assert(floor_x <= max_footprint,
    str("Shelf X (", floor_x, "mm) exceeds max_footprint (", max_footprint, "mm)"));
assert(floor_y <= max_footprint,
    str("Shelf Y (", floor_y, "mm) exceeds max_footprint (", max_footprint, "mm)"));

half_fx = floor_x / 2;
half_fy = floor_y / 2;

// Inner face y / diagonal cut point — dead center of each back corner's
// post socket, same points used by shelf_side.scad's matching cuts.
inner_y = post_spacing_y / 2;

module post_socket(x, y) {
    translate([x, y, wall_height / 2])
        cube([post_size + 2 * post_clearance, post_size + 2 * post_clearance, wall_height + 1], center = true);
}

module floor_rabbet() {
    // Notch along the wall's full inner run (post_spacing_x wide, corner
    // to corner). Overshoots the inner face by 0.5mm each side for a
    // clean boolean — no front/back open boundary to clear here since
    // both ends already stop at the diagonal.
    translate([-post_spacing_x / 2 - 0.5, inner_y - 0.5, -0.5])
        cube([post_spacing_x + 1, rabbet_depth + 0.5, rabbet_height + 0.5]);
}

module shelf_back() {
    difference() {
        linear_extrude(height = wall_height)
            polygon([
                [-post_spacing_x / 2, inner_y], // left diagonal point = left post socket center
                [-half_fx, half_fy],             // back-outer-left
                [half_fx, half_fy],              // back-outer-right
                [post_spacing_x / 2, inner_y]    // right diagonal point = right post socket center
            ]);

        post_socket(-post_spacing_x / 2, inner_y); // left corner — this wall's half of the socket
        post_socket(post_spacing_x / 2, inner_y);  // right corner — this wall's half of the socket

        floor_rabbet();
    }
}

shelf_back();
