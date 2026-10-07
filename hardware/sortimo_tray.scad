// WheresDat — Parametric Sortimo T-Boxx-compatible small-parts tray
//
// Grid module verified against the specific product this targets —
// Sortimo T-Boxx 2018 insert boxes: confirmed grid pitch 52.3mm (not the
// 52mm originally sourced from a general L-BOXX search — close, but a
// real product-specific correction, not a rounding choice). T-Boxx
// heights run H31/H63; unused here regardless, see below.
//
// NOT verified / deliberately simplified: Bosch's actual snap/latch
// retention profile. I don't have real tolerances for their proprietary
// rail-and-latch mechanism, so this design uses a plain recessed pocket
// with a shallow lip instead of replicating their exact latch geometry.
// Print ONE pocket first and test-fit a real box before committing to a
// full tray — the raster spacing (52.3mm grid) should now be correct for
// T-Boxx specifically, but the retention feel will be looser than a
// genuine Sortimo click-fit.
//
// This file is written to be actually parametric: edit the values below
// (openscad-customizer compatible) rather than the geometry itself.

/* [Printer] */
// Actual build volume (300x300x330mm). Z isn't used by this flat-tray
// design — plenty of headroom regardless — kept here for reference.
max_bed_x = 300; // mm
max_bed_y = 300; // mm
max_bed_z = 330; // mm, unused by this design, informational only

/* [Sortimo T-Boxx grid — verified against the real product] */
module_size    = 52.3; // mm, one grid unit (T-Boxx 2018 confirmed pitch)
box_height     = 63;   // mm, T-Boxx H63 variant (reference only, not used for pocket depth — see below)

/* [Tray construction] */
// Bumped up from the first draft: long unsupported walls print poorly
// (warping, weak layer adhesion along the run) — worse on a tray this
// large, not better. outer_wall_thickness is reinforced further since
// the tray's outer perimeter is the single longest unsupported run.
pocket_depth         = 8;   // mm, recess depth — shallow on purpose, this is a cubby not a full socket
// Narrowed 3 -> 2 -> 1mm (2026-09-22) to fit real store-bought clear
// boxes (52mm at the base, verified against the actual STL in CAD, not
// the bare formula — both 3mm and 2mm came up short, the latter by a
// confirmed, measured 1mm cut into the divider). 1mm was rejected once
// already as too thin on its own — accepted now only as PART of a
// combined fix together with tray_extra_width below, not as the sole
// answer. Divider is only 8mm tall (capped at pocket_depth, doesn't rise
// with outer_wall_height), which is the only reason 1mm is viable at
// all here rather than genuinely fragile.
wall_thickness       = 1;   // mm, internal divider wall between adjacent pockets
outer_wall_thickness = 5;   // mm, perimeter wall — thicker on purpose, it's the longest run
// Added 2026-09-22: the module_size grid pitch (52.3mm) is a verified
// real spec (T-Boxx) and isn't the thing to fudge for a same-shaped but
// different real-world box that just happens to not quite fit it. This
// instead grows the tray's own Y size directly, split evenly across the
// two stacked rows, independent of module_size — so length-axis
// compatibility (X, still real T-Boxx pitch) is untouched. Lands the
// channel width around 51.7mm against a 52mm box base — close but not
// zero-interference; verify the real fit before committing to a batch,
// same caveat as everything else in this file.
tray_extra_width     = 1;   // mm, total added to tray_y, split evenly across grid_rows
// Added 2026-09-08: the perimeter wall used to be the same height as
// the rest of the tray (tray_floor + pocket_depth, 13mm) — nowhere
// near tall enough for a label, and not doing much to hold boxes in
// laterally since most of a 25mm box's height stuck up above it
// unsupported. This raises the OUTER perimeter specifically, past the
// pocket tops, without touching pocket_depth (which still controls how
// deep boxes sit) — same outer_wall_thickness footprint, just taller.
outer_wall_height    = 25;  // mm, total height of the raised perimeter rim, measured from the base
fit_clearance        = 0.3; // mm, small per-side tolerance so a box drops in without binding (NOT a structural wall — see fix below)
// Bumped 3 -> 5 (2026-09-07) to make room for the spine channel below
// without cutting into the floor thickness that was already validated —
// 5mm floor minus a 2mm-deep channel still leaves the original 3mm of
// solid material underneath it.
tray_floor           = 5;   // mm, base plate thickness under the pockets

