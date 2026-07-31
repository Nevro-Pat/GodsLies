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
CANVAS = 160  # final square canvas size for every exported cell image

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


def clean_cell(img: Image.Image, canvas: int = CANVAS) -> Image.Image:
    """Threshold to pure black-ink-on-transparent, then center on a
    fixed-size square canvas. Black-on-transparent lets the UI invert()
    the image for dark mode instead of needing two asset sets.

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
    final = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    final.paste(out, ((canvas - new_w) // 2, (canvas - new_h) // 2), out)
    return final


def crop_grid9(tile: Image.Image) -> dict:
    w, h = tile.size
    cells = {}
    cw, ch = w / 3, h / 3
    for r in range(3):
        for c in range(3):
            pos = r * 3 + c + 1
            box = (int(c * cw) + PAD, int(r * ch) + PAD, int((c + 1) * cw) - PAD, int((r + 1) * ch) - PAD)
            cells[pos] = clean_cell(tile.crop(box))
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


def crop_grid9_bands(tile: Image.Image, row_bands: list, col_bands: list) -> dict:
    """Like crop_grid9(), but cell boundaries come from _divider_bands()
    instead of blind even-thirds -- used for Hermès/Áte so each cell
    reliably includes its own complete bordering line(s)."""
    cells = {}
    for r in range(3):
        for c in range(3):
            pos = r * 3 + c + 1
            y0, y1 = row_bands[r]
            x0, x1 = col_bands[c]
            cells[pos] = clean_cell(tile.crop((x0, y0, x1, y1)))
    return cells


def crop_diamond4(tile: Image.Image) -> dict:
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
        cells[direction] = clean_cell(masked.crop(bboxes[direction]))
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
    diamond4_cells_by_god = {}
    manifest = {}
    for row_idx, gods in ((0, TOP_GODS), (2, BOTTOM_GODS)):
        for col_idx, god in enumerate(gods):
            god_dir = OUT / god
            god_dir.mkdir(parents=True, exist_ok=True)

            outer_border_only = god in OUTER_BORDER_ONLY_GODS

            if god in DERIVE_GRID9_FROM:
                source_god, extra_rot = DERIVE_GRID9_FROM[god]
                grid_cells = {
                    pos: cell.rotate(extra_rot, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
                    for pos, cell in grid9_cells_by_god[source_god].items()
                }
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
                else:
                    grid_cells = crop_grid9(grid_tile)
            grid9_cells_by_god[god] = grid_cells
            for pos, cell in grid_cells.items():
                cell.save(god_dir / f"grid9_{pos}.png")
                manifest[f"{god}/grid9_{pos}"] = round(content_fill_fraction(cell), 3)
            compose_grid9_tile(grid_cells).save(god_dir / "grid9_tile.png")

            if god in DERIVE_DIAMOND4_FROM:
                source_god = DERIVE_DIAMOND4_FROM[god]
                diamond_cells = {
                    direction: diamond4_cells_by_god[source_god][OPPOSITE_DIAMOND4_DIRECTION[direction]]
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
            diamond4_cells_by_god[god] = diamond_cells
            for direction, cell in diamond_cells.items():
                cell.save(god_dir / f"diamond4_{direction}.png")
                manifest[f"{god}/diamond4_{direction}"] = round(content_fill_fraction(cell), 3)
            compose_diamond4_tile(diamond_cells).save(god_dir / "diamond4_tile.png")

            print(f"{god}: {len(grid_cells)} grid9 cells, diamond4 tile {diamond_tile.size}")

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    update_html_manifest(manifest)


def update_html_manifest(manifest: dict) -> None:
    """godslies.html is opened directly as a file:// page (no server), and
    fetch()/XHR of a local JSON file is unreliable under that origin in
    Chrome -- so instead of loading assets/manifest.json at runtime, bake
    the same data into a marked-off `const FILL_MANIFEST = {...}` block in
    the HTML itself, regenerated here every time this script runs."""
    html_path = ROOT / "godslies.html"
    text = html_path.read_text(encoding="utf-8")
    start = "const FILL_MANIFEST = "
    end = ";\n// END GENERATED"
    start_idx = text.index(start) + len(start)
    end_idx = text.index(end, start_idx)
    new_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    text = text[:start_idx] + new_json + text[end_idx:]
    html_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
