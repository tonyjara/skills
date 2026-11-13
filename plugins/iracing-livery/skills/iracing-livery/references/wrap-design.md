# From a brand's posters to a full wrap

The brief people actually mean by "make it our livery" is not "put the logo on a black
car". It is the brand's design language over the whole body, still reading as a race car:
bold from a distance, legible at speed, with sponsor-style placement of the name.

The example brand below, Brightwater (a radio station), is made up. `scripts/example_kit.py`
draws it.

## 1. Collect the language

Look at what the brand has really made (posters, covers, merch sheets, its site) and
write down:

- **Palette.** The ground colours, the ink, the one accent, and any category colours.
  Brightwater: cream, ink, teal, coral, sun yellow, sky, plum.
- **Shapes.** The repeatable motifs. Poster systems are usually a few: discs, half discs,
  quarter discs on a grid, arches with a disc, bars, dot grids, a disc cut by a diagonal.
  `livery.py` draws all of these in a frame you can place, turn and clip.
- **Type.** The display face for the name (heavy, condensed and in capitals reads best on
  a car), and a wide-tracked face for the web address.
- **The mark.** The logo, and whether it can stand alone at 30 cm wide on a hood.

If the brand generates its posters from code, read the generator and reuse its rules (the
same seeds draw the same posters). The car then shares real artwork with the brand
instead of imitating it.

## 2. Pick a direction (or two)

Two structures that worked:

- **One poster, scaled to the car.** A single composition across the whole body. One
  example is a sky-blue nose, a big disc over the doors and the back of the hood, and an
  ink tail rising on a diagonal with a thin accent stripe. Three big shapes read from a
  distance, and the diagonal gives motion. It is the more "race car" of the two.
- **A wall of posters.** The body as a run of blocks, one poster per block (arch, disc and
  diagonal, half discs, dots, bars), with four posters on the hood and a quarter-disc
  grid on the tail that reads as a chequered flag. It is the more memorable up close, and
  needs plates and keylines to keep the name legible.

When the request allows, make both, with the same file set, so they can be compared on
the preview sheets.

## 3. Make it a race car, not a pasted poster

- **Forward motion.** Lean every block and line into the direction of travel: a
  parallelogram whose top is shifted towards the nose (`lean_block` with a shear of about
  0.3). Diagonals rise towards the rear. Nothing important is vertical.
- **Flow across panels.** Draw both sides in the same coordinates and render the second
  with `flip`, so a shape that leaves the door continues on the fender. Carry one colour
  from the side onto the hood, and another from the side onto the tail, so the car reads as
  one object from above.
- **Big over small.** Few large shapes beat many small ones at speed. Keep the smallest
  shape bigger than a door handle. Dense patterns (dots, quarter grids) belong on the
  ends of the car, not behind the name.
- **Contrast at the edges.** Dark sills and a dark lower bumper ground the car. A light or
  bright nose makes it read head-on in a mirror.
- **Finish.** Gloss on the colour and satin on the ink (see spec-maps.md) makes the
  graphics pop without extra shapes.

## 4. Sponsor-style placement

Place the name the way a sponsored car would. The positions differ per car (the MX-5's
are in mx5-2016.md):

- **Doors:** the biggest name, after the number panel, on a plate where the ground is busy.
- **Sills:** the web address, tracked wide, light on a dark band.
- **Hood:** a plate, readable from ahead and from above (TV and chase cameras).
- **Windshield banner and header:** the web address or the name, readable from ahead.
- **Trunk:** a plate, readable from behind: the view every car behind has.
- **Front bumper:** two small names, clear of the intakes and the stamped plate.
- **Rear bumper:** the web address next to the number.

Over patterns, put the name on a **plate** (a solid rectangle) with a **keyline** (a thin
ink border) so it separates from the art behind it (`plate(..., keyline=INK)`). Fit long
names to their space (`fit(..., max_width)`) rather than letting them run off a panel.

## 5. Number panels

Give each number block a light, plain panel with a margin, the same on every block, and no
art under it (see install-and-sim.md). This is the one place where the design gives way
completely.

## 6. Helmet and suit to match

Take one motif from the car (the half discs, the diagonal, the poster blocks) and the
car's type and palette. Respect the helmet's visor clearance and seam
(helmet-and-suit.md). On the suit:
- the name on the chest;
- the mark and the web address on the back;
- a band of the poster blocks across the chest or the shins.

## Checks before handing over

- every word inside its panel (`outside_share` near 0);
- nothing under a stamped part or a number block;
- every panel reading the right way up on the views sheet;
- the shrunk preview still legible;
- PSD and TGA identical;
- the template's sample art hidden;
- swatch squares painted on purpose.
