#!/usr/bin/env python3
"""Make a car spec map (car_spec_<id>.tga) from a car template and a finished paint.

    python -I spec.py TEMPLATE.psd PAINT.tga OUT.tga --base 0,45,0 \\
        [--rule "#151515=0,115,0"] [--rule "#c0c0c0=255,60,0"] [--tolerance 40] \\
        [--keep lettering.png] [--keep-value 0,45,0] [--preview OUT.png]

Channels: R metallic, G roughness, B clearcoat, each 0-255 (lower G is glossier).
The template's own "Custom Spec Map" group gives the starting values: its "Parts" layers
(glass, rubber, chrome, the parts the sim draws) keep exactly the template's numbers, and
only the paint ("Base Paint", everything that is not a part) is set here:
  --base     R,G,B for all paint
  --rule     paint whose colour is within --tolerance of HEX gets R,G,B (later rules win),
             e.g. a satin ink under a gloss body, or metal flake on one colour only
  --keep     a PNG layer (full canvas RGBA) whose opaque pixels get --keep-value even if a
             rule matched: lettering that should stay gloss on a satin ground
The result is 24-bit RLE at the template's size; a softening of 0.8 px keeps edges clean.
"""
import argparse
import sys

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from scipy import ndimage as ndi

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from compose import layer_rgba  # noqa: E402


def triple(s):
    v = [int(x) for x in s.split(",")]
    if len(v) != 3 or not all(0 <= x <= 255 for x in v):
        raise argparse.ArgumentTypeError("expected R,G,B with 0-255 each")
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template")
    ap.add_argument("paint")
    ap.add_argument("out")
    ap.add_argument("--base", type=triple, required=True)
    ap.add_argument("--rule", action="append", default=[])
    ap.add_argument("--tolerance", type=int, default=40)
    ap.add_argument("--keep")
    ap.add_argument("--keep-value", type=triple)
    ap.add_argument("--preview")
    a = ap.parse_args()

    psd = PSDImage.open(a.template)
    w, h = psd.size
    group = next((l for l in psd if l.name == "Custom Spec Map"), None)
    if group is None:
        sys.exit('no "Custom Spec Map" group in the template')
    channels = {}
    parts = np.zeros((h, w), bool)
    for ch in group:
        key = "R" if "red" in ch.name.lower() else "G" if "green" in ch.name.lower() else "B"
        value = np.zeros((h, w))
        for layer in ch:
            rgba = layer_rgba(layer, psd.size)
            al = rgba[..., 3] / 255
            value = value * (1 - al) + rgba[..., 0] * al
            if "part" in layer.name.lower():
                parts |= al > 0.5
        channels[key] = value
    template = np.stack([channels.get(k, np.zeros((h, w))) for k in "RGB"], -1)

    paint = np.array(Image.open(a.paint).convert("RGB")).astype(int)
    if paint.shape[:2] != (h, w):
        sys.exit(f"paint is {paint.shape[1]}x{paint.shape[0]}, template is {w}x{h}")
    finish = np.zeros((h, w, 3))
    finish[:] = a.base
    for rule in a.rule:
        hexc, _, val = rule.partition("=")
        c = np.array([int(hexc.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)])
        hit = np.abs(paint - c).max(-1) <= a.tolerance
        finish[hit] = triple(val)
        print(f"rule {rule}: {hit[~parts].mean() * 100:.1f}% of the paint")
    if a.keep:
        if not a.keep_value:
            sys.exit("--keep needs --keep-value")
        k = np.array(Image.open(a.keep).convert("RGBA"))[..., 3] > 128
        finish[k] = a.keep_value
    for i in range(3):
        finish[..., i] = ndi.gaussian_filter(finish[..., i], 0.8)
    spec = np.where(parts[..., None], template, finish)
    spec = np.clip(np.round(spec), 0, 255).astype(np.uint8)
    Image.fromarray(spec).save(a.out, compression="tga_rle")
    print(f"wrote {a.out}: parts kept from the template on {parts.mean() * 100:.1f}% of the sheet")
    if a.preview:
        Image.fromarray(spec).resize((w // 2, h // 2), Image.LANCZOS).save(a.preview)


if __name__ == "__main__":
    main()
