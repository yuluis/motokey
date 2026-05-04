// MotoKey Lock Box — Castellated Finger Joint Enclosure (2 pieces, no drilling)
// Base and lid interlock like interlaced fingers. Gaps at connector locations
// form cable/port openings. Where no openings needed, fingers mesh tightly.
//
// v3 2026-03-10
// Units: mm
// Print: PETG or ABS, 0.2mm layers, 3 walls, 20% infill
// Orientation: both pieces print open-side-up (fingers point up)
// No supports needed — all features are vertical extrusions
// Render: F5 preview, F6 full render

/* [Enclosure] */
ext_l = 140;            // length (x) — fits PCB + battery side by side
ext_w = 75;             // width (y) — fits 60mm PCB + clearance
ext_h = 38;             // total height (z)
wall = 2.5;             // wall thickness
corner_r = 3;           // external corner radius
split_z = 19;           // z height where base ends and lid begins

/* [Finger Joint] */
finger_w = 8;           // finger width along wall
finger_tol = 0.2;       // clearance per side for fit
finger_depth = 8;       // how far fingers extend into mating part

/* [PCB] */
pcb_l = 95;
pcb_w = 60;
pcb_t = 1.6;
pcb_off_x = 5;          // PCB offset from inner left wall
pcb_off_y = 5;          // PCB offset from inner front wall
standoff_h = 6;
standoff_d = 6;
standoff_hole = 2.8;
standoff_inset = 4;     // from PCB edge (matches M3 mounting holes)

/* [Battery] */
batt_d = 18.5;          // 18650 diameter + clearance
batt_l = 66;            // 18650 length + 1mm
cradle_wall = 2;

/* [Mounting Flanges] */
flange_l = 22;
flange_w = 10;
flange_t = 3.5;
flange_hole = 4.2;      // M4

/* [Rendering] */
show_base = true;
show_lid = true;
show_pcb = true;
show_battery = true;
explode = 20;           // 0 = assembled, >0 = exploded view
$fn = 48;

// ============================================================
// Derived dimensions
// ============================================================
int_l = ext_l - 2*wall;
int_w = ext_w - 2*wall;
pcb_x = wall + pcb_off_x;
pcb_y = wall + pcb_off_y;
pcb_z = wall + standoff_h;

// Battery position — right of PCB, centered in y
batt_cx = wall + pcb_off_x + pcb_l + 8 + batt_d/2;
batt_cy = ext_w / 2;

// ============================================================
// PCB connector positions (from gen_pcb.py PLACEMENTS)
// Mapped to enclosure walls where they need openings
//
// PCB origin in enclosure: (pcb_x, pcb_y)
// PCB coords → enclosure coords: ex = pcb_x + px, ey = pcb_y + (pcb_w - py)
//   (y flipped because PCB y=0 is top, enclosure y=0 is front)
// ============================================================

// --- LEFT WALL (x = 0) openings ---
// J7 USB Micro-B at PCB (5, 34) — on left edge, rotated 90°
// USB connector is ~9mm wide, 6mm tall
usb_ex = 0;  // on left wall
usb_ey = pcb_y + (pcb_w - 34);  // ~31mm from front
usb_width = 12;
usb_height = 8;

// --- TOP WALL (y = ext_w) openings ---
// J1 12V input at PCB (12, 10) — near top edge
j1_ex = pcb_x + 12;
j1_width = 10;  // screw terminal

// --- RIGHT WALL (x = ext_l) openings ---
// J2 relay output at PCB (88, 10) — near top-right
j2_ex = pcb_x + 88;  // but this is relative to right wall
j2_width = 10;

// --- BOTTOM WALL (y = 0) openings ---
// J4 SX1278 at PCB (38, 40→58) — headers extend toward bottom
// J5 E-paper at PCB (46, 40→58)
// J6 Zones at PCB (62, 40→55)
// J8 GPS at PCB (54, 44→52)
// These are pin headers — wires route out bottom

