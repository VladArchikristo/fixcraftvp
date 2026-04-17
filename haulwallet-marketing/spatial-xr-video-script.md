# HaulWallet — Spatial XR Video Script
## "Your Road, Your Rules" — 60-Second Immersive Experience
### For Apple Vision Pro / Android XR

---

## CONCEPT

The viewer is placed inside a truck cab. No narrator. Just ambient sound, the road, and HaulWallet panels floating naturally in 3D space around the driver's field of view. The experience feels like a day in the life — not a product demo.

**Viewer POV:** Driver's seat, slightly elevated. Steering wheel visible at the bottom edge of view. Side mirrors reflect highway scenery. Panels appear where a driver's eyes would naturally go — instrument cluster zone, passenger seat space, windshield periphery.

---

## SCENE-BY-SCENE BREAKDOWN

---

### [0:00 — 0:10] DAWN — The Cab Before the Road

**Environment:**
- Truck cab, pre-dawn. Parking lot of a truck stop. Amber light from nearby diner sign leaks through windshield.
- Faint sounds: distant engine hum, coffee cup setting down on the dash, radio crackle.
- Stars fading. The horizon starts to glow orange-pink.

**Spatial UI — appears:**
- A soft panel materializes in the center-right field of view, like a phone screen floating at arm's length.
- **HaulWallet home screen** fades in:
  - Header: "Good morning, Mike. Ready to roll?"
  - Today's potential: **$847** highlighted in green
  - 2 loads available nearby — pins glow on a mini map
  - Weather: Clear. 68°F. No delays on I-40.

**Audio:** Gentle chime. Ambient wind outside. No voiceover.

**Text overlay (spatial, floating near the panel):**
> _"Before the key turns, you already know your day."_

---

### [0:10 — 0:20] CHOOSING THE LOAD — Decision Time

**Environment:**
- The viewer (driver) leans slightly forward. The truck cab is still parked. Sunrise intensifies.
- Hands grip steering wheel casually.

**Spatial UI — active:**
- Two load cards float side-by-side in the windshield area, like comparing papers laid on a dashboard:

**Card 1 — LEFT:**
```
LOAD #4821
Charlotte, NC → Atlanta, GA
412 miles | Flatbed 34,000 lbs
Rate: $620 | Per mile: $1.51
Pickup: 7:00 AM | Drop: 3:00 PM
[ACCEPT]
```

**Card 2 — RIGHT:**
```
LOAD #4822
Charlotte, NC → Nashville, TN
490 miles | Dry Van 28,000 lbs
Rate: $810 | Per mile: $1.65
Pickup: 8:00 AM | Drop: 6:30 PM
[ACCEPT]
```

- User (viewer) gazes at Card 2. It subtly brightens — gaze-activated hover.
- A tap gesture (or eye-select): card pulses. **"Load Accepted"** appears in green.
- Mini map shifts to Nashville route. ETA populates.

**Audio:** Satisfying soft tap sound. Engine starts rumble (background).

**Text overlay:**
> _"Pick smarter. Every mile counts."_

---

### [0:20 — 0:35] ON THE ROAD — Real-Time Intelligence

**Environment:**
- Highway. Daytime. Open road through Tennessee hills. Truck is moving.
- Subtle motion parallax on the cab interior — mirrors show passing scenery.
- Speedometer on dash: 65 mph.

**Spatial UI — three panels active simultaneously, non-intrusive:**

