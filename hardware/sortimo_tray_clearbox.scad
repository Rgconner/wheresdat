// WheresDat — Parametric small-parts tray, clear-box variant
//
// New filename (2026-09-22), not just new parameter values — sortimo_tray.scad's
// edits weren't showing up across STL exports/converters when tested under
// the original filename (identical output across three separate exports
// and two different SCAD-to-STL engines), pointing at a stale/cached
// source somewhere rather than a real geometry bug. This file exists so
// there's zero ambiguity: nothing could possibly have cached content
// under a name that didn't exist until now. Same design, same math,
// clean slate.
//
// Sized for real store-bought clear boxes (52mm at the base), NOT the
// Sortimo T-Boxx insert boxes sortimo_tray.scad still targets — X (length)
// keeps the real T-Boxx grid pitch since nothing else needs it changed,
// but Y (the channel/row axis) no longer matches T-Boxx spacing on
// purpose. If T-Boxx compatibility is ever needed again, that's still
// sortimo_tray.scad, unmodified from before this variant branched off.
//
// NOT verified / deliberately simplified: Bosch's actual snap/latch
// retention profile — irrelevant for this variant anyway, since it's not
// targeting Sortimo boxes.
//
// This file is written to be actually parametric: edit the values below
// (openscad-customizer compatible) rather than the geometry itself.

/* [Printer] */
// Actual build volume (300x300x330mm). Z isn't used by this flat-tray
// design — plenty of headroom regardless — kept here for reference.
max_bed_x = 300; // mm
max_bed_y = 300; // mm
max_bed_z = 330; // mm, unused by this design, informational only

/* [Grid — X still real T-Boxx pitch, Y no longer matches T-Boxx on purpose] */
module_size    = 52.3; // mm, one grid unit along X (real T-Boxx pitch — length axis only, see tray_extra_width for Y)
box_height     = 63;   // mm, reference only, not used for pocket depth

/* [Tray construction] */
pocket_depth         = 8;   // mm, recess depth — shallow on purpose, this is a cubby not a full socket
// 1mm divider, accepted only as PART of a combined fix together with
// tray_extra_width below — 1mm alone was tried and rejected as too thin.
// Divider is only 8mm tall (capped at pocket_depth, doesn't rise with
// outer_wall_height), which is the only reason 1mm is viable at all here.
wall_thickness       = 1;   // mm, internal divider wall between adjacent pockets
// Narrowed 5 -> 3mm (2026-09-22) for real channel clearance, not just to
// save material — outer_wall_thickness alone does NOT grow the channel
// under this file's pocket-inset formula (traced through explicitly:
// reducing it repositions a pocket closer to the tray edge without
// changing its width, since only one side of each row is truly
// outer-facing). The actual channel-width gain is routed through
// tray_extra_width below instead. NOTE: this changes tray_x too, since
// there's one outer_wall_thickness for both axes — tray_x is now 215.2mm
// (4*module_size + 2*3), not the old 219.2mm (that number came from a
// 5mm wall and wasn't preserved deliberately; flag if X specifically
// needs to hold at 219.2, which would need asymmetric wall thickness
// per axis, not implemented here).
outer_wall_thickness = 3;   // mm, perimeter wall
// The module_size grid pitch (52.3mm) is a verified real spec (T-Boxx)
// and isn't the thing to fudge for a same-shaped but different
// real-world box that just happens to not quite fit it. This instead
// grows the tray's own Y size directly, split evenly across the two
// stacked rows, independent of module_size — so length-axis
// compatibility (X, still real T-Boxx pitch) is untouched. Set so that,
// combined with outer_wall_thickness=3 above, tray_y lands at exactly
// 115.6mm (solved: 115.6 = 2*(module_size + tray_extra_width/2) + 2*3)
// — channel width comes out to 53.7mm against a 52mm box base, real
// margin (1.7mm) rather than the earlier razor-thin fits.
tray_extra_width     = 5;   // mm, total added to tray_y, split evenly across grid_rows
outer_wall_height    = 25;  // mm, total height of the raised perimeter rim, measured from the base
fit_clearance        = 0.3; // mm, small per-side tolerance so a box drops in without binding (NOT a structural wall)
tray_floor           = 5;   // mm, base plate thickness under the pockets

/* [Rigidity spine — bottom-side channel under each central divider] */
// Cross-section is a reasonable guess, NOT sourced from a specific spine
// material — verify against whatever stock you actually use.
spine_channel_enabled = true;
spine_channel_width   = 6;   // mm, channel width, centered on the divider
spine_channel_depth   = 2;   // mm, cut depth from the bottom face up into the floor

/* [Base chamfer — relieves corner curling on the print bed] */
chamfer_size   = 2; // mm, cut along each edge meeting at the corner
chamfer_height = 2; // mm, how far up from the base the cut runs

/* [Layout — one row per box: [col, row, width_units, height_units]] */
// One central divider running the full long axis (the wall between row 0
// and row 1), splitting the tray into two open channels. Each channel is
// one long pocket, 4 units end to end, with NO interior dividers. Full
// tiling of its own 4x2 bounding box (8 cells, all claimed) — if you edit
// this list yourself, watch for that: any grid cell inside the overall
// bounding box that no entry claims stays solid, uncut material.
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

module sortimo_tray_clearbox() {
    union() {
    difference() {
        // Solid base slab
        cube([tray_x, tray_y, tray_z]);

        // One recessed pocket per box in the layout. A side gets the full
        // div_inset (wall_thickness/2 + fit_clearance) only where it
        // borders ANOTHER pocket — that's what actually leaves a full
        // wall_thickness of solid divider material between two adjacent
        // boxes. A side sitting at the grid's own outer edge (0 or
        // grid_cols/rows*module_size, or grid_rows*row_pitch for Y) borders
        // the solid outer wall directly instead, which needs no structural
        // margin of its own — fit_clearance alone is enough there.
        for (b = boxes) {
            div_inset = wall_thickness / 2 + fit_clearance;
            // X stays on module_size (real T-Boxx pitch, untouched). Y
            // uses row_pitch so each row carries its share of
            // tray_extra_width.
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

sortimo_tray_clearbox();
