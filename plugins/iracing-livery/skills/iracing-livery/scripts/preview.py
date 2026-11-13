#!/usr/bin/env python3
"""Flat previews of a paint on its template: judge a design before anyone copies a file.

  The whole sheet, with what the sim adds drawn on top:
    python -I preview.py sheet TEMPLATE.psd PAINT.tga OUT.png [--wire-alpha 0.55]
  - the parts the sim stamps itself (Car Mandatory on a car, helmet_decal on a helmet),
  - the number blocks outlined in magenta (the sim draws the race number inside them),
  - the wireframe, its white lines turned grey so they show on light paint too.
  Wire alpha 0.55 suits a car, 0.35 a helmet or suit.

  Panels cut out and turned the way they are seen (sides, front, rear, top):
    python -I preview.py views SHEET.png ISLANDS.npy VIEWS.json OUT.png
  VIEWS.json lists rows of views; each view is a box on the sheet, the islands it keeps
  (everything else turns to the background) and a rotation to make it read as seen:
    {"background": "#e8e4da", "rows": [
       [{"title": "LEFT SIDE (nose to the left)", "box": [40,1590,1850,2030], "islands": [439]}],
       [{"title": "RIGHT SIDE (nose to the right)", "box": [40,460,1850,900], "islands": [205], "rotate": 180}],
       [{"title": "FRONT", "box": [0,870,775,1620], "islands": [271,282], "rotate": 90, "scale": 0.7},
        {"title": "REAR", "box": [1200,105,1890,595], "islands": [126,55,209], "scale": 0.7}]]}
  ISLANDS.npy comes from template_map.py. These sheets are flat: they show what is on each
  panel and which way up it is, not how it wraps over the car's curves.
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage
from scipy import ndimage as ndi

STAMPED = ("car mandatory", "helmet_decal")


def full_canvas(layer, size):
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    pil = layer.topil()
    if pil is not None:
        pil = pil.convert("RGBA")
        canvas.paste(pil, (layer.left, layer.top), pil)
    return np.array(canvas).astype(float)


def find(psd):
    found = {}

    def walk(group):
        for layer in group:
            if layer.is_group():
                walk(layer)
            else:
                found.setdefault(layer.name.lower(), layer)
    walk(psd)
    return found


def over(base, layer):
    a = layer[..., 3:] / 255
    return base * (1 - a) + layer[..., :3] * a


def cmd_sheet(a):
    psd = PSDImage.open(a.template)
    layers = find(psd)
    paint = np.array(Image.open(a.paint).convert("RGB")).astype(float)
    if paint.shape[1::-1] != tuple(psd.size):
        sys.exit(f"paint is {paint.shape[1]}x{paint.shape[0]}, template is {psd.size[0]}x{psd.size[1]}")
    for name in STAMPED:
        if name in layers:
            paint = over(paint, full_canvas(layers[name], psd.size))
    if "number blocks" in layers:
        blocks = full_canvas(layers["number blocks"], psd.size)[..., 3] > 128
        paint[blocks & ~ndi.binary_erosion(blocks, iterations=3)] = (255, 0, 255)
    if "wire" in layers:
        wire = full_canvas(layers["wire"], psd.size)
        white = (wire[..., :3] > 150).all(-1)
        wire[white, :3] = (110, 110, 120)
        wire[..., 3] *= a.wire_alpha
        paint = over(paint, wire)
    Image.fromarray(np.clip(np.round(paint), 0, 255).astype(np.uint8)).save(a.out)
    print(f"wrote {a.out}")


def cmd_views(a):
    sheet = np.array(Image.open(a.sheet).convert("RGB")).astype(float)
    islands = np.load(a.islands)
    spec = json.load(open(a.views))
    bg = np.array([int(spec.get("background", "#e8e4da").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)])
    font = ImageFont.load_default(size=22) if hasattr(ImageFont, "load_default") else None
    rendered = []
    for row in spec["rows"]:
        cells = []
        for v in row:
            x0, y0, x1, y1 = v["box"]
            keep = np.isin(islands, v["islands"])
            keep = ndi.binary_dilation(keep, iterations=v.get("grow", 4))[y0:y1, x0:x1, None]
            cut = sheet[y0:y1, x0:x1] * keep + bg * (1 - keep)
            im = Image.fromarray(cut.astype(np.uint8))
            if v.get("rotate"):
                im = im.rotate(v["rotate"], expand=True, fillcolor=tuple(int(c) for c in bg))
            s = v.get("scale", 1)
            if s != 1:
                im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            cells.append((v.get("title", ""), im))
        rendered.append(cells)
    pad, cap = 30, 40
    width = max(sum(im.width for _, im in row) + pad * (len(row) + 1) for row in rendered)
    height = sum(max(im.height for _, im in row) + cap + pad for row in rendered) + pad
    out = Image.new("RGB", (width, height), tuple(int(c) for c in bg))
    d = ImageDraw.Draw(out)
    y = pad
    for row in rendered:
        x = pad
        for title, im in row:
            d.text((x, y), title, fill=(20, 20, 20), font=font)
            out.paste(im, (x, y + cap))
            x += im.width + pad
        y += max(im.height for _, im in row) + cap + pad
    out.save(a.out)
    print(f"wrote {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sheet")
    p.add_argument("template")
    p.add_argument("paint")
    p.add_argument("out")
    p.add_argument("--wire-alpha", type=float, default=0.55)
    p = sub.add_parser("views")
    p.add_argument("sheet")
    p.add_argument("islands")
    p.add_argument("views")
    p.add_argument("out")
    a = ap.parse_args()
    cmd_sheet(a) if a.cmd == "sheet" else cmd_views(a)


if __name__ == "__main__":
    main()