**Panel A (LEFT, near driver's window — peripheral):**
- Live cargo status tracker:
  ```
  LOAD #4822 — IN TRANSIT
  Origin: Charlotte NC ✓
  Current: Cookeville, TN
  Destination: Nashville, TN
  ETA: 2:15 PM  (on schedule)
  Temp: 68°F (within range)
  ```
- Subtle green pulse on "IN TRANSIT"

**Panel B (CENTER, heads-up display zone — windshield lower edge):**
- Route strip: I-40 W with real-time overlays
  - Mile 287: Weigh station OPEN — truck weight clears (checkmark auto-populated)
  - Mile 301: Fuel stop — diesel $3.42/gal (cheapest next 50 miles) — flagged
  - Mile 315: Construction zone — 8-minute delay projected

**Panel C (RIGHT, passenger seat area):**
- Earnings ticker:
  ```
  Miles completed: 287 / 490
  Earned so far: $473
  Remaining: $337
  Fuel cost deducted: -$84
  NET progress: $389 earned
  ```
- Live progress bar, green fill moving as miles pass.

**Audio:** Road noise, wind, radio off. Occasional soft notification chime as panels update.

**Text overlay (fades in/out on windshield glass effect):**
> _"Every mile tracked. Every dollar counted."_

---

### [0:35 — 0:50] ARRIVAL & DELIVERY — No Paperwork Chaos

**Environment:**
- Truck slows. Industrial district. Loading dock visible through windshield.
- Backing in sound. Air brakes hiss.
- Clock on dash shows 2:09 PM — 6 minutes early.

**Spatial UI — delivery workflow:**

- Central panel expands as truck stops:
  ```
  DELIVERY CONFIRMATION
  Load #4822 — Nashville, TN
  Arrived: 2:09 PM (6 min early)
  
  [ SCAN BOL ]   [ PHOTO PROOF ]
  
  Receiver: Premier Logistics Hub
  Contact: James R. | Dock 7
  ```

- Viewer "taps" SCAN BOL — camera overlay activates, BOL document scanned in 2 seconds.
- Green checkmark appears: **"Bill of Lading Verified"**
- Photo proof: 3 quick photos captured, auto-tagged with GPS + timestamp.

- New panel slides in from right:
  ```
  DELIVERY COMPLETE
  Documentation: Submitted ✓
  Invoice: Generated ✓
  Payment request: Sent ✓
  
  Expected payment: $810
  Within: 24 hours (FastPay)
  ```

**Audio:** Satisfying completion chime. Air brakes. Distant dock activity.

**Text overlay:**
> _"Paperwork done in 30 seconds. Not 3 hours."_

---

### [0:50 — 1:00] PAYMENT & CTA — The Reward

**Environment:**
- Truck cab. Parked at dock. Driver leans back. Golden afternoon light.
- A coffee cup raises (viewer POV — the driver's hand lifts the cup).
- Outside: dock workers, another truck leaving. The day is done.

**Spatial UI — final moment:**

- Single large panel, centered, warm:
  ```
  TODAY'S SUMMARY
  
  Loads completed: 1
  Miles driven: 490
  
  EARNED:         $810.00
  Fuel deducted:  -$84.00
  App fee:        -$2.45
  
  NET PAY:        $723.55
  
  Payment status: PROCESSING
  ETA: Tomorrow 9:00 AM
  
  [View Full Breakdown]  [Find Next Load]
  ```

- Panel slowly dissolves. The road ahead (through windshield) remains.
- **HaulWallet logo** materializes in 3D space, floating center. Clean. Confident.

**Audio:** Quiet satisfaction. Distant engine hum. Soft piano note resolves.

**Final text overlay — appears letter by letter:**

> # Download HaulWallet
> ## Your Road, Your Rules.

**Sub-line (small, below):**
> Available on iOS and Android. Free to start.

---

## TECHNICAL NOTES FOR XR PRODUCTION

### Depth Layers
| Layer | Content | Depth from viewer |
|-------|---------|-------------------|
| Background | Road environment, cab | 3–50m |
| Mid | Cargo tracker, route panel | 1.5–2m |
| Near | Action panels (BOL, payment) | 0.8–1.2m |
| Overlay | Text callouts, logo | 0.5–0.7m |

### Interaction Design
- Panels follow gaze but don't move aggressively — they drift slightly, settled
- Eye-gaze hover: panel brightens 10%
- Selection: dwell 1.5 seconds OR pinch gesture (Vision Pro) OR tap (Android XR)
- All panels have soft drop shadow and frosted glass background (iOS-native aesthetic)

### Accessibility
- All text minimum 18pt equivalent at 1m distance
- High contrast mode available
- No flicker, no rapid movement

### Audio Mix
- Spatial audio: road sounds pan with head movement
- UI chimes: non-directional (always center)
- No music until final 10 seconds (soft, ambient)

---

## PRODUCTION CHECKLIST

- [ ] 180-degree HDR truck cab capture (real or high-quality CGI)
- [ ] All UI panels built as spatial components (SwiftUI / Compose XR)
- [ ] Motion capture for hand/steering wheel elements
- [ ] Custom spatial audio mix (stereo to binaural)
- [ ] End card with App Store + Google Play QR codes in 3D space
