#!/usr/bin/env python3
"""A worked full wrap for a made-up brand, "Brightwater" (a radio station), on the
Global Mazda MX-5 Cup template (MX-5 2016), plus its helmet. Copy it, swap the brand.

    python -I example_kit.py --car-islands car_map/islands.npy \\
        --helmet-islands helmet_map/islands.npy --font BrandBold.ttf --out kit/

Writes full-canvas RGBA layers to kit/car/*.png and kit/helmet/*.png, lowest first in
kit/car/order.txt and kit/helmet/order.txt, for compose.py layers.

The design: the brand's posters as a wall of blocks leaning forward along the sides, one
poster per block; four posters on the hood; a bold nose; a quarter-disc grid (a
chequered flag) on the tail; the name on plates with a keyline; light number panels; the
web address on a dark sill. Every coordinate below is for this template only: read your
own car's from template_map.py's grid.png (references/mx5-2016.md explains these).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
from livery import (Canvas, Frame, arch, clip, disc_diagonal, dot_grid, fit, halves,  # noqa: E402
                    island_at, island_mask, lean_block, outside_share, plate, quarter_grid,
                    rgb, save_layer, solid, text, union)

# The brand (made up). Posters use a ground, a first and a second colour each.
CREAM, INK = rgb("#f4efe6"), rgb("#151515")
TEAL, CORAL, SUN, SKY, PLUM = rgb("#0f7c7a"), rgb("#ff6b4a"), rgb("#ffc23d"), rgb("#8ecae6"), rgb("#5b3a82")
NAME, URL = "BRIGHTWATER", "BRIGHTWATER.FM"

# MX-5 2016 template facts (references/mx5-2016.md)
FLIP = 2490                 # right side island = left side flipped: y_right = 2490 - y_left
NUMBER_PANEL = (468, 1790, 640, 1950)    # around the door's number block, left side coordinates
REAR_NUMBER = (338, 220, 442, 325)       # the rear bumper's number block
REAR_BUMPER = (0, 92, 1215, 470)         # the rear bumper is not one closed island here: use its box


def car(islands, font, out):
    P = lambda x, y: island_at(islands, x, y)  # noqa: E731
    left, right, hood, front = P(900, 1800), P(900, 690), P(368, 1245), P(1300, 1000)
    trunk, arc_, strip = P(1547, 394), P(1547, 62), P(726, 1246)
    M = {k: island_mask(islands, [v]) for k, v in
         dict(left=left, right=right, hood=hood, front=front, trunk=trunk).items()}
    S = 2048
    layers = {}
    layers["Brand body"] = solid(INK, S)

    # Sides: one drawing, rendered twice (the right side with flip). Blocks lean forward:
    # the nose is at small x, so a positive shear (anchored at the bottom) moves the top
    # edge towards smaller x.
    def side(flip=None):
        c = Canvas(S, TEAL, flip)
        top, bottom = 1560, 2060
        lean_block(c, -200, 430, top, bottom, 0.3, TEAL,
                   lambda f, w: (f.disc(450, 150, 62, CREAM), f.rect(0, 196, 700, 400, CORAL)))
        lean_block(c, 430, 655, top, bottom, 0.3, SUN, lambda f, w: arch(f, 110, 78, 128, 600, INK, TEAL))
        lean_block(c, 655, 875, top, bottom, 0.3, SKY,
                   lambda f, w: disc_diagonal(f, 105, 170, 88, TEAL, INK, -70, w + 70, 236, 96))
        lean_block(c, 875, 1095, top, bottom, 0.3, CORAL, lambda f, w: halves(f, 112, 150, 78, INK, CREAM, 34, 9))
        lean_block(c, 1095, 1310, top, bottom, 0.3, PLUM, lambda f, w: dot_grid(f, -12, 52, 4, 7, 62, SUN, CREAM, seed=5))
        lean_block(c, 1310, 2300, top, bottom, 0.3, INK, lambda f, w: quarter_grid(f, -60, 34, 14, 8, 56, CREAM, SUN, seed=23))
        c.rect(0, 1950, S, 2100, INK)  # the sill, for the web address
        return c.out()
    layers["Brand sides"] = union(clip(side(), M["left"]), clip(side(FLIP), M["right"]))

    # Hood: its UV runs sideways (the car's nose at small x), so draw in a frame turned
    # -90 degrees: u runs along the car's width, v from the windshield towards the nose.
    h = Canvas(S, TEAL)
    def quad(x0, x1, y0, y1, ground, fn):
        t = Canvas(S, ground)
        fn(Frame(t, lambda u, v: (x1 - v, y0 + u)), y1 - y0, x1 - x0)
        h.paste_masked(t, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    quad(368, 800, 800, 1245, CORAL, lambda f, w, hh: halves(f, w - 190, hh - 205, 120, INK, CREAM, 40, 12))
    quad(368, 800, 1245, 1700, PLUM, lambda f, w, hh: dot_grid(f, 18, hh - 345, 4, 4, 84, SUN, CREAM, seed=9))
    quad(-50, 368, 1245, 1700, SUN, lambda f, w, hh: arch(f, 165, hh - 330, 190, hh + 50, INK, TEAL))
    layers["Brand hood"] = clip(h.out(), M["hood"])
    layers["Brand front"] = clip(solid(SUN, S), M["front"])

    rear = Canvas(S, INK)
    quarter_grid(Frame(rear, lambda u, v: (u, v)), 1232, 246, 7, 3, 90, CREAM, SUN, seed=41)
    layers["Brand rear"] = clip(rear.out(), M["trunk"])

    # Lettering on top. Number panels: light, plain, around the sim's number blocks.
    c = Canvas(S)
    for flip, angle in ((None, 0), (FLIP, 180)):
        panel = Canvas(S, None, flip)
        panel.rect(*NUMBER_PANEL, CREAM)
        c.im.alpha_composite(panel.im)
        y = (lambda v: v) if flip is None else (lambda v: FLIP - v)
        name = plate(fit([(NAME, INK)], 74, font, 540), CREAM, keyline=INK)
        c.paste(name, 950, y(1870), angle)              # the right side reads turned 180 in the UV
        c.paste(text([(URL, CREAM)], 22, font, 0.3), 990, y(1989), angle)
    c.paste(plate(fit([(NAME, INK)], 60, font, 560), CREAM, keyline=INK), 368, 1245, -90)   # hood: -90
    c.paste(plate(fit([(NAME, INK)], 60, font, 440), CREAM, keyline=INK), 1547, 394, 0)     # trunk: upright in the UV
    # front bumper: two small words above the side intakes, clear of the stamped plate and
    # emblem in the middle; each fits a 125 x 30 box
    small = fit([(NAME, INK)], 30, font, 125)
    c.paste(small, 1010, 1085)
    c.paste(small, 1690, 1085)
    c.rect(*REAR_NUMBER, CREAM)
    c.paste(fit([(URL, CREAM)], 34, font, 480, 0.2), 1547, 62, 180)     # the windshield header (the arc), read from ahead
    c.paste(fit([(URL, CREAM)], 36, font, 520, 0.14), 726, 1246, -90)   # the strip behind the hood
    layers["Brand lettering"] = c.out()

    every = island_mask(islands, [left, right, hood, front, trunk, arc_, strip])
    x0, y0, x1, y1 = REAR_BUMPER
    every[y0:y1, x0:x1] = 1
    share = outside_share(layers["Brand lettering"], every)
    print(f"car lettering outside its panels: {share * 100:.2f}%")
    if share >= 0.002:
        save_layer(layers["Brand lettering"], os.path.join(out, "debug_lettering.png"))
    assert share < 0.002, "a word falls off its panel: move it"
    write(layers, os.path.join(out, "car"))


def helmet(islands, font, out):
    """Helmet rules from the sim (1024 template): the shell is one island; its centre top
    (x ~512, y ~720) is the front, under a seam; side art stays behind x=810 and in front
    of x=1000 (mirror: 24..214) or the visor hinge covers it."""
    S = 1024
    shell = island_mask(islands, [island_at(islands, 170, 845)])
    c = Canvas(S, CREAM)
    for x0, mirror in ((810, False), (24, True)):
        t = Canvas(S, CORAL)
        f = Frame(t, lambda u, v, x0=x0: (x0 + u, 760 + v))
        halves(f, 95, 85, 70, INK, CREAM, 20, 6)
        c.paste_masked(t, [(x0, 760), (x0 + 190, 760), (x0 + 190, 950), (x0, 950)])
    t = Canvas(S)
    word = fit([(NAME, INK)], 36, font, 220)       # the brow above the visor is narrow
    t.paste(word, 512, 788 - 18)                   # front: small, its foot at y=788, clear of the seam
    side = fit([(NAME, INK)], 22, font, 160)
    sw = side.shape[1] / 2
    for cx in (905, 1024 - 905):
        assert 810 <= cx - sw / 2 and cx + sw / 2 <= 1000 or 24 <= cx - sw / 2 and cx + sw / 2 <= 214, \
            "side word inside the visor zone"
        t.paste(plate(side, CREAM), cx, 930)
    write({"Brand body": solid(INK, S), "Brand shell": clip(c.out(), shell), "Brand lettering": clip(t.out(), shell)},
          os.path.join(out, "helmet"))


def write(layers, folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "order.txt"), "w") as f:
        for name, rgba in layers.items():
            path = os.path.join(folder, name.replace(" ", "_").lower() + ".png")
            save_layer(rgba, path)
            f.write(f"{name}={path}\n")
    print(f"wrote {len(layers)} layers to {folder}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--car-islands", required=True)
    ap.add_argument("--helmet-islands")
    ap.add_argument("--font", required=True, help="the brand's bold display face (.ttf/.otf)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    car(np.load(a.car_islands), a.font, a.out)
    if a.helmet_islands:
        helmet(np.load(a.helmet_islands), a.font, a.out)


if __name__ == "__main__":
    main()
