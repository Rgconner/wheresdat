// WheresDat — Shelf side wall (left or right), split out from the
// original fused floor+3-walls design in shelf.scad. Large flat floor
// fused to tall thin walls was warping badly — this splits the shelf
// into 4 printed parts (this side wall x2, shelf_back.scad, and
// shelf_floor.scad) so each piece has a much simpler, more uniform
// cross-section.
//
// Runs the full front-to-back depth. The back end is sliced diagonally
// exactly through the post socket's center (not through solid wall
// material) — the socket is always split at exactly 45 degrees here,
// since both the left/right wall and the back wall shift by the same
// wall_thickness in x and y at that corner. shelf_back.scad has the
// matching cut, so the two halves recombine into the full 6.6mm post
// socket once assembled, and the corner post itself pins the seam once
// glued in.
//
// The floor is now shelf_floor.scad, not fused here — this wall's own
// bottom sits flush on the floor's top surface, and a groove is cut
// straight up into the bottom-inner corner from there (not into the
// floor's body) for a raised tongue on shelf_floor.scad's edge to glue
// into. Outer band stays solid the whole way down, same as before.
//
// Supersedes shelf.scad. Not yet rendered/validated — open in the app
// and test-fit one corner (post through both halves' sockets, floor
// glued into the rabbet) before committing to a full run of 8.

/* [Printer] */
max_footprint = 280; // mm

/* [Which side — mirrors the same geometry in x] */
side = "left"; // [left,right]

/* [Post geometry — must match shelf_floor.scad and shelf_back.scad] */
post_size      = 6;   // mm, square cross-section
post_clearance = 0.3; // mm, per-side fit clearance

/* [Footprint — must match shelf_floor.scad and shelf_back.scad] */
post_spacing_x = 241.2; // mm
post_spacing_y = 245.8; // mm

/* [Wall construction — must match shelf_back.scad] */
min_wall       = 3;  // mm
wall_thickness = post_size + min_wall; // 9mm
wall_height    = 50; // mm

/* [Floor tongue groove — must match shelf_back.scad; rabbet_height must
   equal shelf_floor.scad's tongue_height + tongue_clearance] */
floor_thickness  = 4;   // mm — not used for sizing the groove itself (see
                          // rabbet_height below), only kept for reference/
                          // consistency with the other files
rabbet_clearance = 0.3; // mm — this is the TONGUE's clearance (shelf_floor.scad's
                          // tongue_clearance), named for the groove it cuts here
// Bumped up from an initial 6mm — more glue surface, and cheap to give
// since the groove only occupies the low rabbet_height band, not the
// wall's full height. Leaves wall_thickness - rabbet_depth = 2mm of
// solid material outward of the groove in that band, which is fine for a
// short continuous lip (not a thin unsupported column).
rabbet_depth  = 7; // mm, inward from the wall's inner face
// Height of the groove cut UP from this wall's own bottom (which sits on
// the floor's top surface) — must equal shelf_floor.scad's
// tongue_height (4) + tongue_clearance (0.3), NOT floor_thickness.
// Numerically the same (4 + 0.3 = 4.3) purely because that's what was
// picked for both; the groove has nothing to do with floor_thickness.
rabbet_height = 4.3;

assert(rabbet_depth < wall_thickness,
    str("rabbet_depth (", rabbet_depth, "mm) must leave solid wall material outward of the notch (wall_thickness = ", wall_thickness, "mm)"));

// ---------------------------------------------------------------------
// Derived geometry — shouldn't need editing below this line
// ---------------------------------------------------------------------

floor_x = post_spacing_x + 2 * wall_thickness;
floor_y = post_spacing_y + 2 * wall_thickness;

assert(floor_x <= max_footprint,
    str("Shelf X (", floor_x, "mm) exceeds max_footprint (", max_footprint, "mm)"));
assert(floor_y <= max_footprint,
    str("Shelf Y (", floor_y, "mm) exceeds max_footprint (", max_footprint, "mm)"));

half_fx = floor_x / 2;
half_fy = floor_y / 2;

// Inner face x / diagonal cut point — dead center of the back corner's
// post socket, same point used by shelf_back.scad's matching cut.
inner_x = post_spacing_x / 2;
diag_y  = post_spacing_y / 2;

module post_socket(x, y) {
    translate([x, y, wall_height / 2])
        cube([post_size + 2 * post_clearance, post_size + 2 * post_clearance, wall_height + 1], center = true);
}

module floor_rabbet() {
    // Notch along the wall's full straight inner run, front face to the
    // start of the back diagonal. Overshoots both the front face (open
    // part boundary) and the inner face (coincident with the polygon's
    // own edge) by 0.5mm for a clean boolean.
    inner_run_length = floor_y - wall_thickness;
    translate([-half_fx + wall_thickness - rabbet_depth, -half_fy - 0.5, -0.5])
        cube([rabbet_depth + 0.5, inner_run_length + 0.5, rabbet_height + 0.5]);
}

module shelf_side_left() {
    difference() {
        linear_extrude(height = wall_height)
            polygon([
                [-half_fx, -half_fy], // front-outer
                [-half_fx, half_fy],  // back-outer
                [-inner_x, diag_y],   // diagonal cut point = post socket center
                [-inner_x, -half_fy]  // front-inner
            ]);

        post_socket(-inner_x, -diag_y); // front corner
        post_socket(-inner_x, diag_y);  // back corner — this wall's half of the socket

        floor_rabbet();
    }
}

module shelf_side() {
    if (side == "right") {
        mirror([1, 0, 0]) shelf_side_left();
    } else {
        shelf_side_left();
    }
}

shelf_side();
