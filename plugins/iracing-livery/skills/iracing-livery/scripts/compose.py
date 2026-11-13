#!/usr/bin/env python3
"""Put layers into an iRacing template and export the paint.

  Add PNG layers (full canvas RGBA, the template's size) inside "Paintable Area":
    python -I compose.py layers TEMPLATE.psd OUT.psd --add "Brand body=body.png" \\
        --add "Brand lettering=lettering.png" [--after "Base"] [--hide car_decal,banner] [--replace]
  Layers go in the order given, the first one lowest, just above --after (default: the
  group's lowest layer). --replace first removes existing layers of the same names, so a
  kit can be rebuilt into its own PSD. --hide hides the template's sample artwork, which
  sits inside Paintable Area and would otherwise be baked into the paint.

  Flatten "Paintable Area" to a TGA, as iRacing wants it (24-bit, RLE, template size):
    python -I compose.py tga IN.psd OUT.tga [--check EXISTING.tga]

  Read a TGA's header:
    python -I compose.py check FILE.tga ...

Only "Paintable Area" is flattened: the group "Turn Off Before Exporting TGA" (mask, wire,
the parts the sim stamps itself) never reaches the paint. Layer masks and opacity are
honoured; blend modes other than normal are not, and are reported.
"""
import argparse
import struct
import sys

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

SAMPLES = ("car_decal", "banner", "color change logos")


def paintable(psd):
    for layer in psd:
        if layer.name == "Paintable Area":
            return layer
    sys.exit('no "Paintable Area" group: is this an iRacing paint template?')


def layer_rgba(layer, size):
    w, h = size
    out = np.zeros((h, w, 4), float)
    pil = layer.topil()
    if pil is None:
        return out
    t = np.array(pil.convert("RGBA")).astype(float)
    x0, y0 = layer.left, layer.top
    lh, lw = t.shape[:2]
    xs0, ys0 = max(0, -x0), max(0, -y0)
    xs1, ys1 = min(lw, w - x0), min(lh, h - y0)
    out[y0 + ys0:y0 + ys1, x0 + xs0:x0 + xs1] = t[ys0:ys1, xs0:xs1]
    if layer.has_mask() and not layer.mask.disabled:
        m = np.full((h, w), float(layer.mask.background_color))
        mt = np.array(layer.mask.topil()).astype(float)
        mx, my = layer.mask.left, layer.mask.top
        m[my:my + mt.shape[0], mx:mx + mt.shape[1]] = mt
        out[..., 3] *= m / 255
    out[..., 3] *= layer.opacity / 255
    return out


def flatten(psd):
    w, h = psd.size
    out = np.zeros((h, w, 3))
    for layer in paintable(psd):
        if layer.is_group() or not layer.visible:
            continue
        if str(layer.blend_mode) != "BlendMode.NORMAL":
            print(f"warning: {layer.name!r} uses {layer.blend_mode}; flattened as normal", file=sys.stderr)
        rgba = layer_rgba(layer, psd.size)
        a = rgba[..., 3:] / 255
        out = out * (1 - a) + rgba[..., :3] * a
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def header(path):
    h = open(path, "rb").read(18)
    kind, (w, ht), bpp = h[2], struct.unpack("<HH", h[12:16]), h[16]
    ok = kind == 10 and bpp == 24
    return f"{path}: type {kind} ({'RLE truecolour' if kind == 10 else 'not RLE'}), {w}x{ht}, {bpp} bpp {'OK' if ok else '<- iRacing wants 24-bit RLE'}"


def cmd_layers(a):
    psd = PSDImage.open(a.template)
    group = paintable(psd)
    if not a.add:
        sys.exit("nothing to add: give one or more --add \"Layer name=file.png\"")
    names = []
    for spec in a.add:
        name, _, path = spec.partition("=")
        names.append((name, path))
    if a.replace:
        for layer in [l for l in group if l.name in {n for n, _ in names}]:
            group.remove(layer)
    hide = {s.strip().lower() for s in (a.hide.split(",") if a.hide else SAMPLES)}
    for layer in group:
        if layer.name.lower() in hide and layer.visible:
            layer.visible = False
            print(f"hid {layer.name!r}")
    index = 0
    if a.after:
        found = [i for i, l in enumerate(group) if l.name == a.after]
        if not found:
            sys.exit(f"no layer {a.after!r} in Paintable Area")
        index = found[0] + 1
    for k, (name, path) in enumerate(names):
        im = Image.open(path).convert("RGBA")
        if im.size != psd.size:
            sys.exit(f"{path} is {im.size}, the template is {psd.size}")
        group.insert(index + k, PixelLayer.frompil(im, psd, name))
        print(f"added {name!r}")
    psd.save(a.out)
    print(f"wrote {a.out}")


def cmd_tga(a):
    psd = PSDImage.open(a.psd)
    rgb = flatten(psd)
    Image.fromarray(rgb).save(a.out, compression="tga_rle")
    print(header(a.out))
    if a.check:
        old = np.array(Image.open(a.check).convert("RGB")).astype(int)
        diff = np.abs(old - rgb.astype(int)).max(-1)
        print(f"against {a.check}: max difference {diff.max()}, pixels off by more than 8: {(diff > 8).sum()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("layers")
    p.add_argument("template")
    p.add_argument("out")
    p.add_argument("--add", action="append", default=[], help='"Layer name=file.png", lowest first')
    p.add_argument("--after", help="insert above this layer of Paintable Area")
    p.add_argument("--hide", help="comma-separated layer names to hide (default: the template's sample artwork)")
    p.add_argument("--replace", action="store_true", help="remove existing layers with the same names first")
    p = sub.add_parser("tga")
    p.add_argument("psd")
    p.add_argument("out")
    p.add_argument("--check", help="compare with another TGA")
    p = sub.add_parser("check")
    p.add_argument("files", nargs="+")
    a = ap.parse_args()
    if a.cmd == "layers":
        cmd_layers(a)
    elif a.cmd == "tga":
        cmd_tga(a)
    else:
        for f in a.files:
            print(header(f))


if __name__ == "__main__":
    main()
