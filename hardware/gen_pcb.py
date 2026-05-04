#!/usr/bin/env python3
"""Generate MotoKey Lock Box PCB layout.

Reads the netlist exported from the schematic and creates
a rectangular 2-layer PCB with component placement.

Board: 95x60mm, 2-layer FR4
  Left:   Power input + LDO + USB charger + sensors
  Center: MCU (ATmega328P TQFP-32)
  Right:  Relay driver + relay (Finder 40.11, 29x27mm)
  Top:    LEDs, learn button, buzzer, relay output
  Bottom: Headers (ICSP, SX1278, e-paper, GPS, zones)
  BT1:    Off-board (18650 holder 88mm, too large for PCB)

Usage:
    /Applications/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
"""
import pcbnew
import re
import os

KICAD_FP = "/Applications/KiCad.app/Contents/SharedSupport/footprints"
HERE = os.path.dirname(os.path.abspath(__file__))
NETLIST = "/tmp/motokey-netlist.xml"
OUTPUT = os.path.join(HERE, "motokey-lockbox.kicad_pcb")

BOARD_W = 95.0
BOARD_H = 60.0
MH_INSET = 4.0


def mm(val):
    return pcbnew.FromMM(val)

def vec(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))

def ang(deg):
    return pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T)


# ============================================================
# Netlist parser
# ============================================================

