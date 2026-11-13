# Templates and the UV layout

## Getting the templates

Every iRacing car has its own paint template, and the helmet and the driver suit have one
each. iRacing offers them as downloads: look on the car's page (paint or template
download) or iRacing's list of paint templates. Trading Paints links them too. Each comes
as a zip holding a layered PSD at the paint's real size: 2048×2048 for most cars, 1024×1024
for the helmet and the suit.

Unzip each one into its own new, empty folder and treat it as data. Keep your scripts
elsewhere and pass the PSD by path. A downloaded archive is untrusted input.

Use the newest template. iRacing rebuilds cars and moves their UVs, and a paint made on an
old template lands on the wrong panels. The template's name or readme often says which
build it matches.

## What is in a template

`template_map.py` lists every layer (`layers.txt`). The parts that matter:

- **Paintable Area** (group): everything here is flattened into the TGA. Its lowest layer
  is a base colour, often named "Base" or "Helmet Color". It also holds the sample artwork
  (`car_decal`, `banner`, `Color Change Logos`, a pattern group), which would be baked into
  your paint: hide those layers.
- **Turn Off Before Exporting TGA** (group): guides that must never reach the paint.
  - `Mask`: the paintable area, transparent where you may paint.
  - `Wire`: the UV wireframe. Panel outlines are green and the interior mesh grey.
  - `Car Mandatory` or `helmet_decal`: parts the sim stamps itself (maker logos, a model
    badge, black trim, a helmet's inner shell).
  - `Number Blocks`: where the sim draws the race number.
  - `Sponsor Blocks` or `Sponsor Locations`: iRacing's own sponsor places. Custom paints
    don't get its sponsor decals, but the places are a good hint for what shows.
  - `License` (helmet): the licence colour on both ends of the sunstrip.
- **Custom Spec Map** (group, car only): base values for the spec channels and the parts
  that keep their own finish (see spec-maps.md).

## Finding the panels

`template_map.py TEMPLATE.psd OUT` cuts the paintable area along the green outlines and
labels each piece:

- `islands.npy`: an id per pixel.
- `islands.json`: the islands over a minimum size, biggest first, with their bboxes.
- `islands.png`: a flat colour per island, with its id written on it.
- `grid.png`: the wireframe, stamped parts and number blocks, with a 100 px grid.

Read `grid.png` and name the islands. In a kit script, find islands by a point rather
than by id: `island_at(islands, x, y)`. A point read off the grid survives a re-run, and
the error is clear when the point misses.

Some panels are not closed islands, such as a rear bumper whose outline is open. Use a box
for those, or close the outline with a morphological closing of the wire layer.

The suit's wire has no green outlines, so its islands merge into one. Use the suit
template's own hidden "Template" layers (Torso, Pants, Belt, Neck, Lapels) as panel masks
instead.

## Working out which way each panel faces

Settle this before any design: what was easy to get wrong cost a round trip to the sim.
For each panel, find:

1. **Front or back.** The maker logos in Car Mandatory, the headlight and taillight cut-outs,
   wheel arches and door handles in the wire all tell you. The side with the front wheel
   arch is the front.
2. **Up or down.** Number blocks and badges are usually upright. On a side panel, the sill is
   the long straight edge and the beltline the curved one.
3. **Mirroring.** Many templates draw one side and reuse its shape flipped for the other.
   If the second side's island has the same outline upside down, it is the first side
   flipped vertically. Draw the art once and render it again with the y axis mirrored
   (`Canvas(..., flip=Y)` in livery.py, where `Y = y_top + y_bottom` of the pair). Text on
   it must then be turned 180° to read.

Then mark text direction on a copy of `grid.png`, one arrow per panel for "letter tops point
this way".

## The traps actually hit

- **The trunk.** By symmetry with the side panels it looked as if trunk text should be
  turned 180°. On the car that put it upside down when seen from behind. The trunk's UV
  was upright all along. Check the trunk and rear bumper in the sim early.
- **The hood.** Its UV ran sideways (the nose at small x), so text had to be turned -90°.
  The windshield banner strip next to it ran the same way.
- **The right side.** It was the left side mirrored vertically. The same art rendered with
  `flip` lines up across both sides, and its text is turned 180°.
- **A band seen beyond the windshield.** From behind and above, the hood's graphics show past
  the windshield, foreshortened and upside down. That is not a banner on the trunk lip.
  Before "fixing" a panel from a screenshot, map what you see back to the UV.
- **Small words near cut-outs.** Intakes, lamps and slots are holes in the panel. A word
  that crosses one loses letters ("ASAPY"). Clip each word to its own island, and assert
  that almost nothing falls outside it (`outside_share`).

## Making the TGA

iRacing wants a 24-bit TGA with RLE compression (type 10) at the template's size, with no
alpha. Flatten only "Paintable Area". `compose.py tga` does this and honours layer masks
and opacity. It reports any blend mode other than normal, because it can't reproduce
those. `compose.py check` reads a TGA's header. After editing a PSD by hand, export it
again the same way, or with an editor's "flatten, 24-bit, RLE" export under the same name.
