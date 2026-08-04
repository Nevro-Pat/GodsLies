"""Render a god's glyphs to a PNG you can actually look at, plus a geometry
audit of the things the eye measures badly.

    python preview_glyphs.py kolax
    python preview_glyphs.py kolax --from <dir>        # proposed PNGs, not assets/
    python preview_glyphs.py kolax --ref sketch.png    # paste a reference alongside

Why this exists: four glyph proposals in a row were rejected on sight because
they were only ever checked numerically and as ASCII art. Both misled --
downsampling a 24px render into 2x2 blocks closes a 1px gap, so "the bars
merge" was reported when they were separate, and the reverse the next round.
Worse, the metrics answered "is there a measurable difference?" rather than
"does it look right?": a bar offset 8px sideways passes every numeric test and
is obvious to the eye.

So the loop is: generate -> run this -> LOOK at the image -> only then respond.
The audit does not replace the look, it covers the other half: numbers catch a
3px asymmetry, the eye catches "that isn't the drawing".
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"

# the app's own colours, so the preview matches what ships (see css/base.css)
BG = (42, 34, 25)
INK = (255, 248, 236)
ACCENT = (217, 154, 78)
MUTED = (140, 122, 100)

GRID9 = [f"grid9_{i}" for i in range(1, 10)]
DIAMOND4 = [f"diamond4_{d}" for d in "NESW"]
CHART_PX, STREAM_PX = 42, 24     # the two sizes the UI actually renders at


def load(god, pos, src):
    f = src / f"{pos}.png"
    return Image.open(f).convert("RGBA") if f.exists() else None


def tint(glyph, size, colour=INK):
    """Ink is black-on-transparent; the UI inverts it for dark mode. Do the
    same here or the preview is a black square on a dark ground."""
    g = glyph.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", g.size, colour + (255,))
    out.putalpha(g.getchannel("A"))
    return out


def label(draw, xy, text, colour=MUTED, size=13):
    from PIL import ImageFont
    try:
        font = ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    draw.text(xy, text, fill=colour, font=font)


def contact_sheet(god, src, ref=None):
    from PIL import ImageDraw
    cell, gap, pad, head = 128, 10, 30, 34
    positions = [p for p in GRID9 if (src / f"{p}.png").exists()]
    arms = [p for p in DIAMOND4 if (src / f"{p}.png").exists()]

    grid_w = cell * 3 + gap * 2
    width = pad * 2 + grid_w * 2 + 60
    height = pad * 2 + head + grid_w + 90 + (cell // 2 + 40 if arms else 0)
    sheet = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(sheet)

    label(d, (pad, pad), f"{god.upper()}  ·  tuile 3x3, taille d'examen", ACCENT, 15)
    for i, p in enumerate(GRID9):
        g = load(god, p, src)
        if g is None:
            continue
        r, c = divmod(i, 3)
        x, y = pad + c * (cell + gap), pad + head + r * (cell + gap)
        sheet.paste(tint(g, cell), (x, y), tint(g, cell))
        label(d, (x + 2, y + 2), str(i + 1), MUTED, 11)

    # real display sizes, side by side, on the same ground
    x0 = pad + grid_w + 60
    label(d, (x0, pad), "aux tailles reelles", ACCENT, 15)
    y = pad + head
    for name, size in (("grille alphabet · 42 px", CHART_PX),
                       ("flux de message · 24 px", STREAM_PX)):
        label(d, (x0, y), name, MUTED, 12)
        y += 20
        for i, p in enumerate(GRID9):
            g = load(god, p, src)
            if g is None:
                continue
            sheet.paste(tint(g, size), (x0 + i * (size + 6), y), tint(g, size))
        y += size + 26

    if arms:
        label(d, (x0, y), "bras diamant", MUTED, 12)
        y += 20
        for i, p in enumerate(arms):
            g = load(god, p, src)
            sheet.paste(tint(g, cell // 2), (x0 + i * (cell // 2 + 8), y),
                        tint(g, cell // 2))

    if ref and Path(ref).exists():
        r = Image.open(ref).convert("RGB")
        scale = min(1.0, (height - pad * 2) / r.height)
        r = r.resize((int(r.width * scale), int(r.height * scale)), Image.LANCZOS)
        joined = Image.new("RGB", (width + r.width + 30, max(height, r.height)), BG)
        joined.paste(sheet, (0, 0))
        joined.paste(r, (width + 30, 0))
        dd = ImageDraw.Draw(joined)
        label(dd, (width + 30, 6), "REFERENCE", ACCENT, 15)
        sheet = joined
    return sheet


# ----------------------------------------------------------------- audit ---
def ink(im):
    return np.array(im)[:, :, 3] > 8


def line_profile(m, axis):
    src = m if axis == 1 else m.T
    out = np.zeros(src.shape[0], int)
    for k, line in enumerate(src):
        i = np.flatnonzero(line)
        if len(i):
            out[k] = max(len(s) for s in np.split(i, np.flatnonzero(np.diff(i) != 1) + 1))
    return out


def stroke_centre(m, axis):
    """Centre of the dominant stroke on that axis -- NOT the first line hitting
    the maximum, which is its leading edge. Anchoring on the edge is what put
    every crossing bar half a stroke off to one side."""
    prof = line_profile(m, axis)
    peak = int(np.argmax(prof))
    hot = prof >= prof.max() * 0.8
    lo = hi = peak
    while lo - 1 >= 0 and hot[lo - 1]:
        lo -= 1
    while hi + 1 < len(hot) and hot[hi + 1]:
        hi += 1
    return (lo + hi) / 2.0, int(prof.max())


def audit(god, src, base=ASSETS):
    """Compare proposal against the shipped asset and report the geometry that
    the eye judges poorly: is the added mark centred, how far is it, how thick."""
    print(f"\naudit geometrique — {god}")
    print(f"  {'case':6s} {'ajout':>7s} {'ecart':>7s} {'debord A/B':>13s} {'ecart':>7s} {'trait':>6s}")
    rows = 0
    for p in GRID9 + DIAMOND4:
        new_f, old_f = src / f"{p}.png", base / god / f"{p}.png"
        if not (new_f.exists() and old_f.exists()):
            continue
        new, old = ink(Image.open(new_f).convert("RGBA")), ink(Image.open(old_f).convert("RGBA"))
        if new.shape != old.shape:
            continue
        added = new & ~ndimage.binary_dilation(old, iterations=1)
        if added.sum() < 30:
            continue
        rows += 1
        ys, xs = np.nonzero(added)
        horiz = (xs.max() - xs.min()) >= (ys.max() - ys.min())
        thick = int(np.median(line_profile(added, 0 if horiz else 1)[
            np.flatnonzero(line_profile(added, 0 if horiz else 1))])) if added.any() else 0
        if horiz:
            cx, _ = stroke_centre(old, 0)          # vertical stem it crosses
            a, b = cx - xs.min(), xs.max() - cx
            cy_base, _ = stroke_centre(old, 1)     # horizontal base bar
            gap = abs((ys.min() + ys.max()) / 2 - cy_base)
            kind = "horiz."
        else:
            cy, _ = stroke_centre(old, 1)
            a, b = cy - ys.min(), ys.max() - cy
            cx_base, _ = stroke_centre(old, 0)
            gap = abs((xs.min() + xs.max()) / 2 - cx_base)
            kind = "vert."
        flag = "  <-- decentre" if abs(a - b) > 2 else ""
        print(f"  {p:6s} {kind:>7s} {gap:6.0f}px {a:5.0f}/{b:<5.0f}px "
              f"{abs(a-b):5.0f}px {thick:4d}px{flag}")
    if rows == 0:
        print("  (aucune marque ajoutee detectee)")
    print("  rappel : debord A/B doit etre egal a ~1px pres, ecart vise 52px "
          "(2x le diametre d'un point)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("god")
    ap.add_argument("--from", dest="src", default=None,
                    help="directory of proposed PNGs (defaults to assets/<god>)")
    ap.add_argument("--ref", default=None, help="reference image to paste alongside")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    src = Path(a.src) if a.src else ASSETS / a.god
    if not src.exists():
        print(f"not found: {src}")
        return 2
    sheet = contact_sheet(a.god, src, a.ref)
    out = Path(a.out) if a.out else ROOT / f"preview_{a.god}.png"
    sheet.save(out)
    print(f"ecrit {out}  ({sheet.width}x{sheet.height})")
    print(">>> REGARDE cette image avant de repondre quoi que ce soit <<<")
    audit(a.god, src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
