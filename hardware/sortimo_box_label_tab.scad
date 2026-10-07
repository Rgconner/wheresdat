// WheresDat — Label tab for sortimo_box.scad, printed separately.
//
// The corner label platform from the original box design got cut from
// the box itself: floating above the rim, it was an overhang, forcing
// support material when the box prints on its side (see SPEC.md,
// "Label platform tried and removed"). Same idea, better execution:
// print this flat (trivial, no supports needed at all) and attach with
// a dab of superglue to the box's top corner after the fact.
//
// Not yet rendered/validated (no OpenSCAD CLI in this environment).

/* [Sized to match sortimo_box.scad's label tier] */
label_w      = 20;  // mm — must match the confirmed 20x10mm inner label tier
label_h      = 10;  // mm
label_margin = 2;   // mm, tab footprint = label size + margin on all sides
tab_thickness = 2;  // mm — flat plate, thin enough to be trivial to print, thick enough to handle/glue

/* [Registration rim — self-aligns the tab in the box's corner] */
// The tab sits in the same back-right corner the original built-in
// platform used (flush against both walls there). A rim on those same 2
// outer edges, dropping down alongside the box's own wall, means the tab
// physically locates itself when glued on instead of needing to be
// eyeballed into position.
rim_depth = 3;   // mm, how far the rim drops below the plate to engage the box's wall
rim_wall  = 1.5; // mm, rim thickness — still flat-printable, no overhang (drops straight down, prints fine on its back)

tab_x = label_w + 2 * label_margin;
tab_y = label_h + 2 * label_margin;

module label_tab() {
    union() {
        // Flat plate — the label-mounting surface
        cube([tab_x, tab_y, tab_thickness]);

        // Rim on the 2 outer edges (matching the box's back-right corner
        // placement), dropping down to hook alongside the box's wall.
        translate([tab_x - rim_wall, 0, -rim_depth])
            cube([rim_wall, tab_y, rim_depth]);
        translate([0, tab_y - rim_wall, -rim_depth])
            cube([tab_x, rim_wall, rim_depth]);
    }
}

label_tab();