// --- BACK WALL (y = ext_w) ---
// LED1, LED2 at PCB y=8 → enclosure y = pcb_y + (60-8) = ~57 (near back)
// SW1 learn button at PCB (56, 8) → near back wall
// BZ1 buzzer at PCB (66, 8) → near back wall

// ============================================================
// Connector opening definitions
// Each: [wall, position_along_wall, width, z_bottom, z_top]
// wall: 0=front(y=0), 1=right(x=ext_l), 2=back(y=ext_w), 3=left(x=0)
// ============================================================

// Opening specs: [wall_id, center_pos_along_wall, opening_width, z_start, z_end]
openings = [
    // J7 USB — left wall
    [3, pcb_y + (pcb_w - 34), 14, pcb_z - 1, pcb_z + 6],
    // J1 12V screw terminal — back wall (PCB y=10 → near back)
    [2, pcb_x + 12, 12, pcb_z, pcb_z + 10],
    // J2 relay output — back wall
    [2, pcb_x + 88, 12, pcb_z, pcb_z + 10],
    // LED1+LED2 light pipes — back wall
    [2, pcb_x + 45, 18, pcb_z + 2, pcb_z + 6],
    // Cable entry — front wall (for sensor/zone wires)
    [0, ext_l * 0.35, 10, 4, 14],
    [0, ext_l * 0.6, 10, 4, 14],
    // Battery wires — right wall
    [1, ext_w * 0.5, 10, 4, 14],
];

// ============================================================
// Primitives
// ============================================================

module rounded_box(l, w, h, r) {
    hull()
        for (x = [r, l-r], y = [r, w-r])
            translate([x, y, 0])
                cylinder(r=r, h=h);
}

// ============================================================
// Finger joint generation
//
// For each wall, we divide it into segments of finger_w.
// Base gets even-numbered fingers (0, 2, 4...) pointing up.
// Lid gets odd-numbered fingers (1, 3, 5...) pointing down.
// Where an opening exists, BOTH base and lid omit the finger,
// leaving a hole.
// ============================================================

// Check if a finger at position [start, end] along a wall overlaps any opening
function finger_overlaps_opening(wall_id, fstart, fend) =
    let(results = [for (o = openings)
        if (o[0] == wall_id)
            let(ostart = o[1] - o[2]/2, oend = o[1] + o[2]/2)
                (fstart < oend && fend > ostart) ? 1 : 0
    ])
    len([for (r = results) if (r == 1) r]) > 0;


// Fingers for front/back walls (along X axis, full length including corners)
module x_wall_fingers(wall_id, y_pos, z_base, is_base) {
    n = floor(ext_l / finger_w);
    fw = ext_l / n;
    for (i = [0 : n - 1]) {
        fstart = i * fw;
        fend = fstart + fw;
        my_finger = is_base ? (i % 2 == 0) : (i % 2 == 1);
        has_opening = finger_overlaps_opening(wall_id, fstart, fend);
        if (my_finger && !has_opening) {
            translate([fstart + finger_tol, y_pos, z_base])
                cube([fw - 2 * finger_tol, wall, finger_depth]);
        }
    }
}

// Fingers for left/right walls (along Y axis, skip corners to avoid overlap)
module y_wall_fingers(wall_id, x_pos, z_base, is_base) {
    inner_start = wall;
    inner_len = ext_w - 2 * wall;
    n = max(1, floor(inner_len / finger_w));
    fw = inner_len / n;
    for (i = [0 : n - 1]) {
        fstart = inner_start + i * fw;
        fend = fstart + fw;
        my_finger = is_base ? (i % 2 == 0) : (i % 2 == 1);
        has_opening = finger_overlaps_opening(wall_id, fstart, fend);
        if (my_finger && !has_opening) {
            translate([x_pos, fstart + finger_tol, z_base])
                cube([wall, fw - 2 * finger_tol, finger_depth]);
        }
    }
}

