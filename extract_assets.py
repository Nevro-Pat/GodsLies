"""One-off extraction: crop the real symbols out of archive/CRYPTO2.jpg into
individual per-cell PNGs under assets/<name>/. Run once; the results are
checked into assets/ and used by both godslies.py and godslies.html.

Each of the 14 original Olympian tiles in the source sheet is renamed here
to a real (or Greek-word-derived) minor deity/personification that already
embodies a lie/deception archetype -- so these are still gods (fitting
"Gods' Lies"), just not the same 14 as the source sheet. NAME_MAP records
old->new plus what each new name means, so this script still knows which
sheet position maps to which folder if it's ever re-run against a fresh
scan.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
from scipy import ndimage

ROOT = Path(__file__).parent
SRC = ROOT.parent / "archive" / "CRYPTO2.jpg"
OUT = ROOT / "assets"

ROW_BANDS = [(689, 1316), (1489, 2116), (2336, 2966), (3139, 3763)]
COL_BANDS = [
    [(686, 1307), (1489, 2110), (2289, 2910), (3092, 3713), (3892, 4513), (4736, 5357), (5533, 6154)],
    [(689, 1310), (1489, 2110), (2292, 2913), (3092, 3713), (3892, 4513), (4739, 5360), (5539, 6160)],
    [(692, 1313), (1495, 2116), (2295, 2916), (3095, 3716), (3936, 4557), (4739, 5360), (5536, 6160)],
    [(689, 1310), (1486, 2107), (2292, 2913), (3092, 3713), (3936, 4557), (4736, 5357), (5539, 6160)],
]

# row 0 = top-name grid9, row 1 = top-name diamond4, row 2 = bottom-name grid9, row 3 = bottom-name diamond4
# (original sheet god -> new name, see NAME_MAP)
TOP_GODS = ["horkos", "arnesis", "phantasos", "dolos", "apate", "kolax", "hermes"]
BOTTOM_GODS = ["lethe", "limos", "lochos", "daidalos", "mnemon", "loxias", "ate"]

# new name -> (original sheet god, what the new name means / why it fits)
NAME_MAP = {
    "horkos": ("Zeus", "Hórkos: the Oath personified -- invoked against those who break it (perjury)"),
    "arnesis": ("Héra", "Árnesis: Greek 'denial/refusal'"),
    "phantasos": ("Poséidon", "Phántasos: minor god of unreal/inanimate dream-images (illusion, mirage)"),
    "dolos": ("Athéna", "Dólos: god of trickery and guile"),
    "apate": ("Arès", "Apáte: goddess of deceit and fraud"),
    "kolax": ("Aphrodite", "Kólax: Greek 'flatterer'"),
    "hermes": ("Hermès", "kept as-is -- the messenger/trickster god, plain 'vanilla' style"),
    "lethe": ("Hadès", "Léthe: river/spirit of forgetting and concealment"),
    "limos": ("Déméter", "Limós: personification of hunger and famine (the harvest goddess's blight)"),
    "lochos": ("Artémis", "Lóchos: Greek 'ambush, hidden armed party'"),
    "daidalos": ("Héphaïstos", "Daídalos: master craftsman of illusions and the labyrinth (facade)"),
    "mnemon": ("Hestia", "Mnémon: 'the rememberer' -- a private, counted account (alibi)"),
    "loxias": ("Apollon", "Loxías: real epithet of Apollo, 'the ambiguous/oblique one' (his riddling oracle)"),
    "ate": ("Dionysos", "Áte: goddess of delusion, ruin and blind folly"),
}

GRID9_POS = list(range(1, 10))
DIAMOND4_POS = ["N", "E", "S", "W"]

PAD = 6  # trim a few px of the tile's own border so cell crops don't include stray border ink
# Ink islands below BOTH thresholds are scan grit, not drawn marks -- see
# clean_cell(). Set either to 0 to disable, which is how the effect was
# isolated when it turned out to reach five cells rather than the two expected.
DESPECKLE_MAX_PX = 60
DESPECKLE_MAX_FRAC = 0.03
CANVAS = 160  # final square canvas size for every exported cell image

# boost_small_content() targets -- diamond4 arms are typically a single
# small dot/chevron (content-fill ~0.06-0.32 per manifest.json) next to
# grid9's denser digit-like marks (~0.5-0.88), which reads as "diamonds
# are too small/empty" even after clean_cell()'s own scaling (that scale
# is relative to each cell's own crop region, not to other cells -- see
# its docstring). Diamond gets a strong boost since it needs one; grid9
# gets a mild one (mostly already full) -- both capped, not a full
# re-normalization to one shared target, so a genuinely tiny mark (a
# single dot) still reads as a dot, not a blown-up disc.
GRID9_BOOST = (0.62, 1.3)      # (target_fill, max_boost)
DIAMOND4_BOOST = (0.62, 3.2)

# Hermès is the plain, undecorated "vanilla" pigpen style, and Áte (née
# Dionysos) is its dotted variant (classic pigpen: corner/edge/center cell
# shape + a dot). Unlike the other 12, these two must NOT go through the
# usual full frame-strip: their internal divider/diagonal lines ARE the
# symbol (that's what makes a corner cell look different from an edge cell
# or the center), so only the tile's own decorative outer box comes off --
# see strip_outer_border_only() / OUTER_BORDER_ONLY_GODS below.
OUTER_BORDER_ONLY_GODS = {"hermes", "ate"}

# Apáte's grid9 tile is scanned rotated -- the digits read correctly (as
# the classical 1-9 layout: 1/2/3 top row, 4/5/6 middle, 7/8/9 bottom) only
# if the *whole tile* is rotated 90° before cropping into cells, not each
# cell rotated in place after cropping (rotating in place only reorients a
# digit, it can't also move it to a different grid position -- confirmed by
# comparing whole-tile vs per-cell rotation directly).
WHOLE_TILE_ROTATE_GRID9 = {"apate": 90}

# Mnémon isn't cropped from its own scan for grid9 at all -- it's Apáte's
# already-correct cells rotated 180° in place, same position numbering
# (e.g. position 6 shows Apáte's "6" flipped upside down, which reads like
# a "9" but with its dot relocated to the top-left instead of bottom-right
# -- confirmed against the user's own worked example).
DERIVE_GRID9_FROM = {"mnemon": ("apate", 180)}

# Hermès/Áte's own scanned diamond4 arms read as awkward next to the
# rest of the set. Swapped for Phántasos'/Lóchos' cleaner ornament style
# instead -- same plain/dotted pairing as before (Phántasos has no dots
# like Hermès, Lóchos has dots like Áte) -- but NOT a straight per-arm
# swap: each arm is taken from the OPPOSITE compass position, unmodified
# (no rotation). Phántasos/Lóchos' own arms point outward from center
# (e.g. the North arm's mark points further up/out), which composes into
# an outward-pointing "phantom square"; using each position's opposite
# arm instead (North <- source's South, East <- source's West, etc.)
# means a mark that pointed outward at its original position now points
# back in toward the tile's center from across the tile, composing into
# a proper inward cross instead -- confirmed against the user's own
# worked example/reference image.
DERIVE_DIAMOND4_FROM = {"hermes": "phantasos", "ate": "lochos"}
OPPOSITE_DIAMOND4_DIRECTION = {"N": "S", "S": "N", "E": "W", "W": "E"}


def strip_frame(tile: Image.Image) -> Image.Image:
    """Remove a diamond4 tile's decorative frame (outer border + X
    diagonals) by finding the single largest connected ink component and
    erasing it. For diamond4 the frame never touches the arm ornaments, so
    it's always one connected shape spanning the whole tile (tens of
    thousands of px) while each arm's own ornament is a separate, much
    smaller component -- cleanly separating scaffold from real symbol
    without needing to guess exact line positions.

    NOT used for grid9 tiles anymore: see strip_grid_frame() below -- on
    several names (Dólos, Kólax, Limós, Daídalos) a cell's ink physically
    touches the divider line, so this connected-component approach merged
    frame+cell into one blob and erased most of the grid when it shipped
    (caught via direct visual inspection, not just re-running this script)."""
    arr = np.array(tile.convert("RGB"))
    gray = np.array(tile.convert("L"))
    ink = gray < 150
    labels, n = ndimage.label(ink, structure=np.ones((3, 3)))
    if n == 0:
        return tile
    sizes = ndimage.sum(ink, labels, index=range(1, n + 1))
    frame_label = int(np.argmax(sizes)) + 1
    arr[labels == frame_label] = 255
    return Image.fromarray(arr)


def strip_grid_frame(tile: Image.Image, thresh: float = 0.85, pad: int = 3) -> Image.Image:
    """Remove a grid9 tile's decorative frame (outer border + internal 3x3
    dividers) by row/column ink-density profile instead of connected
    components: a true border/divider line covers >85% of a full row or
    column, while even a cell stroke that happens to touch the line only
    covers a small fraction of it -- so this can't accidentally merge with
    and erase real ink the way the connected-component approach did."""
    arr = np.array(tile.convert("RGB"))
    gray = np.array(tile.convert("L"))
    ink = gray < 150
    row_frac = ink.mean(axis=1)
    col_frac = ink.mean(axis=0)
    row_mask = ndimage.binary_dilation(row_frac > thresh, iterations=pad)
    col_mask = ndimage.binary_dilation(col_frac > thresh, iterations=pad)
    arr[row_mask, :] = 255
    arr[:, col_mask] = 255
    return Image.fromarray(arr)


def _high_density_runs(mask: np.ndarray) -> list:
    """Contiguous [start, end) index ranges where `mask` is True."""
    runs = []
    start = None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def strip_outer_border_only(tile: Image.Image, thresh: float = 0.85, pad: int = 3) -> Image.Image:
    """Remove only a grid9 tile's outermost bounding edge, leaving the
    internal 3x3 divider lines alone -- for Hermès/Áte, where those
    dividers ARE the classic-pigpen symbol (a corner cell reads as 2
    sides, an edge cell as 3 sides, the center as a closed box; true
    pigpen has no outer bounding box at all, just a "#"). Reuses the same
    row/column ink-density profiling as strip_grid_frame(), but only
    erases the first and last high-density run per axis (the outer box)
    instead of every run (which would also wipe the 2 internal dividers
    that make each cell's shape legible)."""
    arr = np.array(tile.convert("RGB"))
    gray = np.array(tile.convert("L"))
    ink = gray < 150
    row_runs = _high_density_runs(ink.mean(axis=1) > thresh)
    col_runs = _high_density_runs(ink.mean(axis=0) > thresh)
    erase_rows = np.zeros(ink.shape[0], dtype=bool)
    erase_cols = np.zeros(ink.shape[1], dtype=bool)
    outer_row_runs = [row_runs[0], row_runs[-1]] if len(row_runs) > 1 else row_runs
    outer_col_runs = [col_runs[0], col_runs[-1]] if len(col_runs) > 1 else col_runs
    for lo, hi in outer_row_runs:
        erase_rows[lo:hi] = True
    for lo, hi in outer_col_runs:
        erase_cols[lo:hi] = True
    erase_rows = ndimage.binary_dilation(erase_rows, iterations=pad)
    erase_cols = ndimage.binary_dilation(erase_cols, iterations=pad)
    arr[erase_rows, :] = 255
    arr[:, erase_cols] = 255
    return Image.fromarray(arr)


def _center_ink(img: Image.Image, canvas: int = CANVAS) -> Image.Image:
    """Put the ink's bounding-box center on the center of a `canvas` square.

    Used by both clean_cell() and boost_small_content(): centering once isn't
    enough, because scaling a centered mark and pasting it back at an integer
    offset reintroduces a couple of pixels of drift, multiplied by a boost of
    up to 3.2x. Re-centering after the boost costs nothing and is what keeps
    the worst glyph in the set within a pixel of true center."""
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ys, xs = np.nonzero(np.array(img)[:, :, 3] > 8)
    if len(xs) == 0:
        return out
    ink_cx, ink_cy = (int(xs.min()) + int(xs.max())) / 2, (int(ys.min()) + int(ys.max())) / 2
    out.paste(img, (int(round((canvas - 1) / 2 - ink_cx)),
                    int(round((canvas - 1) / 2 - ink_cy))), img)
    return out


def content_fill_fraction(img: Image.Image) -> float:
    """Fraction of the canvas a cell's actual ink occupies (the larger of
    its non-transparent bounding box's width/height, over the canvas
    size). Saved to manifest.json so the UI can boost undersized glyphs
    (e.g. Áte's lone dot) toward a comfortable minimum on-screen size,
    without touching the underlying asset -- keeps clean_cell()'s
    original-size-based scale (below) intact, since that's what keeps a
    small mark honestly small relative to a full glyph."""
    alpha = np.array(img.convert("RGBA"))[:, :, 3]
    ys, xs = np.nonzero(alpha)
    if len(xs) == 0:
        return 0.0
    w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    return max(w, h) / img.size[0]


def clean_cell(img: Image.Image, canvas: int = CANVAS,
               center_ink: bool = True) -> Image.Image:
    """Threshold to pure black-ink-on-transparent, then place it on a
    fixed-size square canvas. Black-on-transparent lets the UI invert()
    the image for dark mode instead of needing two asset sets.

    `center_ink` picks which of the two things a cell image is used for:

      True  -- the per-letter glyph, shown ALONE in the alphabet chart and
               the message stream. Nothing around it implies where it sat in
               its tile, so it must be centered or it reads as crooked.
      False -- the same cell as one ninth (or one quarter) of the composed
               tile preview, where its offset inside its own cell is what
               makes the 9 cells line up into a coherent drawing. Phantasos'
               outer-wall pigpen only closes into a square because each mark
               stays pinned to its cell's edge; centering every cell turns
               the tile into nine marks floating in a void.

    (Tried two "standardize stroke width" post-passes here -- skeletonize
    + redilate, and morphological open/close -- both actively destroyed
    real symbols: skeletonizing collapses filled shapes like dots/digits
    to their centerline first, and opening erodes away anything thinner
    than its structuring element, which wiped out most of Arès' digits and
    Hermès' border lines. Consistency instead comes from strip_frame()
    (uniform frame removal) and the original-size-based scale below, both
    of which don't touch stroke geometry.)"""
    gray = np.array(img.convert("L"))
    ink = gray < 180
    # Drop ink islands too small to be a drawn mark -- scan grit. Two exist in
    # the sheet: a 12px speck on Kolax's cell 9 and a 2px one on Dolos' cell 1,
    # both of which shipped as visible dots. Both thresholds sit far below any
    # real feature (Ate's dot is 538px, Phantasos' cell-5 dots ~200px each).
    lab, n = ndimage.label(ink, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(ink, lab, index=range(1, n + 1))
        total = sizes.sum()
        for i, sz in enumerate(sizes, 1):
            if sz < DESPECKLE_MAX_PX and sz < total * DESPECKLE_MAX_FRAC:
                ink[lab == i] = False
    mask = Image.fromarray((ink * 255).astype(np.uint8))
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(black, (0, 0), mask)

    # Scale from the cell's own original size (NOT its content bbox), so a
    # small dot stays visually small relative to a full glyph -- cropping to
    # content first and re-normalizing every symbol to fill ~82% of the
    # canvas made tiny marks (e.g. Dionysos' single dots) blow up into
    # oversized blobs while full glyphs looked normal.
    w, h = out.size
    margin = 0.88
    scale = (canvas * margin) / max(w, h) if max(w, h) > 0 else 1
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    out = out.resize((new_w, new_h), Image.LANCZOS)

    # Place the INK's bounding box at the canvas center -- NOT the crop
    # region's center. The two are only the same when a mark happens to sit
    # dead center of its own cell/wedge, which is rare: grid9 cells are cut
    # on even thirds and diamond4 arms on a triangular wedge, so a mark
    # drawn toward the outside of its cell used to land off-center on the
    # canvas and stay there. That was visible three times over, because the
    # offset is then multiplied: boost_small_content() below scales about
    # the canvas center (up to 3.2x, which pushed 6 arms clean off the
    # canvas and cropped them), and the UI's own fillScale() scales about
    # the element center again (up to 3.0x). Centering the ink here is what
    # makes both of those safe, so neither needs a compensating offset.
    #
    # Note this only moves the mark; it deliberately does NOT re-scale it.
    # The scale above stays keyed to the crop region so a small dot still
    # reads as honestly small next to a full glyph (see the comment above).
    if center_ink:
        return _center_ink(out, canvas)
    final = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    final.paste(out, ((canvas - new_w) // 2, (canvas - new_h) // 2), out)
    return final


def boost_small_content(img: Image.Image, target_fill: float, max_boost: float,
                        canvas: int = CANVAS, center_ink: bool = True) -> Image.Image:
    """Boost a cell whose actual ink is small relative to the canvas
    (diamond4 arms especially -- a dot or thin chevron, vs. grid9's
    denser digit-like marks) toward a more consistent visual weight,
    capped so it can't run away into an oversized blob -- same spirit as
    godslies.html's client-side fillScale(), and the same failure mode
    that ruled out a full, uncapped re-normalization here before (see
    clean_cell()'s comment): capping the boost instead of forcing every
    mark to hit the same target is what keeps a tiny dot looking like a
    (bigger, but still clearly a) dot rather than a disc. Baked into the
    asset -- unlike fillScale() -- so the composed tile PREVIEWS
    (grid9_tile.png / diamond4_tile.png, used for gallery/slot-box
    thumbnails) benefit too, not just the per-letter chart/write/read
    display, which is the only thing fillScale ever touched."""
    alpha = np.array(img)[:, :, 3]
    ys, xs = np.nonzero(alpha)
    if len(xs) == 0:
        return img
    fill = max(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1) / canvas
    if fill <= 0:
        return img
    boost = min(max_boost, max(1.0, target_fill / fill))
    if boost <= 1.0:
        return img
    new_size = max(1, round(canvas * boost))
    resized = img.resize((new_size, new_size), Image.LANCZOS)
    if center_ink:
        # Re-center on the ink rather than pasting at (canvas-new_size)//2:
        # the scale-up magnifies any leftover sub-pixel offset from
        # clean_cell(), and a plain centered paste bakes it in (~4px at 3.2x).
        return _center_ink(resized, canvas)
    final = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    off = (canvas - new_size) // 2
    final.paste(resized, (off, off), resized)  # negative offset when boosted -- PIL clips it, i.e. center-crops back to `canvas`
    return final


# --- glyph modifiers -------------------------------------------------------
#
# A key is 2 grid gods + 2 diamond gods and ANY pair is drawable, so all 182
# glyphs have to be mutually distinct. They weren't: several gods encode a
# letter purely by WHERE its mark sits in the cell (Phantasos' cells 2 and 8
# are the same horizontal bar, top vs bottom; likewise Arnesis and Limos), and
# once clean_cell() centers the ink -- which is the whole point, see above --
# that distinction is gone. Others were already duplicates before centering:
# Dolos and Kolax are drawn identically on 8 of 9 cells, and Hermes'/Ate's
# diamond arms ARE Phantasos'/Lochos' files (see DERIVE_DIAMOND4_FROM).
#
# So the letter has to be carried by the SHAPE instead of the placement. Each
# entry below adds one mark to one glyph, in that god's own drawing vocabulary:
#
#   ("dot", corner)  a filled dot the size of Ate's, set in that corner of the
#                    mark -- for the gods that already carry dots
#   ("crossbar",)    a bar crossing the cell's dominant stroke at right angles,
#                    parallel to its base stroke -- for the gods drawn in plain
#                    strokes
#   ("ring_x",)      replaces the cell outright with a ring crossed by an X
#
# Hermes and Ate are never modified: they are the original pigpen pair the
# whole set is a variation on. Where they collide with another god, the other
# god yields. Dolos likewise keeps all 9 of its cells.
#
# Nothing lands here on measurement alone. Each god is rendered with
# preview_glyphs.py and looked at first -- four proposals were rejected on
# sight while every numeric check passed -- and check_glyph_distinctness.py
# then re-tests all 16,471 pairs for a collision the new mark may have created
# somewhere else, which is a real hazard: doubling a bar to split two of
# Phantasos' cells lands straight on Mnemon's North arm.
#
# Sizes are all derived from the set's own drawing, not invented: DOT_R is
# Ate's dot measured off its own cells (26px across on a 160 canvas), and
# MOD_GAP is twice that diameter -- the spacing that read correctly when the
# proposal was reviewed. BAR_LEN is odd so a bar centred on an integer pixel
# overhangs identically on both sides; at 64 it came out 32/30 and looked
# skewed.
MOD_DOT_R = 13
MOD_CLEAR = 7            # ink-free ring kept around an added dot
MOD_GAP = 4 * MOD_DOT_R  # centre-to-centre spacing from the stroke it echoes
MOD_BAR_LEN = 65
MOD_QUADRANT = {"NW": (-1, -1), "NE": (1, -1), "SW": (-1, 1), "SE": (1, 1)}


def _line_profile(m: np.ndarray, axis: int) -> np.ndarray:
    """Longest ink run on each row (axis=1) or column (axis=0)."""
    src = m if axis == 1 else m.T
    out = np.zeros(src.shape[0], int)
    for k, line in enumerate(src):
        i = np.flatnonzero(line)
        if len(i):
            out[k] = max(len(r) for r in np.split(i, np.flatnonzero(np.diff(i) != 1) + 1))
    return out


def _dominant_stroke(m: np.ndarray, axis: int):
    """(centre, length) of the strongest stroke on that axis.

    The CENTRE of the band, not the first line reaching the maximum -- that
    line is the stroke's leading edge, and anchoring a crossing bar there put
    it half a stroke off to one side in every cell."""
    prof = _line_profile(m, axis)
    hot = prof >= prof.max() * 0.8
    lo = hi = int(np.argmax(prof))
    while lo - 1 >= 0 and hot[lo - 1]:
        lo -= 1
    while hi + 1 < len(hot) and hot[hi + 1]:
        hi += 1
    return (lo + hi) / 2.0, int(prof.max())


def _stroke_width(m: np.ndarray) -> int:
    runs = []
    for row in m:
        i = np.flatnonzero(row)
        if len(i) == 0:
            continue
        runs.extend(len(r) for r in np.split(i, np.flatnonzero(np.diff(i) != 1) + 1))
    return int(np.clip(np.median(runs), 5, 16)) if runs else 8


def _disc(r: int) -> np.ndarray:
    d = 2 * r + 1
    yy, xx = np.ogrid[:d, :d]
    return (xx - r) ** 2 + (yy - r) ** 2 <= r * r


def _stamp(img: Image.Image, shape: np.ndarray, cx: int, cy: int) -> Image.Image:
    """Draw a boolean shape centred on (cx, cy).

    A mark that would run off the canvas is SHIFTED back inside rather than
    cropped at the edge. The two matter differently: the per-letter glyph is
    centred so its marks always fit, but the tile-preview variant keeps each
    cell where it was drawn -- and a diamond arm sits hard against one edge, so
    a crossbar centred on its stroke used to lose half its length there and
    read as an L instead of a cross. Shifting keeps the symbol whole and the
    two variants recognisably the same."""
    a = np.array(img.copy())
    sh, sw = shape.shape
    H, W = a.shape[0], a.shape[1]
    x0 = int(np.clip(round(cx - sw / 2), 0, max(0, W - sw)))
    y0 = int(np.clip(round(cy - sh / 2), 0, max(0, H - sh)))
    x1, y1 = min(W, x0 + sw), min(H, y0 + sh)
    if y1 <= y0 or x1 <= x0:
        return img
    cut = shape[:y1 - y0, :x1 - x0]
    sub = a[y0:y1, x0:x1]
    sub[cut] = (0, 0, 0, 255)
    a[y0:y1, x0:x1] = sub
    return Image.fromarray(a)


def _dot_position(m: np.ndarray, quadrant: str):
    """Nearest clear spot to the mark, inside the named quadrant OF THE MARK.

    Quadrants are measured against the ink's own bounding box rather than the
    canvas, so a cell gets the same mark whether it was centred (the per-letter
    glyph) or left where it was drawn (the tile preview)."""
    st = _disc(MOD_DOT_R)
    sh, sw = st.shape
    fit = ~ndimage.binary_dilation(
        ndimage.binary_dilation(m, iterations=MOD_CLEAR), structure=np.ones((sh, sw)))
    H, W = m.shape
    inside = np.zeros_like(fit)
    inside[sh // 2 + 2:H - sh // 2 - 2, sw // 2 + 2:W - sw // 2 - 2] = True
    fit &= inside
    ys, xs = np.nonzero(m)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    qx, qy = MOD_QUADRANT[quadrant]
    q = np.zeros_like(fit)
    ry = slice(int(cy), H) if qy > 0 else slice(0, int(cy))
    rx = slice(int(cx), W) if qx > 0 else slice(0, int(cx))
    q[ry, rx] = True
    if (fit & q).any():
        fit &= q
    if not fit.any():
        return None
    fy, fx = np.nonzero(fit)
    k = int(np.argmin((fx - cx) ** 2 + (fy - cy) ** 2))
    return int(fx[k]), int(fy[k])


def _crossbar(m: np.ndarray):
    """A bar PERPENDICULAR to the cell's dominant stroke, crossing it, sitting
    MOD_GAP from the parallel base stroke and centred on the stroke it crosses.

    Perpendicular is the rule the reviewed drawing settled: cells whose long
    stroke is the vertical stem take a horizontal bar, cells whose long stroke
    is the horizontal arm take a vertical one. Forcing a single orientation on
    all four got half of them wrong."""
    w = _stroke_width(m)
    cy_h, len_h = _dominant_stroke(m, 1)
    cx_v, len_v = _dominant_stroke(m, 0)
    ys, xs = np.nonzero(m)
    if len_h <= len_v:
        # base stroke is the horizontal one -> bar parallel to it, crossing the stem
        inward = 1 if cy_h < m.shape[0] / 2 else -1
        y = float(np.clip(cy_h + inward * MOD_GAP, ys.min() + w, ys.max() - w))
        return np.ones((w, MOD_BAR_LEN), bool), int(round(cx_v)), int(round(y))
    inward = 1 if cx_v < m.shape[1] / 2 else -1
    x = float(np.clip(cx_v + inward * MOD_GAP, xs.min() + w, xs.max() - w))
    return np.ones((MOD_BAR_LEN, w), bool), int(round(x)), int(round(cy_h))


def _ring_with_x(m: np.ndarray, canvas: int = CANVAS) -> Image.Image:
    """A ring crossed by an X, drawn where the cell's ink sat.

    Deliberately an outline: Daidalos' own centre cell is the same motif drawn
    with strokes so heavy that its four voids collapsed to specks, so a ring
    with open quadrants can never be taken for it. The X reaches the ring's
    inner edge rather than floating inside it."""
    w = _stroke_width(m)
    ys, xs = np.nonzero(m)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    outer = 54
    d.ellipse([cx - outer, cy - outer, cx + outer, cy + outer],
              outline=(0, 0, 0, 255), width=w)
    half = (outer - w / 2) / (2 ** 0.5)
    for sx, sy in ((1, 1), (1, -1)):
        d.line([(cx - half * sx, cy - half * sy), (cx + half * sx, cy + half * sy)],
               fill=(0, 0, 0, 255), width=max(5, w - 2))
    return out


def apply_modifier(img: Image.Image, modifier: tuple) -> Image.Image:
    """Add one distinguishing mark. Every placement is measured from the ink's
    own bounding box, never from the canvas, so the per-letter glyph and the
    tile-preview cell receive the same symbol even though one is centred and
    the other is not."""
    kind = modifier[0]
    m = np.array(img)[:, :, 3] > 8
    if not m.any():
        return img
    if kind == "dot":
        pos = _dot_position(m, modifier[1])
        return _stamp(img, _disc(MOD_DOT_R), *pos) if pos else img
    if kind == "crossbar":
        shape, cx, cy = _crossbar(m)
        return _stamp(img, shape, cx, cy)
    if kind == "ring_x":
        return _ring_with_x(m)
    raise ValueError(f"unknown modifier kind: {kind!r}")


# (god, segment, position) -> modifier. Resolved one god at a time, each design
# rendered and looked at (preview_glyphs.py) and confirmed before landing here;
# check_glyph_distinctness.py then re-tests all 16,471 pairs for collisions the
# change may have created elsewhere.
#
# Kolax: drawn identically to Dolos on 8 of its 9 cells. It becomes "Dolos
# dotted" -- the relationship Ate already has to Hermes -- with the corners
# taking a dot in their own grid corner, the edges a bar crossing their
# dominant stroke, and the centre cell a ring. Dolos keeps all nine of its own.
GLYPH_MODIFIERS = {
    ("kolax", "grid9", 1): ("dot", "NW"),
    ("kolax", "grid9", 2): ("crossbar",),
    ("kolax", "grid9", 3): ("dot", "NE"),
    ("kolax", "grid9", 4): ("crossbar",),
    ("kolax", "grid9", 5): ("ring_x",),
    ("kolax", "grid9", 6): ("crossbar",),
    ("kolax", "grid9", 7): ("dot", "SW"),
    ("kolax", "grid9", 8): ("crossbar",),
    ("kolax", "grid9", 9): ("dot", "SE"),
    # Kolax's four diamond arms are deliberately left alone: "Kolax is Dolos
    # dotted" describes its GRID. Its W arm does collide with Lochos' cell 4
    # (both a vertical bar with a dot beside it, identical at every render
    # size), but every mark tried on it made the composed diamond worse -- a
    # second dot gave the arm two, and a crossbar ran off the canvas edge,
    # since the tile variant keeps each arm hard against its own side. Lochos
    # yields there instead, when its turn comes: its four arms already have to
    # yield to Ate's, so the pair is resolved on that side for free.
}


def modified(god: str, seg: str, pos, cell: Image.Image,
             recenter: bool = True) -> Image.Image:
    mod = GLYPH_MODIFIERS.get((god, seg, pos))
    if not mod:
        return cell
    out = apply_modifier(cell, mod)
    return _center_ink(out) if recenter else out


def crop_grid9(tile: Image.Image, center_ink: bool = True) -> dict:
    w, h = tile.size
    cells = {}
    cw, ch = w / 3, h / 3
    for r in range(3):
        for c in range(3):
            pos = r * 3 + c + 1
            box = (int(c * cw) + PAD, int(r * ch) + PAD, int((c + 1) * cw) - PAD, int((r + 1) * ch) - PAD)
            cells[pos] = boost_small_content(
                clean_cell(tile.crop(box), center_ink=center_ink),
                *GRID9_BOOST, center_ink=center_ink)
    return cells


def _divider_bands(stripped_tile: Image.Image, thresh: float = 0.85) -> tuple:
    """For a grid9 tile that's already had strip_outer_border_only() run
    on it (so only the 2 internal divider lines remain per axis), find
    those 2 lines directly and return 3 (start, end) bands per axis, each
    reaching all the way to its neighboring divider(s) -- unlike naive
    even-thirds division, this can't clip a divider that isn't *exactly*
    at 1/3 and 2/3 of the tile (hand-drawn lines rarely are), which is
    what left Hermès' bottom row missing its own bordering lines entirely
    when this shipped with plain thirds. Falls back to even thirds if
    exactly 2 divider runs aren't found."""
    gray = np.array(stripped_tile.convert("L"))
    ink = gray < 150

    def bands(runs, size):
        if len(runs) != 2:
            return [(0, size // 3), (size // 3, 2 * size // 3), (2 * size // 3, size)]
        (d1s, d1e), (d2s, d2e) = runs
        return [(0, d1e), (d1s, d2e), (d2s, size)]

    h, w = ink.shape
    row_bands = bands(_high_density_runs(ink.mean(axis=1) > thresh), h)
    col_bands = bands(_high_density_runs(ink.mean(axis=0) > thresh), w)
    return row_bands, col_bands


def crop_grid9_bands(tile: Image.Image, row_bands: list, col_bands: list,
                     center_ink: bool = True) -> dict:
    """Like crop_grid9(), but cell boundaries come from _divider_bands()
    instead of blind even-thirds -- used for Hermès/Áte so each cell
    reliably includes its own complete bordering line(s)."""
    cells = {}
    for r in range(3):
        for c in range(3):
            pos = r * 3 + c + 1
            y0, y1 = row_bands[r]
            x0, x1 = col_bands[c]
            cells[pos] = boost_small_content(
                clean_cell(tile.crop((x0, y0, x1, y1)), center_ink=center_ink),
                *GRID9_BOOST, center_ink=center_ink)
    return cells


def crop_diamond4(tile: Image.Image, center_ink: bool = True) -> dict:
    w, h = tile.size
    tile = tile.convert("RGBA")
    cx, cy = w / 2, h / 2
    polys = {
        "N": [(0, 0), (w, 0), (cx, cy)],
        "E": [(w, 0), (w, h), (cx, cy)],
        "S": [(w, h), (0, h), (cx, cy)],
        "W": [(0, h), (0, 0), (cx, cy)],
    }
    bboxes = {
        "N": (PAD, PAD, w - PAD, int(cy)),
        "E": (int(cx), PAD, w - PAD, h - PAD),
        "S": (PAD, int(cy), w - PAD, h - PAD),
        "W": (PAD, PAD, int(cx), h - PAD),
    }
    cells = {}
    for direction, poly in polys.items():
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        masked = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        masked.paste(tile, (0, 0), mask)
        cells[direction] = boost_small_content(
            clean_cell(masked.crop(bboxes[direction]), center_ink=center_ink),
            *DIAMOND4_BOOST, center_ink=center_ink)
    return cells


def compose_grid9_tile(cells: dict, cell_size: int = 96, gap: int = 4) -> Image.Image:
    """Build the whole-tile preview from the already-cleaned (and, where
    applicable, rotated) individual cells, so the preview always matches
    what the UI actually renders instead of drifting out of sync with a
    separately-processed whole-tile crop."""
    size = cell_size * 3 + gap * 4
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for pos, cell in cells.items():
        r, c = divmod(pos - 1, 3)
        thumb = cell.resize((cell_size, cell_size), Image.LANCZOS)
        x = gap + c * (cell_size + gap)
        y = gap + r * (cell_size + gap)
        out.paste(thumb, (x, y), thumb)
    return out


def compose_diamond4_tile(cells: dict, half: int = 100, gap: int = 4) -> Image.Image:
    """Same idea as compose_grid9_tile() but arranges the 4 diamond arms
    (N/E/S/W) around a shared center point instead of a 3x3 grid."""
    size = half * 2 + gap
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    positions = {
        "N": (half - half // 2 + gap // 2, 0),
        "W": (0, half - half // 2 + gap // 2),
        "E": (half + gap, half - half // 2 + gap // 2),
        "S": (half - half // 2 + gap // 2, half + gap),
    }
    for direction, cell in cells.items():
        thumb = cell.resize((half, half), Image.LANCZOS)
        out.paste(thumb, positions[direction], thumb)
    return _crop_to_content_square(out)


def _crop_to_content_square(img: Image.Image, margin: int = 6) -> Image.Image:
    """Crop tight around the actual ink, then pad the shorter axis back
    out so the result stays square. A cross/plus arrangement (4 arms
    around a center, unlike grid9's dense edge-to-edge 3x3) leaves its
    canvas corners empty by construction -- that dead space doesn't
    matter for the per-letter glyphs (drawn from the individual
    diamond4_<N/E/S/W>.png crops, untouched here), but it made the
    *composed preview tile* look small once scaled down into a fixed-
    size thumbnail box elsewhere. This only changes what fraction of
    that same-size box the image fills, never the box itself."""
    w, h = img.size
    alpha = np.array(img)[:, :, 3]
    ys, xs = np.nonzero(alpha)
    if len(xs) == 0:
        return img
    x0, x1 = max(0, xs.min() - margin), min(w, xs.max() + 1 + margin)
    y0, y1 = max(0, ys.min() - margin), min(h, ys.max() + 1 + margin)
    cw, ch = x1 - x0, y1 - y0
    if cw > ch:
        pad = (cw - ch) // 2
        y0, y1 = max(0, y0 - pad), min(h, y1 + (cw - ch - pad))
    elif ch > cw:
        pad = (ch - cw) // 2
        x0, x1 = max(0, x0 - pad), min(w, x1 + (ch - cw - pad))
    return img.crop((x0, y0, x1, y1))


def main():
    im = Image.open(SRC).convert("RGB")
    grid9_cells_by_god = {}
    grid9_placed_by_god = {}
    diamond4_cells_by_god = {}
    diamond4_placed_by_god = {}
    manifest = {}
    for row_idx, gods in ((0, TOP_GODS), (2, BOTTOM_GODS)):
        for col_idx, god in enumerate(gods):
            god_dir = OUT / god
            god_dir.mkdir(parents=True, exist_ok=True)

            outer_border_only = god in OUTER_BORDER_ONLY_GODS

            if god in DERIVE_GRID9_FROM:
                source_god, extra_rot = DERIVE_GRID9_FROM[god]
                def rot(c):
                    return c.rotate(extra_rot, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
                grid_cells = {pos: rot(c) for pos, c in grid9_cells_by_god[source_god].items()}
                grid_placed = {pos: rot(c) for pos, c in grid9_placed_by_god[source_god].items()}
            else:
                g_x0, g_x1 = COL_BANDS[row_idx][col_idx]
                g_y0, g_y1 = ROW_BANDS[row_idx]
                grid_tile = im.crop((g_x0, g_y0, g_x1, g_y1))
                grid_tile = (
                    strip_outer_border_only(grid_tile) if outer_border_only
                    else strip_grid_frame(grid_tile)
                )
                if god in WHOLE_TILE_ROTATE_GRID9:
                    grid_tile = grid_tile.rotate(
                        WHOLE_TILE_ROTATE_GRID9[god], resample=Image.BICUBIC,
                        expand=True, fillcolor=(255, 255, 255),
                    )
                if outer_border_only:
                    row_bands, col_bands = _divider_bands(grid_tile)
                    grid_cells = crop_grid9_bands(grid_tile, row_bands, col_bands)
                    grid_placed = crop_grid9_bands(grid_tile, row_bands, col_bands,
                                                   center_ink=False)
                else:
                    grid_cells = crop_grid9(grid_tile)
                    grid_placed = crop_grid9(grid_tile, center_ink=False)
            # Two variants of the same cells, for the two different jobs a
            # cell image does -- see clean_cell()'s center_ink. The per-letter
            # PNG is centered (it is shown alone); the tile preview keeps each
            # mark pinned where it sits in its cell, which is what makes the 9
            # of them compose into a coherent drawing.
            #
            # Modifiers are applied on the way out, so DERIVE_GRID9_FROM keeps
            # deriving from the god's own unmarked cells -- Mnemon carries its
            # own entries rather than inheriting Apate's rotated 180 degrees,
            # which would have put a mark meant for one corner in the opposite
            # one. Both variants get them, so a gallery thumbnail always shows
            # the same symbols the chart will.
            grid9_cells_by_god[god] = grid_cells
            grid9_placed_by_god[god] = grid_placed
            grid_final = {pos: modified(god, "grid9", pos, cell)
                          for pos, cell in grid_cells.items()}
            grid_tile_cells = {pos: modified(god, "grid9", pos, cell, recenter=False)
                               for pos, cell in grid_placed.items()}
            for pos, cell in grid_final.items():
                cell.save(god_dir / f"grid9_{pos}.png")
                manifest[f"{god}/grid9_{pos}"] = round(content_fill_fraction(cell), 3)
            compose_grid9_tile(grid_tile_cells).save(god_dir / "grid9_tile.png")

            if god in DERIVE_DIAMOND4_FROM:
                source_god = DERIVE_DIAMOND4_FROM[god]
                diamond_cells = {
                    direction: diamond4_cells_by_god[source_god][OPPOSITE_DIAMOND4_DIRECTION[direction]]
                    for direction in DIAMOND4_POS
                }
                diamond_placed = {
                    direction: diamond4_placed_by_god[source_god][OPPOSITE_DIAMOND4_DIRECTION[direction]]
                    for direction in DIAMOND4_POS
                }
            else:
                d_row = row_idx + 1
                d_x0, d_x1 = COL_BANDS[d_row][col_idx]
                d_y0, d_y1 = ROW_BANDS[d_row]
                diamond_tile = im.crop((d_x0, d_y0, d_x1, d_y1))
                if outer_border_only:
                    # The X diagonals never span a full row/column the way an
                    # axis-aligned border does, so the row/column profiling in
                    # strip_grid_frame() naturally leaves them alone and only
                    # takes off the tile's own outer square -- unlike
                    # strip_frame()'s connected-component approach, which would
                    # also erase the diagonals since they touch the border.
                    diamond_tile = strip_grid_frame(diamond_tile)
                else:
                    diamond_tile = strip_frame(diamond_tile)
                diamond_cells = crop_diamond4(diamond_tile)
                diamond_placed = crop_diamond4(diamond_tile, center_ink=False)
            diamond4_cells_by_god[god] = diamond_cells
            diamond4_placed_by_god[god] = diamond_placed
            diamond_final = {d: modified(god, "diamond4", d, cell)
                             for d, cell in diamond_cells.items()}
            diamond_tile_cells = {d: modified(god, "diamond4", d, cell, recenter=False)
                                  for d, cell in diamond_placed.items()}
            for direction, cell in diamond_final.items():
                cell.save(god_dir / f"diamond4_{direction}.png")
                manifest[f"{god}/diamond4_{direction}"] = round(content_fill_fraction(cell), 3)
            compose_diamond4_tile(diamond_tile_cells).save(god_dir / "diamond4_tile.png")

            print(f"{god}: {len(grid_cells)} grid9 cells, diamond4 tile {diamond_tile.size}")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
