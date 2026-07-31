"""Build a real, installable Windows font (.ttf) from a Gods Lies key --
type normally in any application (Word, Notepad, a browser, ...) and see
your own cipher symbols in place of A-Z. The same PNG glyphs the
browser/CLI tools render are vectorized (marching-squares contour trace
via scikit-image, simplified, then built into TrueType outlines with
fontTools) so the font shows your exact hand-drawn symbols, not a
redrawn approximation.

    python make_font.py keys/mykey.json
    python make_font.py keys/mykey.json -o MyCipher.ttf --name "Gods Lies - mykey"

Then in Windows: right-click the .ttf -> Install (or "Install for all
users"), and pick it from the font list in any app like any other
typeface.

A-Z/a-z (case-insensitive, same as the cipher itself), space, and
accented Latin letters (e, a, n~, etc. -- same base-letter fold the
browser/CLI tools already apply before enciphering) get a glyph. Digits,
punctuation, and ligatures (oe, ae, ss, o-with-stroke) are deliberately
left undefined -- the browser/CLI tools pass digits/punctuation through
unciphered too (see godslies.py's encode()), and drawing a full
placeholder alphabet for them here would be an unrelated typeface, out
of scope for "a font for this key".

Requires: fontTools, scikit-image, numpy, Pillow --
    pip install fonttools scikit-image numpy pillow
"""
from __future__ import annotations

import argparse
import json
import string
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import measure

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from godslies import Key, glyph_asset, asset_path, GODS

ROOT = Path(__file__).parent
GRID9_POSITIONS = list(range(1, 10))
DIAMOND4_POSITIONS = ["N", "E", "S", "W"]

UNITS_PER_EM = 1000
# Every cipher symbol is scaled to fit under this height, sitting on the
# baseline -- there's no real cap-height/x-height to preserve since a-z
# reuse the exact same glyph as A-Z (the cipher itself is
# case-insensitive), so each symbol gets dingbat/symbol-font treatment
# instead of normal Latin-letter metrics.
GLYPH_TOP = 720
ADVANCE_WIDTH = 820
SPACE_WIDTH = 500
ASCENT = 900
DESCENT = -200

# Every letter also gets a second cmap entry at a Private Use Area
# codepoint (Unicode guarantees U+E000-U+F8FF is never assigned a real
# character by any font/OS), pointing at the same glyph as the plain
# letter. A font only changes how a letter DISPLAYS, not what's actually
# stored, so typed/copied plain text always round-trips back to the real
# message the instant it's viewed without this font. Enciphering to these
# PUA codepoints instead of plain letters (see godslies.html's matching
# textToCipherFontText()/PUA_BASE) keeps the stored text meaningless
# outside this specific font's cmap -- not readable by casual copy-paste.
PUA_BASE = 0xE000


