# WheresDat — Small Parts Inventory System

Status: **PoC build started** — datastore + registration services underway.

## Problem

Small-parts clutter: fasteners, springs, washers, gaskets, glue/paint bottles,
and similar tinkerer odds-and-ends accumulate faster than they can be organized.
Mixed-content assortments (e.g. an M3 bolt/nut/washer kit) get spilled and
re-sorting by hand is a hassle. Goal is a low-friction inventory system that
can answer "where is X" and "how much X do I have" without manual bookkeeping
on every put-away.

## Who this is for

Two user personas, deliberately not the same bar:

- **The Adam Savage type** — highly organized, wants precision (exact
  spec/size, tidy Sortimo-style pre-sorted bins). Served by the calibrated
  fixed-rig measurement path and Sortimo-compatible tray sizing, but this
  is the *stretch* case, not the default target.
- **The primary user (Russ)** — "I just want to find shit, it does not
  have to be perfect." Default target. Most decisions already made in
  this spec lean here on purpose: 1/2/many counting instead of exact
  counts, category-level ("what is this?") accepted as a sufficient
  outcome rather than a fallback, ask-the-human over silently guessing,
  $100 BOM target over precision hardware.

  Worth naming explicitly, not just as flavor: the "where do I start,
  where does this go, what's the best fit" decision paralysis this
  project targets (see the bin-allocation flow above) isn't just
  laziness-adjacent — it's a real, disproportionate burden for
  ADHD/dyslexic/certain personality-type brains (and probably others),
  broadly "people with clutter problems." Not a clinical claim, just a
  reason this matters more than "convenience" framing alone suggests —
  removing a decision entirely helps more, the harder that decision is
  for a given brain to make in the first place.

**How to apply:** when a new feature idea comes up, check which persona it
actually serves. Precision/completeness features are fine to build (they
don't hurt persona 2), but they shouldn't become required just because
they'd satisfy persona 1 — the system has to work for "good enough, fast"
first.

**The actual thesis:** the system's value isn't just answering "where is
X" — it's removing the friction of the *decision* to organize. Toss an
item in view; the system says "matches an existing bin, put it there" or
"no match, here's a new bin" — the human never has to think about
categorization. That's how a persona-2 person ends up with
persona-1-quality organization without becoming more disciplined: the
discipline gets automated out of the loop entirely. Put-away assist isn't
just a convenience mode under this framing, it's the mechanism the whole
project is really for.

**Not a lesser real-inventory-system — a different kind of system.** The
stock-level design (see Parking Lot: as-of-last-scan nudges, not live
tracking or confident reorder points) is the clearest example of this
distinction. A real inventory system optimizes for accuracy and assumes
the discipline to maintain it. This one is built for an enthusiast with
executive-function blind spots — it optimizes for working *with* that
constraint rather than assuming it away. Precision that requires
discipline this project's own target user won't reliably provide isn't a
more rigorous design, it's a design that will quietly fail; the "worse"
option (a stale, honestly-labeled count) is the one that actually holds
up in real use.

**The actual design test, hard-won from having tried a lot of
organization systems before this one: visually accessible, low
organization effort.** Both, not either — a system that's visible but
demands constant upkeep fails the same way a tidy-on-paper system that's
hard to scan does. Nearly every design choice in this doc already serves
this without it having been named explicitly until now: open shelves
over precise pockets for irregular items, "dump it" storage where
precision isn't earned, the Kanban board's visible-but-ignorable cards,
1/2/many instead of exact counts. Worth using as the actual checklist for
future decisions: does this stay visually scannable, and does it avoid
asking for upkeep discipline this project already knows won't reliably
show up.

## Goals

- Physical storage: small plastic totes (~3x5x4in) on 3D-printed 3x3 shelf
  racks, each slot with a human-readable alphanumeric location code
  (QR optional, not required given the grid is already neat/fixed).
- A database of parts + quantities + bin location, queryable in natural
  language ("I need some superglue" → tells you which container).
- Re-inventory workflow when a bin's contents change: dump the tote onto a
  fixed photographing surface, shoot it, contents get (re)recorded, dump
  back into the tote, put it away. No manual data entry per item.
- Voice control from the phone app ("Hey WheresDat, M5x30 bolt?" → spoken
  bin location). Confirmed as a required feature, not a stretch goal —
  motivating use case is hands-dirty/hands-full workshop work (e.g.
  wrenching on a classic motorcycle) where touching a screen isn't
  practical. On-device speech-to-text + a small wake-word engine (e.g.
  Picovoice Porcupine for the custom phrase) on the phone, query goes to
  the mini-PC's search API over the hotspot link, answer spoken back via
  TTS.
- Mixed-content bins are in scope (not restricted to single-SKU bins).
- Counting model: **1, 2, many** — exact counts matter only below a small
  "clip level" threshold; above that, a bulk/bucket estimate is acceptable.
  This is a deliberate simplification, not a limitation to work around later.

## Non-goals (for now)

- Exact counts at high quantity (e.g. "sees" a stack of 40 washers is
  reported as "many", not necessarily "38±").
- Fully automatic classification of arbitrary/novel objects with no prior
  reference (paint bottles, glue, etc. still get a human-assigned label —
  vision's job is measurement/counting/re-identification, not open-world
  object recognition).
- Reliable optical thread-pitch measurement in the MVP (see Open Questions).

## Phase 0: prototype with existing hardware

Before buying purpose-built cameras (stereo module, dedicated macro), validate
the software pipeline (calibration, segmentation, measurement, counting,
DB/lookup) using gear already on hand:

- **Anker C200** (currently used for video calls) in a locked/fixed position,
  standing in for the wide/pan camera.
- **Phone** (Galaxy S25 Ultra) in a cradle/lock, standing in for macro/
  high-res verification shots.

Both get mounted in fixed positions for this phase too — not just the
software gets validated, the "camera stays put, part moves" mounting
principle does too, so nothing here is throwaway once purpose-built
cameras (e.g. a stereo module for depth-based stack disambiguation) get
added later.

## Budget

Target BOM for the base build: **~$100** (may need to flex up, but that's
the target, not a hard ceiling). Framing: this is the cost of finding out
*"does this actually work for me?"* — for the person building it, or
anyone else evaluating whether the whole approach is worth it — not the
cost of a finished/final product. Reuse existing hardware wherever
possible (see Phase 0) rather than buying dedicated gear up front; the
$100 number applies to the base build specifically, and is separate from
later upgrade paths (stereo camera module, larger "deluxe" tray tiers,
etc.) which are explicitly pricier by design.

## Hardware / capture station

- Fixed camera station (not handheld) — a phone (Galaxy S25 Ultra: 200MP
  main sensor, ultra-wide macro mode) mounted via its existing MagSafe-style
  ring holder.
- Two magnetic mount points on the rig for repeatable positioning:
  - **Wide station**: top-down shot of the full dump pan, used for
    counting/segmentation and length/diameter measurement.
  - **Macro station**: close-up crop for fine detail (e.g. thread pitch)
    when needed.
  - Magnets provide quick-attach/detach; a rigid mechanical stop at each
    mount (a flush plate/lip) fixes standoff distance and tilt, since a
    magnetic connection alone can rock and isn't reliable for alignment.
- **Dump pan**: a shallow pan/tray with one open corner for easy dumping
  back into the tote. Doubles as the calibration surface:
  - One side: white paper with a 5mm grid, for scale calibration
    (pixels-per-mm) and general contrast, same principle as an OpenCV
    checkerboard calibration target.
  - Flip side: dark grey with white grid lines, for chrome/reflective
    parts, where a white background blows out specular highlights and
    kills edge detection.
- Pan sizing: must fit the *actual* worst-case bin's contents spread in a
  single layer without excessive overlap — sized to real worst-case
  contents, not a theoretical max (oversizing costs pixel density/resolution
  at the wide station). A physical spread/settle step (shake, tilt, rake)
  is still expected between dump and shoot — pan area alone does not
  guarantee a single layer, since pouring clumps rather than tiles.
  Now that lighting brightness is resolved across the whole size range
  (see Lighting control above), a larger pan no longer carries a lighting
  penalty — using one of the Adam-Savage-sized commercial containers
  directly *as* the scanning tray, instead of fabricating a bespoke pan,
  is genuinely practical now rather than something to avoid.

### Physical frame — arch/gantry, now in build

The camera mount evolved from a simple magnetic phone rig into an
inverted-U arch straddling the tray: only two legs (front/back), so two
full sides stay open by default for the dump-corner — no corner-cutting
needed the way a 4-legged frame would require. Tray alignment is
mechanical, not just visual: rails on the arch's legs guide the tray in,
with slotted optical switches on both sides (not one) so a skewed/
partial insertion is caught before a shot ever fires — square on one
rail but not the other means no capture. The tray's own front lip is
built taller specifically to plug the gap in the light box's 3/4-height
front wall when seated, rather than needing a separate light-blocking
flap — self-sealing by construction.

**Two trigger mechanisms, self-selected by a keyed physical feature, not
by mode-switching logic or height clearance** — resolved after realizing
containers now vary a lot more in size than the original single-pan
design assumed (see the dock-whole-container re-inventory path above).
**Still noodling — candidate trigger mechanisms, not yet decided.** Core
constraint all of these share: the sizing/precision tray needs a
repeatable, verified-square stop position (calibration depends on it);
the bulk-container path doesn't, because that path is qualitative, not
quantitative (see Classification Depth Is Need-Based above) — it just
needs "something is fully docked," no alignment guarantee required.
Options on the table, roughly in the order they came up:

1. **Up-facing slotted optical switches + downward keel.** The precision
   tray has ~5-6mm keels that descend into the slots and physically
   bottom out — that bottoming-out is simultaneously the hard mechanical
   stop and the optical trigger, giving both calibration repeatability
   and skew detection in one event. Bulk containers have no keel, so they
   glide over the whole assembly untouched and hit a separate contact
   switch at the true back wall instead. Two physically distinct events,
   naturally lock each other out.
2. **Two endstops in series, inboard of the sizing tray's rails.** Plain
   mechanical endstops, wired so both must be depressed for the circuit
   to complete (a hardware AND, no logic needed; timing of the two
   presses doesn't matter). Elegant because it serves both tray classes
   for free from the same two switches: the sizing tray is exactly
   rail-width, so both firing genuinely verifies alignment; a bulk
   container is wider by construction, so it trivially spans and
   depresses both switches without needing precision — correctly strict
   where strictness matters, correctly loose where it doesn't, without
   special-casing either tray class in software.
3. **Mechanical-only alignment via rail fit** (e.g. an L-profile rail),
   relying on binding/drag to make a skewed insertion physically
   difficult rather than electronically detecting it, endstop just
   confirms "fully in." Simplest, but trades away an active signal for a
   passive guarantee — worn rails or a warped tray could degrade
   alignment quietly over time with nothing to flag it, unlike options 1
   or 2 which fail cleanly (stop triggering) the moment fit degrades.
4. **Magnetic reed switch on the enclosure's front door**, for a
   door-based enclosure rather than an open rail path — remains a valid
   option specifically for the bulk-container case regardless of which
   of the above the sizing tray ends up using.

**Structural update: a 4-tine fork off one connected rear base**, not
separate arch legs plus a separate rail assembly. One rigid base at the
back; the two outer tines rise up and over as the camera/light arch, the
two inner tines stay low as the sizing tray's guide rails — arch and
rails share a single common anchor instead of being independently
mounted. Meaningfully more stable and less jittery (a connected base
resists racking/twisting far better than separate point-contacts), which
matters beyond just feeling sturdier: less vibration at the camera mount
directly means less motion blur/inconsistency in the actual photos this
whole rig exists to take. It also directly helps option 3's weak point
above — a stiffer, unified rail mount is inherently less prone to
developing the kind of slop that would let misalignment degrade silently.

**Concrete construction: aluminum extrusion across the back, outer tines
running forward from it, arch mounted mid-span on the outer tines rather
than at their tip.** Mounting the arch partway along the tine's length
(not at the very end) means it's braced by extrusion on both sides of
its mount point, front and back — bidirectional stability instead of a
pure cantilever off one end. Joints locked with **T-plates**, standard
aluminum-extrusion hardware already on hand from the CoreXY build — a
nice direct payoff of that same build's lesson from earlier (bought metal
for stress-bearing joints, not printed parts): the prior project isn't
just the source of the lesson anymore, it's now also the parts bin.

**The inner tines' T-slot channel can double as the sizing tray's rail,
no separate custom rail needed.** The 20mm extrusion's T-slot is already
precision-manufactured for consistent width/depth along its full length
— that's its whole purpose, accepting T-nuts smoothly — which makes it a
ready-made linear guide for free, rather than a bespoke printed rail
profile with its own tolerances to get right.

Simplified further: no need for a feature that hooks over the top into
the *opposite* face's slot — that's more geometry than the job needs.
Just a few (3-4 per side) small **printed T-nut-shaped protrusions**
along the tray's edge, captured directly in the near-side T-slot the same
way a real T-nut is (wider below the slot opening, so it can't pull out
vertically, but slides freely along the channel's length). Discrete
points, not a continuous rail — a T-nut shape is already fully captured
on its own, so it doesn't need continuous engagement to be stable.

Structural approach, now actually being printed: **aluminum extrusion
frame + modular 3D-printed connector parts** at the joints, rather than
printing the whole arch as monolithic pieces. Everything is printed
*except* the 90-degree junctions themselves, which are bought hardware —
this is a lesson from prior experience, not a default: a home-built
CoreXY printer with printed corner joints worked, but needed constant
maintenance because printed parts under sustained vibration/repeated
stress shake themselves apart over time. The 90° junctions are exactly
the highest-stress points on this frame, so they're the one place that
learning gets applied — everywhere else sees less repeated stress and
stays printed for iteration speed. Extrusion on hand is standard 20x20
and 20x40 (2020/2040), so span choice isn't just length, there's a
stiffness/weight knob too depending on which stock a given run uses. The
printed parts aren't just brackets —
they're doing real integration work: mounting the status LCD strip,
molded cable channels (routing camera/light wiring cleanly up the legs
rather than dangling), housing for the optical stop switches, a camera
mounting base at the apex (the actual point of an arch in the first
place), and end-pieces sized to mate with the right-angle junctions.
Attachment points use heat-set brass threaded
inserts rather than screwing directly into printed plastic — same fix
Adam's own Case 49 exists for (heat-set inserts + the heat tool to set
them), and for the same reason: printed threads strip out with repeated
assembly/disassembly, brass inserts don't. Splitting structure (aluminum,
load-bearing, cheap per linear
foot) from function (printed parts, easy to iterate/reprint if a mount
point is wrong) is a sound way to prototype this kind of frame — the
expensive-to-get-wrong long structural members are a commodity part, and
the parts worth iterating on are exactly the ones a printer is fast/cheap
at redoing.

