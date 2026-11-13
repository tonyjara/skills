"""Drawing helpers for iRacing paints: import this from a kit script.

    import sys; sys.path.insert(0, "<this skill>/scripts")
    from livery import *

Everything is drawn in template pixels on a supersampled canvas (SS x the template size)
and comes back as a float RGBA array of the template's size, ready to clip to a panel and
save as a PSD layer. Shapes follow a poster vocabulary that wraps well: discs, half and
quarter discs, arches, bars, dot grids, quarter-disc grids, a disc cut by a diagonal.

Three things this module exists for, learnt the hard way:
  * one drawing for both sides of the car: a Canvas with `flip` mirrors y, so the right
    side's island (often the left one flipped vertically in the UV) gets the same graphics;
  * text at any angle: paste(..., angle) turns a rendered word; panels whose UV runs
    sideways (hoods) or upside down (trunks, right sides) need 90 or 180 degrees;
  * clipping: clip(layer, island_mask(...)) keeps a panel's art on its panel, grown by a
    few pixels so no seam shows the base colour.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

SS = 2  # supersampling factor


def rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Canvas:
    """A drawing surface in template pixels. ground=None is transparent.
    flip=Y mirrors every y as Y - y (draw the left side once, render the right side with it)."""

    def __init__(self, size, ground=None, flip=None):
        self.size, self.flip = size, flip
        fill = (tuple(ground) + (255,)) if ground is not None else (0, 0, 0, 0)
        self.im = Image.new("RGBA", (size * SS, size * SS), fill)
        self.d = ImageDraw.Draw(self.im)

    def pt(self, p):
        x, y = p
        if self.flip is not None:
            y = self.flip - y
        return (x * SS, y * SS)

    def poly(self, pts, fill):
        self.d.polygon([self.pt(p) for p in pts], fill=tuple(fill) + (255,))

    def rect(self, x0, y0, x1, y1, fill):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill)

    def disc(self, cx, cy, r, fill):
        x, y = self.pt((cx, cy))
        self.d.ellipse([x - r * SS, y - r * SS, x + r * SS, y + r * SS], fill=tuple(fill) + (255,))

    def paste(self, rgba, cx, cy, angle=0):
        """Paste an RGBA array made by text()/plate() (already at SS scale), centred on
        (cx, cy) in template pixels, turned counter-clockwise by `angle` degrees."""
        im = Image.fromarray(np.clip(np.round(rgba), 0, 255).astype(np.uint8), "RGBA")
        if angle:
            im = im.rotate(angle, expand=True, resample=Image.BICUBIC)
        x, y = self.pt((cx, cy))
        self.im.alpha_composite(im, (int(round(x - im.width / 2)), int(round(y - im.height / 2))))

    def paste_masked(self, other, polygon):
        """Copy another canvas onto this one inside a polygon (template pixels)."""
        m = Image.new("L", self.im.size, 0)
        ImageDraw.Draw(m).polygon([self.pt(p) for p in polygon], fill=255)
        self.im.paste(other.im, (0, 0), m)

    def out(self):
        """Downsample to the template size: float RGBA (size, size, 4)."""
        small = self.im.convert("RGBa").resize((self.size, self.size), Image.LANCZOS).convert("RGBA")
        return np.array(small).astype(float)


def arc(cx, cy, r, a0, a1, n=96):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


class Frame:
    """A poster's own coordinates (u right, v down) placed on a canvas by a function
    P(u, v) -> (x, y). Use it to draw a composition inside a block, or turned for a hood."""

    def __init__(self, canvas, P):
        self.c, self.P = canvas, P

    def poly(self, pts, fill):
        self.c.poly([self.P(*p) for p in pts], fill)

    def rect(self, u0, v0, u1, v1, fill):
        self.poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], fill)

    def disc(self, u, v, r, fill):
        self.poly(arc(u, v, r, 0, 360, 120), fill)

    def half(self, u, v, r, facing, fill):
        a0, a1 = {"up": (180, 360), "down": (0, 180), "left": (90, 270), "right": (-90, 90)}[facing]
        self.poly(arc(u, v, r, a0, a1), fill)

    def quarter(self, u, v, r, corner, fill):
        """Square corner at (u, v); corner 0 bulges to +u+v, 1 to -u+v, 2 to -u-v, 3 to +u-v."""
        a0, a1 = {0: (0, 90), 1: (90, 180), 2: (180, 270), 3: (270, 360)}[corner]
        self.poly([(u, v)] + arc(u, v, r, a0, a1, 32), fill)


def seeded(seed):
    """A small deterministic random (mulberry32), so a seed always draws the same grid."""
    state = [seed & 0xFFFFFFFF]

    def mul(a, b):
        return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF

    def nxt():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        s = state[0]
        t = mul(s ^ (s >> 15), 1 | s)
        t = ((t + mul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return nxt


# --- poster compositions, each drawn in a Frame -------------------------------------

def arch(f, u, v_top, width, v_bottom, first, second, dot=0.42):
    """An arch standing on the bottom edge, with a disc in its crown."""
    r = width / 2
    f.poly([(u - r, v_bottom), (u - r, v_top + r)] + arc(u, v_top + r, r, 180, 360) + [(u + r, v_bottom)], first)
    f.disc(u, v_top + r, r * dot, second)


def halves(f, u, v, r, first, second, shift=30, gap=10):
    """Two half discs that do not quite meet."""
    f.half(u - shift / 2, v - gap, r, "up", first)
    f.half(u + shift / 2, v + gap, r, "down", second)


def dot_grid(f, u0, v0, cols, rows, cell, first, second, seed=7, r=0.34):
    """Dots in rows, a few of them squares or the second colour."""
    n = seeded(seed)
    for row in range(rows):
        for col in range(cols):
            roll = n()
            cu, cv = u0 + col * cell + cell / 2, v0 + row * cell + cell / 2
            if roll > 0.8:
                f.rect(cu - r * cell, cv - r * cell, cu + r * cell, cv + r * cell, second)
            else:
                f.disc(cu, cv, r * cell, second if roll < 0.12 else first)


def quarter_grid(f, u0, v0, cols, rows, cell, first, second, seed=11, skip=0.22):
    """Quarter discs on a grid, each turned its own way: reads as a chequered flag."""
    n = seeded(seed)
    for row in range(rows):
        for col in range(cols):
            roll = n()
            if roll < skip:
                continue
            corner = int(n() * 4)
            u = u0 + col * cell + (cell if corner in (1, 2) else 0)
            v = v0 + row * cell + (cell if corner in (2, 3) else 0)
            f.quarter(u, v, cell, corner, second if roll > 0.72 else first)


def bars(f, u0, v_tops, width, gap, v_bottom, fill):
    """Vertical bars standing on a baseline, one per entry of v_tops."""
    for i, top in enumerate(v_tops):
        u = u0 + i * (width + gap)
        f.rect(u, top, u + width, v_bottom, fill)


def disc_diagonal(f, u, v, r, first, second, u0, u1, v_at_u0, rise):
    """A disc, and everything below a rising diagonal in the second colour."""
    f.disc(u, v, r, first)
    f.poly([(u0, v_at_u0), (u1, v_at_u0 - rise), (u1, v_at_u0 + 5000), (u0, v_at_u0 + 5000)], second)


def lean_block(canvas, x0, x1, top, bottom, shear, ground, draw, anchor=None):
    """A block of the wrap leaning into the direction of travel: a parallelogram whose top
    edge is shifted by `shear` per pixel of height (negative leans towards smaller x).
    `draw(frame, width)` paints its poster in block coordinates (u from x0, v from top)."""
    anchor = bottom if anchor is None else anchor
    block = Canvas(canvas.size, ground, canvas.flip)
    draw(Frame(block, lambda u, v: (x0 + u, top + v)), x1 - x0)
    shape = [(x0 + shear * (top - anchor), top), (x1 + shear * (top - anchor), top),
             (x1 + shear * (bottom - anchor), bottom), (x0 + shear * (bottom - anchor), bottom)]
    canvas.paste_masked(block, shape)


# --- type -----------------------------------------------------------------------------

def text(parts, cap, font, track=0.0):
    """Set [(string, rgb), ...] in one line with a cap height of `cap` template pixels.
    track is extra letter spacing in units of the cap height. Returns RGBA at SS scale."""
    capp = cap * SS
    probe = ImageFont.truetype(font, 1000)
    b = probe.getbbox("H")
    f = ImageFont.truetype(font, 1000 * capp / (b[3] - b[1]))
    hb = f.getbbox("H")
    top, caph = hb[1], hb[3] - hb[1]
    tr = track * capp
    chars = [(ch, c) for t, c in parts for ch in t]
    x, pos = 0.0, []
    for ch, _ in chars:
        pos.append(x)
        x += f.getlength(ch) + tr
    m = int(0.05 * caph) + 2
    im = Image.new("RGBA", (int(x - tr + 2 * m + 4), int(caph + 2 * m)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for (ch, c), px in zip(chars, pos):
        d.text((px + m, m - top), ch, font=f, fill=tuple(c) + (255,))
    a = np.array(im)
    xs = np.nonzero(a[..., 3].max(0) > 8)[0]
    return a[:, xs.min():xs.max() + 1].astype(float)


def fit(parts, cap, font, max_width, track=0.0):
    """text(), with the cap height lowered until the line is at most max_width template
    pixels wide. Long brand names are the usual reason a word falls off its panel."""
    t = text(parts, cap, font, track)
    w = t.shape[1] / SS
    if w <= max_width:
        return t
    return text(parts, cap * max_width / w * 0.99, font, track)


def plate(word_rgba, ground, pad=0.28, keyline=None, keyline_width=0.08):
    """A name plate: the word on a solid rectangle, optionally inside a keyline of another
    colour (a must over busy patterns). Takes and returns RGBA at SS scale."""
    h, w = word_rgba.shape[:2]
    p = int(pad * h)
    k = int(keyline_width * h) if keyline is not None else 0
    out = np.zeros((h + 2 * (p + k), w + 2 * (p + k), 4))
    if keyline is not None:
        out[..., :3] = keyline
    out[..., 3] = 255
    out[k:k + h + 2 * p, k:k + w + 2 * p, :3] = ground
    a = word_rgba[..., 3:] / 255
    y, x = k + p, k + p
    out[y:y + h, x:x + w, :3] = out[y:y + h, x:x + w, :3] * (1 - a) + word_rgba[..., :3] * a
    return out


# --- layers ---------------------------------------------------------------------------

def solid(colour, size):
    o = np.zeros((size, size, 4))
    o[..., :3] = colour
    o[..., 3] = 255
    return o


def over(base, layer):
    a = layer[..., 3:] / 255
    return base * (1 - a) + layer[..., :3] * a


def clip(layer, mask):
    o = layer.copy()
    o[..., 3] *= mask
    return o


def union(*layers):
    """Stack several layers into one (later ones on top)."""
    out = np.zeros_like(layers[0])
    for lay in layers:
        a = lay[..., 3:] / 255
        oa = out[..., 3:] / 255
        na = a + oa * (1 - a)
        out[..., :3] = np.where(na > 0, (lay[..., :3] * a + out[..., :3] * oa * (1 - a)) / np.maximum(na, 1e-9), 0)
        out[..., 3:] = na * 255
    return out


def island_mask(islands, ids, grow=4):
    """A float mask of the given island ids, grown by `grow` pixels to cover the seams."""
    m = np.isin(islands, ids)
    if grow:
        m = ndi.binary_dilation(m, iterations=grow)
    return m.astype(float)


def island_at(islands, x, y):
    """The island id under a template pixel: find panels by a point you read on grid.png."""
    i = int(islands[y, x])
    if i == 0:
        raise ValueError(f"({x}, {y}) is not on a paintable island")
    return i


def outside_share(layer, mask):
    """How much of a layer's ink falls outside a mask (0..1): assert it is ~0 for lettering."""
    a = layer[..., 3] / 255
    return float((a * (1 - mask)).sum() / max(a.sum(), 1))


def save_layer(rgba, path):
    Image.fromarray(np.clip(np.round(rgba), 0, 255).astype(np.uint8), "RGBA").save(path)
