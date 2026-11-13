# Helmet and suit

Both templates are 1024×1024 and are worn in every car: a helmet or suit in the root
`paint` folder is the driver's default everywhere. Design them with the car so the set
reads as one team kit: same palette, same type, one motif from the car.

## Helmet

The helmet template (`Helmet.psd`) has one big island for the shell, the wide piece along
the bottom of the sheet (find it with `island_at(islands, 170, 845)`). Its centre top (x ≈ 512,
y ≈ 720) is the front, just above the visor opening. Its two ends are the back and meet
behind the head. Its left and right thirds are the sides: the helmet's left side is the
**right** half of the sheet, and the front of each side is towards the centre of the sheet.
The top cap, visor, sunstrip and inner parts are separate islands above.

Learnt in the sim:

- **Visor clearance.** The visor and its hinge cover the sides' front. At the height of the
  side graphics (y ≈ 800-900), anything in front of x ≈ 810 on the sheet's right half
  (mirror: x ≈ 214 on the left) can disappear under the hinge. A word that started at
  x 770 lost its first letter there. Keep side words and their plates between x 810 and
  1000 (mirror 24-214). Behind x 1000 they run into the back seam. Assert it in code
  (example_kit.py does).
- **The seam above the visor.** The shell meets the top cap at about y 718 in the middle.
  Letters just under it get stretched and slanted in the sim, and the first letters can
  read wrongly (an "S" became a "6"). Keep the front word small, with a cap height of about
  40 at most, centred on x 512, its foot at about y 788, so it sits low on the brow
  clear of the seam.
- **Glare.** The viewer's light makes a bright spot near the top front of the shell. That
  is lighting, not paint. Say so when someone reads it as a smudge.
- **Stamped by the sim:** `helmet_decal` (the inner shell and fittings) and the licence
  colour on both ends of the sunstrip. Put the web address or a short word in the middle
  of the sunstrip only.
- Hide the template's sample `Helmet Sunstrip` and `Seatbelt Labels` art if you replace them
  (`compose.py layers --hide "Helmet Sunstrip,Seatbelt Labels"`). The seatbelt labels are
  two small plates the driver sees: a good place for the wordmark.

## Suit

The suit template's wire has no green outlines, so `template_map.py` can't split it into
panels. Use the suit template's own hidden "Template" layers as masks:

| part | where on the sheet |
|---|---|
| sleeves | the left block, x 0-400, y 0-608 (two sleeves stacked) |
| torso, front (chest) | x 401-710, y 95-392 |
| torso, back | x 710-1020, y 95-392 |
| pants | x 399-1024, y 367-1024 |
| belt, collar, lapels | thin strips: `Belt`, `Neck`, `Lapels` layers |
| gloves, shoes, crew parts | bottom left; the template's own colour layers |

The hidden `Sponsor Locations` layer marks where logos show best:
- a chest logo at about 484-633 × 188-332;
- a large back logo at about 784-944 × 168-321;
- a small chest patch, and sleeve patches.

A chest wordmark at about (557, 150-180) and a back logo with the web address under it
were clear in the sim.

Paint gloves and shoes as well; the template's defaults clash with most palettes. Keep the
"again" copies of the template's own detail layers (glove bits, shoe soles, radio parts) on
top of your colours, as they come.