// Slot cutters — remove wall material where the OPPOSING part's fingers go
// For base: cut slots where lid fingers (odd) will drop in
// For lid: cut slots where base fingers (even) will poke up into

module x_wall_slots(wall_id, y_pos, is_base) {
    n = floor(ext_l / finger_w);
    fw = ext_l / n;
    for (i = [0 : n - 1]) {
        fstart = i * fw;
        // The opposing part's finger: base cuts for lid (odd), lid cuts for base (even)
        opp_finger = is_base ? (i % 2 == 1) : (i % 2 == 0);
        has_opening = finger_overlaps_opening(wall_id, fstart, fstart + fw);
        if (opp_finger && !has_opening) {
            // Cut a slot finger_depth deep into this wall
            translate([fstart, y_pos - 0.01, is_base ? split_z - finger_depth : split_z])
                cube([fw, wall + 0.02, finger_depth + 0.01]);
        }
    }
}

module y_wall_slots(wall_id, x_pos, is_base) {
    inner_start = wall;
    inner_len = ext_w - 2 * wall;
    n = max(1, floor(inner_len / finger_w));
    fw = inner_len / n;
    for (i = [0 : n - 1]) {
        fstart = inner_start + i * fw;
        opp_finger = is_base ? (i % 2 == 1) : (i % 2 == 0);
        has_opening = finger_overlaps_opening(wall_id, fstart, fstart + fw);
        if (opp_finger && !has_opening) {
            translate([x_pos - 0.01, fstart, is_base ? split_z - finger_depth : split_z])
                cube([wall + 0.02, fw, finger_depth + 0.01]);
        }
    }
}

// ============================================================
// Base
// ============================================================

module base() {
    difference() {
        union() {
            // Floor + lower walls up to split_z
            difference() {
                rounded_box(ext_l, ext_w, split_z, corner_r);
                translate([wall, wall, wall])
                    rounded_box(int_l, int_w, split_z, max(corner_r - wall, 0.5));
            }

            // Upward-pointing fingers — front/back own the corners
            x_wall_fingers(0, 0, split_z, true);              // Front wall
            x_wall_fingers(2, ext_w - wall, split_z, true);   // Back wall
            y_wall_fingers(3, 0, split_z, true);               // Left wall
            y_wall_fingers(1, ext_l - wall, split_z, true);    // Right wall
        }

        // Cut openings through base walls where connectors are
        base_openings();

        // Cut receiving slots in base top for lid fingers to drop into
        // Where base has NO finger (odd slots), cut wall down by finger_depth
        // so lid's odd fingers can nest in
        x_wall_slots(0, 0, true);              // Front
        x_wall_slots(2, ext_w - wall, true);   // Back
        y_wall_slots(3, 0, true);               // Left
        y_wall_slots(1, ext_l - wall, true);    // Right
    }

    // PCB standoffs
    pcb_standoffs();

    // Battery cradle
    battery_cradle();

    // Internal alignment pins (2x, help register lid)
    for (pos = [[wall + 10, wall + 10], [ext_l - wall - 10, ext_w - wall - 10]])
        translate([pos[0], pos[1], split_z])
            cylinder(d=3, h=finger_depth - 1);
}

module base_openings() {
    for (o = openings) {
        wid = o[0];
        pos = o[1];
        w = o[2];
        z0 = o[3];
        z1 = o[4];

        if (wid == 0) {
            // Front wall (y=0)
            translate([pos - w/2, -1, z0])
                cube([w, wall + 2, z1 - z0]);
        }
        if (wid == 1) {
            // Right wall (x=ext_l)
            translate([ext_l - wall - 1, pos - w/2, z0])
                cube([wall + 2, w, z1 - z0]);
        }
        if (wid == 2) {
            // Back wall (y=ext_w)
            translate([pos - w/2, ext_w - wall - 1, z0])
                cube([w, wall + 2, z1 - z0]);
        }
        if (wid == 3) {
            // Left wall (x=0)
            translate([-1, pos - w/2, z0])
                cube([wall + 2, w, z1 - z0]);
        }
    }
}

