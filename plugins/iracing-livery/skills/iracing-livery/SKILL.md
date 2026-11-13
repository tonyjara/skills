---
name: iracing-livery
description: Design iRacing paints - a car livery, its spec map (car_spec), a helmet and a driver suit - from a brand's design language, as TGA files made from iRacing's own paint templates with free, scriptable tools (Python, psd-tools, Pillow). Covers getting the car's template and reading its UV layout (which island is which panel, which way each one faces), the orientation traps (trunk text upside down from behind, the hood's sideways UV, the right side mirrored), helmet visor clearance and the seam above the visor, spec map channels, file names with the customer ID and where each file goes, Ctrl+R reloads outside the pit stall, leaving the sim-stamped number panels alone (and why not car_num), flat preview sheets on the template wireframe, the screenshot loop for checking in the sim, and turning a brand's posters into a full wrap that still looks like a race car. Load it whenever someone wants an iRacing livery, paint, skin, wrap, helmet or suit, mentions Trading Paints, a paint template, car_<id>.tga, car_spec, a spec map, the paint folder, Ctrl+R in iRacing, or sends screenshots of a paint from the sim.
---

# iRacing liveries from a brand's design language

An iRacing paint is a flat image (a TGA) that the sim wraps around a 3D model through a UV
layout nobody can see from the image alone: panels are scattered, cut, turned and mirrored.
Almost every mistake is one of a few kinds: text that reads upside down on the car, a
word cut by a panel edge or hidden by a part, art painted where the sim stamps its own
parts, or a design that looks great flat and becomes noise at 150 km/h. This skill is the
workflow that avoids them, plus scripts that do the mechanical parts.

## Workflow

1. **Get the templates and map them.** Download the car's paint template (and the helmet
   and suit templates) from iRacing, unzip each into its own empty folder, and run
   `scripts/template_map.py` on each PSD. Read `grid.png` and `islands.png` until you can
   name every big panel. Details: [references/templates-and-uv.md](references/templates-and-uv.md).
2. **Settle orientation before any design.** For each panel (both sides, hood, front
   bumper, trunk, rear bumper, windshield banner) write down which way is forward and
   which way is up, and how text must be turned to read on the car. Do not trust your first
   guess on the trunk or the right side. If the car is the Global Mazda MX-5 Cup, the
   answers are already in [references/mx5-2016.md](references/mx5-2016.md).
3. **Design from the brand.** Collect the brand's real posters, colours, type and marks,
   then choose one or two directions (one big poster across the car, or a wall of posters
   along it). See [references/wrap-design.md](references/wrap-design.md).
4. **Draw as layers, in code.** A kit script (copy `scripts/example_kit.py`) draws each
   layer with `scripts/livery.py` and clips it to its panels. Check that no word falls off
   its panel (`outside_share` near 0).
5. **Build the files.** `scripts/compose.py layers` puts the layers into a copy of the
   template, which stays as the editable source. `compose.py tga` exports the 24-bit RLE
   TGA, and `scripts/spec.py` makes the spec map. Helmet and suit follow the same steps;
   see [references/helmet-and-suit.md](references/helmet-and-suit.md) and
   [references/spec-maps.md](references/spec-maps.md).
6. **Preview flat, then in the sim.** `scripts/preview.py sheet` and `views` give sheets to
   judge before anyone copies a file. Then the files go to the racing PC
   ([references/install-and-sim.md](references/install-and-sim.md)) and you work from
   in-sim screenshots ([references/previews-and-screenshots.md](references/previews-and-screenshots.md)).

## Rules that are easy to break

- **Text direction is per panel.** On the MX-5 template, the right side is the left side
  flipped vertically, so its text is turned 180°. The hood's UV runs sideways (text turned
  -90°). The trunk text is upright in the UV, which looks wrong on the sheet and is right
  on the car. Every car is different: confirm in the sim before calling a kit done.
