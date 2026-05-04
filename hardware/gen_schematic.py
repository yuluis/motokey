#!/usr/bin/env python3
"""Generate MotoKey Lock Box KiCad schematic.

KeeLoq receiver + relay kill switch for e-motorcycles.
  U1: ATmega328P-A (TQFP-32), 8MHz internal osc
  U2: AMS1117-5.0 (SOT-223) LDO
  U3: MCP73831-2-OT (SOT-23-5) LiPo charger
  Q1: MMBT2222A (SOT-23) NPN relay driver
  K1: Relay_SPDT, 5V coil
  D1: Zener/TVS 16V input protection
  D2: 1N4148 flyback diode
  D3: Schottky diode (battery → +5V power path)
  BT1: LiPo battery cell (3.7V)
  LED1/LED2: status LEDs (red=armed, green=unlocked)
  BZ1: passive piezo buzzer (PWM on PD6/OC0A)
  J4: SX1278 LoRa/ASK radio module (8-pin header)
  J5: 1.54" e-paper display (8-pin header, optional)
  J6: Zone inputs for NO/NC contact sensors (7-pin header)
  J7: USB Micro-B (charging input for LiPo)
  RT1: NTC thermistor (10k, tamper/ambient temp)
  R_LDR: LDR photoresistor (light/tamper detect)
  R1-R9, C1-C6, SW1, J1-J7, BT1
"""
import uuid, os, re, sys

KICAD_SYMS = "/Applications/KiCad.app/Contents/SharedSupport/symbols"
HERE = os.path.dirname(os.path.abspath(__file__))

def uid():
    return str(uuid.uuid4())

# ============================================================
# Symbol extraction from KiCad libraries
# ============================================================

def _find_symbol(text, name):
    """Find and extract a top-level symbol by balanced parens."""
    target = f'(symbol "{name}"'
    pos = 0
    while True:
        idx = text.find(target, pos)
        if idx < 0:
            return None
        # Ensure exact name match (not a sub-symbol like Name_0_1)
        end_of_name = idx + len(target)
        if end_of_name < len(text) and text[end_of_name] not in '\n\r \t':
            pos = end_of_name
            continue
        # Extract by balanced parens
        depth = 0
        for i in range(idx, len(text)):
            if text[i] == '(':
                depth += 1
            elif text[i] == ')':
                depth -= 1
                if depth == 0:
                    return text[idx:i+1]
        break
    return None

def _get_sub_symbols(sym_text, name):
    """Extract sub-symbols (Name_0_1, Name_1_1, etc.)."""
    subs = []
    target = f'(symbol "{name}_'
    pos = 0
    while True:
        idx = sym_text.find(target, pos)
        if idx < 0:
            break
        depth = 0
        for i in range(idx, len(sym_text)):
            if sym_text[i] == '(':
                depth += 1
            elif sym_text[i] == ')':
                depth -= 1
                if depth == 0:
                    subs.append(sym_text[idx:i+1])
                    pos = i + 1
                    break
    return subs

def flatten(lib_file, child_name):
    """Extract symbol from library, flattening 'extends' if needed."""
    with open(f"{KICAD_SYMS}/{lib_file}") as f:
        text = f.read()

    child = _find_symbol(text, child_name)
    if child is None:
        raise ValueError(f"Symbol '{child_name}' not found in {lib_file}")

    m = re.search(r'\(extends "([^"]+)"\)', child)
    if not m:
        return child  # already flat

    parent_name = m.group(1)
    # Recursively flatten parent if it also extends
    parent = _find_symbol(text, parent_name)
    if parent is None:
        raise ValueError(f"Parent '{parent_name}' not found in {lib_file}")
    pm = re.search(r'\(extends "([^"]+)"\)', parent)
    if pm:
        parent = flatten(lib_file, parent_name)

    # Get parent sub-symbols, rename to child
    subs = _get_sub_symbols(parent, parent_name)
    renamed = [re.sub(rf'"{re.escape(parent_name)}_(\d+_\d+)"', rf'"{child_name}_\1"', s) for s in subs]

    # Remove extends directive from child
    result = re.sub(r'\n?\s*\(extends "[^"]+"\)', '', child)

    # Copy missing attributes from parent
    for attr in ['exclude_from_sim', 'in_bom', 'on_board']:
        if attr not in result:
            am = re.search(rf'\({attr}\s+\w+\)', parent)
            if am:
                nl = result.find('\n')
                result = result[:nl+1] + '\t\t\t' + am.group(0) + '\n' + result[nl+1:]

    # Also copy pin_numbers/pin_names if present in parent but not child
    for attr in ['pin_numbers', 'pin_names']:
        if attr not in result:
            # Extract the full block
            am_idx = parent.find(f'({attr}')
            if am_idx >= 0:
                depth = 0
                for i in range(am_idx, len(parent)):
                    if parent[i] == '(':
                        depth += 1
                    elif parent[i] == ')':
                        depth -= 1
                        if depth == 0:
                            block = parent[am_idx:i+1]
                            nl = result.find('\n')
                            result = result[:nl+1] + '\t\t\t' + block + '\n' + result[nl+1:]
                            break

    # Insert sub-symbols before closing paren
    close = result.rstrip().rfind(')')
    sub_text = '\n'.join('\t\t\t' + s for s in renamed)
    result = result[:close] + '\n' + sub_text + '\n\t\t' + result[close:]

    return result

def lib_symbol(lib_file, name, lib_prefix):
    """Get symbol for schematic lib_symbols section with proper prefix."""
    sym = flatten(lib_file, name)
    full = f"{lib_prefix}:{name}"
    # Only rename the top-level symbol name; sub-symbols keep original names
    sym = sym.replace(f'(symbol "{name}"', f'(symbol "{full}"', 1)
    # Add two tabs prefix (preserving internal indentation from library)
    lines = sym.split('\n')
    return '\n'.join('\t\t' + line for line in lines)

# ============================================================
# Pin endpoint transform
# ============================================================

def pxy(sx, sy, px, py, theta=0):
    """Transform library pin (px,py) to schematic coords for symbol at (sx,sy) rotation theta."""
    if theta == 0:   return (round(sx + px, 2), round(sy - py, 2))
    if theta == 90:  return (round(sx - py, 2), round(sy - px, 2))
    if theta == 180: return (round(sx - px, 2), round(sy + py, 2))
    if theta == 270: return (round(sx + py, 2), round(sy + px, 2))
    return (round(sx + px, 2), round(sy - py, 2))

# ============================================================
# Schematic element generators
# ============================================================

ROOT = uid()

def s_wire(x1, y1, x2, y2):
    return (f'\t(wire\n\t\t(pts (xy {x1} {y1}) (xy {x2} {y2}))\n'
            f'\t\t(stroke (width 0) (type default))\n\t\t(uuid "{uid()}")\n\t)')

def s_label(name, x, y, rot=0):
    return (f'\t(label "{name}"\n\t\t(at {x} {y} {rot})\n'
            f'\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t)\n'
            f'\t\t(uuid "{uid()}")\n\t)')

def s_nc(x, y):
    return f'\t(no_connect (at {x} {y}) (uuid "{uid()}"))'