module pcb_standoffs() {
    // Snap-fit standoffs — PCB press-fits onto posts, no screws
    // Post has slight taper and a snap ring at top to grip PCB
    positions = [
        [pcb_x + standoff_inset, pcb_y + standoff_inset],
        [pcb_x + pcb_l - standoff_inset, pcb_y + standoff_inset],
        [pcb_x + standoff_inset, pcb_y + pcb_w - standoff_inset],
        [pcb_x + pcb_l - standoff_inset, pcb_y + pcb_w - standoff_inset],
    ];
    post_d = 3.0;       // slightly under M3 hole (3.2mm) for friction
    ring_d = 4.0;       // snap ring catches PCB top
    ring_h = 0.6;       // ring height
    for (p = positions)
        translate([p[0], p[1], wall]) {
            // Main post
            cylinder(d=post_d, h=standoff_h);
            // Support base
            cylinder(d=standoff_d, h=2);
            // Snap ring at top (catches above PCB)
            translate([0, 0, standoff_h + pcb_t - 0.1])
                cylinder(d1=post_d, d2=ring_d, h=ring_h);
        }
}

module battery_cradle() {
    batt_cy_start = batt_cy - batt_l/2;
    cradle_r = batt_d/2 + cradle_wall;

    // Semi-circular trough
    translate([batt_cx, batt_cy_start, wall])
        rotate([-90, 0, 0])
            linear_extrude(batt_l)
                difference() {
                    circle(r=cradle_r);
                    circle(d=batt_d);
                    // Cut top half open for insertion
                    translate([-cradle_r - 1, 0])
                        square([cradle_r * 2 + 2, cradle_r + 1]);
                }

    // End retainer walls
    for (dy = [-cradle_wall, batt_l])
        translate([batt_cx - cradle_r, batt_cy_start + dy, wall])
            cube([cradle_r * 2, cradle_wall, batt_d/2 + 4]);

    // Zip-tie channels — slots through cradle floor for zip ties to loop over battery
    zt_slot_w = 4;    // zip tie width
    zt_slot_h = 2.5;  // zip tie thickness + clearance
    for (dy = [batt_l * 0.25, batt_l * 0.75]) {
        // Slot on left side of cradle
        translate([batt_cx - cradle_r - 1, batt_cy_start + dy - zt_slot_w/2, wall - 0.01])
            cube([zt_slot_h, zt_slot_w, zt_slot_h + 0.02]);
        // Slot on right side of cradle
        translate([batt_cx + cradle_r + 1 - zt_slot_h, batt_cy_start + dy - zt_slot_w/2, wall - 0.01])
            cube([zt_slot_h, zt_slot_w, zt_slot_h + 0.02]);
    }
}

// ============================================================
// Lid
// ============================================================

module lid() {
    lid_wall_h = ext_h - split_z;

