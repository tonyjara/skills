#!/usr/bin/env python3
"""Read an iRacing paint template (PSD) and map its UV layout.

    python -I template_map.py TEMPLATE.psd OUTDIR

Writes to OUTDIR:
  layers.txt     every layer: kind, name, visible, bbox (groups indented, bottom to top)
  layers/*.png   the guide layers at full canvas size: Mask, Wire, Number Blocks,
                 Car Mandatory / helmet_decal, Sponsor Blocks / Locations, License
  islands.npy    an int32 label image: one id per paintable panel ("island"), 0 = not paintable
  islands.json   every island over --min-size pixels: id, size, bbox, centroid, biggest first
  islands.png    the islands in flat colours with their ids written on them
  grid.png       a reference sheet: the wireframe, the sim-stamped parts, the number
                 blocks in magenta and a 100 px grid with coordinates

Panels are found as the template's paintable area (Mask alpha < 128) cut along the green
outlines of the Wire layer. Interior grid lines are grey, so a panel stays one island.
Needs psd-tools, pillow, numpy and scipy.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from scipy import ndimage as ndi

GUIDES = ("mask", "wire", "number blocks", "car mandatory", "helmet_decal",
          "sponsor blocks", "sponsor locations", "license")


def full_canvas(layer, size):
    """A layer's pixels on a transparent canvas of the document's size, as RGBA uint8."""
    w, h = size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pil = layer.topil()
    if pil is None:
        return np.array(canvas)
    pil = pil.convert("RGBA")
    canvas.paste(pil, (layer.left, layer.top), pil)
    return np.array(canvas)


def walk(group, depth, out, found):
    for layer in group:
        out.append(f"{'  ' * depth}{layer.kind:6} {layer.name!r} visible={layer.visible} bbox={layer.bbox}")
        if layer.is_group():
            # pattern groups hold dozens of sample patterns; list the group, not each one
            if "pattern" in layer.name.lower():
                out.append(f"{'  ' * (depth + 1)}... {len(list(layer))} pattern layers")
                continue
            walk(layer, depth + 1, out, found)
        elif layer.name.lower() in GUIDES and layer.name.lower() not in found:
            found[layer.name.lower()] = layer


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template")
    ap.add_argument("outdir")
    ap.add_argument("--min-size", type=int, default=2000, help="smallest island listed and labelled (pixels)")
    ap.add_argument("--grid", type=int, default=100, help="grid spacing on grid.png")
    a = ap.parse_args()

    psd = PSDImage.open(a.template)
    size = psd.size
    os.makedirs(os.path.join(a.outdir, "layers"), exist_ok=True)

    lines, found = [], {}
    walk(psd, 0, lines, found)
    with open(os.path.join(a.outdir, "layers.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\ncanvas {size[0]}x{size[1]}")

    arrays = {}
    for name, layer in found.items():
        arr = full_canvas(layer, size)
        arrays[name] = arr
        Image.fromarray(arr).save(os.path.join(a.outdir, "layers", name.replace(" ", "_") + ".png"))
    if "mask" not in arrays or "wire" not in arrays:
        sys.exit("no Mask or Wire layer found: is this an iRacing paint template?")

    paint = arrays["mask"][..., 3] < 128
    wire = arrays["wire"].astype(int)
    r, g, b, al = (wire[..., i] for i in range(4))
    outline = (al > 60) & (g > 150) & (r < 110) & (b < 110)
    if outline.mean() < 0.001:
        print("warning: almost no green outline in the Wire layer; islands will merge", file=sys.stderr)
    labels, n = ndi.label(paint & ~ndi.binary_dilation(outline, iterations=1))
    np.save(os.path.join(a.outdir, "islands.npy"), labels.astype(np.int32))

    sizes = ndi.sum(np.ones_like(labels), labels, range(1, n + 1))
    slices = ndi.find_objects(labels)
    centroids = ndi.center_of_mass(np.ones_like(labels), labels, range(1, n + 1))
    rows = []
    for i in np.argsort(-sizes):
        if sizes[i] < a.min_size:
            break
        sl = slices[i]
        cy, cx = centroids[i]
        rows.append({"id": int(i + 1), "size": int(sizes[i]),
                     "bbox": [sl[1].start, sl[0].start, sl[1].stop, sl[0].stop],
                     "centroid": [round(cx), round(cy)]})
    with open(os.path.join(a.outdir, "islands.json"), "w") as f:
        json.dump(rows, f, indent=1)

    rng = np.random.default_rng(7)
    colours = rng.integers(70, 245, (n + 1, 3))
    listed = np.zeros(n + 1, bool)
    listed[[r["id"] for r in rows]] = True
    flat = np.where(listed[labels][..., None], colours[labels], 0)
    flat[~paint] = (45, 45, 45)
    im = Image.fromarray(flat.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for row in rows:
        x, y = row["centroid"]
        d.rectangle([x - 4, y - 4, x + 8 * len(str(row["id"])) + 4, y + 14], fill=(255, 255, 255))
        d.text((x, y - 2), str(row["id"]), fill=(0, 0, 0))
    im.save(os.path.join(a.outdir, "islands.png"))

    sheet = np.full(arrays["mask"].shape[:2] + (3,), 245.0)
    alpha = wire[..., 3:] / 255 * 0.8
    sheet = sheet * (1 - alpha) + wire[..., :3] * 0.4 * alpha
    for key in ("car mandatory", "helmet_decal"):
        if key in arrays:
            al2 = arrays[key][..., 3:] / 255
            sheet = sheet * (1 - al2) + arrays[key][..., :3] * al2
    if "number blocks" in arrays:
        blocks = arrays["number blocks"][..., 3] > 128
        sheet[blocks] = (255, 0, 255)
        lab, k = ndi.label(blocks)
        for sl in ndi.find_objects(lab):
            print(f"number block x {sl[1].start}-{sl[1].stop} y {sl[0].start}-{sl[0].stop}")
    im = Image.fromarray(sheet.astype(np.uint8))
    d = ImageDraw.Draw(im)
    w, h = size
    for x in range(0, w, a.grid):
        d.line([(x, 0), (x, h - 1)], fill=(255, 150, 150))
        for y in range(40, h, a.grid * 4):
            d.text((x + 2, y), str(x), fill=(200, 0, 0))
    for y in range(0, h, a.grid):
        d.line([(0, y), (w - 1, y)], fill=(150, 150, 255))
        for x in range(40, w, a.grid * 4):
            d.text((x, y + 2), str(y), fill=(0, 0, 200))
    im.save(os.path.join(a.outdir, "grid.png"))
    print(f"{len(rows)} islands over {a.min_size} px; biggest: " +
          ", ".join(f"{r['id']} {r['bbox']}" for r in rows[:8]))


if __name__ == "__main__":
    main()
