# MotoKey — Claude Context

**Domain:** kindro.store (hosted as subpage)
**GitHub:** github.com/yuluis/motokey (private)

---

## What It Does

Aftermarket encrypted keycard kill switch for electric motorcycles/scooters/e-bikes. A weatherproof lock box wires inline with the battery and cuts power unless a paired key fob is nearby. Relay defaults to open (locked) — no key, no power, bike does not move. AES-128 rolling codes prevent replay attacks.

Two SKUs:
| Product | Price | Key Differences |
|---------|-------|-----------------|
| MotoKey Basic | $89 | AES-128, single relay, CR2032 fob, 30ft range, 2 fobs |
| MotoKey Enhanced | $149 | AES-256, dual relay + tamper alert, USB-C fob, 50ft range, 3 fobs |

---

## Status

**Concept / prototype phase.** Website and business plan complete. Hardware design (KiCad schematic + PCB + 3D enclosure) complete. No physical prototype built yet — next steps are on Julio (breadboard prototype, then PCB production).

---

## Origin

Built in a single AI-assisted session by Luis and Julio on 2026-02-21. Went from idea to live website to full hardware design in one sitting. The `hardware/` directory was expanded in a later session (2026-03-09 to 2026-03-13) with KiCad schematic/PCB generation scripts, an OpenSCAD enclosure, and a system design document.

---

## Architecture

**No backend.** Static HTML + CSS + JS storefront. No framework, no build step, no database.

| File | Purpose |
|------|---------|
| `index.html` | Product storefront (hero, products, how-it-works, security, FAQ) |
| `style.css` | Dark-theme storefront styles |
| `app.js` | Cart UI + FAQ accordion (demo only, no real checkout) |
| `hardware-design.html` | Hardware architecture document (components, BOM, security protocol) |

The cart is a demo — "Add to Cart" works visually but there is no payment integration. The cart note says "This is a demo storefront for learning purposes."

---

## Hardware Design (`hardware/`)

KiCad project + supporting files for the lock box PCB and enclosure.

| File | Description |
|------|-------------|
| `motokey-lockbox.kicad_sch` | Full schematic (ATmega328P, relay driver, RF, power) |
| `motokey-lockbox.kicad_pcb` | PCB layout (95x60mm, 2-layer FR4) |
| `motokey-lockbox.kicad_pro` | KiCad project file |
| `motokey-lockbox.pdf` | Schematic PDF export |
| `gen_schematic.py` | Python script to generate KiCad schematic programmatically |
| `gen_pcb.py` | Python script to generate KiCad PCB layout |
| `enclosure.scad` | OpenSCAD 3D-printable enclosure (ABS, IP65) |
| `enclosure.stl` | Exported STL mesh (1.9 MB) |
| `enclosure-design.html` | Interactive enclosure design document |
| `system-design.html` | System design doc (KeeLoq fob + buzzer phase 1, LoRa phase 2) |

### Key Components (Lock Box)

| Component | Part | Role |
|-----------|------|------|
| MCU | ATmega328P-AU (TQFP-32) | Main controller |
| RF Receiver | SYN480R 433MHz | Receives fob signals |
| Relay | JQX-62F 80A (normally open) | Power cut switch |
| Voltage Reg | LM2596 buck converter | 48-72V battery to 5V logic |
| EEPROM | AT24C256 | Stores up to 8 paired key records |
| Relay Driver | 2N2222A + 1N4007 flyback | Drives relay coil |

### Key Fob

ATtiny85 + SYN115 433MHz TX + CR2032 coin cell. Press button, MCU wakes from sleep, encrypts (counter + device ID) with shared AES key, transmits 16-byte packet, sleeps. ~50ms active time, ~18 month battery life.

### Security Protocol

- **Pairing:** One-time physical key exchange (NFC/wired). Lock box generates random 128-bit key. Both devices store shared secret + set counter to 0.
- **Unlock:** Fob increments counter, encrypts (counter + fob ID), transmits. Lock box decrypts, verifies fob ID, checks counter > last seen. Valid = close relay. Auto-locks after 30 seconds out of range.
- **Replay protection:** Rolling counter. Old codes rejected.

---

## Economics

| | Basic ($89) | Enhanced ($149) |
|---|---|---|
| BOM + materials | $18.34 | $31.10 |
| Assembly + QC | $5.00 | $8.25 |
| **Total COGS** | **$23.34** | **$39.35** |
| **Gross margin** | **73.8%** | **73.6%** |

At 10 hand-built units (~$30 COGS each), Basic still clears $59/unit.

---

## Deployment

Hosted on the VPS as part of kindro.store. Static files served by nginx.

| Component | Location |
|-----------|----------|
| Source | /srv/motokey/ |
| Nginx | Part of kindro.store config |

```bash
# Deploy
ssh root@159.223.206.160 "cd /srv/motokey && git pull origin main"
```

No build step needed — all static files.

---

## Development

No local dev server needed. Open `index.html` in a browser.

```bash
open index.html                  # Storefront
open hardware-design.html        # Hardware architecture doc
open hardware/system-design.html # System design doc
open hardware/enclosure-design.html # 3D enclosure doc
```

KiCad files require KiCad 8+ to open. The `gen_schematic.py` and `gen_pcb.py` scripts require KiCad's bundled Python (`/Applications/KiCad.app/.../python3`).

---

## Next Steps (Julio's Responsibility)

1. **Breadboard prototype** — Arduino Nano + relay + ATtiny85 fob, basic TX/RX (~$35)
2. **Add encryption** — AES-128 library (`tiny-AES-c`), rolling counter, replay rejection
3. **Pairing + polish** — Pair button, LED states, EEPROM storage, auto-lock timeout
4. **Enclosure + real test** — Perfboard in ABS box, test with actual e-moto
5. **First production run** — Custom PCBs from JLCPCB, assemble 10 units
6. **Payment integration** — Add Stripe or PayPal to the storefront

---

**Last Updated**: 2026-03-15