This also quietly answers the tray-size-tiering question from way back
(the 10cm/15cm/25cm "deluxe" idea): since aluminum extrusion comes in
standardized lengths, the same printed joint parts fit any span — a
bigger arch is just a longer cut of extrusion between identical
connectors, not a redesigned rig. Size-tiering turns out to be close to
free once the frame is built this way, rather than needing a separate
structure per size.

## Compute / network architecture

Revised from an earlier mini-PC-does-everything design after weighing cost:
splits the shed-side capture hardware from wherever inference actually runs.

- **Capture node — any Raspberry Pi, new or used** (cost-driven choice;
  reopened after realizing the node's job is now narrow enough that CPU
  headroom stops being the constraint). Job: driving the camera(s),
  reading the tray-alignment optical switches, and — new — running the
  wake-word voice satellite (below). No inference runs here.

  **Lighting control, revised twice, now network-distributed.** History:
  started as BlinkStick Square (USB-addressable RGB, top+side), moved to
  plain 12V LED strips + a GPIO relay (cheaper, brighter, simpler — traded
  away per-pixel color for cost/brightness), now moved again to
  **ESP8266 boards driving WS2812/NeoPixel strips over WiFi** — a pattern
  borrowed from a friend's actual studio lighting setup (same idea, more
  strips). This decouples each light from the Pi's own wiring entirely —
  strips get positioned wherever needed and receive commands over the
  local network instead of a physical GPIO/USB run back to one
  controller, which matters once there's more than one light or more than
  one station. Gets back per-pixel addressability without the on-Pi
  USB/GPIO budget problem the original BlinkStick approach had — useful
  for more than just the earlier raking-light/material-ID experiment now:
  the friend who suggested this setup does macro/product photography and
  specifically wants adjustable color to make shots look "natural,"
  which is a stronger, more general argument for real color control than
  the material-ID case alone. Accurate color rendering also matters for
  the catalog photos/thumbnails themselves looking like the real part,
  not just for the specularity trick.

  **One dense strip covers both light zones, not two separate devices.**
  The BlinkStick approach was heading somewhere genuinely awkward —
  needing two separate USB devices (top + side), each with its own power
  draw to budget for. A single 1m high-density WS2812 strip has far more
  individual LEDs than an 8-LED BlinkStick Square, so one physical strip
  (or two segments cut from it, wired on one data line) can cover *both*
  the top-fill and side-raking positions, addressed by LED-index range
  rather than needing two separate lights entirely. This also happens to
  resolve the original brightness worry from way back (2W across 8 LEDs
  being thin for a fill light at larger tray sizes) — a meter of
  high-density strip is a lot more total light output than that ever was
  — enough that it's considered closed across the whole size-tiering
  range (10cm/15cm/25cm "deluxe" tiers from earlier), not just the base
  tray size. Lighting brightness is no longer a scaling concern alongside
  camera resolution/pan size.

  **Voice satellite runs on the same Pi**, via `wyoming-satellite`
  (openWakeWord running locally + a USB mic/speaker) — no separate ESP32
  device needed, see Voice hardware below. Power: a small
  **externally-powered USB hub** for the camera(s) and mic/speaker, so
  their combined draw never comes off the Pi's own USB rail (lighting no
  longer draws through the Pi at all now that it's network-distributed,
  which only helps this budget further) — this is what actually makes
  "any Pi" true without model-specific power caveats; without the powered
  hub, older/cheaper Pis risk brownout under combined USB peripheral load
  regardless of CPU choice.
- **Inference + database of record — run together, in one Docker
  container, on whatever machine the user points it at** (laptop, home
  desktop over the network, etc.). Deliberately **single-host at a time**:
  the container (with its DB volume) can be moved between machines, but
  is not meant to run on multiple hosts simultaneously with independent,
  unsynced copies of the data — that's explicitly ruled out as unwanted
  complexity (distributed DB sync), not a limitation to design around.
- **Phone** (Galaxy S25 Ultra): app control/UI (registration + item-scan
  web app), macro camera, and acts as a **WiFi hotspot** so the shed-side
  Pi can reach wherever the inference container is running — the shed has
  no reliable existing network, so phone-hotspot avoids needing to run
  wiring or depend on shed infrastructure. Wake-word voice control moved
  off the phone (see Voice hardware below) — a web app can only listen
  reliably while it's the open, foregrounded, screen-on view, so it never
  covered true ambient/background listening anyway.

**Voice hardware — resolved, open-source, runs on the capture Pi.**
Explored Alexa/Echo Dot (real always-on hardware, but fixed wake word,
cloud-dependent speech processing, and needs the backend reachable from
the public internet — a mismatch with the shed's no-internet/hotspot-only
network) before landing on **Home Assistant's local voice stack**:
openWakeWord (wake-word detection) + Whisper (STT) + Piper (TTS) over the
Wyoming protocol. Fully local, no cloud, no account, genuinely custom
wake word ("Hey WheresDat") unlike Alexa's fixed option, and stays on the
local network entirely — no internet-reachability requirement. Runs via
`wyoming-satellite` directly on the capture Pi (USB mic/speaker, or reuse
the Anker C200's built-in mic for Phase 0 rather than buying a dedicated
one) instead of a separate ESP32 satellite device — one Pi doing camera +
optical-switch reading + voice, not three separate boxes (lighting no
longer runs through the Pi at all, see above). The piece tying wake-word → STT →
intent-routing → TTS together is most naturally a lightweight Home
Assistant instance acting as the hub, even without using its
home-automation features.

## Software components (sketch)

- **Capture**: fixed-camera shot pipeline (wide + optional macro), using the
  grid for scale calibration each session (sanity check against rig drift)
  or a one-time calibration if the rig proves stable enough.
- **Segmentation/measurement**: per-object detection on the wide shot;
  measure length/diameter via calibrated pixels-per-mm; bucket by measured
  dimensions + silhouette (head shape, etc.) rather than needing a trained
  classifier per exact part SKU.
- **Counting**: exact count for low-count blobs; density/area-based bulk
  estimate ("many") once segmentation confidence drops or count exceeds a
  threshold.
- **Database**: parts + quantity + bin location + human legend/alias tags;
  fuzzy/NL search on top (e.g. "superglue" → matches a tagged item) —
  doesn't need to be vision-driven, plain search (optionally LLM-assisted
  for fuzzy matching) is enough. InvenTree is a reasonable prior-art
  reference for the schema/UX shape, without necessarily adopting it
  wholesale.
