"""Referee for the glyph set: proves that no two of the 182 exported glyphs
read as the same symbol on screen.

Why this has to exist as a script rather than a careful look: a key is 2 grid
gods + 2 diamond gods, and ANY pair is drawable, so every glyph has to be
distinct from every other glyph -- 16,471 pairs. And because the fix for a
collision is to add a small mark to one of the two, every fix can create a
NEW collision somewhere else in the set (doubling a bar to separate two of
Phantasos' cells, for instance, lands straight on Mnemon's North arm, which
is already two horizontal bars). Only an exhaustive re-check after each edit
can tell you that you're actually finished.

Run after extract_assets.py:

    python check_glyph_distinctness.py

Exits non-zero, listing the offending groups, if any pair collides.

## The metric

Two glyphs count as the same symbol when, after being centered and scaled to
a common size, the leftover difference between them is too small/too diffuse
to see. Getting that right took three attempts, and the two rejected ones are
recorded here because both look reasonable until tested:

  - Raw IoU on the shipped bitmaps. Rejected: it is scale-sensitive, so the
    same shape drawn at two sizes scores as different -- yet the UI boosts
    small glyphs toward a common fill (see glyph-render.js fillScale), so
    they DO land on screen at the same size and read as identical.

  - Symmetric difference (XOR) area after normalizing scale. Rejected in the
    other direction: it counts a uniformly thicker stroke as a large
    difference. Dolos and Kolax share eight cells drawn identically, differing
    only in scan stroke weight, and XOR happily scored them as distinct.

What both miss is that stroke weight is noise while structure is signal. So:
dilate each mask by ROUGH_STROKE before comparing, and keep only the parts of
each glyph that fall outside the other's dilated body. A slightly fatter
stroke is swallowed by the tolerance; a dot, an added tick, or a different
topology survives it. Then require what survives to form one connected blob of
at least MIN_VISIBLE_BLOB px -- a difference scattered as single pixels around
an outline is not something an eye picks up at 24px.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"

GRID9_POS = [f"grid9_{i}" for i in range(1, 10)]
DIAMOND4_POS = [f"diamond4_{d}" for d in ("N", "E", "S", "W")]
POSITIONS = GRID9_POS + DIAMOND4_POS

# Comparison canvas. Bigger than the 24px the message stream actually renders
# at, so the tolerances below can be expressed in whole pixels without
# rounding swamping them; the ratios are what matter, not the absolute size.
COMPARE = 48
# Stroke-weight tolerance, ~6% of the glyph box: a stroke up to this much
# fatter than its twin is treated as the same stroke.
ROUGH_STROKE = 3
# Smallest connected difference that still reads as a mark on screen.
MIN_VISIBLE_BLOB = 10


def normalized(path: Path) -> np.ndarray:
    """Ink mask cropped to its bounding box, uniformly scaled so its longer
    side is COMPARE, and centered -- i.e. exactly what the eye compares once
    the assets are centered and the UI has boosted them toward a common size.
    Aspect ratio is preserved, so a horizontal bar never normalizes into a
    vertical one."""
    alpha = np.array(Image.open(path).convert("RGBA"))[:, :, 3]
    ys, xs = np.nonzero(alpha > 8)
    if len(xs) == 0:
        return np.zeros((COMPARE, COMPARE), bool)
    cropped = Image.fromarray(alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    w, h = cropped.size
    scale = COMPARE / max(w, h)
    cropped = cropped.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    canvas = Image.new("L", (COMPARE, COMPARE), 0)
    canvas.paste(cropped, ((COMPARE - cropped.size[0]) // 2,
                           (COMPARE - cropped.size[1]) // 2))
    return np.array(canvas) > 96


def residual_difference(a: np.ndarray, b: np.ndarray,
                        a_fat: np.ndarray, b_fat: np.ndarray) -> int:
    """Largest connected piece of either glyph lying outside the other's
    stroke-weight tolerance. 0 means the two are the same symbol."""
    diff = (a & ~b_fat) | (b & ~a_fat)
    if not diff.any():
        return 0
    labels, n = ndimage.label(diff, structure=np.ones((3, 3)))
    if n == 0:
        return 0
    return int(ndimage.sum(diff, labels, index=range(1, n + 1)).max())


def load_all() -> dict:
    glyphs = {}
    for god_dir in sorted(p for p in ASSETS.iterdir() if p.is_dir()):
        for pos in POSITIONS:
            f = god_dir / f"{pos}.png"
            if f.exists():
                glyphs[(god_dir.name, pos)] = normalized(f)
    return glyphs


def find_collisions(glyphs: dict) -> list:
    fat = {k: ndimage.binary_dilation(v, iterations=ROUGH_STROKE)
           for k, v in glyphs.items()}
    keys = list(glyphs)
    hits = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            if residual_difference(glyphs[a], glyphs[b], fat[a], fat[b]) < MIN_VISIBLE_BLOB:
                hits.append((a, b))
    return hits


def group(hits: list, keys: list) -> list:
    """Collisions are transitive in practice (three gods sharing one bar), so
    report connected groups rather than raw pairs -- a group of n needs n-1
    fixes, which is the number that actually matters."""
    parent = {k: k for k in keys}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in hits:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    clusters = {}
    for k in keys:
        clusters.setdefault(find(k), []).append(k)
    return [sorted(v) for v in clusters.values() if len(v) > 1]


# Pairs this metric flags but a human has looked at and cleared. The tolerance
# that lets it see past stroke weight also blurs a solid disc into a bar of
# similar extent, so a "T with a dot on the stem" and a "T with a crossbar"
# score as the same symbol while reading as obviously different on screen --
# confirmed by eye at 96, 42 and 24px. Keep this list short and only add to it
# after actually looking at the two glyphs side by side.
ACCEPTED = {
    (("dolos", "diamond4_N"), ("kolax", "grid9_2")),
    (("dolos", "diamond4_E"), ("kolax", "grid9_6")),
}


def main() -> int:
    glyphs = load_all()
    if not glyphs:
        print("no glyphs found under assets/ -- run extract_assets.py first")
        return 2
    hits = [h for h in find_collisions(glyphs)
            if tuple(sorted(h)) not in {tuple(sorted(a)) for a in ACCEPTED}]
    groups = group(hits, list(glyphs))
    total = len(glyphs)
    involved = sum(len(g) for g in groups)
    fixes = involved - len(groups)

    print(f"{total} glyphs, {total * (total - 1) // 2} pairs compared "
          f"(tolerance {ROUGH_STROKE}px @ {COMPARE}px, visible blob {MIN_VISIBLE_BLOB}px)")
    if not groups:
        print("OK: every glyph is visually distinct from every other.")
        return 0

    print(f"\nFAIL: {len(groups)} collision groups, {involved} glyphs involved, "
          f"{fixes} need a distinguishing mark\n")
    for g in sorted(groups, key=lambda g: (-len(g), g)):
        print(f"  [{len(g)}] " + " = ".join(f"{god}/{pos}" for god, pos in g))
    return 1


if __name__ == "__main__":
    sys.exit(main())