def _simplify(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Ramer-Douglas-Peucker. Marching squares emits one point per traced
    pixel edge (hundreds per glyph) -- far more detail than a clean font
    outline needs, and it makes for a needlessly heavy/jittery shape.
    Keeps only the points a straight segment between two ends can't
    already approximate within `tolerance` px."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    line = end - start
    line_len = np.hypot(*line)
    diffs = points - start
    if line_len == 0:
        dists = np.hypot(*diffs.T)
    else:
        # 2D cross product z-component (perpendicular distance to the
        # line) -- np.cross() itself now refuses plain 2D vectors, so
        # this is the same lx*dy - ly*dx computed by hand.
        cross_z = line[0] * diffs[:, 1] - line[1] * diffs[:, 0]
        dists = np.abs(cross_z) / line_len
    idx = int(np.argmax(dists))
    if dists[idx] > tolerance:
        left = _simplify(points[:idx + 1], tolerance)
        right = _simplify(points[idx:], tolerance)
        return np.vstack([left[:-1], right])
    return np.array([start, end])


def trace_polygons(png_path: Path):
    """Binary alpha mask -> simplified closed polygons, in image pixel
    (row, col) coordinates. extract_assets.py's clean_cell() already
    produces a pure black-ink-on-transparent PNG with no antialiasing, so
    a flat alpha>127 threshold is all marching squares needs to find
    crisp ink boundaries -- including both the outer and inner edge of a
    stroke that encloses empty space (e.g. Hermès' closed-box center
    cell), which is what makes that read as a ring instead of a solid
    square once wound onto the font (see build_glyph)."""
    img = Image.open(png_path).convert("RGBA")
    alpha = np.array(img)[:, :, 3]
    mask = alpha > 127
    if not mask.any():
        return [], img.size
    padded = np.pad(mask, 1, mode="constant", constant_values=False)
    raw_contours = measure.find_contours(padded.astype(float), level=0.5)
    polys = []
    for c in raw_contours:
        c = c - 1  # undo the padding offset
        if len(c) > 1 and np.allclose(c[0], c[-1]):
            c = c[:-1]  # closed loop -- drop the duplicated closing point
        simplified = _simplify(c, tolerance=1.2)
        if len(simplified) >= 3:
            polys.append(simplified)
    return polys, img.size


def bake_all_contours() -> dict:
    """Every glyph's traced+simplified polygon, in raw 160x160-canvas
    pixel coordinates as flat [x,y,x,y,...] lists -- keyed exactly like
    the FILL_MANIFEST block already baked into godslies.html
    (<god>/<seg>_<pos>). This is what lets the browser's own "Download
    font" button build a .ttf without re-tracing images at runtime:
    canvas getImageData() throws a SecurityError on file://-loaded
    images (every browser's cross-origin image policy treats file://
    resources this way, confirmed against this exact page), so runtime
    tracing in the browser simply isn't possible in the fully-offline
    mode this tool is built for -- the trace has to happen here, ahead
    of time, same as FILL_MANIFEST's fill-fraction data does."""
    data = {}
    for god in GODS:
        for seg, positions in (("grid9", GRID9_POSITIONS), ("diamond4", DIAMOND4_POSITIONS)):
            for pos in positions:
                polys, _size = trace_polygons(asset_path(seg, pos, god))
                data[f"{god}/{seg}_{pos}"] = [
                    [coord for y, x in poly for coord in (round(x), round(y))]
                    for poly in polys
                ]
    return data


def update_html_glyph_contours(data: dict) -> None:
    """Bakes bake_all_contours()'s output into godslies.html the same
    way extract_assets.py's update_html_manifest() bakes FILL_MANIFEST
    -- a marked, regenerate-in-place block, not hand-maintained."""
    html_path = ROOT / "godslies.html"
    text = html_path.read_text(encoding="utf-8")
    start = "const GLYPH_CONTOURS = "
    end = ";\n// END GENERATED GLYPH_CONTOURS"
    start_idx = text.index(start) + len(start)
    end_idx = text.index(end, start_idx)
    new_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    text = text[:start_idx] + new_json + text[end_idx:]
    html_path.write_text(text, encoding="utf-8")


def build_glyph(polys, canvas_size):
    pen = TTGlyphPen(None)
    w, h = canvas_size
    scale = GLYPH_TOP / max(w, h) if max(w, h) else 1
    for poly in polys:
        # image (row, col) = (y, x), y-down -> font units, y-up from the
        # baseline: flip y, scale both, and swap to (x, y) for the pen.
        pts = [(x * scale, (h - y) * scale) for y, x in poly]
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
    return pen.glyph()


def accented_cmap_extra(base_letter_glyph: dict) -> dict:
    """Every precomposed Latin letter that NFD-decomposes to a plain
    A-Z/a-z base (e -> e, C, -> C, n~ -> n, ...) maps to that base
    letter's glyph too -- mirrors the same accent-folding
    godslies.html's encode() already does before enciphering (see
    foldForCipher() there), so the font -- used for actually typing, not
    just displaying already-known text -- doesn't show a blank box the
    moment someone types an ordinary accented letter. Scanned
    automatically via unicodedata instead of a hand-typed list, so it
    covers French and most other Latin-script languages' accented
    letters at once. Ligatures (oe, ae, ss, o-with-stroke) have no
    single-base NFD decomposition (oe's Unicode decomposition, if any,
    is to TWO letters, not one glyph) and are left undefined here, same
    as digits/punctuation -- see the module docstring."""
    extra = {}
    for codepoint in range(0x00C0, 0x0250):  # Latin-1 Supplement + Latin Extended-A/B
        ch = chr(codepoint)
        decomposed = unicodedata.normalize("NFD", ch)
        base = decomposed[0]
        if base != ch and base in base_letter_glyph:
            extra[codepoint] = base_letter_glyph[base]
    return extra


def build_font(key: Key, family_name: str):
    glyph_order = [".notdef", "space"]
    cmap = {ord(" "): "space"}
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
    advances = {".notdef": (ADVANCE_WIDTH, 0), "space": (SPACE_WIDTH, 0)}

    base_letter_glyph = {}
    for letter in string.ascii_uppercase:
        seg, which, pos = key.letter_to_slot[letter]
        polys, size = trace_polygons(glyph_asset(seg, which, pos, key))
        glyph_name = f"cipher.{letter}"
        glyphs[glyph_name] = build_glyph(polys, size)
        advances[glyph_name] = (ADVANCE_WIDTH, 0)
        glyph_order.append(glyph_name)
        cmap[ord(letter)] = glyph_name          # uppercase
        cmap[ord(letter.lower())] = glyph_name  # lowercase -> same glyph (cipher is case-insensitive)
        cmap[PUA_BASE + (ord(letter) - 65)] = glyph_name  # paste-safe PUA alias, see PUA_BASE above
        base_letter_glyph[letter] = glyph_name
        base_letter_glyph[letter.lower()] = glyph_name
    cmap.update(accented_cmap_extra(base_letter_glyph))

    fb = FontBuilder(UNITS_PER_EM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(advances)
    fb.setupHorizontalHeader(ascent=ASCENT, descent=DESCENT)
    fb.setupNameTable({
        "familyName": family_name,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{family_name};GodsLies;{key.seed}",
        "fullName": family_name,
        "psName": family_name.replace(" ", "") + "-Regular",
        "version": "Version 1.0",
    })
    fb.setupOS2(sTypoAscender=ASCENT, sTypoDescender=DESCENT, usWinAscent=ASCENT, usWinDescent=-DESCENT)
    fb.setupPost()
    return fb.font


def main(argv=None):
    p = argparse.ArgumentParser(description="Build an installable Windows .ttf font from a Gods Lies key")
    p.add_argument("key", nargs="?", help="path to a key JSON file (e.g. keys/mykey.json)")
    p.add_argument("-o", "--out", help="output .ttf path (default: <key file name>.ttf next to the key)")
    p.add_argument("--name", help="font family name shown in apps (default: 'Gods Lies - <key file name>')")
    p.add_argument("--bake-html", action="store_true",
                    help="regenerate godslies.html's baked GLYPH_CONTOURS block instead of "
                         "building a font -- run this after extract_assets.py whenever the "
                         "source scan or glyph-cleanup logic changes, so the browser's own "
                         "'Download font' button stays in sync with the real assets")
    args = p.parse_args(argv)

    if args.bake_html:
        update_html_glyph_contours(bake_all_contours())
        print("Baked GLYPH_CONTOURS -> godslies.html")
        return

    if not args.key:
        p.error("the following arguments are required: key (unless --bake-html is given)")

    key_path = Path(args.key)
    key = Key.load(key_path)
    family_name = args.name or f"Gods Lies - {key_path.stem}"
    out_path = Path(args.out) if args.out else key_path.with_suffix(".ttf")

    font = build_font(key, family_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    font.save(out_path)
    print(f"Font '{family_name}' -> {out_path}")
    print("Windows: right-click the .ttf -> Install, then pick it from the font list in any app.")
    print("Covers A-Z/a-z, space, and accented Latin letters -- digits/punctuation/ligatures are left undefined (see module docstring).")


if __name__ == "__main__":
    main()
