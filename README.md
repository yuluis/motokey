# MotoKey — Aftermarket E-Moto Security System

Encrypted keycard lock for electric motorcycles. Cut the power, pocket the key.

**Live site:** https://kindro.store
**Hardware design:** https://kindro.store/hardware-design.html

---

## What Is This

MotoKey is an aftermarket security system for electric mopeds/motorcycles/scooters. It's a small weatherproof box that wires inline with the battery and cuts power unless an encrypted key fob is nearby. No key = no power = bike doesn't move.

Every kit ships with:
- 1 lock box (mounts on bike, inline with battery)
- 2 encrypted key fobs (pocket/keychain sized)
- Mounting kit (bracket, zip ties, adhesive, wire terminals, heat shrink)
- Instruction card with QR link to install video

Two products:
| Product | Price | Key Difference |
|---------|-------|----------------|
| **MotoKey Basic** | $89 | AES-128, single relay, CR2032 fob, 30ft range |
| **MotoKey Enhanced** | $149 | AES-256, dual relay + tamper alert, USB-C fob, 50ft range, 3 fobs |

---

## Origin

This project started as a learning exercise between Luis and Julio on 2026-02-21. The goal: use AI (Claude) to go from idea to live website to hardware design in a single session.

**The conversation:**
- Julio builds aftermarket e-motos and wanted a keycard security system to sell
- Start with two versions: a basic remote and an enhanced remote
- Key fobs should be small (keychain/pocket dongle)
- The lock box connects to the battery with a simple power-cut circuit
- Must be weatherproof (outdoor bike use)
- Programming between keycard and hardware must be secured to prevent hacking
- Comes with 2 keys and a mounting kit

**What got built in this session:**
1. Product storefront website (static HTML/CSS/JS)
2. Full hardware architecture with real component selection
3. Security protocol design (AES-128 rolling codes, challenge-response)
4. Bill of materials with per-unit costs
5. Margin analysis proving profitability at $89/$149
6. Pushed to GitHub, deployed to production at kindro.store

---

## How It Works

### The Lock Box

Wires inline with the bike's main battery positive cable. Contains:
- **ATmega328P** microcontroller (same chip as Arduino)
- **SYN480R** 433MHz RF receiver
- **JQX-62F** 80A automotive relay (normally OPEN = locked)
- **LM2596** buck converter (48-72V battery → 5V logic)
- **AT24C256** EEPROM (stores up to 8 paired key records)
- Status LED + recessed pair button

The relay defaults to **open** (no power). When a valid key fob signal is received, the relay closes and power flows. When the key fob is out of range for 30 seconds, the relay opens and the bike is locked.

Cutting the wires doesn't help — the relay is normally open, so cutting anything just keeps the bike dead.

### The Key Fob

Small enough for a keychain. Contains:
- **ATtiny85** microcontroller (1.8μA sleep current)
- **SYN115** 433MHz RF transmitter
- **CR2032** coin cell battery (~18 month life)
- Single button

Press the button → MCU wakes from sleep → encrypts (counter + device ID) with the shared AES key → transmits 16-byte packet → goes back to sleep. Total active time: ~50ms.

### Security Protocol