- **Bin identity**: alphanumeric code per shelf slot, human-legible; QR
  considered unnecessary given fixed/neat rack slots, revisit if that
  assumption breaks (e.g. totes get moved between slots).

## Known hard cases / risks

- **Stacking**: flat parts (washers) stack on each other when dumped; a
  stack of 3 looks like 1 thick washer from directly overhead. No fix from
  top-down vision alone. Mitigated by the 1/2/many model — undercounting
  within a "many" bucket doesn't matter — but still a source of error at the
  boundary of the clip-level threshold. **Confirmed not solvable with a
  phone camera, even a good one** — a real-world manufacturing-inspection
  reference (smartphone-based auto-parts QC, iPhone 13) validates that
  ordinary phone cameras are plenty for 2D pass/fail inspection generally,
  but that's a different problem than depth; even iPhone Pro-model LiDAR
  is built for room-scale AR mapping, not resolving a ~1mm stack-height
  difference on a handful of washers. This is a resolution mismatch, not
  a phone-generation limitation — a better phone doesn't fix it. The
  stereo camera module considered earlier (see Hardware above) remains
  the right tool specifically for this sub-problem.
- **Nesting**: nuts and rings can nest into each other; springs/wire can
  tangle regardless of available pan area. Not solved by pan sizing.
- **Angled parts**: a screw leaning on another part measures short from
  top-down (projected length < true length).
- **Thread pitch**: too fine (~0.5-1mm ridges) to resolve in a normal
  top-down shot; needs macro + raking side-light to catch shadow contrast
  in the grooves, or fall back to a diameter→standard-pitch lookup table
  with manual override for known fine-thread exceptions.
- **Resolution vs. pan size tradeoff**: a pan sized for the worst-case bin
  (spread thin) increases field of view at the wide station and reduces
  pixels-per-mm, which works against distinguishing near-identical parts
  (e.g. M3x8 vs M3x10, ~2mm difference).

## Human-in-the-loop disambiguation

Confirmed design principle: when a classification is ambiguous (confidence
low), the system asks the human rather than guessing silently. Example
case: black zinc-plated metal vs. black rubber/paper/felt — both read as
"black" under any light color, so color alone can't discriminate. The
intended signal is specularity (metal gives a sharp point highlight that
shifts with light angle; rubber/paper/felt are diffuse, no crisp highlight,
plus visible fiber texture at macro resolution) — but when that signal
itself is ambiguous (e.g. a worn/dulled zinc part), don't fall through to a
guess. Show the human the crop, offer a quick choice ("metal or rubber?"),
and log the answer both to resolve the item now and as a labeled example
to improve future confidence on similar cases.

## Operating modes

Five distinct interaction modes, all sharing the same underlying
measurement/template-matching engine:

1. **Re-inventory** — dump a whole tote onto the pan, shoot, contents get
   (re)recorded against that bin, dump back in. The routine put-away/
   upkeep workflow.

   **Dumping isn't always necessary now that the scanning station can be
   sized like a whole standard container.** Concrete trigger case: a
   Rescan Kanban card asks "how many X in bin AF" — pull bin AF and dock
   the *whole container* into the scanning station directly, rather than
   dumping its contents onto a separate pan and scooping back after. This
   only works for pre-compartmented containers (the Sortimo/HF-case
   style, where each compartment is already a natural photographable
   unit — see the Sortimo test/"easy mode" observation above); loose
   mixed-parts totes still benefit from the dump-and-spread step for
   segmentation.

   Depends on item size too, not just container type: this shortcut is
   for **macro items** — spools of wire, larger ball bearings, tubes of
   glue/lube — not the small critical parts (screws, washers) that still
   need calibrated measurement precision. A compartmented bin full of
   tiny fasteners doesn't get enough pixel density per compartment when
   the whole container is shot from dock-in distance, so it stays on the
   pan/macro-station path despite being pre-compartmented. Three
   re-inventory sub-paths in total: dock-whole-container (compartmented +
   macro items), dump-and-spread (loose mixed totes), and pan/macro
   station (compartmented but small/critical items, precision still
   matters).
2. **Lookup** — natural-language or voice query against existing DB
   entries ("I need some superglue" / "Hey WheresDat, M5x30 bolt?") →
   returns bin location. No camera involved.
3. **Put-away assist** — the reverse of lookup: a handful of loose/new
   items in hand (not a whole bin), shoot them, each gets matched against
   existing silhouette templates and routed to its existing bin. Anything
   with no match falls through to the intake case (no home yet, human
   assigns one — see Open Questions). This is the direct answer to the
   original "I dropped the box and spilled small bits everywhere"
   scenario — sort the spill by shooting it once, not by hand.

   **The no-match/new-item case, made concrete:** a broad, one-or-two-of-
   a-kind item (a tube of gasket maker, a can of silicone grease — not a
   pile of many similar small parts) gets shot, doesn't match any existing
   template, and rather than just punting "no home yet, human decides,"
   the system should actively recommend one: check the list of currently
   **free/available bin slots and their specs** (sizes), pick the
   best-fit empty slot for this item, and generate a new bin ID for it —
   including a physical labeling note: waterproof labels, or a regular
   printed label with clear tape over it, since this lives in a shed. This
   is the mirror image of consolidation (which *frees* bins by merging
   fragmented stock) — together, allocation (new item → best-fit free
   bin) and consolidation (fragmented item → merge, freeing a bin) form
   one bin-lifecycle loop, not two unrelated features.

   This directly targets the sharpest version of the core pain point
   stated so far: *"I got a pile of shit to sort, and I hate that. Where
   do I start? Where does it go? What's the best fit?"* — decision
   paralysis when facing a pile of unsorted miscellaneous items is the
   actual friction being removed (see "the actual thesis" above), and
   this is what removing it looks like concretely: the system decides,
   the human just executes (put it in bin X, stick label Y on it).

   Two capture paths for this mode, deliberately different in rigor:
   - **Fixed-rig capture** (calibrated pan, controlled lighting) — needed
     whenever precise measurement matters, e.g. cataloging a part type for
     the first time.
   - **Ad-hoc single-item capture** (handheld phone, any background/
     lighting, no calibration reference in frame) — for re-identifying a
     part *already known* to the system. This only needs silhouette/
     template matching against the existing catalog, not fresh absolute
     measurement, so it's a fundamentally easier task than intake despite
     the uncontrolled conditions. "One item in my hand, snap it, it tells
     me where it goes" only has to work for already-cataloged parts — and
     naturally, it's opt-in: if the human already knows where something
     goes, they just put it away, no need to invoke the system at all.