def parse_netlist(path):
    with open(path) as f:
        text = f.read()

    components = {}
    for m in re.finditer(
        r'\(comp \(ref "([^"]+)"\)(.*?)\(tstamps "([^"]+)"\)\)',
        text, re.DOTALL
    ):
        ref, block, tstamp = m.group(1), m.group(2), m.group(3)
        val = re.search(r'\(value "([^"]+)"\)', block).group(1)
        fp = re.search(r'\(footprint "([^"]+)"\)', block).group(1)
        components[ref] = {'value': val, 'footprint': fp, 'tstamp': tstamp}

    nets = {}
    nets_start = text.find('(nets')
    if nets_start >= 0:
        nets_text = text[nets_start:]
        p = 0
        while True:
            idx = nets_text.find('(net (code', p)
            if idx < 0:
                break
            depth = 0
            end = idx
            for i in range(idx, len(nets_text)):
                if nets_text[i] == '(':
                    depth += 1
                elif nets_text[i] == ')':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            blk = nets_text[idx:end]
            name = re.search(r'name "([^"]*)"', blk).group(1)
            nodes = re.findall(
                r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', blk)
            nets[name] = nodes
            p = end

    return components, nets


# ============================================================
# Component placements: ref -> (x_mm, y_mm, rotation_deg)
#
# Footprint reference sizes (from library):
#   K1 Relay_SPDT_Finder_40.11: 29x27mm
#      Pads: A1(0,0), A2(0,18), COM/11(20,7.5), NO/12(16.5,0), NC/14(23.5,0)
#   U1 TQFP-32: 10x10mm
#   U2 SOT-223: 9x7mm
#   U3 SOT-23-5: ~3x3mm
#   BZ1 Buzzer_12x9.5: 13x13mm
#   SW1 PTS645: 10x7mm
#   J7 USB_Micro-B: 9x6mm
#   BT1 Keystone_1042_18650: 88x22mm (off-board)
#   1x8 pin header: extends 17.78mm from pin1
# ============================================================

PLACEMENTS = {
    # ---- Power input (top-left) ----
    'J1':   (12,  10,  0),      # 12V screw terminal (1x2)
    'D1':   (20,  10,  0),      # TVS diode (SMB)
    'U2':   (26,  18,  0),      # AMS1117 LDO (SOT-223)
    'C1':   (18,  17,  90),     # 10uF input cap
    'C2':   (18,  21,  90),     # 100nF input cap
    'C3':   (34,  18,  90),     # 10uF output cap

    # ---- Schottky power-path ----
    'D3':   (34,  26,  90),     # BAT54 Schottky (VBAT → +5V)

    # ---- USB charger (left side) ----
    'J7':   (5,   34,  90),     # USB Micro-B on left edge
    'U3':   (18,  34,  0),      # MCP73831 charger (SOT-23-5)
    'R9':   (12,  38,  0),      # 2k PROG resistor
    'C6':   (24,  38,  90),     # 4.7uF VBAT cap

    # ---- Battery (off-board, 88x22mm holder) ----
    'BT1':  (150, 30,  0),      # Off-board: connect via wires or swap to JST

    # ---- MCU (center) ----
    'U1':   (48,  30,  0),      # ATmega328P TQFP-32 (center of board)
    'C4':   (40,  22,  90),     # 100nF VCC decoupling
    'C5':   (56,  22,  90),     # 100nF AREF decoupling
    'R4':   (40,  16,  0),      # 10k reset pullup

    # ---- Indicators (top) ----
    'LED1': (42,  8,   0),      # Red LED (armed)
    'LED2': (48,  8,   0),      # Green LED (unlocked)
    'R1':   (42,  12,  0),      # 330 LED1 resistor
    'R2':   (48,  12,  0),      # 330 LED2 resistor
    'SW1':  (56,  8,   0),      # Learn button (PTS645, 10x7mm)
    'BZ1':  (66,  8,   0),      # Buzzer (12mm dia)
    'R5':   (60,  16,  0),      # 100 buzzer resistor

    # ---- Relay section (right side) ----
    # K1 at (68,22): A1(68,22)+5V, A2(68,40)coil_lo,
    #   COM(88,29.5), NO(84.5,22), NC(91.5,22)
    'K1':   (68,  22,  0),      # Relay SPDT (Finder 40.11, 29x27mm)
    'D2':   (72,  16,  0),      # 1N4148 flyback diode (above relay)
    'R3':   (62,  28,  90),     # 1k base resistor
    'Q1':   (62,  36,  0),      # MMBT2222A NPN (SOT-23)
    'J2':   (88,  10,  0),      # Relay output (1x3 header, top-right)

    # ---- Bottom headers ----
    # Pin headers: pin1 at origin, subsequent pins at +2.54mm in y
    # 1x8 extends 17.78mm downward from pin1
    'J3':   (30,  48,  0),      # ICSP 2x3 (extends to y=53)
    'J4':   (38,  40,  0),      # SX1278 radio 1x8 (extends to y=57.8)
    'J5':   (46,  40,  0),      # E-paper 1x8 (extends to y=57.8)
    'J8':   (54,  44,  0),      # GPS 1x4 (extends to y=51.6)
    'J6':   (62,  40,  0),      # Zone inputs 1x7 (extends to y=55.2)

    # ---- Sensors (bottom-left) ----
    'TH1':  (12,  48,  0),      # NTC thermistor (0805)
    'R6':   (12,  52,  0),      # 10k temp pullup
    'R8':   (20,  48,  0),      # LDR photoresistor (0805)
    'R7':   (20,  52,  0),      # 10k light pullup
}


# ============================================================
# Board creation helpers
# ============================================================

def add_outline(board):
    corners = [
        (0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)
    ]
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(vec(x1, y1))
        seg.SetEnd(vec(x2, y2))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(mm(0.15))
        board.Add(seg)


def add_mounting_holes(board):
    positions = [
        (MH_INSET, MH_INSET),
        (BOARD_W - MH_INSET, MH_INSET),
        (MH_INSET, BOARD_H - MH_INSET),
        (BOARD_W - MH_INSET, BOARD_H - MH_INSET),
    ]
    lib = os.path.join(KICAD_FP, "MountingHole.pretty")
    for i, (mx, my) in enumerate(positions):
        try:
            mh = pcbnew.FootprintLoad(lib, "MountingHole_3.2mm_M3")
            mh.SetReference(f"MH{i + 1}")
            mh.SetValue("MountingHole")
            mh.SetPosition(vec(mx, my))
            board.Add(mh)
        except Exception as e:
            print(f"WARNING: mounting hole: {e}")
            break


def add_zones(board, net_map):
    if 'GND' not in net_map:
        return
    margin = 0.5
    pts = [
        (margin, margin),
        (BOARD_W - margin, margin),
        (BOARD_W - margin, BOARD_H - margin),
        (margin, BOARD_H - margin),
    ]
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(net_map['GND'])
        zone.SetIsRuleArea(False)
        zone.SetDoNotAllowTracks(False)
        zone.SetDoNotAllowVias(False)
        zone.SetDoNotAllowPads(False)
        zone.SetDoNotAllowCopperPour(False)
        zone.SetDoNotAllowFootprints(False)
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in pts:
            outline.Append(mm(x), mm(y))
        board.Add(zone)


def add_title(board):
    text = pcbnew.PCB_TEXT(board)
    text.SetText("MotoKey Lock Box v1")
    text.SetPosition(vec(BOARD_W / 2, 3))
    text.SetLayer(pcbnew.F_SilkS)
    text.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
    text.SetTextThickness(mm(0.15))
    board.Add(text)


# ============================================================
# Main
# ============================================================

def create_board():
    components, nets = parse_netlist(NETLIST)

    board = pcbnew.BOARD()
    settings = board.GetDesignSettings()
    settings.SetBoardThickness(mm(1.6))

    add_outline(board)

    # Create all nets
    net_map = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        net_map[name] = ni

    # (ref, pin) -> net_name lookup
    pin_net = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            pin_net[(ref, pin)] = name

    # Place components
    fp_map = {}
    off_y = 10
    for ref in sorted(components):
        info = components[ref]
        lib_name, fp_name = info['footprint'].split(':', 1)
        lib_path = os.path.join(KICAD_FP, f"{lib_name}.pretty")

        try:
            fp = pcbnew.FootprintLoad(lib_path, fp_name)
        except Exception as e:
            print(f"ERROR loading {info['footprint']} for {ref}: {e}")
            continue

        fp.SetReference(ref)
        fp.SetValue(info['value'])

        if ref in PLACEMENTS:
            x, y, rot = PLACEMENTS[ref]
            fp.SetPosition(vec(x, y))
            if rot != 0:
                fp.SetOrientation(ang(rot))
        else:
            fp.SetPosition(vec(BOARD_W + 20, off_y))
            off_y += 8
            print(f"NOTE: {ref} has no placement, parked off-board")

        board.Add(fp)
        fp_map[ref] = fp

    # Assign nets to pads
    assigned = 0
    for ref, fp in fp_map.items():
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in pin_net:
                net_name = pin_net[key]
                if net_name in net_map:
                    pad.SetNet(net_map[net_name])
                    assigned += 1

    add_mounting_holes(board)
    add_zones(board, net_map)
    add_title(board)

    board.Save(OUTPUT)
    print(f"PCB saved: {OUTPUT}")
    print(f"Board: {BOARD_W}x{BOARD_H}mm, 2-layer, 1.6mm FR4")
    print(f"Components: {len(fp_map)}, Nets: {len(net_map)}, Pad assignments: {assigned}")
    print(f"NOTE: BT1 (18650 holder) placed off-board — connect via wires or swap footprint")


if __name__ == '__main__':
    create_board()
