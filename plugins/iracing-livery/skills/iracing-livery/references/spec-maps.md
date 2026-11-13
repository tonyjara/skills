# Spec maps (car_spec)

A spec map gives the car its finish per pixel: gloss, satin, matte, metal. It is a second
TGA the same size as the paint, named `car_spec_<id>.tga`, in the car's folder next to
`car_<id>.tga`. Without one, the car gets iRacing's default finish. Helmets and suits have
no spec map.

## Channels

| channel | meaning | 0 | 255 |
|---|---|---|---|
| R | metallic | not metal | metal |
| G | roughness | mirror gloss | fully matte |
| B | clearcoat | see the template's Blue group, which starts at 0 | |

The car template's hidden **Custom Spec Map** group holds a group per channel, each with a
"Base Paint" layer (the paint's default) and on some channels a "Parts" layer. Parts are
glass, rubber, chrome and the stamped pieces, with their own values. On the MX-5 template
the paint's defaults are R 0, G 33, B 0.

Values that read clearly in the sim:
- gloss paint G ≈ 45;
- satin G ≈ 110-115;
- matte G ≈ 180;
- metal flake R 255 with G ≈ 60.

A matte body with glossy graphics and lettering is a strong look. So is gloss paint with a
satin black.

## Making one

`spec.py TEMPLATE.psd PAINT.tga OUT.tga --base R,G,B [--rule "#hex=R,G,B"] [--keep layer.png --keep-value R,G,B]`

- Builds each channel from the template's Custom Spec Map group, so every part keeps
  exactly the template's numbers.
- Sets the paint (everything that is not a part) to `--base`.
- Applies colour rules, matching paint within `--tolerance` of a colour. Later rules win.
- Forces `--keep` pixels, such as the lettering layer, to a value of their own.
- Softens edges by 0.8 px and writes a 24-bit RLE TGA.

Keep the finish rules tied to the design's colours, not to areas. When the design moves,
the finish follows it without redrawing.

## Pitfalls

- **Leftover spec files.** A spec map stays applied until its file is gone. When switching
  to a kit without a spec map, delete the old `car_spec_<id>.tga` from the car's folder.
  Otherwise the new paint gets the old kit's finish pattern.
- **A changed paint needs a new spec.** After moving or rotating any graphic, rebuild the
  spec too: its glossy shapes were cut to the old positions.
- **Not every viewer gets it.** Other drivers see the spec map only through Trading Paints,
  and some uploads of extras need its paid tier. Check what the upload page says.
