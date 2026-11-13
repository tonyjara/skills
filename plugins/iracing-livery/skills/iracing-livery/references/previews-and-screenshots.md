# Previews, and the screenshot loop

## Flat previews before anything is copied

Nobody can judge a livery from the raw TGA. Its panels are scattered, sideways and
mirrored. Build two kinds of sheet with `preview.py` and judge with those.

**The sheet** (`preview.py sheet TEMPLATE.psd PAINT.tga OUT.png`) shows the paint with:
- the parts the sim stamps on top;
- the number blocks outlined in magenta;
- the wireframe, with its white lines turned grey so they show on light paint.

Use wire alpha 0.55 for a car and 0.35 for a helmet or suit. This sheet answers "is
anything under a stamped part, a number block or a panel edge".

**The views** (`preview.py views SHEET.png islands.npy views.json OUT.png`) cut each panel
out and turn it the way it is seen:
- the left side with the nose to the left, the right side with the nose to the right;
- the hood as seen from ahead, the front bumper, and the trunk as seen from behind.

A second views file can lay out a top view: the right side above, the hood and the trunk
in the middle, the left side below. These answer "does the design flow along the car, and
does every word read the right way up".

Say plainly that these are flat: they show what is on each panel and which way up, not
how it bends over the car. Small trim parts whose place you couldn't confirm are best
left in the body colour, and listed.

For a kit sheet, put the car, helmet and suit previews side by side on one image. When
there are two or more directions, make the same sheets for each so they compare directly.

Check legibility the way a track does: shrink a views sheet to a tenth of its size. The
name and number should still read, and the colour blocks should still be distinct.

## The screenshot loop

The sim is the only real test. Ask the driver to install one kit and send screenshots.
Name the views, or the ones that would have caught your mistakes won't come:

- both sides, square on;
- the front three-quarter, and from above the front (hood and windshield);
- the rear from behind at about car height (trunk and rear bumper), and from above;
- the helmet from the front, from the left and from the right;
- the driver standing (the suit).

Reading them:

1. **Fix the photo first.** Phone photos of a monitor carry an EXIF rotation; apply it
   (`ImageOps.exif_transpose`) before cropping. Crop each problem area large and look at
   it at full resolution: a squashed letter at thumbnail size is often glare.
2. **Map what you see back to the UV before changing anything.** From behind and above,
   the hood's graphics show past the windshield, upside down. That is not a separate
   banner. Find which island, and which spot on it, the pixels come from.
3. **Sort each finding:**
   - a real orientation error (turn the text in that panel);
   - a word cut by an edge, hole or part (move or shrink it, and check `outside_share`);
   - hidden by a part (move it, as with the helmet visor);
   - lighting (say so, and maybe make the art more robust to it);
   - taste (ask, or offer to drop it).
4. **Check every kit with the same layout.** A trunk turned the wrong way is wrong in
   every direction drawn on that template. A side word under the visor hinge on one
   helmet means the others need the same measurement, even if not seen.
5. **Change the layers, never the TGA alone.** Edit the kit's layer (or the PSD's named
   layer), re-export the TGA, rebuild the spec map if graphics moved, and rebuild the
   previews. Check that the PSD still flattens to exactly the TGA you hand over
   (`compose.py tga ... --check`).
6. **Hand back only what changed,** each file with its folder, and remind the driver to
   press Ctrl+R outside the pit stall. Then wait for the next screenshots.

Write down what the sim confirmed: which panels were checked and which way each reads. The
next kit on the same car starts from facts, not guesses. references/mx5-2016.md is one
such record.