/* [Rigidity spine — bottom-side channel under each central divider] */
// Added 2026-09-07: as trays get longer (more modules end to end), a
// single divider wall organizes the boxes but doesn't by itself keep a
// long span from flexing — especially at a seam where two separately
// printed trays get placed together (see the layout note below). This
// cuts a channel into the underside, centered on each interior row
// divider and running the tray's full length, for a stiffening spine
// (printed strip, aluminum bar, etc.) inserted from below. Cross-section
// is a reasonable guess, NOT sourced from a specific spine material —
// verify against whatever stock you actually use before committing to a
// batch, same caveat as the pocket fit above.
spine_channel_enabled = true;
spine_channel_width   = 6;   // mm, channel width, centered on the divider
spine_channel_depth   = 2;   // mm, cut depth from the bottom face up into the floor

/* [Base chamfer — relieves corner curling on the print bed] */
// 2 x 45s instead of 1 sharp 90 at each base corner touching the plate
// — sharp corners concentrate cooling stress and curl/lift; this
// relieves the stress point instead of fighting it with more bed
// adhesion. Only the bottom chamfer_height, not a structural taper.
chamfer_size   = 2; // mm, cut along each edge meeting at the corner
chamfer_height = 2; // mm, how far up from the base the cut runs

/* [Layout — one row per box: [col, row, width_units, height_units]] */
// Changed from two 2x2 pockets to two 4x1 channels (2026-09-07): one
// central divider running the full long axis (the wall between row 0
// and row 1), splitting the tray into two open channels instead of a
// full grid of individually-walled cells. Each channel is one long
// pocket, 4 units end to end, with NO interior dividers — a run of
// separate boxes (hardware/sortimo_box.scad, now 1x1 through 4x1, width
// fixed to one channel) sits inside it, sized so a longer tool
// (screwdriver, pliers) can get an unbroken 3x1/4x1 box instead of being
// forced into a wall-bounded cell. Outer footprint was 219.2 x 114.6mm
// (print-validated) until tray_extra_width above grew Y by 1mm to
// 115.6mm (2026-09-22, for real store-bought box clearance) — re-verify
// shelf fit against 115.6mm, not the old number. Still a FULL tiling of its own 4x2
// bounding box (8 cells, all claimed) — if you edit this list yourself,
// watch for that: any grid cell inside the overall bounding box that no
// entry claims stays solid, uncut material.
boxes = [
    [0, 0, 4, 1],
    [0, 1, 4, 1],
];

// ---------------------------------------------------------------------
// Derived geometry — shouldn't need editing below this line
// ---------------------------------------------------------------------

grid_cols = max([for (b = boxes) b[0] + b[2]]);
grid_rows = max([for (b = boxes) b[1] + b[3]]);

// tray_extra_width split evenly across the row axis only — row_pitch is
// what a row-index actually advances by (module_size plus its share of
// the extra), kept separate from module_size itself since X/length still
// needs the real, unmodified T-Boxx pitch.
row_extra = tray_extra_width / grid_rows;
row_pitch = module_size + row_extra;

// Grid origin sits inset by outer_wall_thickness from the tray edge, so
// the perimeter is a full outer_wall_thickness regardless of grid size.
tray_x = grid_cols * module_size + outer_wall_thickness * 2;
tray_y = grid_rows * row_pitch + outer_wall_thickness * 2;
tray_z = tray_floor + pocket_depth;

assert(tray_x <= max_bed_x,
    str("Tray X (", tray_x, "mm) exceeds max_bed_x (", max_bed_x, "mm) — trim the layout or fix max_bed_x"));