    difference() {
        union() {
            // Ceiling + upper walls from split_z to ext_h
            translate([0, 0, split_z])
                difference() {
                    rounded_box(ext_l, ext_w, lid_wall_h, corner_r);
                    translate([wall, wall, -1])
                        rounded_box(int_l, int_w, lid_wall_h - wall + 1, max(corner_r - wall, 0.5));
                }

            // Downward-pointing fingers — same layout as base, opposite parity
            x_wall_fingers(0, 0, split_z - finger_depth, false);              // Front
            x_wall_fingers(2, ext_w - wall, split_z - finger_depth, false);   // Back
            y_wall_fingers(3, 0, split_z - finger_depth, false);               // Left
            y_wall_fingers(1, ext_l - wall, split_z - finger_depth, false);    // Right
        }

        // Cut openings through lid walls where connectors are
        lid_openings();

        // Cut receiving slots in lid bottom for base fingers to poke up into
        x_wall_slots(0, 0, false);              // Front
        x_wall_slots(2, ext_w - wall, false);   // Back
        y_wall_slots(3, 0, false);               // Left
        y_wall_slots(1, ext_l - wall, false);    // Right

        // Alignment pin holes
        for (pos = [[wall + 10, wall + 10], [ext_l - wall - 10, ext_w - wall - 10]])
            translate([pos[0], pos[1], split_z - finger_depth - 1])
                cylinder(d=3 + 0.4, h=finger_depth + 2);

        // LoRa antenna channel — groove in lid interior ceiling
        // 82mm long for 915MHz quarter-wave, runs along front wall (y = wall)
        // Press-fit copper wire into this channel
        ant_ch_w = 1.8;     // channel width (fits 1mm wire + clearance)
        ant_ch_d = 1.5;     // channel depth into lid ceiling
        ant_start_x = pcb_x + 44;  // starts near LoRa module (J4 at pcb_x+38)
        ant_len = 82;        // quarter-wave at 915MHz
        // Straight run along front interior wall
        translate([ant_start_x, wall + 2, ext_h - wall - ant_ch_d])
            cube([ant_len, ant_ch_w, ant_ch_d + 0.1]);
        // Entry notch — vertical slot so wire can come up from module
        translate([ant_start_x - 1, wall + 2, split_z - 2])
            cube([ant_ch_w + 1, ant_ch_w, ext_h - wall - split_z + 3]);
    }

    // Antenna channel guide ribs (keep wire from falling out)
    // Small bumps every 20mm that the wire snaps past
    for (dx = [20, 40, 60]) {
        translate([pcb_x + 44 + dx, wall + 2, ext_h - wall - 1.5])
            cube([0.6, 1.8, 0.5]);
    }
}

module lid_openings() {
    for (o = openings) {
        wid = o[0];
        pos = o[1];
        w = o[2];
        z0 = o[3];
        z1 = o[4];
        // Extend opening up through the lid portion too
        z_top = ext_h;

        if (wid == 0) {
            translate([pos - w/2, -1, z0])
                cube([w, wall + 2, z_top - z0]);
        }
        if (wid == 1) {
            translate([ext_l - wall - 1, pos - w/2, z0])
                cube([wall + 2, w, z_top - z0]);
        }
        if (wid == 2) {
            translate([pos - w/2, ext_w - wall - 1, z0])
                cube([w, wall + 2, z_top - z0]);
        }
        if (wid == 3) {
            translate([-1, pos - w/2, z0])
                cube([wall + 2, w, z_top - z0]);
        }
    }
}

// ============================================================
// Mounting Flanges (on base)
// ============================================================

module mounting_flanges() {
    for (side = [0, 1]) {
        translate([side * ext_l, ext_w/2 - flange_l/2, 0])
            mirror([side, 0, 0])
                difference() {
                    hull() {
                        cube([flange_w, flange_l, flange_t]);
                        cube([1, flange_l, split_z * 0.4]);
                    }
                    translate([flange_w/2, flange_l/2, -1])
                        cylinder(d=flange_hole, h=flange_t + 2);
                }
    }
}

// ============================================================
// Visual models (preview only — not printed)
// ============================================================

module pcb_model() {
    color("#1a5a1a", 0.8)
    translate([pcb_x, pcb_y, pcb_z])
        cube([pcb_l, pcb_w, pcb_t]);

    // Relay (tallest component: ~16mm)
    color("#3a3a6a", 0.6)
    translate([pcb_x + 63, pcb_y + 12, pcb_z + pcb_t])
        cube([24, 20, 16]);

    // MCU TQFP-32
    color("#2a2a2a", 0.7)
    translate([pcb_x + 43, pcb_y + 25, pcb_z + pcb_t])
        cube([10, 10, 1.5]);

    // Buzzer
    color("#4a4a4a", 0.6)
    translate([pcb_x + 60, pcb_y + 46, pcb_z + pcb_t])
        cylinder(d=12, h=9.5);