def s_junction(x, y):
    return (f'\t(junction\n\t\t(at {x} {y})\n\t\t(diameter 0)\n'
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{uid()}")\n\t)')

def s_power(lib_id, ref, value, x, y, rot=0):
    """Power symbol instance (+5V, GND, +12V)."""
    vy = y - 3.556 if 'GND' not in value else y + 3.81
    ry = y + 3.81 if 'GND' not in value else y - 6.35
    return f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {rot})
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{uid()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x} {ry} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x} {vy} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Datasheet" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Description" ""
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(pin "1" (uuid "{uid()}"))
\t\t(instances
\t\t\t(project ""
\t\t\t\t(path "/{ROOT}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""

def s_comp(lib_id, ref, value, fp, x, y, rot, pins, desc=""):
    """Component instance. pins = list of pin identifiers (numbers or names)."""
    pin_lines = '\n'.join(f'\t\t(pin "{p}" (uuid "{uid()}"))' for p in pins)
    return f"""\t(symbol
\t\t(lib_id "{lib_id}")
\t\t(at {x} {y} {rot})
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(uuid "{uid()}")
\t\t(property "Reference" "{ref}"
\t\t\t(at {x} {y - 2.54} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Value" "{value}"
\t\t\t(at {x} {y + 2.54} 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Footprint" "{fp}"
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Description" "{desc}"
\t\t\t(at {x} {y} 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
{pin_lines}
\t\t(instances
\t\t\t(project ""
\t\t\t\t(path "/{ROOT}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""

# ============================================================
# Main schematic generation
# ============================================================

def generate():
    elements = []  # wires, labels, NCs, junctions
    components = []  # symbol instances
    pwr_idx = [0]  # mutable counter for power symbol refs

    def add_pwr(lib_id, value, x, y, rot=0):
        pwr_idx[0] += 1
        components.append(s_power(lib_id, f"#PWR{pwr_idx[0]:02d}", value, x, y, rot))

    def add_5v(x, y):
        add_pwr("power:+5V", "+5V", x, y)

    def add_gnd(x, y):
        add_pwr("power:GND", "GND", x, y)

    def add_12v(x, y):
        add_pwr("power:+12V", "+12V", x, y)

    flg_idx = [0]
    def add_pwrflag(x, y, rot=0):
        flg_idx[0] += 1
        components.append(s_power("power:PWR_FLAG", f"#FLG{flg_idx[0]:02d}", "PWR_FLAG", x, y, rot))

    # ---- Component positions (all on 2.54mm grid) ----
    G = 2.54
    # MCU at center of A3 sheet
    U1x, U1y = 60*G, 44*G       # 152.4, 111.76
    # LDO — spaced right for caps
    U2x, U2y = 28*G, 30*G       # 71.12, 76.2
    # NPN — Q1y set below from u1_pd3 for horizontal wire
    Q1x = 85*G                   # 215.9
    # Relay
    K1x, K1y = 93*G, 42*G       # 236.22, 106.68

    # ---- U1: ATmega328P-A ----
    # Pin endpoints (from library data, theta=0):
    # Right-side pins at lib(15.24, py): schematic (U1x+15.24, U1y-py)
    def u1r(py): return pxy(U1x, U1y, 15.24, py)
    # Left-side pins at lib(-15.24, py)
    def u1l(py): return pxy(U1x, U1y, -15.24, py)
    # Top pins
    def u1t(px, py): return pxy(U1x, U1y, px, py)

    u1_vcc  = u1t(0, 38.1)       # (150, 71.9)
    u1_avcc = u1t(2.54, 38.1)    # (152.54, 71.9)
    u1_gnd  = u1t(0, -38.1)      # (150, 148.1)
    u1_aref = u1l(30.48)         # (134.76, 79.52)
    u1_adc6 = u1l(25.4)          # ADC6 — TEMP_SENSE
    u1_adc7 = u1l(22.86)         # ADC7 — LIGHT_SENSE

    # Right-side port pins
    u1_pb0 = u1r(30.48)   # PB0 — LEARN
    u1_pb1 = u1r(27.94)   # PB1 — ZONE1
    u1_pb2 = u1r(25.4)    # PB2 — ZONE2
    u1_pb3 = u1r(22.86)   # PB3 — MOSI
    u1_pb4 = u1r(20.32)   # PB4 — MISO
    u1_pb5 = u1r(17.78)   # PB5 — SCK
    u1_xtal1 = u1r(15.24) # XTAL1 — NC
    u1_xtal2 = u1r(12.7)  # XTAL2 — NC
    u1_pc0 = u1r(7.62)    # PC0 — SX1278_NSS
    u1_pc1 = u1r(5.08)    # PC1 — SX1278_RST
    u1_pc2 = u1r(2.54)    # PC2 — EPD_CS
    u1_pc3 = u1r(0)       # PC3 — EPD_DC
    u1_pc4 = u1r(-2.54)   # PC4 — EPD_RST
    u1_pc5 = u1r(-5.08)   # PC5 — EPD_BUSY
    u1_reset = u1r(-7.62) # ~RESET/PC6
    u1_pd0 = u1r(-12.7)   # PD0 — ZONE3
    u1_pd1 = u1r(-15.24)  # PD1 — ZONE4
    u1_pd2 = u1r(-17.78)  # PD2 — RADIO_IRQ (INT0)
    u1_pd3 = u1r(-20.32)  # PD3 — RELAY_DRV
    u1_pd4 = u1r(-22.86)  # PD4 — LED1
    u1_pd5 = u1r(-25.4)   # PD5 — LED2
    u1_pd6 = u1r(-27.94)  # PD6 — BUZZER (OC0A)
    u1_pd7 = u1r(-30.48)  # PD7 — ZONE5

    # Set Q1y to match PD3 for horizontal R3→Q1 wire
    Q1y = u1_pd3[1]

    components.append(s_comp(
        "MCU_Microchip_ATmega:ATmega328P-A", "U1", "ATmega328P-AU",
        "Package_QFP:TQFP-32_7x7mm_P0.8mm", U1x, U1y, 0,
        [str(i) for i in range(1, 33)],
        "20MHz, 32kB Flash, 2kB SRAM, 1kB EEPROM, TQFP-32"))

    # U1 power connections
    elements.append(s_wire(*u1_vcc, u1_vcc[0], u1_vcc[1] - 2.54))
    add_5v(u1_vcc[0], u1_vcc[1] - 2.54)
    elements.append(s_wire(*u1_avcc, u1_avcc[0], u1_avcc[1] - 2.54))
    add_5v(u1_avcc[0], u1_avcc[1] - 2.54)
    elements.append(s_wire(*u1_gnd, u1_gnd[0], u1_gnd[1] + 2.54))
    add_gnd(u1_gnd[0], u1_gnd[1] + 2.54)

    # U1 AREF — C5 (100nF to GND)
    C5x, C5y = u1_aref[0] - 5.08, u1_aref[1]
    # C5 vertical: pin1 at top (C5x, C5y-3.81), pin2 at bottom (C5x, C5y+3.81)
    components.append(s_comp("Device:C", "C5", "100nF",
        "Capacitor_SMD:C_0805_2012Metric", C5x, C5y, 90, ["1", "2"],
        "AREF decoupling"))
    # C5 rot90: pin1 at (C5x-3.81, C5y), pin2 at (C5x+3.81, C5y)
    c5_p1 = pxy(C5x, C5y, 0, 3.81, 90)   # left
    c5_p2 = pxy(C5x, C5y, 0, -3.81, 90)   # right
    elements.append(s_wire(*c5_p2, *u1_aref))  # C5.pin2 → AREF
    elements.append(s_wire(*c5_p1, c5_p1[0] - 2.54, c5_p1[1]))
    add_gnd(c5_p1[0] - 2.54, c5_p1[1])

    # U1 unused pins — NC markers (only XTAL1/XTAL2 remain unused)
    for p in [u1_xtal1, u1_xtal2]:
        elements.append(s_nc(*p))

    # U1 signal connections via net labels
    # Wire stub RIGHT 5.08mm from each used right-side pin, then label
    def label_right(pin, name):
        elements.append(s_wire(*pin, pin[0] + 5.08, pin[1]))
        elements.append(s_label(name, pin[0] + 5.08, pin[1]))

    def label_left(pin, name):
        elements.append(s_wire(*pin, pin[0] - 5.08, pin[1]))
        elements.append(s_label(name, pin[0] - 5.08, pin[1], 180))

    # Left-side MCU signal labels (ADC6, ADC7)
    label_left(u1_adc6, "TEMP_SENSE")
    label_left(u1_adc7, "LIGHT_SENSE")

    # Right-side MCU signal labels
    label_right(u1_pb0, "LEARN")
    label_right(u1_pb1, "ZONE1")
    label_right(u1_pb2, "ZONE2")
    label_right(u1_pb3, "MOSI")
    label_right(u1_pb4, "MISO")
    label_right(u1_pb5, "SCK")
    label_right(u1_reset, "RESET")
    label_right(u1_pc0, "SX1278_NSS")
    label_right(u1_pc1, "SX1278_RST")
    label_right(u1_pc2, "EPD_CS")
    label_right(u1_pc3, "EPD_DC")
    label_right(u1_pc4, "EPD_RST")
    label_right(u1_pc5, "EPD_BUSY")
    label_right(u1_pd0, "ZONE3")
    label_right(u1_pd1, "ZONE4")
    label_right(u1_pd2, "RADIO_IRQ")
    label_right(u1_pd3, "RELAY_DRV")
    label_right(u1_pd4, "LED1_NET")
    label_right(u1_pd5, "LED2_NET")
    label_right(u1_pd6, "BUZZER")
    label_right(u1_pd7, "ZONE5")

    # ---- U2: AMS1117-5.0 LDO ----
    # Pins: VI(3) at (-7.62,0), GND(1) at (0,-7.62), VO(2) at (7.62,0)
    components.append(s_comp(
        "Regulator_Linear:AMS1117-5.0", "U2", "AMS1117-5.0",
        "Package_TO_SOT_SMD:SOT-223-3_TabPin2", U2x, U2y, 0,
        ["1", "2", "3"],
        "1A Low Dropout regulator, 5.0V fixed output"))
    u2_vi  = pxy(U2x, U2y, -7.62, 0)    # (57.38, 80)
    u2_gnd = pxy(U2x, U2y, 0, -7.62)    # (65, 87.62)
    u2_vo  = pxy(U2x, U2y, 7.62, 0)     # (72.62, 80)

    # U2 output → +5V
    elements.append(s_wire(*u2_vo, u2_vo[0] + 2.54, u2_vo[1]))
    add_5v(u2_vo[0] + 2.54, u2_vo[1])
    # U2 GND
    elements.append(s_wire(*u2_gnd, u2_gnd[0], u2_gnd[1] + 2.54))
    add_gnd(u2_gnd[0], u2_gnd[1] + 2.54)

    # ---- J1: 12V input connector (Conn_01x02) ----
    J1x, J1y = 12*G, 30*G
    components.append(s_comp(
        "Connector_Generic:Conn_01x02", "J1", "12V_IN",
        "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
        J1x, J1y, 180, ["1", "2"],
        "12V power input screw terminal"))
    # Rotation 180: pin1 lib(-5.08,0) → (J1x+5.08, J1y)
    j1_p1 = pxy(J1x, J1y, -5.08, 0, 180)     # +12V
    j1_p2 = pxy(J1x, J1y, -5.08, -2.54, 180)  # GND
    elements.append(s_wire(*j1_p1, j1_p1[0] + 2.54, j1_p1[1]))
    add_12v(j1_p1[0] + 2.54, j1_p1[1])
    elements.append(s_wire(*j1_p2, j1_p2[0] + 2.54, j1_p2[1]))
    add_gnd(j1_p2[0] + 2.54, j1_p2[1])

    # PWR_FLAG on +12V net (required for ERC)
    # GND net gets power_output from J7 (USB_B_Micro) GND pin
    add_pwrflag(j1_p1[0] + 2.54, j1_p1[1])

    # ---- D1: TVS / Zener 16V input protection ----
    D1x, D1y = 20*G, 30*G
    components.append(s_comp(
        "Device:D_Zener", "D1", "SMBJ16A",
        "Diode_SMD:D_SMB_Handsoldering", D1x, D1y, 270, ["1", "2"],
        "16V TVS diode, input protection"))
    # D_Zener rot 270: K(1) lib(-3.81,0) → pxy(270)=(D1x+0, D1y-3.81)
    # Wait, D_Zener pin positions: K at lib(-3.81,0), A at lib(3.81,0)
    # rot 270: x'=sx+py, y'=sy+px
    d1_k = pxy(D1x, D1y, -3.81, 0, 270)  # cathode → (50, 106.19)
    d1_a = pxy(D1x, D1y, 3.81, 0, 270)   # anode → (50, 113.81)
    # Actually for rot270: K: x'=50+0=50, y'=80+(-3.81)=76.19; A: x'=50+0=50, y'=80+3.81=83.81
    # Cathode up (+12V side), anode down (GND side) — correct for TVS
    elements.append(s_wire(*d1_k, d1_k[0], d1_k[1] - 2.54))
    add_12v(d1_k[0], d1_k[1] - 2.54)
    elements.append(s_wire(*d1_a, d1_a[0], d1_a[1] + 2.54))
    add_gnd(d1_a[0], d1_a[1] + 2.54)

    # Wire from J1/+12V to U2 input
    elements.append(s_wire(*u2_vi, u2_vi[0] - 2.54, u2_vi[1]))
    add_12v(u2_vi[0] - 2.54, u2_vi[1])

    # ---- C1: 10µF LDO input ----
    C1x, C1y = 24*G, 36*G
    components.append(s_comp("Device:C", "C1", "10uF",
        "Capacitor_SMD:C_0805_2012Metric", C1x, C1y, 0, ["1", "2"],
        "LDO input decoupling"))
    c1_p1 = pxy(C1x, C1y, 0, 3.81, 0)   # top
    c1_p2 = pxy(C1x, C1y, 0, -3.81, 0)  # bottom
    elements.append(s_wire(*c1_p1, c1_p1[0], c1_p1[1] - 2.54))
    add_12v(c1_p1[0], c1_p1[1] - 2.54)
    elements.append(s_wire(*c1_p2, c1_p2[0], c1_p2[1] + 2.54))
    add_gnd(c1_p2[0], c1_p2[1] + 2.54)

    # ---- C2: 100nF LDO input ----
    C2x, C2y = 26*G, 36*G
    components.append(s_comp("Device:C", "C2", "100nF",
        "Capacitor_SMD:C_0805_2012Metric", C2x, C2y, 0, ["1", "2"],
        "LDO input decoupling"))
    c2_p1 = pxy(C2x, C2y, 0, 3.81, 0)
    c2_p2 = pxy(C2x, C2y, 0, -3.81, 0)
    elements.append(s_wire(*c2_p1, c2_p1[0], c2_p1[1] - 2.54))
    add_12v(c2_p1[0], c2_p1[1] - 2.54)
    elements.append(s_wire(*c2_p2, c2_p2[0], c2_p2[1] + 2.54))
    add_gnd(c2_p2[0], c2_p2[1] + 2.54)

    # ---- C3: 10µF LDO output ----
    C3x, C3y = 32*G, 36*G
    components.append(s_comp("Device:C", "C3", "10uF",
        "Capacitor_SMD:C_0805_2012Metric", C3x, C3y, 0, ["1", "2"],
        "LDO output decoupling"))
    c3_p1 = pxy(C3x, C3y, 0, 3.81, 0)
    c3_p2 = pxy(C3x, C3y, 0, -3.81, 0)
    elements.append(s_wire(*c3_p1, c3_p1[0], c3_p1[1] - 2.54))
    add_5v(c3_p1[0], c3_p1[1] - 2.54)
    elements.append(s_wire(*c3_p2, c3_p2[0], c3_p2[1] + 2.54))
    add_gnd(c3_p2[0], c3_p2[1] + 2.54)

    # ---- C4: 100nF MCU VCC ----
    C4x, C4y = 34*G, 36*G
    components.append(s_comp("Device:C", "C4", "100nF",
        "Capacitor_SMD:C_0805_2012Metric", C4x, C4y, 0, ["1", "2"],
        "MCU VCC decoupling"))
    c4_p1 = pxy(C4x, C4y, 0, 3.81, 0)
    c4_p2 = pxy(C4x, C4y, 0, -3.81, 0)
    elements.append(s_wire(*c4_p1, c4_p1[0], c4_p1[1] - 2.54))
    add_5v(c4_p1[0], c4_p1[1] - 2.54)
    elements.append(s_wire(*c4_p2, c4_p2[0], c4_p2[1] + 2.54))
    add_gnd(c4_p2[0], c4_p2[1] + 2.54)

    # ---- R4: 10kΩ RESET pullup ----
    R4x, R4y = 72*G, u1_reset[1]
    components.append(s_comp("Device:R", "R4", "10k",
        "Resistor_SMD:R_0805_2012Metric", R4x, R4y, 90, ["1", "2"],
        "RESET pullup"))
    r4_p1 = pxy(R4x, R4y, 0, 3.81, 90)   # left
    r4_p2 = pxy(R4x, R4y, 0, -3.81, 90)   # right
    elements.append(s_label("RESET", r4_p1[0], r4_p1[1]))
    elements.append(s_wire(*r4_p2, r4_p2[0] + 2.54, r4_p2[1]))
    add_5v(r4_p2[0] + 2.54, r4_p2[1])

    # ---- R1: 330Ω + LED1 (red, armed) ----
    R1x, R1y = 78*G, u1_pd4[1]
    components.append(s_comp("Device:R", "R1", "330",
        "Resistor_SMD:R_0805_2012Metric", R1x, R1y, 90, ["1", "2"],
        "LED1 current limit"))
    r1_p1 = pxy(R1x, R1y, 0, 3.81, 90)
    r1_p2 = pxy(R1x, R1y, 0, -3.81, 90)
    elements.append(s_label("LED1_NET", r1_p1[0], r1_p1[1]))

    LED1x = R1x + 4*G
    components.append(s_comp("Device:LED", "LED1", "Red",
        "LED_SMD:LED_0805_2012Metric", LED1x, R1y, 180, ["1", "2"],
        "Armed status LED"))
    led1_a = pxy(LED1x, R1y, 3.81, 0, 180)   # anode (now on LEFT)
    led1_k = pxy(LED1x, R1y, -3.81, 0, 180)  # cathode (now on RIGHT)
    # R1.pin2 → LED1.anode
    elements.append(s_wire(*r1_p2, *led1_a))
    # LED1.cathode → GND
    elements.append(s_wire(*led1_k, led1_k[0] + 2.54, led1_k[1]))
    add_gnd(led1_k[0] + 2.54, led1_k[1])

    # ---- R2: 330Ω + LED2 (green, unlocked) ----
    R2x, R2y = 78*G, u1_pd5[1]
    components.append(s_comp("Device:R", "R2", "330",
        "Resistor_SMD:R_0805_2012Metric", R2x, R2y, 90, ["1", "2"],
        "LED2 current limit"))
    r2_p1 = pxy(R2x, R2y, 0, 3.81, 90)
    r2_p2 = pxy(R2x, R2y, 0, -3.81, 90)
    elements.append(s_label("LED2_NET", r2_p1[0], r2_p1[1]))

    LED2x = R2x + 4*G
    components.append(s_comp("Device:LED", "LED2", "Green",
        "LED_SMD:LED_0805_2012Metric", LED2x, R2y, 180, ["1", "2"],
        "Unlocked status LED"))
    led2_a = pxy(LED2x, R2y, 3.81, 0, 180)   # anode (LEFT)
    led2_k = pxy(LED2x, R2y, -3.81, 0, 180)  # cathode (RIGHT)
    elements.append(s_wire(*r2_p2, *led2_a))
    elements.append(s_wire(*led2_k, led2_k[0] + 2.54, led2_k[1]))
    add_gnd(led2_k[0] + 2.54, led2_k[1])

    # ---- R5: 100Ω buzzer series resistor + BZ1: passive piezo buzzer ----
    R5x, R5y = 78*G, u1_pd6[1]
    components.append(s_comp("Device:R", "R5", "100",
        "Resistor_SMD:R_0805_2012Metric", R5x, R5y, 90, ["1", "2"],
        "Buzzer current limit"))
    r5_p1 = pxy(R5x, R5y, 0, 3.81, 90)   # left
    r5_p2 = pxy(R5x, R5y, 0, -3.81, 90)  # right
    elements.append(s_label("BUZZER", r5_p1[0], r5_p1[1]))

    # BZ1: passive piezo buzzer (vertical, pin1(+) aligns with R5 pin2)
    BZ1x, BZ1y = 82*G, R5y + 2.54
    components.append(s_comp("Device:Buzzer", "BZ1", "Buzzer",
        "Buzzer_Beeper:Buzzer_12x9.5RM7.6", BZ1x, BZ1y, 0, ["1", "2"],
        "Passive piezo buzzer, PWM driven"))
    bz1_p1 = pxy(BZ1x, BZ1y, -2.54, 2.54, 0)   # + (upper-left)
    bz1_p2 = pxy(BZ1x, BZ1y, -2.54, -2.54, 0)   # - (lower-left)
    # R5.pin2 → BZ1.pin1 (horizontal wire)
    elements.append(s_wire(*r5_p2, *bz1_p1))
    # BZ1.pin2 → GND
    elements.append(s_wire(*bz1_p2, bz1_p2[0], bz1_p2[1] + 2.54))
    add_gnd(bz1_p2[0], bz1_p2[1] + 2.54)

    # ---- R3: 1kΩ relay driver base resistor ----
    R3x, R3y = 80*G, u1_pd3[1]
    components.append(s_comp("Device:R", "R3", "1k",
        "Resistor_SMD:R_0805_2012Metric", R3x, R3y, 90, ["1", "2"],
        "Relay driver base resistor"))
    r3_p1 = pxy(R3x, R3y, 0, 3.81, 90)
    r3_p2 = pxy(R3x, R3y, 0, -3.81, 90)
    elements.append(s_label("RELAY_DRV", r3_p1[0], r3_p1[1]))

    # ---- Q1: MMBT2222A NPN relay driver ----
    # Pins: B at (-5.08,0), C at (2.54,5.08), E at (2.54,-5.08)
    components.append(s_comp(
        "Transistor_BJT:MMBT2222A", "Q1", "MMBT2222A",
        "Package_TO_SOT_SMD:SOT-23", Q1x, Q1y, 0,
        ["1", "2", "3"],
        "600mA NPN transistor, relay driver"))
    q1_b = pxy(Q1x, Q1y, -5.08, 0, 0)       # base
    q1_c = pxy(Q1x, Q1y, 2.54, 5.08, 0)      # collector
    q1_e = pxy(Q1x, Q1y, 2.54, -5.08, 0)     # emitter
    # R3.pin2 → Q1.base
    elements.append(s_wire(*r3_p2, *q1_b))
    # Q1.emitter → GND
    elements.append(s_wire(*q1_e, q1_e[0], q1_e[1] + 2.54))
    add_gnd(q1_e[0], q1_e[1] + 2.54)

    # ---- K1: Relay_SPDT ----
    # Pins: A1(-5.08,7.62), A2(-5.08,-7.62), 12(2.54,7.62), 11(5.08,-7.62), 14(7.62,7.62)
    components.append(s_comp(
        "Relay:Relay_SPDT", "K1", "SRD-05VDC-SL-C",
        "Relay_THT:Relay_SPDT_Finder_40.11", K1x, K1y, 0,
        ["A1", "A2", "11", "12", "14"],
        "5V SPDT relay, 10A contacts"))
    k1_a1 = pxy(K1x, K1y, -5.08, 7.62, 0)   # coil+
    k1_a2 = pxy(K1x, K1y, -5.08, -7.62, 0)  # coil-
    k1_12 = pxy(K1x, K1y, 2.54, 7.62, 0)     # NO
    k1_11 = pxy(K1x, K1y, 5.08, -7.62, 0)    # COM
    k1_14 = pxy(K1x, K1y, 7.62, 7.62, 0)     # NC

    # K1.A1 (coil+) → +5V
    elements.append(s_wire(*k1_a1, k1_a1[0], k1_a1[1] - 2.54))
    add_5v(k1_a1[0], k1_a1[1] - 2.54)
    # K1.A2 (coil-) → Q1.collector via COIL_LO net
    elements.append(s_wire(*k1_a2, k1_a2[0], k1_a2[1] + 2.54))
    elements.append(s_label("COIL_LO", k1_a2[0], k1_a2[1] + 2.54, 270))
    elements.append(s_wire(*q1_c, q1_c[0], q1_c[1] - 2.54))
    elements.append(s_label("COIL_LO", q1_c[0], q1_c[1] - 2.54, 90))

    # ---- D2: 1N4148 flyback diode ----
    D2x, D2y = K1x - 4*G, K1y  # left of relay coil
    components.append(s_comp("Device:D", "D2", "1N4148",
        "Diode_SMD:D_SOD-123", D2x, D2y, 270, ["1", "2"],
        "Flyback diode across relay coil"))
    # rot 270: K(1) lib(-3.81,0) → (D2x+0, D2y-3.81); A(2) lib(3.81,0) → (D2x+0, D2y+3.81)
    d2_k = pxy(D2x, D2y, -3.81, 0, 270)   # cathode (top, +5V side)
    d2_a = pxy(D2x, D2y, 3.81, 0, 270)    # anode (bottom, coil- side)
    # D2 cathode → +5V (same as K1.A1)
    elements.append(s_wire(*d2_k, d2_k[0], d2_k[1] - 2.54))
    add_5v(d2_k[0], d2_k[1] - 2.54)
    # D2 anode → COIL_LO
    elements.append(s_wire(*d2_a, d2_a[0], d2_a[1] + 2.54))
    elements.append(s_label("COIL_LO", d2_a[0], d2_a[1] + 2.54, 270))

    # ---- J2: Relay output (3-pin screw terminal) ----
    J2x, J2y = 100*G, K1y
    components.append(s_comp(
        "Connector_Generic:Conn_01x03", "J2", "RELAY_OUT",
        "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
        J2x, J2y, 180, ["1", "2", "3"],
        "Relay output: COM/NO/NC"))
    # rot 180: pin1 lib(-5.08,2.54) → (J2x+5.08, J2y+2.54)
    j2_p1 = pxy(J2x, J2y, -5.08, 2.54, 180)    # COM
    j2_p2 = pxy(J2x, J2y, -5.08, 0, 180)        # NO
    j2_p3 = pxy(J2x, J2y, -5.08, -2.54, 180)    # NC

    # Connect relay switch pins to J2 via labels
    elements.append(s_wire(*k1_11, k1_11[0] + 2.54, k1_11[1]))
    elements.append(s_label("RELAY_COM", k1_11[0] + 2.54, k1_11[1]))
    elements.append(s_wire(*j2_p1, j2_p1[0] + 2.54, j2_p1[1]))
    elements.append(s_label("RELAY_COM", j2_p1[0] + 2.54, j2_p1[1]))

    elements.append(s_wire(*k1_12, k1_12[0] + 2.54, k1_12[1]))
    elements.append(s_label("RELAY_NO", k1_12[0] + 2.54, k1_12[1]))
    elements.append(s_wire(*j2_p2, j2_p2[0] + 2.54, j2_p2[1]))
    elements.append(s_label("RELAY_NO", j2_p2[0] + 2.54, j2_p2[1]))

    elements.append(s_wire(*k1_14, k1_14[0] + 2.54, k1_14[1]))
    elements.append(s_label("RELAY_NC", k1_14[0] + 2.54, k1_14[1]))
    elements.append(s_wire(*j2_p3, j2_p3[0] + 2.54, j2_p3[1]))
    elements.append(s_label("RELAY_NC", j2_p3[0] + 2.54, j2_p3[1]))

    # ---- J3: ICSP header (2x3) ----
    J3x, J3y = 60*G, 67*G
    components.append(s_comp(
        "Connector_Generic:Conn_02x03_Odd_Even", "J3", "ICSP",
        "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical",
        J3x, J3y, 0, ["1", "2", "3", "4", "5", "6"],
        "ICSP programming header"))
    # Pin positions (rot 0):
    # Pin 1 lib(-5.08,2.54): (J3x-5.08, J3y-2.54) = MISO
    # Pin 2 lib(7.62,2.54):  (J3x+7.62, J3y-2.54) = VCC
    # Pin 3 lib(-5.08,0):    (J3x-5.08, J3y)       = SCK
    # Pin 4 lib(7.62,0):     (J3x+7.62, J3y)       = MOSI
    # Pin 5 lib(-5.08,-2.54):(J3x-5.08, J3y+2.54)  = RESET
    # Pin 6 lib(7.62,-2.54): (J3x+7.62, J3y+2.54)  = GND
    j3_pins = {
        1: pxy(J3x, J3y, -5.08, 2.54, 0),
        2: pxy(J3x, J3y, 7.62, 2.54, 0),
        3: pxy(J3x, J3y, -5.08, 0, 0),
        4: pxy(J3x, J3y, 7.62, 0, 0),
        5: pxy(J3x, J3y, -5.08, -2.54, 0),
        6: pxy(J3x, J3y, 7.62, -2.54, 0),
    }
    # ICSP standard pinout: 1=MISO, 2=VCC, 3=SCK, 4=MOSI, 5=RESET, 6=GND
    # Left-side pins go left, right-side pins go right
    elements.append(s_wire(*j3_pins[1], j3_pins[1][0] - 5.08, j3_pins[1][1]))
    elements.append(s_label("MISO", j3_pins[1][0] - 5.08, j3_pins[1][1]))
    elements.append(s_wire(*j3_pins[2], j3_pins[2][0] + 2.54, j3_pins[2][1]))
    add_5v(j3_pins[2][0] + 2.54, j3_pins[2][1])
    elements.append(s_wire(*j3_pins[3], j3_pins[3][0] - 5.08, j3_pins[3][1]))
    elements.append(s_label("SCK", j3_pins[3][0] - 5.08, j3_pins[3][1]))
    elements.append(s_wire(*j3_pins[4], j3_pins[4][0] + 5.08, j3_pins[4][1]))
    elements.append(s_label("MOSI", j3_pins[4][0] + 5.08, j3_pins[4][1]))
    elements.append(s_wire(*j3_pins[5], j3_pins[5][0] - 5.08, j3_pins[5][1]))
    elements.append(s_label("RESET", j3_pins[5][0] - 5.08, j3_pins[5][1]))
    elements.append(s_wire(*j3_pins[6], j3_pins[6][0] + 2.54, j3_pins[6][1]))
    add_gnd(j3_pins[6][0] + 2.54, j3_pins[6][1])

    # ---- J4: SX1278 LoRa/ASK radio module (8-pin header) ----
    # Pin assignment: 1=VCC, 2=GND, 3=MOSI, 4=MISO, 5=SCK, 6=NSS, 7=RST, 8=DIO0
    J4x, J4y = 44*G, 67*G
    components.append(s_comp(
        "Connector_Generic:Conn_01x08", "J4", "SX1278",
        "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
        J4x, J4y, 0, [str(i) for i in range(1, 9)],
        "SX1278 LoRa/ASK radio: VCC/GND/MOSI/MISO/SCK/NSS/RST/DIO0"))
    # Conn_01x08 pins: pin k at lib(-5.08, 7.62 - (k-1)*2.54)
    j4_pins = {k: pxy(J4x, J4y, -5.08, 7.62 - (k-1)*2.54, 0) for k in range(1, 9)}

    # Pin 1: VCC → +5V
    elements.append(s_wire(*j4_pins[1], j4_pins[1][0] - 2.54, j4_pins[1][1]))
    add_5v(j4_pins[1][0] - 2.54, j4_pins[1][1])
    # Pin 2: GND
    elements.append(s_wire(*j4_pins[2], j4_pins[2][0] - 2.54, j4_pins[2][1]))
    add_gnd(j4_pins[2][0] - 2.54, j4_pins[2][1])
    # Pin 3: MOSI (shared SPI bus with ICSP)
    elements.append(s_wire(*j4_pins[3], j4_pins[3][0] - 5.08, j4_pins[3][1]))
    elements.append(s_label("MOSI", j4_pins[3][0] - 5.08, j4_pins[3][1]))
    # Pin 4: MISO
    elements.append(s_wire(*j4_pins[4], j4_pins[4][0] - 5.08, j4_pins[4][1]))
    elements.append(s_label("MISO", j4_pins[4][0] - 5.08, j4_pins[4][1]))
    # Pin 5: SCK
    elements.append(s_wire(*j4_pins[5], j4_pins[5][0] - 5.08, j4_pins[5][1]))
    elements.append(s_label("SCK", j4_pins[5][0] - 5.08, j4_pins[5][1]))
    # Pin 6: NSS (chip select, active low)
    elements.append(s_wire(*j4_pins[6], j4_pins[6][0] - 5.08, j4_pins[6][1]))
    elements.append(s_label("SX1278_NSS", j4_pins[6][0] - 5.08, j4_pins[6][1]))
    # Pin 7: RESET
    elements.append(s_wire(*j4_pins[7], j4_pins[7][0] - 5.08, j4_pins[7][1]))
    elements.append(s_label("SX1278_RST", j4_pins[7][0] - 5.08, j4_pins[7][1]))
    # Pin 8: DIO0 (interrupt)
    elements.append(s_wire(*j4_pins[8], j4_pins[8][0] - 5.08, j4_pins[8][1]))
    elements.append(s_label("RADIO_IRQ", j4_pins[8][0] - 5.08, j4_pins[8][1]))

    # ---- J5: 1.54" E-Paper display (optional, 8-pin header) ----
    # Pin assignment: 1=VCC, 2=GND, 3=MOSI, 4=SCK, 5=EPD_CS, 6=EPD_DC, 7=EPD_RST, 8=EPD_BUSY
    J5x, J5y = 28*G, 67*G
    components.append(s_comp(
        "Connector_Generic:Conn_01x08", "J5", "E-PAPER",
        "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical",
        J5x, J5y, 0, [str(i) for i in range(1, 9)],
        "1.54in e-paper display: VCC/GND/MOSI/SCK/CS/DC/RST/BUSY"))
    j5_pins = {k: pxy(J5x, J5y, -5.08, 7.62 - (k-1)*2.54, 0) for k in range(1, 9)}

    # Pin 1: VCC → +5V
    elements.append(s_wire(*j5_pins[1], j5_pins[1][0] - 2.54, j5_pins[1][1]))
    add_5v(j5_pins[1][0] - 2.54, j5_pins[1][1])
    # Pin 2: GND
    elements.append(s_wire(*j5_pins[2], j5_pins[2][0] - 2.54, j5_pins[2][1]))
    add_gnd(j5_pins[2][0] - 2.54, j5_pins[2][1])
    # Pin 3: MOSI (shared SPI bus)
    elements.append(s_wire(*j5_pins[3], j5_pins[3][0] - 5.08, j5_pins[3][1]))
    elements.append(s_label("MOSI", j5_pins[3][0] - 5.08, j5_pins[3][1]))
    # Pin 4: SCK (shared SPI bus)
    elements.append(s_wire(*j5_pins[4], j5_pins[4][0] - 5.08, j5_pins[4][1]))
    elements.append(s_label("SCK", j5_pins[4][0] - 5.08, j5_pins[4][1]))
    # Pin 5: EPD_CS (chip select)
    elements.append(s_wire(*j5_pins[5], j5_pins[5][0] - 5.08, j5_pins[5][1]))
    elements.append(s_label("EPD_CS", j5_pins[5][0] - 5.08, j5_pins[5][1]))
    # Pin 6: EPD_DC (data/command)
    elements.append(s_wire(*j5_pins[6], j5_pins[6][0] - 5.08, j5_pins[6][1]))
    elements.append(s_label("EPD_DC", j5_pins[6][0] - 5.08, j5_pins[6][1]))
    # Pin 7: EPD_RST (reset)
    elements.append(s_wire(*j5_pins[7], j5_pins[7][0] - 5.08, j5_pins[7][1]))
    elements.append(s_label("EPD_RST", j5_pins[7][0] - 5.08, j5_pins[7][1]))
    # Pin 8: EPD_BUSY (busy signal, input)
    elements.append(s_wire(*j5_pins[8], j5_pins[8][0] - 5.08, j5_pins[8][1]))
    elements.append(s_label("EPD_BUSY", j5_pins[8][0] - 5.08, j5_pins[8][1]))

    # ---- RT1 + R6: NTC thermistor voltage divider (TEMP_SENSE on ADC6) ----
    # +5V → R6 (10k) → junction → RT1 (NTC 10k) → GND
    R6x, R6y = 16*G, 50*G
    components.append(s_comp("Device:R", "R6", "10k",
        "Resistor_SMD:R_0805_2012Metric", R6x, R6y, 0, ["1", "2"],
        "Temp sensor pullup"))
    r6_p1 = pxy(R6x, R6y, 0, 3.81, 0)   # top → +5V
    r6_p2 = pxy(R6x, R6y, 0, -3.81, 0)  # bottom → junction
    elements.append(s_wire(*r6_p1, r6_p1[0], r6_p1[1] - 2.54))
    add_5v(r6_p1[0], r6_p1[1] - 2.54)

    RT1x, RT1y = 16*G, 53*G
    components.append(s_comp("Device:Thermistor_NTC", "TH1", "NTC 10k",
        "Resistor_SMD:R_0805_2012Metric", RT1x, RT1y, 0, ["1", "2"],
        "NTC thermistor, tamper/ambient temp"))
    rt1_p1 = pxy(RT1x, RT1y, 0, 3.81, 0)   # top → junction (matches r6_p2)
    rt1_p2 = pxy(RT1x, RT1y, 0, -3.81, 0)  # bottom → GND
    elements.append(s_wire(*rt1_p2, rt1_p2[0], rt1_p2[1] + 2.54))
    add_gnd(rt1_p2[0], rt1_p2[1] + 2.54)
    # Junction label at R6.pin2 = RT1.pin1
    elements.append(s_label("TEMP_SENSE", r6_p2[0] - 5.08, r6_p2[1], 180))
    elements.append(s_wire(*r6_p2, r6_p2[0] - 5.08, r6_p2[1]))

    # ---- R_LDR + R7: Photoresistor voltage divider (LIGHT_SENSE on ADC7) ----
    # +5V → R7 (10k) → junction → LDR → GND
    R7x, R7y = 20*G, 50*G
    components.append(s_comp("Device:R", "R7", "10k",
        "Resistor_SMD:R_0805_2012Metric", R7x, R7y, 0, ["1", "2"],
        "Light sensor pullup"))
    r7_p1 = pxy(R7x, R7y, 0, 3.81, 0)   # top → +5V
    r7_p2 = pxy(R7x, R7y, 0, -3.81, 0)  # bottom → junction
    elements.append(s_wire(*r7_p1, r7_p1[0], r7_p1[1] - 2.54))
    add_5v(r7_p1[0], r7_p1[1] - 2.54)

    LDRx, LDRy = 20*G, 53*G
    components.append(s_comp("Device:R_Photo", "R8", "LDR",
        "Resistor_SMD:R_0805_2012Metric", LDRx, LDRy, 0, ["1", "2"],
        "Photoresistor, light/tamper detect"))
    ldr_p1 = pxy(LDRx, LDRy, 0, 3.81, 0)   # top → junction
    ldr_p2 = pxy(LDRx, LDRy, 0, -3.81, 0)  # bottom → GND
    elements.append(s_wire(*ldr_p2, ldr_p2[0], ldr_p2[1] + 2.54))
    add_gnd(ldr_p2[0], ldr_p2[1] + 2.54)
    # Junction label
    elements.append(s_label("LIGHT_SENSE", r7_p2[0] - 5.08, r7_p2[1], 180))
    elements.append(s_wire(*r7_p2, r7_p2[0] - 5.08, r7_p2[1]))

    # ---- J6: Zone inputs for NO/NC contact sensors (7-pin header) ----
    # Pin assignment: 1=+5V, 2=GND, 3=ZONE1, 4=ZONE2, 5=ZONE3, 6=ZONE4, 7=ZONE5
    # Each zone uses MCU internal pullup. Sensor wires between ZONEx and GND.
    J6x, J6y = 100*G, 60*G
    components.append(s_comp(
        "Connector_Generic:Conn_01x07", "J6", "ZONES",
        "Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical",
        J6x, J6y, 180, [str(i) for i in range(1, 8)],
        "Zone inputs: +5V/GND/ZONE1-5 for NO/NC contact sensors"))
    # Conn_01x07 rot 180: pin k at pxy(J6x, J6y, -5.08, 7.62-(k-1)*2.54, 180)
    j6_pins = {k: pxy(J6x, J6y, -5.08, 7.62 - (k-1)*2.54, 180) for k in range(1, 8)}

    # Pin 1: +5V (for sensors that need power)
    elements.append(s_wire(*j6_pins[1], j6_pins[1][0] + 2.54, j6_pins[1][1]))
    add_5v(j6_pins[1][0] + 2.54, j6_pins[1][1])
    # Pin 2: GND (sensor return)
    elements.append(s_wire(*j6_pins[2], j6_pins[2][0] + 2.54, j6_pins[2][1]))
    add_gnd(j6_pins[2][0] + 2.54, j6_pins[2][1])
    # Pins 3-7: ZONE1-ZONE5 via net labels
    for i, zone in enumerate(["ZONE1", "ZONE2", "ZONE3", "ZONE4", "ZONE5"], start=3):
        elements.append(s_wire(*j6_pins[i], j6_pins[i][0] + 5.08, j6_pins[i][1]))
        elements.append(s_label(zone, j6_pins[i][0] + 5.08, j6_pins[i][1]))

    # ---- SW1: Learn button (active low, internal pullup) ----
    # Pins: 1 at (-5.08,0), 2 at (5.08,0)
    SW1x, SW1y = 78*G, u1_pb0[1]
    components.append(s_comp(
        "Switch:SW_Push", "SW1", "LEARN",
        "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92", SW1x, SW1y, 0,
        ["1", "2"],
        "Learn/pair button"))
    sw1_p1 = pxy(SW1x, SW1y, -5.08, 0, 0)
    sw1_p2 = pxy(SW1x, SW1y, 5.08, 0, 0)
    elements.append(s_label("LEARN", sw1_p1[0] - 2.54, sw1_p1[1]))
    elements.append(s_wire(*sw1_p1, sw1_p1[0] - 2.54, sw1_p1[1]))
    elements.append(s_wire(*sw1_p2, sw1_p2[0] + 2.54, sw1_p2[1]))
    add_gnd(sw1_p2[0] + 2.54, sw1_p2[1])

    # ---- J8: GPS receiver module (optional, 4-pin header) ----
    # Shares PD0 (RXD/ZONE3) and PD1 (TXD/ZONE4) — firmware selects GPS or zone input
    # Pin assignment: 1=VCC, 2=GND, 3=GPS_TX→MCU_RX(PD0), 4=GPS_RX←MCU_TX(PD1)
    J8x, J8y = 12*G, 67*G
    components.append(s_comp(
        "Connector_Generic:Conn_01x04", "J8", "GPS",
        "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        J8x, J8y, 0, [str(i) for i in range(1, 5)],
        "GPS receiver: VCC/GND/TX/RX (shares PD0,PD1 with zones)"))
    # Conn_01x04 pins: pin k at lib(-5.08, 2.54 - (k-1)*2.54)
    j8_pins = {k: pxy(J8x, J8y, -5.08, 2.54 - (k-1)*2.54, 0) for k in range(1, 5)}
    # Pin 1: VCC → +5V
    elements.append(s_wire(*j8_pins[1], j8_pins[1][0] - 2.54, j8_pins[1][1]))
    add_5v(j8_pins[1][0] - 2.54, j8_pins[1][1])
    # Pin 2: GND
    elements.append(s_wire(*j8_pins[2], j8_pins[2][0] - 2.54, j8_pins[2][1]))
    add_gnd(j8_pins[2][0] - 2.54, j8_pins[2][1])
    # Pin 3: GPS TX → MCU RX (PD0 = ZONE3)
    elements.append(s_wire(*j8_pins[3], j8_pins[3][0] - 5.08, j8_pins[3][1]))
    elements.append(s_label("ZONE3", j8_pins[3][0] - 5.08, j8_pins[3][1]))
    # Pin 4: GPS RX ← MCU TX (PD1 = ZONE4)
    elements.append(s_wire(*j8_pins[4], j8_pins[4][0] - 5.08, j8_pins[4][1]))
    elements.append(s_label("ZONE4", j8_pins[4][0] - 5.08, j8_pins[4][1]))

    # ---- Battery / USB Charger Circuit ----
    # USB Micro-B → MCP73831 → LiPo → Schottky diode-OR to +5V rail
    # When 12V present: system runs from LDO (5V), battery charges from USB
    # When 12V absent: battery powers system through Schottky (~3.4V), low-power mode

    # J7: USB Micro-B charging input
    J7x, J7y = 4*G, 40*G
    components.append(s_comp(
        "Connector:USB_B_Micro", "J7", "USB_CHG",
        "Connector_USB:USB_Micro-B_Molex-105017-0001", J7x, J7y, 0,
        ["1", "2", "3", "4", "5", "6"],
        "USB Micro-B charging input"))
    # Pin endpoints (rot 0):
    j7_vbus   = pxy(J7x, J7y, 7.62, 5.08, 0)      # pin1 VBUS (7*G, 38*G)
    j7_dminus = pxy(J7x, J7y, 7.62, -2.54, 0)      # pin2 D-   (7*G, 41*G)
    j7_dplus  = pxy(J7x, J7y, 7.62, 0, 0)           # pin3 D+   (7*G, 40*G)
    j7_id     = pxy(J7x, J7y, 7.62, -5.08, 0)       # pin4 ID   (7*G, 42*G)
    j7_gnd    = pxy(J7x, J7y, 0, -10.16, 0)          # pin5 GND  (4*G, 44*G)
    j7_shield = pxy(J7x, J7y, -2.54, -10.16, 0)     # pin6 Shld (3*G, 44*G)
    # VBUS → wire to U3.VDD
    elements.append(s_wire(*j7_vbus, 12*G, j7_vbus[1]))
    elements.append(s_wire(12*G, j7_vbus[1], 12*G, 39*G))
    # D+, D-, ID → NC (charge only, no data)
    elements.append(s_nc(*j7_dplus))
    elements.append(s_nc(*j7_dminus))
    elements.append(s_nc(*j7_id))
    # GND
    elements.append(s_wire(*j7_gnd, j7_gnd[0], j7_gnd[1] + 2.54))
    add_gnd(j7_gnd[0], j7_gnd[1] + 2.54)
    # Shield → GND (short wire to GND pin)
    elements.append(s_wire(*j7_shield, *j7_gnd))
    elements.append(s_junction(*j7_gnd))

    # U3: MCP73831-2-OT LiPo charge controller
    U3x, U3y = 12*G, 42*G
    components.append(s_comp(
        "Battery_Management:MCP73831-2-OT", "U3", "MCP73831",
        "Package_TO_SOT_SMD:SOT-23-5", U3x, U3y, 0,
        ["1", "2", "3", "4", "5"],
        "500mA LiPo charge controller"))
    u3_stat = pxy(U3x, U3y, 10.16, -2.54, 0)  # pin1 STAT (16*G, 43*G)
    u3_vss  = pxy(U3x, U3y, 0, -7.62, 0)      # pin2 VSS  (12*G, 45*G)
    u3_vbat = pxy(U3x, U3y, 10.16, 2.54, 0)   # pin3 VBAT (16*G, 41*G)
    u3_vdd  = pxy(U3x, U3y, 0, 7.62, 0)       # pin4 VDD  (12*G, 39*G)
    u3_prog = pxy(U3x, U3y, -10.16, -2.54, 0) # pin5 PROG (8*G, 43*G)
    # VDD ← already wired from J7.VBUS above
    # VSS → GND
    elements.append(s_wire(*u3_vss, u3_vss[0], u3_vss[1] + 2.54))
    add_gnd(u3_vss[0], u3_vss[1] + 2.54)
    # VBAT → wire right + label
    elements.append(s_wire(*u3_vbat, u3_vbat[0] + 5.08, u3_vbat[1]))
    elements.append(s_label("VBAT", u3_vbat[0] + 5.08, u3_vbat[1]))
    # STAT → NC (charge LED not needed for IP67 enclosure)
    elements.append(s_nc(*u3_stat))
    # PROG → R9 (2kΩ to GND, sets 500mA charge current)

    # R9: 2kΩ charge current programming resistor
    R9x, R9y = 8*G, 44.5*G   # center off-grid, but pin endpoints on grid
    components.append(s_comp("Device:R", "R9", "2k",
        "Resistor_SMD:R_0805_2012Metric", R9x, R9y, 0, ["1", "2"],
        "MCP73831 charge current = 1000/R9 = 500mA"))
    r9_p1 = pxy(R9x, R9y, 0, 3.81, 0)   # top (8*G, 43*G) → U3.PROG
    r9_p2 = pxy(R9x, R9y, 0, -3.81, 0)  # bottom (8*G, 46*G) → GND
    # R9 pin1 directly at U3.PROG — no wire needed (same point)
    elements.append(s_wire(*r9_p2, r9_p2[0], r9_p2[1] + 2.54))
    add_gnd(r9_p2[0], r9_p2[1] + 2.54)

    # C6: 4.7µF VBAT decoupling (MCP73831 datasheet requirement)
    C6x, C6y = 18*G, 42.5*G
    components.append(s_comp("Device:C", "C6", "4.7uF",
        "Capacitor_SMD:C_0805_2012Metric", C6x, C6y, 0, ["1", "2"],
        "VBAT decoupling"))
    c6_p1 = pxy(C6x, C6y, 0, 3.81, 0)   # top (18*G, 41*G) → VBAT
    c6_p2 = pxy(C6x, C6y, 0, -3.81, 0)  # bottom (18*G, 44*G) → GND
    elements.append(s_label("VBAT", c6_p1[0], c6_p1[1]))
    elements.append(s_wire(*c6_p2, c6_p2[0], c6_p2[1] + 2.54))
    add_gnd(c6_p2[0], c6_p2[1] + 2.54)

    # BT1: LiPo battery cell (3.7V nominal)
    # Battery_Cell pins: +(0,5.08)→top, -(0,-2.54)→bottom
    BT1x, BT1y = 2*G, 52*G
    components.append(s_comp("Device:Battery_Cell", "BT1", "LiPo 3.7V",
        "Battery:BatteryHolder_Keystone_1042_1x18650", BT1x, BT1y, 0,
        ["1", "2"],
        "LiPo battery cell, 500-1000mAh"))
    bt1_plus  = pxy(BT1x, BT1y, 0, 5.08, 0)   # + (2*G, 50*G)
    bt1_minus = pxy(BT1x, BT1y, 0, -2.54, 0)  # - (2*G, 53*G)
    # BT+ → label VBAT
    elements.append(s_wire(*bt1_plus, bt1_plus[0], bt1_plus[1] - 2.54))
    elements.append(s_label("VBAT", bt1_plus[0], bt1_plus[1] - 2.54, 90))
    # BT- → GND
    elements.append(s_wire(*bt1_minus, bt1_minus[0], bt1_minus[1] + 2.54))
    add_gnd(bt1_minus[0], bt1_minus[1] + 2.54)

    # D3: Schottky diode — battery power path to +5V rail
    # Anode (battery/VBAT) → Cathode (+5V rail)
    # When 12V present: LDO at 5V, Schottky reverse-biased (3.7V < 5V)
    # When 12V absent: battery feeds system through Schottky (~3.4V)
    D3x, D3y = 22*G, 42.5*G
    components.append(s_comp("Device:D_Schottky", "D3", "BAT54",
        "Diode_SMD:D_SOD-123", D3x, D3y, 90, ["1", "2"],
        "Battery power path Schottky diode"))
    # D_Schottky pins: K(-3.81,0), A(3.81,0)
    # rot 90: pxy = (sx-py, sy-px)
    d3_k = pxy(D3x, D3y, -3.81, 0, 90)  # cathode (22*G, 44*G) → +5V
    d3_a = pxy(D3x, D3y, 3.81, 0, 90)   # anode (22*G, 41*G) → VBAT
    elements.append(s_label("VBAT", d3_a[0], d3_a[1]))
    elements.append(s_wire(*d3_k, d3_k[0], d3_k[1] + 2.54))
    add_5v(d3_k[0], d3_k[1] + 2.54)

    # ============================================================
    # Extract lib_symbols
    # ============================================================
    print("Extracting symbols from KiCad libraries...")

    sym_list = [
        ("MCU_Microchip_ATmega.kicad_sym", "ATmega328P-A", "MCU_Microchip_ATmega"),
        ("Regulator_Linear.kicad_sym", "AMS1117-5.0", "Regulator_Linear"),
        ("Transistor_BJT.kicad_sym", "MMBT2222A", "Transistor_BJT"),
        ("Relay.kicad_sym", "Relay_SPDT", "Relay"),
        ("Device.kicad_sym", "R", "Device"),
        ("Device.kicad_sym", "C", "Device"),
        ("Device.kicad_sym", "LED", "Device"),
        ("Device.kicad_sym", "D", "Device"),
        ("Device.kicad_sym", "D_Zener", "Device"),
        ("Device.kicad_sym", "Buzzer", "Device"),
        ("Switch.kicad_sym", "SW_Push", "Switch"),
        ("Connector_Generic.kicad_sym", "Conn_01x02", "Connector_Generic"),
        ("Connector_Generic.kicad_sym", "Conn_01x03", "Connector_Generic"),
        ("Connector_Generic.kicad_sym", "Conn_01x08", "Connector_Generic"),
        ("Connector_Generic.kicad_sym", "Conn_02x03_Odd_Even", "Connector_Generic"),
        ("Device.kicad_sym", "Thermistor_NTC", "Device"),
        ("Device.kicad_sym", "R_Photo", "Device"),
        ("Device.kicad_sym", "D_Schottky", "Device"),
        ("Device.kicad_sym", "Battery_Cell", "Device"),
        ("Battery_Management.kicad_sym", "MCP73831-2-OT", "Battery_Management"),
        ("Connector.kicad_sym", "USB_B_Micro", "Connector"),
        ("Connector_Generic.kicad_sym", "Conn_01x04", "Connector_Generic"),
        ("Connector_Generic.kicad_sym", "Conn_01x07", "Connector_Generic"),
        ("power.kicad_sym", "+5V", "power"),
        ("power.kicad_sym", "GND", "power"),
        ("power.kicad_sym", "+12V", "power"),
        ("power.kicad_sym", "PWR_FLAG", "power"),
    ]

    lib_symbols_text = ""
    for lib_file, name, prefix in sym_list:
        print(f"  {prefix}:{name}")
        sym = flatten(lib_file, name)
        full = f"{prefix}:{name}"
        sym = sym.replace(f'(symbol "{name}"', f'(symbol "{full}"', 1)
        # Add proper indentation
        lines = sym.strip().split('\n')
        indented = '\n'.join('\t\t' + line for line in lines)
        lib_symbols_text += indented + '\n'

    # ============================================================
    # Assemble schematic
    # ============================================================
    sch = f"""(kicad_sch
\t(version 20231120)
\t(generator "motokey-gen")
\t(generator_version "9.0")
\t(uuid "{ROOT}")
\t(paper "A3")
\t(title_block
\t\t(title "MotoKey Lock Box - KeeLoq Receiver")
\t\t(comment 1 "ATmega328P + 433MHz KeeLoq + SPDT Relay Kill Switch")
\t\t(comment 2 "12V input, 5V regulated, fail-secure design")
\t)
\t(lib_symbols
{lib_symbols_text}\t)
{chr(10).join(elements)}
{chr(10).join(components)}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
)
"""
    # Replace ROOT placeholder
    sch = sch.replace("/ROOT_UUID", f"/{ROOT}")
    sch = sch.replace("ROOT_UUID", ROOT)

    out_sch = os.path.join(HERE, "motokey-lockbox.kicad_sch")
    with open(out_sch, 'w') as f:
        f.write(sch)
    print(f"\nSchematic written to {out_sch}")

    # ============================================================
    # Generate project file
    # ============================================================
    pro = """{
  "board": {
    "3dviewports": [],
    "ipc2581": { "dist": "", "distpn": "", "internal_id": "", "mfg": "", "mpn": "" },
    "layer_pairs": [],
    "layer_presets": [],
    "viewports": []
  },
  "boards": [],
  "cvpcb": { "equivalence_files": [] },
  "libraries": { "pinned_footprint_libs": [], "pinned_symbol_libs": [] },
  "meta": { "filename": "motokey-lockbox.kicad_pro", "version": 3 },
  "net_settings": {
    "classes": [
      {
        "bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647,
        "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.25,
        "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6
      }
    ],
    "meta": { "version": 4 },
    "net_colors": null, "netclass_assignments": null, "netclass_patterns": []
  },
  "pcbnew": {
    "last_paths": {
      "gencad": "", "idf": "", "netlist": "", "plot": "",
      "pos_files": "", "specctra_dsn": "", "step": "", "svg": "", "vrml": ""
    },
    "page_layout_descr_file": ""
  },
  "schematic": {
    "annotate_start_num": 0,
    "drawing": {
      "dashed_lines_dash_length_ratio": 12.0,
      "dashed_lines_gap_length_ratio": 3.0,
      "default_line_thickness": 6.0,
      "default_text_size": 50.0,
      "field_names": [],
      "intersheets_ref_own_page": false, "intersheets_ref_prefix": "",
      "intersheets_ref_short": false, "intersheets_ref_show": false,
      "intersheets_ref_suffix": "",
      "junction_size_choice": 3, "label_size_ratio": 0.375,
      "pin_symbol_size": 25.0, "text_offset_ratio": 0.15
    },
    "legacy_lib_dir": "", "legacy_lib_list": [],
    "meta": { "version": 1 },
    "net_format_name": "", "page_layout_descr_file": "", "plot_directory": "",
    "spice_current_sheet_as_root": false,
    "spice_external_command": "spice \\"%I\\"",
    "spice_model_current_sheet_as_root": true,
    "subpart_first_id": 65, "subpart_id_separator": 0
  },
  "sheets": [],
  "text_variables": {}
}
"""
    out_pro = os.path.join(HERE, "motokey-lockbox.kicad_pro")
    with open(out_pro, 'w') as f:
        f.write(pro)
    print(f"Project written to {out_pro}")

if __name__ == "__main__":
    generate()