- **Never paint where the sim stamps.** Layers in "Turn Off Before Exporting TGA" (Car
  Mandatory, helmet_decal, the licence colour on the helmet's sunstrip) are drawn by the
  sim on top of your paint. Keep words clear of them. The template's sample artwork
  (car_decal, banner, Color Change Logos) sits *inside* "Paintable Area" and would be baked
  in: hide it.
- **Leave the number panels to the sim.** The sim stamps the race number inside the
  template's Number Blocks. Give each block a plain, light, solid panel with a margin, so a
  race official can read it, and put no art under it. Don't make a `car_num_<id>.tga`.
- **Helmet: words behind the visor line, small under the seam.** On the 1024 helmet
  template, side words stay between x 810 and 1000 (mirror: 24 to 214) and the front word
  stays small, its foot at about y 788.
- **Files:** `car_<id>.tga` and `car_spec_<id>.tga` go in the car's folder;
  `helmet_<id>.tga` and `suit_<id>.tga` go in the `paint` folder. All are 24-bit RLE at the
  template's size. Press Ctrl+R in the sim to reload, with the car out of its pit stall.
- **Keep the layered source.** Each kit keeps its PSDs (the template plus your named
  layers), so a later fix is a layer change and a re-export, not a rebuild from memory.

## Scripts

All are Python 3 and need `psd-tools`, `pillow`, `numpy` and `scipy`. Make one virtual
environment for them, run them with `python -I`, and pass downloaded templates by path.
Keep templates out of the folder you run from: they are data, not code.

```
python3 -m venv ~/.venvs/livery && ~/.venvs/livery/bin/pip install psd-tools pillow numpy scipy
py() { ~/.venvs/livery/bin/python -I "$@"; }     # a function, so it works in bash and zsh
SK=<this skill's folder>/scripts

py $SK/template_map.py "tpl_car/<Car>.psd" map_car          # layers, islands, grid.png
py $SK/template_map.py "tpl_helmet/Helmet.psd" map_helmet
py $SK/example_kit.py --car-islands map_car/islands.npy \
    --helmet-islands map_helmet/islands.npy --font Brand-Bold.ttf --out kit
add=(); while IFS= read -r l; do add+=(--add "$l"); done < kit/car/order.txt   # layers, lowest first
py $SK/compose.py layers "tpl_car/<Car>.psd" kit/brand_car.psd --after Base "${add[@]}"
py $SK/compose.py tga kit/brand_car.psd kit/car_<id>.tga
py $SK/spec.py "tpl_car/<Car>.psd" kit/car_<id>.tga kit/car_spec_<id>.tga --base 0,45,0 \
    --rule "#151515=0,115,0" --keep kit/car/brand_lettering.png --keep-value 0,45,0
py $SK/preview.py sheet "tpl_car/<Car>.psd" kit/car_<id>.tga kit/preview_car.png
py $SK/preview.py views kit/preview_car.png map_car/islands.npy views.json kit/preview_views.png
py $SK/compose.py check kit/*.tga
```

The helmet goes the same way:
- `compose.py layers` on `Helmet.psd` with `--after "Helmet Color" --hide "Helmet Sunstrip,Seatbelt Labels"`;
- `compose.py tga`;
- `preview.py sheet ... --wire-alpha 0.35`.

`<id>` is the driver's customer ID.

| script | what it does |
|---|---|
| `template_map.py` | Lists a template's layers, saves its guide layers, labels every panel (island) and writes a gridded reference sheet. |
| `livery.py` | The drawing library: a supersampled canvas that can mirror the right side, a poster shape vocabulary, words at any angle, plates with keylines, clipping to panels. |
| `example_kit.py` | A worked full wrap and helmet for a made-up brand on the MX-5 template. Copy it and change the brand. |
| `compose.py` | Adds layers to a template copy (hiding sample art), flattens "Paintable Area" to a 24-bit RLE TGA, checks TGA headers. |
| `spec.py` | Makes the spec map: keeps the template's values on parts, and sets base finishes and per-colour rules on the paint. |
| `preview.py` | Makes flat previews: the whole sheet with the stamped parts, number blocks and wireframe, plus views of panels turned the way they are seen. |
