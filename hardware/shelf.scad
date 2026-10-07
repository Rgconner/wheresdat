// SUPERSEDED 2026-09-10 — the fused floor+walls design below warped
// badly (large flat floor pulling against tall walls rising off it).
// Replaced by 4 separate parts: shelf_side.scad (x2, left/right),
// shelf_back.scad, shelf_floor.scad — each with a much simpler,
// warp-resistant cross-section, joined by a diagonal cut through the
// post socket at each back corner (post pins the seam once glued) and a
// rabbet notch for the floor to glue into. Kept here for reference only
// — do not print from this file.
//
// WheresDat — Shelf: floor + 3 raised solid walls (left, right, back),
// open front and open top. Replaces the earlier full-height triangulated
// side/back panel plan — folding the bracing directly into each shelf's
// own thick walls is simpler and plenty strong for the material cost,
// without a separate tall panel + notch + lattice design to build and
// print in pieces. "We are overengineering at this point" — 2026-09-07.
//
// wall_thickness is a deliberate number, not a leftover from the cap's
// socket margin: 9mm = post_size (6mm, the post itself, sitting flush
// against the wall's inner/tray-facing face) + min_wall (3mm of solid
// material beyond the post's outer face). Trays reference the post's
// INNER face directly — already confirmed to clear comfortably against
// shelf_unit_cap.scad's post_spacing numbers.
//
// Front stays open between the two front posts — that's where the 2mm
// rod stopper/brace goes (a separate feature, not built here) and where
// trays slide in and out. But each front post still gets its own small
// corner collar (same cross-section as the walls, not connected to each
// other) rising the full wall_height — without it the front posts would
// only be gripped by the 4mm floor at each shelf level, vs. the full
// wall_height everywhere else. That mismatch is what stacking 8 shelves
// into one continuous wall depends on being consistent at all 4 corners.
//
// Not yet rendered/validated — same caveat as every other file here.
// Test-fit one corner (post through a socket, into the wall) against a
// real post before committing to a full shelf x 8 levels x however many
// units — "see where it goes" per the simplification call.

/* [Printer] */
max_footprint = 280; // mm — same brim-margin reasoning as the other hardware files

/* [Post geometry — copy of shelf_unit_cap.scad's values] */
post_size      = 6;   // mm, square cross-section
post_clearance = 0.3; // mm, per-side fit clearance so the post slides through cleanly

/* [Footprint — copy of shelf_unit_cap.scad's derived post_spacing] */
post_spacing_x = 241.2; // mm — must match shelf_unit_cap.scad
post_spacing_y = 245.8; // mm — must match shelf_unit_cap.scad

/* [Shelf construction] */
min_wall        = 3;  // mm — same hard constraint as the other files
wall_thickness  = post_size + min_wall; // 9mm — post flush on the inner face, min_wall of material beyond it
floor_thickness = 4;  // mm
// Deliberate, not a guess: 8 shelves x 50mm = the full 400mm usable
// post span (420mm rod minus 10mm consumed by each cap). Stacked with
// zero gap, each shelf's wall top butts directly against the next
// shelf's floor, so the walls form one continuous side/back surface
// floor-to-ceiling instead of a short lip with open post between levels.
wall_height     = 50; // mm

// ---------------------------------------------------------------------
// Derived geometry
// ---------------------------------------------------------------------

// Floor covers the full footprint symmetrically (like the cap) even
// though only 3 of its 4 edges get a raised wall — keeps all 4 post
// sockets simple and consistent instead of special-casing the front.
floor_x = post_spacing_x + 2 * wall_thickness;
floor_y = post_spacing_y + 2 * wall_thickness;

assert(floor_x <= max_footprint,
    str("Shelf X (", floor_x, "mm) exceeds max_footprint (", max_footprint, "mm)"));
assert(floor_y <= max_footprint,
    str("Shelf Y (", floor_y, "mm) exceeds max_footprint (", max_footprint, "mm)"));

// Full-height corner chamfer (2026-09-08 revision) — 2 x 45s instead of
// 1 sharp 90, running the whole vertical edge top to bottom rather than
// just relieving the base. Different from the tray/box treatment on
// purpose: this is a tall standing part (54mm), so the hard corner runs
// the full wall height, not just the print-bed contact point.
chamfer_size   = 3;  // mm, cut along each edge meeting at the corner
chamfer_height = floor_thickness + wall_height; // mm — full part height, not just the base

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

module post_socket(x, y, cut_height) {
    // Through-slot spanning the full local material height (floor alone
    // at the front corners, floor + wall everywhere a wall exists) —
    // +1 total (0.5 each end) so the cut clears both faces cleanly.
    translate([x, y, cut_height / 2])
        cube([post_size + 2 * post_clearance, post_size + 2 * post_clearance, cut_height + 1], center = true);
}

module shelf() {
    difference() {
        union() {
            // Floor slab, full footprint.
            translate([0, 0, floor_thickness / 2])
                cube([floor_x, floor_y, floor_thickness], center = true);

            // Left wall
            translate([-(floor_x - wall_thickness) / 2, 0, floor_thickness + wall_height / 2])
                cube([wall_thickness, floor_y, wall_height], center = true);

            // Right wall
            translate([(floor_x - wall_thickness) / 2, 0, floor_thickness + wall_height / 2])
                cube([wall_thickness, floor_y, wall_height], center = true);

            // Back wall
            translate([0, (floor_y - wall_thickness) / 2, floor_thickness + wall_height / 2])
                cube([floor_x, wall_thickness, wall_height], center = true);

            // Front corner collars — same cross-section as the side
            // walls, same height, but NOT connected across the front:
            // the opening between them stays fully clear.
            translate([-(floor_x - wall_thickness) / 2, -(floor_y - wall_thickness) / 2, floor_thickness + wall_height / 2])
                cube([wall_thickness, wall_thickness, wall_height], center = true);
            translate([(floor_x - wall_thickness) / 2, -(floor_y - wall_thickness) / 2, floor_thickness + wall_height / 2])
                cube([wall_thickness, wall_thickness, wall_height], center = true);
        }

        // Post sockets, all 4 corners — all the same depth now, floor
        // plus wall (or corner collar), since every corner has the same
        // total local material height.
        post_socket(-post_spacing_x / 2, -post_spacing_y / 2, floor_thickness + wall_height); // front-left
        post_socket(post_spacing_x / 2, -post_spacing_y / 2, floor_thickness + wall_height);  // front-right
        post_socket(-post_spacing_x / 2, post_spacing_y / 2, floor_thickness + wall_height);  // back-left
        post_socket(post_spacing_x / 2, post_spacing_y / 2, floor_thickness + wall_height);   // back-right

        // Only the floor's own footprint touches the print bed — the
        // walls rise from it, not the plate, so this is the one corner
        // set that needs relief.
        translate([-floor_x / 2, -floor_y / 2, 0])
            base_chamfer_cut(floor_x, floor_y, chamfer_size, chamfer_height);
    }
}

shelf();