**Pairing (one-time):**
1. Press PAIR button on lock box (LED blinks fast)
2. Press button on key fob
3. Lock box generates random 128-bit key
4. Key transfers to fob via physical contact (NFC/wired — can't intercept from distance)
5. Both devices store shared secret + set counter to 0

**Unlock (every use):**
1. Fob increments counter, encrypts (counter + fob ID) with shared key
2. Transmits encrypted packet over 433MHz
3. Lock box decrypts, verifies fob ID, checks counter > last seen
4. If valid: close relay (power on), start 30-sec timeout

**Why it's secure:**
- **Replay attack** → Fails. Counter already advanced. Old codes rejected.
- **Brute force** → AES-128 = 3.4×10³⁸ possible keys. Would take 10²² years at 1 billion attempts/sec.
- **Signal capture** → Every packet looks like random noise. No patterns.
- **Physical tamper** → Electronics potted in epoxy. Cracking the box destroys the circuits.
- **Wire bypass** → Relay is normally open. Cutting wires = bike stays dead.

---

## Economics

### Bill of Materials (at 100 units)

**Lock Box:** $10.80
| Component | Part | Cost |
|-----------|------|------|
| MCU | ATmega328P-AU | $1.40 |
| RF Receiver | SYN480R 433MHz | $0.50 |
| Relay | JQX-62F 80A | $2.80 |
| Relay Driver | 2N2222A + 1N4007 | $0.10 |
| Voltage Reg | LM2596 buck module | $0.80 |
| EEPROM | AT24C256 | $0.25 |
| Crystal | 16MHz + caps | $0.15 |
| LED + Button | Bicolor + tactile | $0.18 |
| Screw Terminals | 5mm pitch x2 | $0.30 |
| Wire Leads | 10AWG silicone x2 | $0.60 |
| Antenna | 17cm wire | $0.02 |
| PCB | 2-layer 50x40mm (JLCPCB) | $0.80 |
| Enclosure | ABS IP65 80x60x30mm | $1.80 |
| Cable Glands | PG7 nylon x2 | $0.20 |
| Potting | Urethane 2-part ~30ml | $0.50 |
| Misc | Caps, resistors, header | $0.40 |

**Key Fob (x1):** $2.37
| Component | Part | Cost |
|-----------|------|------|
| MCU | ATtiny85-20SU | $0.65 |
| RF Transmitter | SYN115 433MHz | $0.35 |
| Battery Holder | CR2032 SMD | $0.12 |
| Battery | CR2032 | $0.20 |
| Button | Tactile SMD 4x4mm | $0.05 |
| PCB | 2-layer 35x20mm | $0.40 |
| Enclosure | ABS fob case + keyring | $0.45 |
| Misc | Caps, resistors | $0.15 |

**Mounting Kit:** $1.60 | **Packaging:** $1.20

### Margin Analysis

| | Basic ($89) | Enhanced ($149) |
|---|---|---|
| BOM + materials | $18.34 | $31.10 |
| Assembly + QC | $5.00 | $8.25 |
| **Total COGS** | **$23.34** | **$39.35** |
| **Gross margin** | **$65.66 (73.8%)** | **$109.65 (73.6%)** |

At even 10 hand-built units ($30 COGS), the Basic still clears $59/unit.

---

## Next Steps for Julio

### Phase 1: Prototype (Weekends 1-2) — ~$35

Buy from Amazon/AliExpress:
- Arduino Nano (ATmega328P dev board) — $5
- 433MHz TX/RX module pair — $3
- 80A automotive relay module — $6
- ATtiny85 dev board (Digispark) — $4
- LM2596 buck converter module — $2
- Breadboard + jumper wires — $5
- CR2032 battery + holder — $2
- Push buttons + LEDs + resistors — $3
- ABS project box — $3
- Key fob cases (2-pack) — $2

Also need (one-time): USB-ASP programmer (~$8), soldering iron if you don't have one.

**Weekend 1: Proof of concept**
- Wire Arduino Nano + relay on breadboard
- Wire ATtiny85 + 433MHz TX on second breadboard
- Write basic TX/RX code (no encryption yet)
- Goal: press fob button → relay clicks → LED lights up

**Weekend 2: Add security**
- Add AES-128 library to both MCUs (use `tiny-AES-c` library)
- Hardcode a shared test key
- Implement rolling counter
- Verify that replaying a captured signal is rejected

### Phase 2: Complete Product (Weekends 3-4)

**Weekend 3: Pairing + polish**
- Add pair button logic on lock box
- Implement key exchange (wired connection for prototype)
- Add LED status states (green=unlocked, red=locked, blink=pairing)
- Add 30-second auto-lock timeout
- Add EEPROM storage for paired keys (support up to 8)

**Weekend 4: Enclosure + real test**
- Solder onto perfboard (replace breadboard)
- Mount in ABS project box with cable glands
- Fit fob circuit into key fob case
- Test with actual e-moto (or 48V bench supply)
- Range test through walls (target: 20-30m)
- Seal with potting compound

### Phase 3: First Production Run (Week 5-6)

- Order custom PCBs from JLCPCB (5-day turnaround, ~$0.80/board at 100 qty)
- Order components from LCSC (ships with PCBs)
- Assemble 10 units
- Create install video (phone camera is fine, post to YouTube)
- Print instruction cards with QR code to video

### Phase 4: Website + Sales

- Update kindro.store with real product photos
- Add Stripe payment integration (or start with PayPal/Venmo for simplicity)
- Post on e-moto forums, Facebook groups, Reddit r/ebikes r/emotorcycles
- List on eBay/Amazon if volume justifies it

---

## Plan to Sell the First 10 Units

### Target Customer
Owners of Chinese-brand electric mopeds/scooters (Onyx, Monday Motorbikes, Super73-adjacent, Sur-Ron, Talaria, generic 48V-72V e-motos) who currently have zero theft protection.

### Pricing Strategy
- **Launch price: $79 Basic / $129 Enhanced** (introductory discount)
- After first 10 units and reviews: raise to $89 / $149
- Bundle deal: Basic + Extra Fob 2-pack for $99

### Sales Channels (ranked by effort vs return)

**1. E-moto Facebook groups (free, highest conversion)**
- Join: "Sur-Ron Owners Group", "Onyx Motorbikes Owners", "Electric Motorcycle Riders", "E-bike Security"
- Post a demo video: "I made an aftermarket kill switch for my [bike]. Press fob = power. Walk away = dead. $79."
- Engage with theft complaint posts (there are many)
- Offer first 5 buyers a discount for honest reviews

**2. Reddit (free, wide reach)**
- r/ebikes (750K+ members), r/surron, r/emotorcycles, r/ElectricScooters
- Post as "I built this" with demo video/gif
- Link to site in comments (not title — Reddit hates direct sales posts)

**3. Local e-moto shops / repair shops**
- Leave 2 demo units at local shops on consignment
- They sell for $89, keep $15 commission
- Julio's existing network of people who build aftermarket e-motos

**4. eBay listing**
- Low effort to set up
- "Electric Motorcycle Security Kill Switch - Encrypted Key Fob - Aftermarket Anti-Theft"
- eBay takes ~13% but handles payments and provides buyer trust

**5. YouTube install video**
- Film installing MotoKey on an actual e-moto (3-5 min)
- Title: "DIY Anti-Theft for Electric Motorcycles - $79 Kill Switch Install"
- Description links to kindro.store
- This becomes the long-tail discovery channel

### First 10 Units — Concrete Plan

| Unit | Channel | Price | Notes |
|------|---------|-------|-------|
| 1 | Personal use / demo | $0 | Install on Julio's bike for demo videos |
| 2 | Consignment at local shop | $89 | Leave with a shop Julio trusts |
| 3-5 | Facebook groups | $79 | Launch price, ask for reviews |
| 6-7 | Reddit posts | $79 | Link to kindro.store |
| 8 | eBay | $89 | Test marketplace demand |
| 9-10 | Word of mouth / referral | $79 | Offer $10 referral to early buyers |

### Revenue from first 10

| | Units | Revenue |
|---|---|---|
| Demo unit | 1 | $0 |
| At $79 | 7 | $553 |
| At $89 | 2 | $178 |
| **Total** | **10** | **$731** |
| COGS (10 units @ ~$30 hand-built) | | -$300 |
| **Net profit** | | **$431** |

That $431 funds the next batch of 25-50 units at proper PCB pricing, which drops COGS to ~$23/unit and margin jumps to 74%.

### Marketing Assets Needed
1. **Demo video** (30 sec): Press fob → bike powers on. Walk away → bike dies. Film on actual e-moto.
2. **Install video** (3-5 min): Full install process. Phone camera is fine.
3. **Product photos**: Lock box, fobs, complete kit in packaging. Natural light, clean background.
4. **One-liner**: "Encrypted kill switch for your e-moto. $79. Two keys included."

---

## Tech Stack (Website)

- Static HTML + CSS + JavaScript (no framework, no build step)
- Hosted on DigitalOcean VPS behind nginx
- Domain: kindro.store (SSL via Let's Encrypt)

---

## Repository Structure

```
motokey/
├── index.html              # Product storefront
├── style.css               # Storefront styles
├── app.js                  # Cart + FAQ interactivity
├── hardware-design.html    # Full hardware architecture document
├── .gitignore
└── README.md               # This file
```

---

## Built With

This entire project — website, hardware architecture, security protocol, BOM, margin analysis, and go-to-market plan — was designed in a single AI-assisted session using [Claude Code](https://claude.com/claude-code).

The goal was to demonstrate how to go from conversation to live product in one sitting:
1. Discussed the idea → 2. Built the website → 3. Pushed to GitHub → 4. Deployed to production → 5. Designed the hardware → 6. Wrote the business plan

Total time: one session. Total code written by hand: zero.
