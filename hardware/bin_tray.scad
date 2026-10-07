// WheresDat — Grid tray for off-the-shelf clear hinged-lid bins
//
// NOT the Sortimo T-Boxx grid (see sortimo_tray.scad) — that pitch
// (52.3mm) is tied to a specific different product and would leave
// ~14mm of dead space around a bin this small on every side. This is a
// separate tray for a separate product: cheap unbranded clear plastic
// bins with their own hinged lid, bought instead of printing boxes.
//
// Bin spec — SATINIOR 48-pack, the "2 x 2 x 1.4 Inches" variant
// specifically (this listing sells 9 different sizes; don't assume a
// pasted spec is this one without checking the selected size swatch).
// Picked for small hardware (nuts, washers, etc.) over the smaller
// variants because it's the deepest of the bunch (35.6mm vs ~20mm for
// most others) — hardware needs more than one layer of depth to be
// worth a bin. Treated as the OUTER footprint, per usual listing
// convention. Cheap unbranded parts like this often run a little under
// nominal and the hinge may protrude slightly past the footprint when
// closed — print ONE pocket first and test-fit a real bin before
// committing to a full tray, same caveat as sortimo_tray.scad.
//
// Because each bin has its own lid, this tray doesn't need the outer
// perimeter rim height or the separate cap/box.scad system that
// sortimo_tray.scad relies on — it only needs to locate and cradle each
// bin's base. Pocket mechanism (individually-walled cell per `boxes`
// entry) is deliberately copied from sortimo_tray.scad's pattern.

/* [Printer] */
max_bed_x = 300; // mm
max_bed_y = 300; // mm

/* [Bin spec — from the listing, confirm against a physical bin before a full print] */
bin_x = 50.8; // mm, outer footprint (2 in)
bin_y = 50.8; // mm, outer footprint (2 in)
bin_z = 35.6; // mm, closed height (1.4 in) — informational, not used for pocket depth (shallow cubby, see below)

/* [Tray construction] */
pocket_depth         = 10;  // mm, recess depth — a cradle for the bin's base, not a full socket.
                             // Bumped from an earlier 8mm draft sized for a much smaller/lighter
                             // bin variant — nuts and washers are dense, a bit more lateral
                             // cradling helps keep a loaded bin from tipping in the pocket.
wall_thickness       = 3;   // mm, divider wall between adjacent bins — matches sortimo_tray's
                             // value; hardware content is heavier than the smaller bin variant
                             // this file started from, so kept at the same proven thickness
                             // rather than thinned down.
outer_wall_thickness = 4;   // mm, perimeter wall
// Deliberately short — unlike sortimo_tray.scad, there's no shared cap
// sitting on top of this rim (each bin closes itself), so this is just
// enough to protect the edge and leave room for a label, not a
// structural retention wall.
outer_wall_height    = 10;  // mm, total height of the raised perimeter rim, measured from the base
fit_clearance        = 0.5; // mm, per-side tolerance beyond the divider wall — looser than sortimo_tray's
                             // 0.3mm on purpose: this is an unbranded product with no engineering
                             // tolerance to trust, not a sourced spec like the T-Boxx grid.
tray_floor           = 3;   // mm, base plate thickness under the pockets — lighter than sortimo_tray's
                             // 5mm since this tray spans much less distance per bin (see spine note below).

/* [Rigidity spine — off by default] */
// sortimo_tray.scad added this for long unsupported spans on a
// multi-module tray. At this pitch a default 4x4 grid is only ~168mm
// across — short enough that it likely doesn't need it. Left available
// (same mechanism) in case the grid gets scaled up; just off by default.
spine_channel_enabled = false;
spine_channel_width   = 6;   // mm
spine_channel_depth   = 2;   // mm

/* [Base chamfer — relieves corner curling on the print bed] */
chamfer_size   = 2; // mm
chamfer_height = 2; // mm

/* [Grid pitch — derived from the bin size + clearance, not hand-picked] */
// inset (per side) = wall_thickness/2 + fit_clearance, mirroring
// sortimo_tray.scad's pocket formula exactly. module_size is chosen so
// the resulting pocket is bin size + 2mm total slop (1mm/side) — solve
// for it instead of picking a round number so the math traces back to
// the bin spec above.
inset       = wall_thickness / 2 + fit_clearance;
module_size = max(bin_x, bin_y) + 2 * 1.0 + 2 * inset; // 1.0mm/side slop + inset on each side

/* [Layout — [col, row, width_units, height_units], one entry per bin] */
// Starting grid: 4x4 = 16 bins, well under the bed limit, meant as a
// first test tray (per "I have exactly 1 good print" — validate fit
// before scaling up toward the full 48-pack across more trays).
// Every entry here is 1x1 — unlike sortimo_tray.scad's two wide
// channels, this is a genuine full grid, one walled pocket per bin.
grid_size_cols = 4;
grid_size_rows = 4;
boxes = [for (r = [0 : grid_size_rows - 1], c = [0 : grid_size_cols - 1]) [c, r, 1, 1]];

// ---------------------------------------------------------------------
// Derived geometry — shouldn't need editing below this line
// ---------------------------------------------------------------------

grid_cols = max([for (b = boxes) b[0] + b[2]]);
grid_rows = max([for (b = boxes) b[1] + b[3]]);

tray_x = grid_cols * module_size + outer_wall_thickness * 2;
tray_y = grid_rows * module_size + outer_wall_thickness * 2;
tray_z = tray_floor + pocket_depth;

assert(tray_x <= max_bed_x,
    str("Tray X (", tray_x, "mm) exceeds max_bed_x (", max_bed_x, "mm) — trim the grid or fix max_bed_x"));
assert(tray_y <= max_bed_y,
    str("Tray Y (", tray_y, "mm) exceeds max_bed_y (", max_bed_y, "mm) — trim the grid or fix max_bed_y"));
assert(!spine_channel_enabled || spine_channel_depth <= tray_floor - 1,
    str("spine_channel_depth (", spine_channel_depth, "mm) leaves less than 1mm of solid floor under a tray_floor of ", tray_floor, "mm — increase tray_floor or shrink spine_channel_depth"));
assert(module_size - 2 * inset > max(bin_x, bin_y),
    str("Computed pocket (", module_size - 2 * inset, "mm) isn't actually larger than the bin footprint (", max(bin_x, bin_y), "mm) — check bin_x/bin_y/wall_thickness/fit_clearance"));

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

module bin_tray() {
    union() {
    difference() {
        cube([tray_x, tray_y, tray_z]);

        for (b = boxes) {
            pocket_inset = wall_thickness / 2 + fit_clearance;
            translate([
                outer_wall_thickness + b[0] * module_size + pocket_inset,
                outer_wall_thickness + b[1] * module_size + pocket_inset,
                tray_floor
            ])
            cube([
                b[2] * module_size - 2 * pocket_inset,
                b[3] * module_size - 2 * pocket_inset,
                pocket_depth + 1
            ]);
        }

        if (spine_channel_enabled) {
            for (r = [1 : grid_rows - 1]) {
                translate([
                    0,
                    outer_wall_thickness + r * module_size - spine_channel_width / 2,
                    -0.5
                ])
                cube([
                    tray_x,
                    spine_channel_width,
                    spine_channel_depth + 0.5
                ]);
            }
        }

        base_chamfer_cut(tray_x, tray_y, chamfer_size, chamfer_height);
    }
    outer_wall_riser();
    }
}

bin_tray();