    // USB connector (left edge)
    color("#888", 0.7)
    translate([pcb_x - 2, pcb_y + 22, pcb_z])
        cube([9, 8, 4]);

    // Pin headers (bottom area)
    color("#daa520", 0.7)
    for (dx = [28, 36, 44, 52])
        translate([pcb_x + dx, pcb_y + 30, pcb_z + pcb_t])
            cube([2.54, 18, 8]);
}

module battery_model() {
    batt_cy_start = batt_cy - batt_l/2;
    color("#cc7700", 0.7)
    translate([batt_cx, batt_cy_start, wall + batt_d/2 + 2])
        rotate([-90, 0, 0])
            cylinder(d=batt_d, h=batt_l);

    // + terminal
    color("#ddaa00", 0.8)
    translate([batt_cx, batt_cy_start - 0.5, wall + batt_d/2 + 2])
        rotate([-90, 0, 0])
            cylinder(d=6, h=1);
}

// LoRa module (RFM95W ~16x16x3mm) plugged into J4 header
module lora_model() {
    // J4 is at PCB (38, 40), header pins point down from module
    lora_x = pcb_x + 36;               // centered on J4
    lora_y = pcb_y + 38;               // sits over J4 header area
    lora_z = pcb_z + pcb_t + 8;        // above header pins (~8mm pin height)

    // Module PCB
    color("#1a6a1a", 0.8)
    translate([lora_x, lora_y, lora_z])
        cube([16, 16, 1.2]);

    // RF shield can
    color("#aaa", 0.7)
    translate([lora_x + 1, lora_y + 1, lora_z + 1.2])
        cube([14, 12, 2]);

    // Antenna wire — goes up from module then into lid channel
    // Vertical run up to lid
    color("#d44", 0.9)
    translate([lora_x + 1, pcb_y + 2, lora_z + 1])
        cylinder(d=0.8, h=ext_h - wall - 1.5 - lora_z - 1);
    // Horizontal run along lid channel (82mm, along front wall interior)
    color("#d44", 0.9)
    translate([lora_x + 1, pcb_y + 2, ext_h - wall - 0.8])
        rotate([0, 90, 0])
            cylinder(d=0.8, h=82);

    // Label
    color("#fff")
    translate([lora_x + 3, lora_y + 14, lora_z + 1.3])
        linear_extrude(0.2)
            text("LoRa", size=3);
}

// GPS module (BN-220 ~22x20x6mm) mounted on lid interior
module gps_model() {
    // Mounted flat against inside of lid, toward left side
    // Patch antenna faces up (toward sky through plastic lid)
    gps_x = wall + 8;
    gps_y = wall + 8;
    gps_z = ext_h - wall - 6;          // flush against lid interior

    // Module PCB
    color("#2a2a8a", 0.8)
    translate([gps_x, gps_y, gps_z])
        cube([22, 20, 1.2]);

    // Ceramic patch antenna (on top, faces lid/sky)
    color("#f5f0e0", 0.9)
    translate([gps_x + 3, gps_y + 2, gps_z + 1.2])
        cube([16, 16, 4]);

    // Label
    color("#fff")
    translate([gps_x + 5, gps_y + 18, gps_z + 1.3])
        linear_extrude(0.2)
            text("GPS", size=3);
}

/* [Modules] */
show_lora = true;
show_gps = true;

// ============================================================
// Assembly
// ============================================================

if (show_base) {
    color("#555", 0.85)
        base();
    color("#666", 0.8)
        mounting_flanges();
}

if (show_lid) {
    lid_offset = explode > 0 ? explode : 0;
    translate([0, 0, lid_offset])
        color("#555", 0.7)
            lid();
}

if (show_pcb)
    pcb_model();

if (show_battery)
    battery_model();

if (show_lora)
    lora_model();

if (show_gps) {
    gps_offset = explode > 0 ? explode : 0;
    translate([0, 0, gps_offset])
        gps_model();
}