4. **Pre-arrival intake (email-triggered)** — every other mode starts
   from a photo (measure it, or match it against a template); this one
   doesn't. An order confirmation email is already structured text —
   vendor, part description, and an *exact* quantity — and it arrives
   before the physical parts do. That's a higher-confidence data source
   than vision for count specifically, since it's a stated fact from the
   vendor rather than a camera-based estimate.

   Parsing: check for existing structured data before building anything —
   many vendors (Amazon included) already embed schema.org `Order`/
   `Product` markup in confirmation emails specifically so Google's
   "Purchases" feature can parse them; if that's exposed via an API, it
   may cover vendor/description/qty extraction with no custom parsing at
   all. The AI call engine (#2) doing flexible extraction is the fallback
   for vendors that don't emit that markup, not the default path — same
   "structured data when available, AI/vision when not" pattern already
   used elsewhere (barcodes vs. silhouette matching, part numbers vs.
   photos). Matches against an existing item template get the
   friction-removal treatment early — the system can answer "where does
   this go" (or reserve/suggest a bin) before the box is ever opened, the
   same allocation logic as put-away assist, just triggered earlier in
   the timeline. No match yet (a genuinely new part) falls through to the
   normal intake case once it physically arrives.

   Practical/scope note: this needs read access to order-confirmation
   email, which should stay narrowly scoped (a dedicated forwarding
   address or a filtered label) rather than broad inbox access — no
   reason for this feature to see anything beyond purchase confirmations.

   **Manual complement: the "LOG ORDER" button** (see Two Interface
   Modules below) — copy-paste the listing text right at order time
   instead of waiting on email parsing. Same underlying idea (capture
   the rich structured text while it's available), just human-triggered
   at the moment it's most convenient rather than automated. The listing
   title itself is often richer than a terse confirmation-email line item
   anyway (full descriptive text, not just a SKU/qty row).
5. **Pick list** — a miniature version of what picker-vision itself
   already does (warehouse order picking), just for personal projects
   instead of a warehouse. Know ahead of time you're working on a
   project session (Honda, say): generate a list of containers to go
   pull now, gather them as a walking "short-term storage" kit while
   working, return them when done. Reuses two things directly rather
   than needing new mechanics: **domain** filtering (a Honda pick list
   pulls from `honda-cb550`), and the **Return** card (pulling a
   container for the list is the same "checked out, not yet home" state
   already tracked there — a pick-list session is naturally a batch of
   Return cards, not a new card type).

   **This is why container identity needs to be independent of current
   location** (the paused global-numbering/move work above) — a
   container can't be cleanly picked, carried, and returned unless its
   own code/label stays fixed regardless of where it's currently sitting.
   Pick lists are a concrete use case for that design, not just the
   spare-parts-pool motivation from earlier.

   **Concrete session shape**: at the Honda, need a bolt or washer — ask
   WheresDat, get pointed to the item, either drop it into a small
   carrying tray or just grab the whole box (electrical connectors, say)
   if that's the more sensible unit. But real work always generates
   unplanned oddballs mid-session too — that's the actual scattering
   problem right now, not something a pick list alone fixes. Answer: a
   small dedicated **holding bucket** for "came up, dealing with it
   later" — no new mechanism, it's just the input to put-away assist
   (mode 3) once the session's done, same dump-and-sort flow already
   built for everything else. Pick list gets the planned parts out;
   the holding bucket is what keeps the unplanned ones from scattering
   across the workbench instead.

## Two interface modules, not one

- **Landing page** (desktop-oriented "master page"): the Kanban task
  board (see below) plus other administrative functions, surfaced as
  permanent cards in the board's own **Menu** column rather than a
  separate nav component (see Menu column below). First named one:
  **"LOG ORDER"** — while ordering from Amazon (or anywhere)
  on a computer, copy-paste the listing text right there (e.g. "Glarks
  320Pcs Carbon Steel Compression Type Wavy Wave Crinkle Spring Washers
  Assortment Kit") into a logged, pending record *before the item
  arrives*. This is the manual, immediate-and-convenient complement to
  the automated pre-arrival intake mode (#4 in Operating Modes) — same
  underlying idea (capture the rich, structured listing text while it's
  available, not after unboxing), just human-triggered at the exact
  moment it's easiest to grab rather than depending on parsing a
  confirmation email later. Matters specifically because "only new ones
  matter" for a lot of what gets bought here — the listing text is
  available anyway at order time, so capturing it costs nothing extra if
  it happens right then.
- **Phone app** (light, physical-capture-oriented): container/item
  scanning, voice control, registration — the flows described below.
  **Built and verified 2026-09-07**, at `GET /phone` — a genuinely
  separate page from the admin one, not a scaled-down copy: no Kanban
  board, no menu, camera-first, two big entry points matching the
  container/item-are-separate-paths principle below exactly —
  "🔍 What is this?" (calls `find-by-photo`) and "📦 Register a
  container" (calls `register` + attaches the just-taken photo + an
  optional voice-dictated locator note, reusing the same push-to-talk
  SpeechRecognition pattern as the admin page). Verified live at a real
  phone viewport size (390×844): recognize correctly identified and
  resolved a real registered container with its photo/description shown
  large and clear; register correctly created a new container with
  photo, locator, and auto-populated `ai_description` all attached in
  one flow. Label-validation-before-assignable (below) isn't wired up —
  that needs reading the physical label back via camera, not built.

## Interface flow: container vs. item, and the task board

Resolved design for the photo-logging web interface — a genuine
convergence, not a sketch:

**Container and item are separate, explicit UI paths, not inferred from
one ambiguous photo.** The human tells the interface which one they're
capturing (two distinct entry points/buttons) rather than the system
guessing "is this a container or a loose item" from a single shot — same
structured-input-over-inference principle as everywhere else in this doc.

**A registered container is `pending` until its physical label is
validated, and pending containers cannot receive item assignments.**
This closes a real integrity gap: registering a container's *record*
isn't the same as the container being physically identifiable — if a
sticker never actually goes on, the container doesn't functionally exist
for retrieval no matter what the DB says. Validation is a scan of the
applied label confirming it matches the registered code; only then does
the container become an active, assignable target.

**Recognized-item lookup ("here's where this lives") is a standalone
path, not contingent on a pre-scanned container.** Concrete case: doing
laundry, pulling stray items out of a pocket, or finding a tube in a box
that's been separately misplaced for two years — the item gets shot on
its own, the system recognizes it against an existing template, and
answers "this already has a home, goes with its 1-2 siblings in bin X."
No need to have scanned a target container first; that's a *different*
entry point into the same underlying lookup, not a required first step.

**"Use" is symmetric — any material change to a count, in either
direction, for any reason.** Putting a rediscovered item back counts the
same as removing one for a repair — what matters for staleness purposes
is "this bin's true count no longer matches what was last verified,"
not "was something consumed." Direction and reason don't matter, only
that a change happened. This pushed the parking-lot stock-nudge trigger
from a gut "3" toward the top of the earlier "3-5 uses" range, since
symmetric counting racks up qualifying events faster than pure
consumption would.

**The closing/validation question resolves to a Kanban-style task
board, not a linear per-item "close this ticket" step.** Every open loose
end in the system becomes a card on a board that's the natural landing
page — non-blocking, visible, and it can be punched out or ignored, but
never invisible.

**Confirmed: no real board framework, no drag-and-drop — a flat list of
cards, grouped into columns by what action the card needs, open it, read
it, close it out or don't.** This is a deliberate rejection of building a
bespoke Kanban implementation: Kanban-as-a-pattern (visible WIP, pull
when ready, ignorable without being lost) is a solved problem, and
reimplementing drag-and-drop/multi-state board mechanics for this project
would be solving a problem that's already solved elsewhere, for no
benefit here. (A shared knowledge-board service was considered and set aside for the same reason it
was set aside for this project generally — it's scoped to code/project
tracking, not physical household tasks, and mixing personal and
professional boards was already explicitly ruled out earlier.) Same
minimal-HTML approach as the registration UI, not a new framework.

**Columns are organized by action needed, not by lifecycle stage** — lets
the human batch similar real-world actions together (do everything in
"Register" while the label printer's already out, everything in
"Reorder" while placing an Amazon order) instead of thinking in abstract
workflow states. Columns identified so far, mapped to the card types
above:
- **Register** — an added-but-unlabeled container ("Label and register
  Box CC").
- **Return** — something pulled from its home and not yet put back,
  container or item alike ("Return bin 23 to box AB" — pulled 3 days ago
  for one screw, still sitting on a counter upstairs; equally covers a
  single loose item pulled from a bin that itself never left the shelf —
  same word works for both granularities, no need for a separate
  category). New tracked state this introduces: a home location, and
  separately, a "checked out" status until a return-validation scan
  closes the loop.
- **Rescan** — the parking-lot stock nudge ("Check Bin 4 in Box AC for
  stock level, 5 uses recorded") — go verify a count that's gone stale.
- **Reorder** — a stock check that came back genuinely low, ready to
  actually buy more (the natural next stage after a Rescan card resolves
  low, not a replacement for it).
- **Remind** — manually created, not derived from any automated logic:
  a direct voice command ("Hey WheresDat, remind me to order more M5x20
  machine screws") drops an arbitrary card onto the board. Extends the
  existing voice-control feature (previously just lookup queries) into a
  general-purpose catch-all — sometimes the fastest way to not forget
  something is just to say it out loud.
- **Menu** — a genuinely different kind of column, not a task queue: its
  cards are permanent navigation shortcuts, not closeable work items.
  Click a card, go to that interface (e.g. LOG ORDER, see Two Interface
  Modules above) — the card never goes away, just sits fixed on one side
  of the board. New shortcuts/features may or may not earn a card here
  as they come up over time, same way any new column could. The point:
  this reuses the exact same card-rendering/interaction pattern already
  needed for the task columns as the app's *navigation* too, rather than
  building a separate nav-bar/menu component — one visual language for
  both "things to do" and "places to go," differentiated only by whether
  a card is closeable.

  **Resolved: hybrid, not either/or.** Some cards get **pinned** (fixed
  position — for shortcuts used often enough that you rely on spatial
  memory to find them, so they can't be allowed to move); everything
  unpinned **floats by usage frequency** automatically. Predictability
  matters most exactly where spatial memory is actually being relied on —
  pinning solves that specifically, while unpinned cards get the
  convenience of auto-sorting without costing anything, since nobody was
  memorizing their position anyway. Pinning itself is a much
  smaller-scope interaction than the full drag-between-columns mechanics
  already ruled out for task cards, so it doesn't walk back that earlier
  "no drag-and-drop" call.

This is the actual resolution to the "does an abandoned/unvalidated entry
just sit forever" question raised earlier — it doesn't get resolved
automatically, it becomes a visible, ignorable-but-not-forgotten card,
which is consistent with the whole project's friction-removal thesis:
the system's job is to make sure the human *knows*, not to force action.

## Classification depth is need-based

Not every bin needs full measurement-grade identification — category-level
("what is this?") is a legitimate, sufficient standalone outcome for a lot
of real inventory, not merely a fallback when precise measurement fails.
Concretely: an already human-sorted bin (a lamp-hardware assortment, an
automotive-clips assortment) has effectively had the hard sorting work
done already — each compartment groups similar items — so the system's
job shrinks to labeling what's already grouped ("brass lamp nipples,"
"push-type bumper clips"), which a capable general vision-language model
can plausibly do today, no custom pipeline required. Reserve the
calibrated fixed-rig measurement path (silhouette templates, exact
dimensions) for cases where precise spec/interchangeability actually
matters (the fastener-consolidation and put-away-assist scenarios above).

Tray/bin slot dimensions should be **Sortimo-compatible** rather than a
bespoke size — Sortimo's insert system already has an active maker
ecosystem (existing STL files for inserts/dividers), so this avoids
reinventing tray geometry, and as a side benefit, known standard
compartment sizes double as a free rough size-class prior for whatever's
stored in them, before any actual measurement happens.

**Buy large, print small.** Cost comparison worked out during spec'ing:
pre-made Harbor Freight cases (~$13) beat 3D printing for larger
container sizes — not worth the print time/filament to replicate
something that cheap. But for small parts specifically, printing custom
Sortimo/L-BOXX-compatible trays (mixed 1x1/2x1 module layouts) beats
buying oversized commercial bins, since it lets storage be sized to the
actual parts rather than whatever increment a manufacturer sells.
Parametric generator: `hardware/sortimo_tray.scad` — grid module
**corrected to 52.3mm**, verified against the specific real product
being targeted (Sortimo T-Boxx 2018 insert boxes), not the 52mm
originally sourced from a general L-BOXX search — close, but a genuine
product-specific fix, not rounding. Box height (63mm, T-Boxx H63) is
reference-only, unused by the pocket design itself (a shallow 8mm recess,
not full-height). The pocket-and-lip retention is a deliberate
simplification, not a replica of Bosch's actual snap-latch mechanism
(unverified tolerances) — test-fit one pocket against a real box before
printing a full tray. Printer build-volume is a placeholder in the file
pending the actual number.

**First print succeeded** (the original 4x2 mixed-size layout). Follow-on
sizing discussion landed on **doubling to a 4x4-equivalent by printing
two 4x2 half-trays** (two uniform 2x2 pockets each) rather than one
monolithic 4x4 piece — same validated 219.2 x 114.6mm footprint per half,
more margin under the 280mm safety target, and shorter unsupported spans
warp less. This is now the file's actual default `boxes` layout. Pocket
sizing simplified to uniform 2x2 throughout (dropped the earlier mixed
1x1/2x1 example) — finer subdivision within a pocket, if wanted, comes
from dropping a separate printed box (`sortimo_box.scad`, 1x1 sized) into
it rather than the tray's own layout trying to cover every size.

**The box itself, not just the tray it drops into:**
`hardware/sortimo_box.scad`. Parametric to the tray's own grid
(`units_x`/`units_y` in modules, default 1x1), sized to actually clear a
tray pocket with its own additional fit clearance on top of the tray's.
Box wall thickness (2mm) deliberately thinner than the tray's (3-5mm):
short spans on a box this size don't carry the same long-unsupported-wall
risk that drove the tray's walls up. Same caveats as the other hardware
files: not yet rendered/validated, test-fit before committing to a batch.

**Label platform: split into its own separately-printed piece, not
removed.** Originally picked up a good idea spotted on an existing
Sortimo T-Boxx design — a raised corner platform for a label,
independently designed since the source page was blocked (same as other
sites tonight). The built-in version had a real problem: floating above
the box's rim, it was an overhang, forcing support material when the box
prints on its side (the practical orientation for an open-top box) —
wasted filament, and supports touching what's supposed to be a clean
label surface is a lose-lose. Resolution: **`hardware/
sortimo_box_label_tab.scad`** — the same platform, now a standalone flat
tab (prints lying flat, zero supports needed at all), attached to the
box's corner after printing with a dab of superglue. Self-locating: an
L-shaped rim on the tab's 2 outer edges drops down to hook alongside the
box's own wall at that corner, so gluing it on doesn't need to be
eyeballed into position. Keeps the actual feature, loses none of the
print-quality cost. Worth remembering as a
general lesson for the other hardware files too: floating/overhanging
features cost real print material even when they look free in CAD — and
splitting a part in two is often the fix, not deleting the feature.

**Irregular-size kit boxes get open shelves, not fixed pockets — the
inverse case from the Sortimo grid.** The grid-pocket approach above only
works because Sortimo/L-BOXX boxes share a real module standard to design
against. Small purchased kit boxes (the IEXCELL screw kit, the Sonitax
washer assortment) have no such standard — every one is a different size
from a different manufacturer — so a fixed-pocket shelf would be
engineering precision into a problem that doesn't have any to find.
Resolved instead: an open shelf unit (like a desktop paper-tray
organizer), **tier-level location granularity, not pocket-level** — a
box gets tossed onto a specific shelf (roughly 1-4 boxes per shelf,
capacity varies with box size) rather than a precise slot. Same
container/location-coding scheme as everything else (the shelf unit is
just another outer container type, each tier a location code), just
without pretending to track an exact position within the tier — same
"too small to matter" reasoning as the untracked inner-label decision
earlier, applied to storage furniture instead of labels.

Fully 3D-printable, with an optional upgrade path rather than a fixed
design: **pin-located dividers** let an end user subdivide a shelf
further if they want more structure than the open-tier default gives —
base design stays simple, dividers are an add-on for whoever wants to get
fancier. Up to the end user how far to take it.

**Structural direction (still researching Thingiverse before committing
to a custom build): carbon fiber tubes as the 4 corner posts, not just a
front-edge reinforcement channel.** A printed base piece holds the 4
posts in correct rigid alignment; shelves are simple printed pieces that
slide onto the posts rather than being structural themselves — the tubes
carry the rigidity, not the plastic. Bonus this buys for free: **shelf
height becomes adjustable**, not fixed at print time, since a shelf just
sits wherever it's slid to along the posts — a better answer to "every
box is a different size" than fixed tiers would have been. Minimal part
count: one base design, one repeatable shelf design, four off-the-shelf
tubes. Same underlying instinct as reinforcing the front span, just
generalized to the whole unit's structure.

**Real product sourced for the front-edge reinforcement specifically:**
8pcs 1.4mm solid pultruded carbon fiber square rod, 300mm length, ~$12 —
same family available in 1.4/2/3/4/6mm, none over $12. 8 rods maps
directly to 8 shelves, one rod embedded per shelf's front edge. The back
of each shelf doesn't get the same treatment — it's directly supported
against the frame rather than cantilevering the way the front edge does,
so a solid or triangulated printed panel is plenty there without needing
the stiffer material where the load path doesn't call for it. **Confirmed:
same family also covers 2/3/4/6mm** — one unified sourcing decision, not
two separate parts: thin (1.4-2mm) for shelf front-edge reinforcement,
thicker (4-6mm) for the 4 corner posts. **Corner post size settled:
6x6x420mm** — sets the unit's usable post height at 420mm to design the
base and shelf pieces around.

**End caps (top + bottom) — first piece drafted:**
`hardware/shelf_unit_cap.scad`. One cap design for both top and bottom.
Caps consume 10mm of post length at each end (420mm - 10 - 10 = 400mm
usable post span for shelves). Honeycomb lattice cut into the open field
for material savings, with **3mm as the one hard constraint** — minimum
wall/rib width anywhere in the part, driving the margin kept clear
around both the corner post sockets and the plate's outer edge. Post
sockets are through-slots (not blind pockets), sized to the real 6mm
rod plus a small fit clearance. Footprint (post spacing, i.e. the unit's
actual width/depth) is a **placeholder pending a real measurement**, same
caveat as the printer build-volume placeholder in `sortimo_tray.scad` —
and, like that file, not yet rendered/validated (no OpenSCAD CLI in this
environment), open it in the real app before printing. **Design target
now 280mm, not the true 300mm bed max** — large flat prints like this
need a brim for bed adhesion (corners lift otherwise), and a brim needs
room outside the part's own footprint; designing to the raw bed limit
would leave none. Enforced with an `assert()`, same pattern as
`sortimo_tray.scad`.

**Shelf count settled: 8, not the maximum 10 — deliberately matched to
the carbon rod pack size, not just the math.** 400mm of usable post span
technically fits 10 shelves at a tight 40mm spacing. Going with 8 at
~50mm spacing instead means the whole unit's carbon-rod bill of
materials lands on exactly one order of each part with zero leftover: 4
posts (one pack) + 8 front-edge rods (one pack, one rod per shelf) — the
same "design to match what's actually sold in a pack" instinct already
used elsewhere (the ArUco dictionary sized well past realistic container
counts, Phomemo's standard label sizes). Shelf piece itself not started
yet — next up once the footprint placeholder becomes a real number.

**Project-scope note: STLs are meant to ship as part of WheresDat
itself**, not stay private to Russ's own build — this shelf unit joins
`hardware/sortimo_tray.scad` as a printable file intended for anyone who
picks up the project, reinforcing WheresDat as something replicable by
others rather than documentation of a one-off personal build.

**The "kit" is the actual production unit, not the individual parts.**
Confirmed by nesting a tray, its boxes, and several label tabs onto one
plate for a single print job — that bundle (1 tray + N boxes + N label
tabs = everything needed to outfit one rack/shelf position) is the real
deliverable, not separate per-part-type batch runs. Matters for the
shippable-STLs goal above too: a pre-arranged kit plate is a far friendlier
thing to hand someone than a pile of individual files they have to figure
out quantities for themselves.

## Domains — built and verified working

Realization that surfaced while explaining the project out loud: the same
physical part can need to stay in *separate* dedicated stockpiles on
purpose — e.g. M5 bolts reserved for the Honda CB550 restoration vs.
visually-identical generic black zinc M5 bolts for general hobby work.
Silhouette matching alone would happily treat these as fungible and
suggest merging them, which would be wrong — the whole point is that
they're earmarked separately.

**Domain lives on the container, not the type.** The same type ("M5x30
black zinc bolt") can have separate container instances in different
domains — that's the actual real-world shape (one stockpile per project/
purpose, same part). Built into the datastore's `Container` model
(`domain`, defaults to `"general"`), threaded through `/register` and
`/register-batch`, filterable via `GET /containers?domain=`. Verified:
registered the same type into both `honda-cb550` and `general` domains,
confirmed they stay separate and the domain filter isolates each
correctly.

**Consequence for the matching/decision engine (#6), not yet built:**
consolidation and allocation must never cross domain boundaries silently.
A stray Honda-CB550-domain bolt should not get suggested for consolidation
into the general-domain bolt stockpile, or vice versa, even on an exact
silhouette match — domain match is a hard prerequisite before silhouette
match even gets consulted, not an optional refinement.

**Domain-bucket fill is a hash-table-load-factor problem, resolved the
same non-blocking way as everything else here.** A domain's physically
allocated space (a tray, a rack) can fill up the same way a hash bucket
does — not a hard constraint (the domain field doesn't require physical
co-location, it's metadata), but worth a nudge before it's jammed solid,
same reasoning real hash tables use to resize before 100% load rather
than at it. Resolution: a **fill-threshold-triggered Kanban card**
(same pattern as the stock-level Rescan nudge), offering a choice between
the two tools already built — consolidate (free space in the existing
footprint first) or expand (print another kit for that domain, per the
"kit is the production unit" concept above) — not auto-picking either.

**Overflow goes to a designated "parking lot" tray, tracked with the
existing Return card type — no new machinery needed.** An item that
doesn't fit its domain's tray at intake isn't an error, it's the same
state as anything else not yet in its proper home: park it, get a Return
card ("move this to its domain's tray once space frees up"), same
mechanism already built for a container pulled out and not yet put back.

**Rack-organized-by-project also has real standalone value beyond the
data model**: predictable physical location means finding a tray by
walking up and looking, not needing to consult the system at all — same
reasoning as pinning frequently-used menu cards earlier. How many
concurrent domains actually show up in practice (2? 5? 20?) changes
whether "one rack per domain" holds up, but that's a real-use question,
not a now question — exactly two domains exist in the system today
(`general`, `honda-cb550`); worth revisiting once a third shows up for
real, not designed for speculatively.

Candidate future domains floated (still thinking, not committed): PC,
Firearms, Reloading, House, Bicycle. **General's contents drive a
different storage character than project domains, and that's worth
remembering, not incidental** — tools/glue/sealant/lube get used across
everything, so they land in General by nature, and they're also
oddball-sized, so General naturally skews toward "dump it" open-shelf
storage (the carbon-post shelf unit) rather than the precise Sortimo
grid a project domain accumulating small fasteners would want. Domain
and storage-type aren't the same axis, but what a domain actually
contains drives which pattern fits it — worth designing per-domain
storage choices around what's really going in them, not a one-size rule.

For General specifically, existing **open wall-mount bins** (already
owned, the same reinforcement-finger hanging-bin rack type from early in
this project) are probably a better fit than the new carbon-post shelf
unit — open-front, built for bulkier oddball items (lube, glue, tools),
and nothing new to design or print. Not every domain's storage needs a
purpose-built solution; General's may already be solved by hardware on
hand.

## Consolidation suggestions

Emergent feature, surfaces naturally from routine use rather than needing
dedicated scanning: since re-inventory happens via the normal dump-shoot-
record cycle, the DB can notice when the same item is fragmented across
multiple bins within the same domain (e.g. stray M3 bolts turning up in
bins C3, D1, and A7) and recommend consolidating into one location.

Matching mechanism is saved **outline/silhouette templates** per distinct
part, not just dimension-canonicalization (diameter/length/pitch → "M3x10")
— a hard match on outline. This is a feature, not a limitation: it
correctly groups M3 hex-cap bolts together by silhouette without also
lumping in M3 round/pan-head bolts, even though both are nominally "M3" —
those are genuinely different parts for practical reuse (not
interchangeable in a build) even if a human would casually call both
"M3 bolts" in conversation. Template matching is the layer that answers
"is this literally the same physical part" (used for consolidation and
counting); the coarser dimension-based label is a separate layer for
human-facing search/naming (see the diameter→thread-pitch lookup
discussion above) — the two don't need to collapse into one
representation.

**Trigger and human-in-the-loop, graduated by confidence:** consolidation
isn't a constant background nag — it's driven by actual shelf pressure
(e.g. "fewer than 2 free bins — time to consolidate"). When triggered, do
the high-confidence exact-template matches first, surfacing the actual
photos and asking the human to confirm before merging ("I think these can
be consolidated") — same human-in-the-loop principle as material-ID
disambiguation, never silent auto-merge. Only if that doesn't free up
enough space does it escalate to fuzzy/lower-confidence matches, which get
flagged for human review specifically because they're the riskier calls —
i.e. exhaust the easy/certain wins before spending the human's attention
on judgment calls.

## Open questions

- What is the actual worst-case bin content (drives pan sizing)? Rough
  guess needed before committing to a physical pan size.
- Where exactly does the "clip level" threshold sit — is it a fixed count
  (e.g. ≤5 = exact) or driven by segmentation confidence dropping?
- Does the macro station get used every time, or only on-demand when a
  measurement is ambiguous (e.g. diameter alone doesn't disambiguate a
  known coarse/fine thread pair)?
- Bin-to-shelf-slot binding: is a tote ever moved between slots, or is the
  slot code effectively permanent per tote? (Determines whether QR/barcode
  ever becomes necessary after all.)
- Intake vs. re-inventory workflows may end up being the same pipeline
  (dump-shoot-record) — confirm there's no meaningfully different "first
  time cataloging a new part type" step needed (e.g. assigning a legend/
  alias) versus routine re-inventory of known parts.

## Deployment: live + QA, local only for now

Decided 2026-09-07: two local Docker Compose stacks, not one — the
schema is still evolving fast (locator field, arbitrary nesting, five
new container types all landed in one session) and real data is about
to start accumulating once a camera actually touches a real object,
which raises the cost of a careless `docker compose down -v` from
"reset some test rows" to "lose real inventory." k8s deployment is
explicitly deferred until the system is more settled — moving now would
just mean redoing it after another round of "major DB changes," per
Russ's own call.

**Live** (default, no flags): `docker compose up -d --build` — ports
8101/8102/8103/8300, project name `wheresdat` (the directory name,
Compose's default). This is what's been running all session.

**QA**: `docker compose --env-file .env.qa -p wheresdat-qa up -d --build`
— ports 8111/8112/8113/8310, project name `wheresdat-qa`. Compose
namespaces volumes/networks by project name automatically, so this is a
genuinely separate `wheresdat-qa_wheresdat-db` volume — zero shared
state with live, verified by registering a type in QA and confirming it
never appeared in live's list.

One real wrinkle this surfaced: `KANBAN_URL` (internal, service-to-
service, always `http://kanbanman:8300` regardless of environment) and
`KANBAN_PUBLIC_URL` (browser-facing, differs per stack — 8300 live,
8310 QA) are genuinely different values. Registration's static HTML
used to hardcode `http://localhost:8300` for the widget's CSS/JS/
`apiBase`; it's now served through a one-placeholder string substitution
(`GET /` reads the file, swaps `__KANBAN_PUBLIC_URL__` for the env var)
rather than a templating engine, consistent with "no framework" — but
it's the first template*d* page in this codebase, worth knowing about
before assuming every static file here is served byte-for-byte.

## Parking lot

Ideas worth remembering, deliberately not committed decisions yet —
distinct from the rest of this doc, which tracks things actually decided
or built.

- **Stock-level / reorder nudges.** Rejected both "days of stock from
  consumption rate" (hobby fastener usage is bursty, not steady — the
  rate has no real meaning) and pure peak-relative thresholds (skewed by
  one-time bulk buys) as the primary model. Landed on: don't try to track
  live stock at all — surface the last-known count *with its age* from
  the last re-inventory scan, and let a low-and-stale reading be a nudge
  ("this looked low a while back — worth a fresh dump and count") rather
  than a confident reorder alert. No manual "I used X" logging required,
  since re-inventory mode already refreshes counts without it. Trigger
  condition floated for the nudge itself: **90 days since last scan, or
  after X lookup requests against that item** (whichever comes first) —
  the request-count leg matters because a frequently-queried item is more
  likely to have been disturbed/depleted than one nobody's asked about,
  independent of the calendar. "Requests" here means any material count
  change, symmetric in both directions (see Interface Flow below) — that
  realization pushed the gut estimate from 3 toward the top of the
  original "3-5" range. Exact value of X still not locked in.

- **Class containers — the deliberate exception to 1/2/many (design
  agreed 2026-09-29, not built; Backlog cards #1-#6 on the wheresdat
  board).** Some consumables are discrete, individually stickered units
  where running out has a real cost: a filament spool. Running dry
  mid-print with no identical spare is hard to recover from, since a
  different product (or PLA vs. PETG) prints at different temperatures
  and risks layer adhesion. For these, exact counting is free: each unit
  is already its own registered ITM, and "I used one" is an obvious
  physical moment (an empty spool in hand), not the manual "I used X"
  logging rejected above.
  - A **class container** (e.g. `PLA-001`) holds exactly one product —
    "exactly similar unique things" — and its count is just its number
    of children. It isn't a physical box; it's the definition of "same",
    decided by the human filing the spool there, so nothing has to infer
    equivalence.
  - Modeled as **one more type-level setting** on `ContainerType` (next
    to `default_child_count`, `label_tier`, `numbering_scope`), not a new
    framework. Nesting, moves, and counts reuse the existing
    case/sub-bin machinery unchanged. What doesn't carry over: sub-bins
    are permanent pre-staged slots, class members are consumed units —
    so no `default_child_count` / `/register-with-children` for classes.
    Items stay `global`-scoped ITMs so a misfiled one can move without
    changing identity.
  - The flag only turns on: count display, an "N left / last one" reply
    when a unit is marked **used up** (dated, not hard-deleted, to keep
    reorder/burn-rate history), and a **match check** on register/move
    ("looks like PLA-002 — put it there?"; ask, never file silently).
    An empty class container stays registered as the "you're out"
    signal.
  - **Reorder** hangs off it: a per-container `reorder_url` (general, not
    class-only), and when a class hits its last unit, a Reorder card with
    a Decision Desk (Open store page / Ordered → On order / Not
    reordering / Received → register straight into the class).
  - **Printers as containers**: loading a spool = moving it into the
    printer, so "spares" means matching units *not* in a printer and the
    warning fires when the last spare gets loaded, not mid-print.
  - Scope guard: this applies only where the unit is discrete and
    already labeled. It is not a path toward exact counts for fasteners.

- **Admin UI for vision-identify's provider config (endpoints/API keys).**
  Not needed for Russ's own single-user setup — `vision-identify` (see
  PoC punch list #2) already supports swapping providers (local
  llama.cpp, OpenAI-compatible, Anthropic, Google) via env vars alone,
  no code change required, and provider config changes rarely enough
  that a k8s manifest edit + redeploy is fine. Worth revisiting once
  there's a plan to hand this to another user — at that point someone
  without cluster access needs a way to plug in their own
  endpoint/key without editing YAML. The datastore already exists to
  back a config table when this gets picked up; the missing pieces
  would be an authenticated settings page and having vision-identify
  read live config instead of (or in addition to) env vars.

- **Physical (plastic, not paper) labels — codes printed into the object
  itself rather than a stuck-on M110S label.** Two related ideas, one
  waiting on hardware and one buildable now:
  - **Codes baked into a container's own SCAD/STL at print time**, for
    containers that are already 3D-printed (Sortimo boxes, shelf pieces).
    Needs a real multi-material printer (ordered, backordered as of
    2026-09-17) for the ArUco marker specifically — fine per-cell color
    registration at that scale is a hard ask for FDM — but the
    human-readable code text alone is a much easier target. Would move
    "registration" earlier: pick the tray type, generate its SCAD/STL
    with the code extruded in as part of that same generation step
    (already a per-print step today, just not code-aware yet), then
    slice/print — not "print blank, register after."
  - **Standalone mountable label plaques for objects that aren't
    3D-printed (or already exist)** — bought bins too large for precut
    label stock, shelf units, anything worth never re-labeling. Doesn't
    need the multi-material kit: `scripts/generate_label_plaque.py`
    (added 2026-09-17) generates a plaque with the code as an open,
    debossed text pocket, sized for a single manual filament swap
    part-way through the print — light filament on the bottom (shows
    through the letter-shaped pockets as the lettering), black on top
    (the background) — one pause, no multi-material hardware. Text width
    on the generated plate is an estimate, not measured; verify against
    an actual OpenSCAD render before trusting the sizing on a batch.

## Aspirational milestone

Once working well: send it to Adam Savage. Not a serious roadmap item, but
a genuinely useful design bar — he's built a whole philosophy ("First
Order Retrievability") around minimizing the friction between "I need X"
and "X is in my hand," which is exactly what this project is chasing from
a different angle. This project generalizes it to run in both directions,
not just retrieval: lookup mode is First Order Retrievability applied to
"I need X" (minimize steps to X in hand); the bin-allocation flow above is
the same law applied to the opposite end of an item's lifecycle — "I have
X, minimize the steps to X correctly stored." Same underlying principle,
not two separate features. He'd also be an ideal real-world testbed: already has
an extremely organized small-parts tray filing system, so the "intake"
step (shoot each existing tray once, learn what's in it and where) would
bootstrap the whole catalog fast, and ongoing use is exactly the put-away
assist scenario above — one item in hand, ad-hoc phone shot, told where
it goes (or skipped entirely if he already knows).

## PoC punch list

1. **The datastore.** Items, quantities, bin locations, aliases/tags.
   Simplest thing that works for a PoC (e.g. SQLite), not a production DB.
2. **The AI call engine — real starting point now exists, not built into
   WheresDat itself yet.** Wraps calls to a capable vision-language model
   (see the Sortimo test above — category-level ID is already achievable
   this way, no custom-trained model needed for a PoC). `vision-identify`
   in the new shared `code-library` repo (`./code-library\services\
   vision-identify`) is a working, verified FastAPI microservice doing
   exactly this — dual-source cross-checked identification, extracted
   and generalized from insure-me's pattern. Builds, runs, fails gracefully with no API keys
   configured; real credentials not yet tested. Wiring WheresDat's
   registration service to actually call it (replacing the current
   photo-path 501 stub) is the remaining step, not a from-scratch build.
3. **Phone app** to shoot pictures and get things identified — the client
   for put-away assist and intake.
4. **Label maker program — built and verified working** (superseded this
   entry's original 1" square design; see "Three label formats" above for
   the actual current spec). New service, `services/label-maker`
   (port 8103): `label_gen.py` holds pure image-generation functions
   (no network dependency, independently testable), `main.py` wraps them
   in FastAPI, fetching a container's code/type/aruco_id from the
   datastore and returning a PNG. Verified by actually generating and
   visually inspecting one label per tier: outer (real ArUco DICT_5X5_250
   marker + auto-width text strip), inner_40x30, and inner_20x10 — including
   confirming the shrink-to-fit font logic correctly renders a longer
   nested code (`AA-01-01`) smaller than a shorter one (`SB-01`) to stay
   within the same tiny label. `ContainerType` gained a `label_tier` field
   (outer/inner_40x30/inner_20x10) and `Container` gained `aruco_id`
   (sequential, only assigned to outer-tier containers, capped at
   DICT_5X5_250's 250 IDs with a clear error past that). **Actual printing
   is now wired up and verified working, 2026-09-08** — but not via
   `pyphomemo`/Bluetooth as originally planned (see "Hardware decision"
   below for why that plan changed). `scripts/print_label.py`: a native
   Windows script (label-maker's own Docker container can't reach the
   printer either way it's connected — no Bluetooth passthrough into a
   Linux container, and the M110S turned out to be wired over USB anyway,
   showing up as an ordinary Windows print queue that only the host can
   see). Fetches a label PNG from label-maker and sends it to that
   installed printer driver via `pywin32`, scaling the image from its
   fixed 300 DPI source to whatever DPI the driver actually reports so it
   prints at true physical size. Verified end-to-end on real label stock
   (`WH-001`, 40x30mm tier) — first pass printed ~1mm off-center (the
   M110S's label feed just doesn't have much mechanical precision), fixed
   by adding a small blank margin around the border/text in
   `label_gen.py` so drift eats into margin instead of clipping content,
   confirmed on a reprint.

   Location coding scheme (unchanged, already verified in #7): every
   storage unit gets a unique code sized to how many of that type exist —
   2 letters for ~8-10 units, 3 if more are needed — enumerated (01, 02...).
   Nested bins inherit the parent code plus their own suffix (e.g.
   `AA-01-01`), so a removable inner bin that gets separated from its
   parent unit still says where it belongs.
5. **Voice control for retrieval** — see Operating Modes / Lookup above.
6. **The matching/decision engine** — the piece that isn't yet named but
   is load-bearing: #1 and #2 alone don't produce "tells me where to put
   it" on their own. Something has to take the AI's classification output,
   query the datastore for an existing template match or the free-bin
   list, and actually make the allocate/consolidate/lookup decision. Worth
   calling out as its own component rather than assuming it falls out of
   "the AI call engine" for free.

   **Ordering matters: try the local DB/template match first, only
   escalate to the AI call engine (#2) on a miss.** The common case isn't
   "identify a mystery object," it's "I pulled 4 screws, used 3, now I'm
   putting 1 back where it came from" — that's a known part with a known
   home, answerable from local data with no external call needed at all.
   External vision-model calls are for the genuinely novel-item case, not
   the default path — cheaper, faster, and doesn't depend on network/API
   availability for the routine put-back.

7. **Container registration — built and verified working.** A way to
   enter a new *empty* container into the system before anything goes in
   it. Two FastAPI services (`services/datastore`, `services/
   registration`), Docker Compose, SQLite. Real endpoints: register a new
   container type (human-named, chosen prefix), register a new numbered
   instance of a type, nested containers inherit the parent's code
   (`AA-01` → `AA-01-01`, `AA-01-02`). Verified: sequential numbering,
   duplicate-prefix rejection (409).

   Also has a minimal static browser UI (plain HTML/JS, no framework or
   build step — matters since this has to work off a phone hotspot in a
   shed) at the registration service's root, plus a `/register-batch`
   endpoint for staging several instances of a type ahead of time (e.g.
   printing a sheet of labels before the physical containers are even
   unpacked) — capped at 50 per batch.

   **Known-child-count types — built and verified working.** A type can
   declare `default_child_count` (e.g. 20 for a Harbor Freight 20-bin
   case), so registering one instance via `/register-with-children` knows
   its label BOM immediately: it auto-stages that many numbered sub-bins
   nested under the new parent in one call, rather than a separate manual
   batch step. Verified: registering an HF case with
   `default_child_count: 20` correctly produced `HF-01` plus
   `HF-01-01` through `HF-01-20`; types without a declared count still
   register normally with an empty children list. This is the deciding
   factor between the two labeling paths from the same conversation:
   known commercial products with a fixed sub-bin count (HF cases) get
   this auto-stage treatment, where ad-hoc 3D-printed boxes (not labeled
   until needed, count not knowable in advance) stay on the plain
   one-at-a-time `/register` path — both are real, intentional workflows,
   not one superseding the other.

   **Numbering scope and container moves — built and verified working.**
   A type declares `numbering_scope`: `parent` (default — code is
   `parent_code-NN`, permanently tied to whichever parent it was created
   under, e.g. HF sub-bins) or `global` (code is `type_prefix-NNN`,
   independent of current parent — for reshuffleable containers like the
   printed spare 1x1/2x1 boxes discussed earlier). New `PATCH
   /containers/{code}/move` endpoint reassigns `parent_code` without
   touching the container's own code/sequence/aruco_id — identity stays
   fixed, only current location changes. Verified: registered a
   `global`-scoped printed-box type, staged 3 spares with no parent (a
   spare-parts pool) plus a 4th registered directly under a tray — all 4
   shared one continuous sequence regardless of parent
   (`PB-001`-`PB-004`); moved `PB-002` through spare pool → tray A → tray
   B → spare pool again, its code never changed across any of it.
   Parent-scoped types (HF, and a plain tray type) confirmed unaffected —
   nesting still works exactly as before. Move validation confirmed:
   self-parent rejected (422), nonexistent target parent rejected (404).
   This is what actually makes the pick-list mode (Operating Modes #5)
   and the spare-parts-pool idea real rather than aspirational — a
   container can now be picked, carried, and returned without its own
   identity ever needing to change.

   **Arbitrary nesting depth — already fully general, verified working.**
   `parent_code` has no type restriction anywhere in the schema: any
   container can be the parent of any other container, to any depth,
   with zero code changes. A cabinet holding shelves holding bins holding
   cases holding smaller bins works exactly like an HF case holding its
   own sub-bins — the datastore doesn't distinguish "furniture" from
   "small parts container," it's all just containers pointing at a
   parent. Verified live with a real 3-level chain: registered a rack
   (`RK-001`), staged 4 rows under it via `/register-batch` with
   `parent_code: RK-001` (`RK-001-01` .. `RK-001-04`), then staged 3
   wall-hanger bins under the first row (`WH-001` .. `WH-003`,
   `parent_code: RK-001-01`). No schema change was needed for the
   nesting itself — only for `locator` (below), which is a separate
   concern. This also means household/non-shop domains work identically:
   a craft-room cabinet → shelf → a bin labeled "Halloween crafts" →
   a jar of pom-poms is the same mechanism, just a different `domain`
   value and different registered types (nothing shop-specific about the
   nesting itself).

   The taxonomy of *types* is deliberately not fixed or exhaustive —
   registering a new type is a 30-second `/register-type` call, so
   there's no need to speculatively pre-define every container shape
   that might ever exist. Register what corresponds to something real in
   front of you; add more later exactly the same way. Current shop-side
   types beyond the earlier PoC set (HF/PB/TR): `RK` (wall rack — no
   fixed `default_child_count`, since real racks vary, e.g. 4 rows vs. 3
   — stage rows per-instance via `/register-batch` instead), `RW` (a row
   on a rack, `parent`-scoped like HF sub-bins — a fixed, permanently
   addressable slot even when empty, several `WH` bins can sit on one
   row), `WH` (a wall-hanger bin, `global`-scoped since it moves between
   rows/racks via `/move` and keeps its identity), `GB` (a generic larger
   bin — e.g. a 2-gallon clear tote — `global`-scoped, `outer` label tier
   since it's loose/reshuffled like `PB`), `SF` (a general area/shelf —
   "Workbench Shelf 2" — for bins that don't have a rack-and-row
   structure, just sit somewhere).

   **`locator` — free-text, per-instance, not a printed label.** Added
   to `Container` (nullable, `PATCH /containers/{code}/locator`) once it
   became clear `ContainerType.name` (shared across every instance of a
   type) can't carry something like "Mounted above reloading workbench"
   or "North wall of shed" — two `RK` instances need two different
   descriptions, or "Halloween crafts" on one specific craft bin among
   several same-type bins. Distinct from the physical printed label
   (label-maker service) — this is purely a human-readable note for
   telling same-type siblings apart, editable any time, no reprint
   implied. Exposed in the registration UI as its own "Set locator"
   panel (code + text, blank clears it) since it's typically a follow-up
   step after registering something, not part of the registration call
   itself.

   **Oddball one-off registration — confirmed working, no new code
   needed.** Registering a genuinely one-of-a-kind item is just
   `/register-type` with a free-text name (no `default_child_count`,
   default `label_tier`/`numbering_scope`) followed by a single
   `/register` call — already fully supported by the existing endpoints,
   verified with a real "no idea what it goes to" bracket. This is also
   the manual keyboard override for when identification fails entirely:
   the `name` field is unconstrained free text, so "I don't know what
   this is, call it X" always works as the fallback of last resort, no
   AI/vision matching required to get an item registered.

   **Voice input for that same field — built, using a proven reference
   pattern rather than from scratch.** A working browser SpeechRecognition
   wrapper already existed in another project (`insure-me`'s
   `useSpeechRecognition.ts` — Google Vision + vision-LLM identification
   backend there is also a strong reference for the still-unbuilt AI call
   engine, #2). Ported the same pattern to vanilla JS for the registration
   UI: a 🎤 button next to the name field, push-to-talk (not continuous/
   wake-word — that needs native background execution a browser tab can't
   do, per the earlier foreground-only web-app finding), interim/final
   transcript handling, graceful "not supported" fallback if the browser
   lacks the API. Verified: page loads clean with the controls present in
   the HTML. **Not verified: actual microphone/speech behavior** — that
   needs a real browser with mic access, which this environment doesn't
   have. Test by actually clicking the button and speaking before trusting
   it.

   **Reference photo — built and decoupled from identification.** The
   registration-time photo (label visible as the touchpoint) doesn't
   need the AI call engine at all — that was a conflation in the
   original `photo: bool` flag on `RegisterIn`, which mixed "identify
   the type FROM a photo" (genuinely needs #2, still 501s) with "attach
   a reference photo of an already-known registration" (pure file
   storage, no AI involved). Split apart: `POST/GET
   /containers/{code}/photo`, one canonical photo per container
   (jpeg/png/webp, 10MB cap, re-upload replaces — including across
   formats, so there's never a stale second file), stored as plain files
   in the same shared volume as the sqlite db (`/data/photos/{code}.ext`
   — no new DB column; existence is just "does a file for this code
   exist," checked at request time). New "Attach photo" panel in the
   registration UI, with a live preview. Verified end-to-end: uploaded,
   downloaded, confirmed byte-identical dimensions; re-uploaded in a
   different format and confirmed the old file was actually removed, not
   just shadowed; confirmed a non-image content-type is rejected (422).
   Value is type-dependent, not uniform — every `HF` looks the same
   (mass-produced), so the photo there is mostly a registration record;
   a `GB` could be literally anything, so its photo is the only thing
   that actually distinguishes *this* bin from same-type siblings — the
   visual counterpart to `locator`.

   **Text search across AI description + locator — built and verified,
   the actual answer to "can it find this later."** Attaching a photo
   now also fires a best-effort call to `code-library`'s vision-identify
   (via `VISION_IDENTIFY_URL`, cross-project — that service lives in a
   separate Docker Compose project, reached over `host.docker.internal`)
   and stores its raw output (`name` + `text_on_package`) verbatim as a
   new `ai_description` field — not treated as verified fact (a
   vision-LLM can fabricate plausible-looking text, confirmed directly
   this same evening: it invented "Happy Days" on a tape roll that
   actually said "Heavy Duty Tape"), just search fodder. `GET
   /containers/search?q=` does a plain SQL `LIKE` across
   code/domain/locator/ai_description — no embeddings, no vector DB.
   Display precedence: a manually-set `locator` always wins over
   `ai_description` (exposed as a computed `display_name` field) — the
   AI text stays searchable underneath even once a human labels
   something, so search never gets *worse* by adding a locator, only
   more human-readable. New "Find a container" root-level Menu card,
   live-searches (debounced) with photo thumbnails in the results.
   Verified live: registered a container, attached a real product photo,
   confirmed `ai_description` auto-populated with zero manual steps,
   found it by both a product-spec-sheet word ("zinc") and confirmed a
   *different* real photo of the same product type did NOT match on a
   term ("SONTAX") its own particular OCR pass happened to miss —
   genuine model-output variance, not a search bug, and worth remembering
   as an ongoing property of this approach, not a one-time glitch.

   **Visual-similarity search — the deliberate tier this sits in front
   of, not yet wired in.** `code-library/services/jepa-embed` (Meta's
   I-JEPA ViT-H/14, CPU-only, built from source since no prebuilt binary
   exists) is built, running as a real HTTP service, and verified to
   produce a real discriminative signal: cosine similarity of 0.84
   between two photos of the same physical item vs. 0.46-0.68 across
   different items. The design is: text search first (fast, free,
   usually decisive); only fall back to visual similarity — scored
   against the small set text search already narrowed to, never the
   whole database — when text search returns multiple ambiguous
   candidates. Deliberately not a vision-LLM for that second tier: a
   general vision-LLM is tuned for description/OCR, not calibrated
   similarity scoring, and a purpose-built embedding model does that job
   properly.

   **Wired together and verified end-to-end.** New `POST
   /containers/find-by-photo`: identify the photo (same vision-identify
   call as reference-photo capture) → text search on the returned
   `name` → if 0-1 candidates, done; if 2+, embed the query photo and
   each candidate's stored photo via jepa-embed (`JEPA_EMBED_URL`,
   cross-project like vision-identify), rank by cosine similarity,
   resolve to the top score. Verified live with a genuinely ambiguous
   real case: two `GB` containers both matched "flat and spring washer
   assortment" on text search; visual scoring correctly separated them
   (1.0 for the one that was actually the same photo, 0.43 for one whose
   stored reference photo was an unrelated leftover test image) and
   resolved to the right one. Not yet in the UI — proven via the API
   directly, no "search by photo" panel built yet in registration's
   static page.

   One input path is still spec'd but deliberately not built: identifying
   a container's *type* from a photo (vision-matched against a known
   container-type catalog — "this is a 1 cu ft clear plastic bucket"), or
   from a part number (if it's a purchased/known product like a specific
   Harbor Freight organizer, pull its known specs directly instead of
   needing to identify it visually). Both still correctly return 501
   rather than faking a result, since they need the AI call engine (#2),
   not built yet. This is the
   actual answer to "how does a container get into the free-bin list
   #6 needs" — same structured-ID-when-available/vision-fallback-
   otherwise pattern already used on the parts side (barcode vs.
   silhouette matching). Registering a container is also naturally where
   label printing (#4) gets triggered — new container in, label out.

   **Likely the actual first thing to build**, not the last — it matches
   the real-world sequence ("I got these bins, and THEN I got this
   stuff"), so exercising it first means the PoC's build order matches
   how it'll actually get used, not just the order items got listed in.

   Also generalizes cleanly: saving the registration photo as a
   reference — "we have SEEN that thing I buy" — is the same mechanism
   as the silhouette templates already planned for parts (see
   Consolidation Suggestions above), just triggered for containers too.
   Every new container or new item type, first time it's encountered,
   banks a reference photo that becomes its template — that's how the
   template library actually bootstraps and grows over time, rather than
   needing to be pre-populated.

**Labeling refinement worth considering:** for the alignment mark on each
label, an ArUco/AprilTag-style fiducial (not a QR code) is purpose-built
for exactly this job — QR codes are optimized for data density/error
correction on arbitrary payloads, where ArUco/AprilTags are designed
specifically for robust camera pose/scale recovery from a single marker.
Since the human-readable code already carries the location ID, the
machine-readable mark's only job is alignment/scale — meaning it could
double as an in-frame calibration reference (same purpose as the pan's
grid, see Hardware above) on every single bin, not just at the capture
station. Marker generation via OpenCV's `cv2.aruco` (one dependency
covers both generating and later decoding markers); each container gets
a unique marker ID (new `aruco_id` field on the datastore's `Container`
model, assigned at registration from a `DICT_5X5_250` dictionary — 250
IDs is comfortably more than realistic container counts) so the marker
is both a scale reference and a machine-readable identity, not just
decoration.

**Hardware decision: Phomemo M110S thermal label printer (~$35)** (this
printer and not the SUPVAN alternative, which turned out to be
closed/app-only with no known driver). One printer covers both label
tiers below. Supports continuous tape from 20-50mm wide, cut to whatever
length a given print job needs — this replaced an earlier fixed 1" square
design (chosen somewhat arbitrarily, "QR code on the brain") that would
have force-fit every code into the same cramped footprint regardless of
length.

**Dispatch mechanism changed once the printer was actually in hand,
2026-09-08 — Windows USB print queue, not `pyphomemo`/Bluetooth LE as
originally planned.** Bluetooth pairing didn't connect; the M110S is
wired over USB instead, which Windows already exposes as a normal print
queue with its own vendor driver (confirmed working via a manual test
print through it). Since that driver already handles the printer-specific
raster encoding correctly, dispatch just sends the generated PNG to that
Windows printer object (`scripts/print_label.py`, `pywin32`) rather than
reimplementing Phomemo's BLE/ESC-POS protocol from scratch — one less
protocol to get wrong, and it was already proven to work. `pyphomemo`
remains a fallback if BLE independence from this one Windows box ever
matters, but isn't needed for the current setup.

**Three label formats now, not two, on the same printer** — outer
containers, inner sub-bins (physical HF plastic bins), and the 3D-printed
Sortimo-compatible boxes each need a different size:
- **Outer**: landscape strip, fixed tape width (e.g. 40mm) with **variable
  length** — auto-sized to the code (`CB-01` prints shorter than
  `AA-01-02`, no wasted tape and no cramming). Layout: ArUco marker on
  one side (sized to the tape height, with a clean quiet-zone margin —
  can't touch text or the border), the full code as a single line of
  large text on the other side. Thin border framing the whole label.
- **Inner** (sub-bins): different size, and **no ArUco marker** —
  confirmed decision, not a compromise. At the smallest tier (a 20-bin
  Harbor Freight organizer; smallest bin size 2"L x 1-3/8"W x 1-7/8"D) a
  marker sized to stay reliably detectable just doesn't fit alongside
  readable text. **Confirmed size: 1.57" x 1.18" (40mm x 30mm)** — the
  smallest standard off-the-shelf Phomemo die-cut label size, landscape
  orientation, human-readable-only. Fits comfortably against the smallest
  bin's ~2" width with margin to spare (2"L x 1-3/8"W x 1-7/8"D is the
  smallest of the 20-bin set: 8 at 4-1/4"L, 8 at 3"L, 4 at 2"L).
  Identification of inner bins happens by
  **OCR on the human-readable text**, not a decoded marker — whether
  scanning a whole stack of many small bins (5, or 70 like Adam's setup)
  or reading one bin's own label directly when it's already in hand.
  Outer containers keep the marker (they have the room, and they're what
  actually needs scale/pose calibration); inner bins inherit that context
  from their parent rather than each needing their own.
- **3D-printed Sortimo boxes** (`hardware/sortimo_tray.scad`): **3/4" x
  3/8" (20mm x 10mm)**, another standard off-the-shelf Phomemo die-cut
  size. The 40x30mm inner-bin label would dominate a compact ~52mm 1x1
  printed box's face; this size is properly proportioned for it instead.
  Text-only, same reasoning as the HF inner bins. Consumable cost is a
  non-issue — a roll is far more labels than this project will ever use.

  Worth noting for the AI call engine (#2): reading large printed
  alphanumeric text is a much simpler, cheaper problem than general
  visual classification — plain OCR (e.g. Tesseract, run locally) likely
  covers this without needing a cloud vision-language model call at all,
  consistent with the "local/cheap before external" ordering already
  decided for the matching engine (#6).

## Conclusion so far

Feasible as a system. The hardest technical piece (arbitrary open-world
object recognition) is explicitly out of scope via the 1/2/many model and
human-assigned labels; what's left (calibrated measurement, counting with a
bulk fallback, fuzzy DB lookup) is well-trodden CV/software territory. Main
remaining unknowns are physical/mechanical (pan size, rig stability,
spread step) rather than algorithmic.