assert(tray_y <= max_bed_y,
    str("Tray Y (", tray_y, "mm) exceeds max_bed_y (", max_bed_y, "mm) — trim the layout or fix max_bed_y"));
assert(!spine_channel_enabled || spine_channel_depth <= tray_floor - 1,
    str("spine_channel_depth (", spine_channel_depth, "mm) leaves less than 1mm of solid floor under a tray_floor of ", tray_floor, "mm — increase tray_floor or shrink spine_channel_depth"));

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

// A ring/frame matching the existing outer_wall_thickness footprint,
// rising from the tray's current top surface up to outer_wall_height —
// same wall thickness continued taller, not a separate offset feature,
// so it sits flush with the wall below it.
module outer_wall_riser() {
    if (outer_wall_height > tray_z) {
        translate([0, 0, tray_z])
            difference() {
                cube([tray_x, tray_y, outer_wall_height - tray_z]);
                translate([outer_wall_thickness, outer_wall_thickness, -0.5])
                    cube([
                        tray_x - 2 * outer_wall_thickness,
                        tray_y - 2 * outer_wall_thickness,
                        outer_wall_height - tray_z + 1
                    ]);
            }
    }
}

module sortimo_tray() {
    union() {
    difference() {
        // Solid base slab
        cube([tray_x, tray_y, tray_z]);

        // One recessed pocket per box in the layout. A side gets the full
        // div_inset (wall_thickness/2 + fit_clearance) only where it
        // borders ANOTHER pocket — that's what actually leaves a full
        // wall_thickness of solid divider material between two adjacent
        // boxes. A side sitting at the grid's own outer edge (0 or
        // grid_cols/rows*module_size) borders the solid outer wall
        // directly instead, which needs no structural margin of its own —
        // fit_clearance alone is enough there. Fixed 2026-09-22: this used
        // div_inset on all four sides uniformly before, which (given the
        // boxes array fully tiles the grid, so every non-edge boundary is
        // guaranteed to border a neighbor) needlessly narrowed every
        // pocket's outer-facing edges by up to a full div_inset more than
        // necessary — measured as a real 1mm-per-channel intrusion into
        // the tray's upper opening once printed.
        for (b = boxes) {
            div_inset = wall_thickness / 2 + fit_clearance;
            // X stays on module_size (real T-Boxx pitch, untouched). Y
            // uses row_pitch so each row carries its share of
            // tray_extra_width — see tray_extra_width above.
            x0 = b[0] * module_size;
            y0 = b[1] * row_pitch;
            x1 = (b[0] + b[2]) * module_size;
            y1 = (b[1] + b[3]) * row_pitch;

            inset_west  = (x0 <= 0) ? fit_clearance : div_inset;
            inset_east  = (x1 >= grid_cols * module_size) ? fit_clearance : div_inset;
            inset_south = (y0 <= 0) ? fit_clearance : div_inset;
            inset_north = (y1 >= grid_rows * row_pitch) ? fit_clearance : div_inset;

            translate([
                outer_wall_thickness + x0 + inset_west,
                outer_wall_thickness + y0 + inset_south,
                tray_floor
            ])
            cube([
                (x1 - x0) - inset_west - inset_east,
                (y1 - y0) - inset_south - inset_north,
                pocket_depth + 1 // +1 so the cut clears the top face cleanly
            ]);
        }

        // Rigidity spine channel(s) — one per interior row boundary,
        // cut from the bottom face up into the floor only. Kept
        // shallower than tray_floor (asserted above) so it never
        // breaches a pocket above it.
        if (spine_channel_enabled) {
            for (r = [1 : grid_rows - 1]) {
                translate([
                    0,
                    outer_wall_thickness + r * row_pitch - spine_channel_width / 2,
                    -0.5
                ])
                cube([
                    tray_x,
                    spine_channel_width,
                    spine_channel_depth + 0.5 // +0.5 so the cut clears the bottom face cleanly
                ]);
            }
        }

        base_chamfer_cut(tray_x, tray_y, chamfer_size, chamfer_height);
    }
    outer_wall_riser();
    }
}

sortimo_tray();
