"""
Gods' Lies
===========================

A cipher engine built directly from your Crypto notebook's actual
hand-drawn symbols (cropped out of archive/CRYPTO2.jpg by
extract_assets.py into assets/<name>/*.png -- see that file for how).

The 14 original Olympian tiles are renamed here to real (or Greek-word-
derived) minor deities/personifications of lies and deception -- see
extract_assets.py's NAME_MAP for what each name means and which original
god it came from.

  - a "segment" of 9 symbols  -> one name's 3x3 grid tile (9 real cell images)
  - a "segment" of 4 symbols  -> one name's X/diamond tile (4 real N/E/S/W
    triangle crops)
  - a "bloc"       = one name's own 9-segment + 4-segment (13 real symbols)
  - a full alphabet = 2 grid9 segments + 2 diamond4 segments (26 symbols),
    mixed from ANY of the 14 you like -- no fixed pairing required

You pick, independently, which style to use for each of the 2 grid9 slots
and each of the 2 diamond4 slots (14 to choose from, any combination,
repeats allowed). The letter <-> position assignment is randomly
generated per key (see README.md); the symbol IMAGES themselves are your
real originals.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

KEYS_DIR = Path(__file__).parent / "keys"

# Hermès + Áte lead the list: they're the classic plain/dotted pigpen
# pair, so they're the most immediately recognizable starting point. The
# rest keep the source sheet's original top-row/bottom-row pairing order,
# though any of the 14 can be freely mixed with any other (see module
# docstring) -- list position has no bearing on the key/slot mapping.
GODS = [
    "hermes", "ate",
    "horkos", "arnesis", "phantasos", "dolos", "apate", "kolax",
    "lethe", "limos", "lochos", "daidalos", "mnemon", "loxias",
]
GOD_LABELS = {
    "horkos": "Hórkos", "arnesis": "Árnesis", "phantasos": "Phántasos", "dolos": "Dólos",
    "apate": "Apáte", "kolax": "Kólax", "hermes": "Hermès",
    "lethe": "Léthe", "limos": "Limós", "lochos": "Lóchos",
    "daidalos": "Daídalos", "mnemon": "Mnémon", "loxias": "Loxías",
    "ate": "Áte",
}

# Two-digit reference codes for the notebook message header (see "Message
# format" in README.md) -- one for each name's grid9 style, one for its
# diamond4 style. Fixed and hand-assigned (NOT derived from GODS' list
# order) so reordering the display list can never silently change a code
# a written message already relies on.
#
# The first 9 are exactly the real notebook's own numbers (page 1 of
# Cryptographie & Symbole.pdf): grid=N0, diamond=NN for N=1..9 (e.g.
# Aphrodite/Kólax = 30/33). The notebook's own numbering broke that
# pattern for its remaining 5 gods (plain 00/01..08/09); this extends the
# same "round, easy to remember" spirit instead of just continuing
# sequentially, with a digit-reversal pair (grid/diamond are digit-swaps
# of each other) that doesn't collide with the first 9's codes.
GOD_CODES = {
    "hermes":    ("10", "11"),
    "ate":       ("20", "22"),
    "kolax":     ("30", "33"),
    "loxias":    ("40", "44"),
    "apate":     ("50", "55"),
    "mnemon":    ("60", "66"),
    "dolos":     ("70", "77"),
    "daidalos":  ("80", "88"),
    "phantasos": ("90", "99"),
    "lochos":    ("15", "51"),
    "arnesis":   ("25", "52"),
    "limos":     ("35", "53"),
    "horkos":    ("45", "54"),
    "lethe":     ("65", "56"),
}
CODE_TO_GOD = {code: god for god, codes in GOD_CODES.items() for code in codes}

GRID9_POSITIONS = list(range(1, 10))
DIAMOND4_POSITIONS = ["N", "E", "S", "W"]


def _all_slots():
    """The 26 (segment, which, position) slots. `which` is 0 or 1 and
    picks which of the two chosen gods (for that segment type) a symbol
    belongs to -- it plays the role classic pigpen's plain/dotted split
    played, but is now driven by your god choice instead of a fixed dot."""
    slots = []
    for which in (0, 1):
        for pos in GRID9_POSITIONS:
            slots.append(("grid9", which, pos))
    for which in (0, 1):
        for pos in DIAMOND4_POSITIONS:
            slots.append(("diamond4", which, pos))
    return slots


ALL_SLOTS = _all_slots()
assert len(ALL_SLOTS) == 26


def slot_code(seg: str, which: int, pos) -> str:
    letter = "G" if seg == "grid9" else "D"
    return f"{letter}{pos}{'.' if which else ''}"


_MASK32 = 0xFFFFFFFF


def _imul32(a: int, b: int) -> int:
    return (a * b) & _MASK32


def _seeded_rng(seed_str: str):
    """Port of godslies.html's seededRng() (a seed-string hash feeding a
    mulberry32-style generator) using masked 32-bit unsigned arithmetic to
    match JS's Math.imul/>>> semantics exactly -- so the same seed string
    produces the same letter shuffle whether a key is generated here or in
    the browser. Previously this used Python's random.Random(seed), an
    unrelated algorithm: the same seed silently produced two different
    shuffles depending on which tool generated the key. Saved key files
    are unaffected either way (they store the resulting mapping directly,
    not just the seed) -- this only makes *new* generations reproducible
    across both tools."""
    h = (1779033703 ^ len(seed_str)) & _MASK32
    for ch in seed_str:
        h = _imul32(h ^ ord(ch), 3432918353)
        h = ((h << 13) | (h >> 19)) & _MASK32

    def rng() -> float:
        nonlocal h
        h = _imul32(h ^ (h >> 16), 2246822519)
        h = _imul32(h ^ (h >> 13), 3266489917)
        h = (h ^ (h >> 16)) & _MASK32
        return h / 4294967296

    return rng


def _build_slot_to_letter(letter_to_slot: dict) -> dict:
    return {
        slot_code(seg, which, pos): letter
        for letter, (seg, which, pos) in letter_to_slot.items()
    }


def parse_code(code: str):
    code = code.strip()
    which = 1 if code.endswith(".") else 0
    if which:
        code = code[:-1]
    seg = "grid9" if code[0].upper() == "G" else "diamond4"
    pos_str = code[1:]
    pos = int(pos_str) if seg == "grid9" else pos_str.upper()
    return seg, which, pos


@dataclass
class Key:
    grid9_gods: list  # [god_id, god_id]
    diamond4_gods: list  # [god_id, god_id]
    seed: str
    letter_to_slot: dict = field(default_factory=dict)  # letter -> (seg, which, pos)
    slot_to_letter: dict = field(default_factory=dict)  # "G5" style code -> letter

    @classmethod
    def generate(cls, grid9_gods, diamond4_gods, seed=None, canonical=True) -> "Key":
        """`canonical` puts the picks in the order the header writes them
        (see canonical_order), so a header always rebuilds exactly this
        key. Only the legacy header reader passes False: its grammar
        recorded the slot order itself, so re-ordering would decode
        already-sent messages into garbage."""
        for g in (*grid9_gods, *diamond4_gods):
            if g not in GODS:
                raise ValueError(f"Unknown god '{g}'. Choices: {', '.join(GODS)}")
        if len(grid9_gods) != 2 or len(diamond4_gods) != 2:
            raise ValueError("need exactly 2 grid9 gods and 2 diamond4 gods")
        if canonical:
            grid9_gods, diamond4_gods = canonical_order(grid9_gods, diamond4_gods)
        seed = str(seed) if seed is not None else str(random.randint(0, 10**9))
        rng = _seeded_rng(seed)
        letters = list(string.ascii_uppercase)
        for i in range(len(letters) - 1, 0, -1):
            j = int(rng() * (i + 1))
            letters[i], letters[j] = letters[j], letters[i]
        letter_to_slot = dict(zip(letters, ALL_SLOTS))
        return cls(
            grid9_gods=list(grid9_gods),
            diamond4_gods=list(diamond4_gods),
            seed=seed,
            letter_to_slot=letter_to_slot,
            slot_to_letter=_build_slot_to_letter(letter_to_slot),
        )

    def god_for(self, seg: str, which: int) -> str:
        return (self.grid9_gods if seg == "grid9" else self.diamond4_gods)[which]

    def to_json(self) -> dict:
        return {
            "grid9_gods": self.grid9_gods,
            "diamond4_gods": self.diamond4_gods,
            "seed": self.seed,
            "letter_to_slot": {
                letter: [seg, which, pos]
                for letter, (seg, which, pos) in self.letter_to_slot.items()
            },
        }

    @classmethod
    def from_json(cls, data: dict) -> "Key":
        letter_to_slot = {
            letter: (seg, which, pos)
            for letter, (seg, which, pos) in data["letter_to_slot"].items()
        }
        return cls(
            grid9_gods=data["grid9_gods"],
            diamond4_gods=data["diamond4_gods"],
            seed=data["seed"],
            letter_to_slot=letter_to_slot,
            slot_to_letter=_build_slot_to_letter(letter_to_slot),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, path: Path) -> "Key":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Encode / decode  (purely structural: position + which-of-two-gods; the
# god choice below only changes how a symbol is DRAWN, never the mapping)
# ---------------------------------------------------------------------------

def encode(text: str, key: Key) -> str:
    tokens = []
    for ch in text:
        if ch.isalpha():
            slot = key.letter_to_slot.get(ch.upper())
            if slot is None:
                tokens.append(ch)
                continue
            seg, which, pos = slot
            tokens.append(slot_code(seg, which, pos))
        elif ch == " ":
            tokens.append("/")
        else:
            tokens.append(ch)
    return " ".join(tokens)


def decode(code_string: str, key: Key) -> str:
    out = []
    for token in code_string.split():
        if token == "/":
            out.append(" ")
            continue
        try:
            seg, which, pos = parse_code(token)
            code = slot_code(seg, which, pos)
        except (IndexError, ValueError):
            out.append(token)
            continue
        letter = key.slot_to_letter.get(code)
        out.append(letter if letter else token)
    return "".join(out)


# ---------------------------------------------------------------------------
# Rendering: the REAL symbols, cropped straight out of archive/CRYPTO2.jpg
# by extract_assets.py into assets/<god>/<grid9|diamond4>_<pos>.png -- these
# are your actual hand-drawn glyphs, not a synthetic approximation.
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).parent / "assets"
CELL = 40


def asset_path(seg: str, pos, god: str) -> Path:
    return ASSETS_DIR / god / f"{seg}_{pos}.png"


def glyph_asset(seg: str, which: int, pos, key: Key) -> Path:
    return asset_path(seg, pos, key.god_for(seg, which))


def _image_tag_relative_to(path: Path, out_dir: Path, size: int = CELL) -> str:
    rel = os.path.relpath(path, out_dir).replace("\\", "/")
    return f'<image href="{rel}" width="{size}" height="{size}"/>'


def render_message_svg(code_string: str, key: Key, out_path: Path, cols: int = 12) -> str:
    """Render an encoded code string as a strip of the real glyph images.
    `out_path` is where the SVG will be saved, used to compute relative
    links back to assets/ -- keep the SVG under the project folder (e.g.
    in keys/) so that relative path resolves."""
    out_dir = Path(out_path).parent
    tokens = [t for t in code_string.split()]
    cell = CELL + 6
    rows = (len(tokens) + cols - 1) // cols or 1
    width = cell * min(cols, max(len(tokens), 1))
    height = cell * rows
    parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
              f'xmlns:xlink="http://www.w3.org/1999/xlink">',
              '<rect width="100%" height="100%" fill="white" />']
    for i, token in enumerate(tokens):
        col, row = i % cols, i // cols
        gx, gy = col * cell, row * cell
        if token == "/":
            continue
        if len(token) >= 2 and token[0].upper() in "GD":
            try:
                seg, which, pos = parse_code(token)
                img = _image_tag_relative_to(glyph_asset(seg, which, pos, key), out_dir)
                parts.append(f'<g transform="translate({gx+3},{gy+3})">{img}</g>')
                continue
            except (IndexError, ValueError, KeyError):
                pass
        parts.append(f'<text x="{gx+8}" y="{gy+26}" font-size="20" fill="black">{token}</text>')
    parts.append("</svg>")
    return "".join(parts)


def alphabet_chart_svg(key: Key, out_path: Path) -> str:
    out_dir = Path(out_path).parent
    letters = sorted(key.letter_to_slot)
    cell = CELL + 30
    cols = 13
    rows = (len(letters) + cols - 1) // cols
    parts = [f'<svg width="{cell*cols}" height="{cell*rows}" xmlns="http://www.w3.org/2000/svg" '
              f'xmlns:xlink="http://www.w3.org/1999/xlink">',
              '<rect width="100%" height="100%" fill="white" />']
    for i, letter in enumerate(letters):
        seg, which, pos = key.letter_to_slot[letter]
        col, row = i % cols, i // cols
        gx, gy = col * cell, row * cell
        img = _image_tag_relative_to(glyph_asset(seg, which, pos, key), out_dir)
        parts.append(f'<text x="{gx+CELL/2}" y="{gy+16}" font-size="14" text-anchor="middle" font-family="sans-serif" fill="black">{letter}</text>')
        parts.append(f'<g transform="translate({gx},{gy+20})">{img}</g>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Message-format helper: mood_cipher_seed_punctuation (see README).
# The cipher field is one dot-joined list covering all 4 picks: a god
# filling a grid slot AND a diamond slot is written once as its NAME (it
# is that whole god), every other pick as its 2-digit code -- grid code
# then diamond code, per slot, so codes always precede names and the list
# is always 2 or 4 tokens, never 1 or 3.
#
# It reads back unambiguously because a code carries its own segment: the
# 14 grid codes {10,20,...,65} and 14 diamond codes {11,22,...,56} are
# disjoint, so each token says which list it joins and its position in
# that list is its slot.
#
# The header is self-sufficient: GOD_CODES (fixed/shared) plus the cipher
# field and seed rebuild the full key with no saved key file -- seed is
# always the key's real seed, not a decorative label.
#
# Mirrors godslies.html's cipherField()/parseCipherField() -- keep in sync.
# ---------------------------------------------------------------------------

def _ascii_name(label: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", label)
                   if not unicodedata.combining(c))


NAME_TO_GOD = {_ascii_name(label).lower(): god for god, label in GOD_LABELS.items()}


def canonical_order(grid9_gods, diamond4_gods):
    """The canonical order of one set of picks, shared by the key and the
    header so both describe the same thing: a god filling a grid AND a
    diamond slot (a "godblock") goes last with its two halves on the same
    index, independent picks keep their order in front. Without it the
    header couldn't say which grid slot a god sits in, and two different
    keys could share one header."""
    blocks = [g for g in grid9_gods if g in diamond4_gods]
    return (
        [g for g in grid9_gods if g not in blocks] + blocks,
        [d for d in diamond4_gods if d not in blocks] + blocks,
    )


def cipher_field(grid9_gods, diamond4_gods) -> str:
    grid, diamond = canonical_order(grid9_gods, diamond4_gods)
    codes, names = [], []
    for i in range(2):
        if grid[i] == diamond[i]:
            names.append(_ascii_name(GOD_LABELS[grid[i]]))
        else:
            codes += [GOD_CODES[grid[i]][0], GOD_CODES[diamond[i]][1]]
    return ".".join(codes + names)


def parse_cipher_field(field: str):
    """Reverse of cipher_field() -> (grid9_gods, diamond4_gods), already in
    canonical order (names last land last in both lists)."""
    grid, diamond = [], []
    for token in field.split("."):
        token = token.strip()
        named = NAME_TO_GOD.get(_ascii_name(token).lower())
        if named:
            grid.append(named)
            diamond.append(named)
            continue
        god = CODE_TO_GOD.get(token)
        if god is None:
            raise ValueError(f"unknown god code or name in header: {token!r}")
        (grid if GOD_CODES[god][0] == token else diamond).append(god)
    if len(grid) != 2 or len(diamond) != 2:
        raise ValueError("a header must name 2 grid styles and 2 diamond styles")
    return grid, diamond


def key_from_header(field: str, seed: str) -> Key:
    grid, diamond = parse_cipher_field(field)
    return Key.generate(grid, diamond, seed)


def key_from_legacy_header(slot_a: str, slot_b: str, seed: str) -> Key:
    """Messages written before the header became one dot-joined field used
    two separate slotA/slotB fields, each either a single "godblock" code
    or a dot-joined grid.diamond pair. Read-only: nothing writes this form
    any more, but anything already sent still decodes."""
    def parse_ref(ref):
        if "." in ref:
            grid_code, diamond_code = ref.split(".", 1)
            return CODE_TO_GOD[grid_code], CODE_TO_GOD[diamond_code]
        god = CODE_TO_GOD[ref]
        return god, god

    g0, d0 = parse_ref(slot_a)
    g1, d1 = parse_ref(slot_b)
    return Key.generate([g0, g1], [d0, d1], seed, canonical=False)


def compose_message(mood: str, punctuation: str, secret_text: str, key: Key) -> dict:
    header = f"{mood}_{cipher_field(key.grid9_gods, key.diamond4_gods)}_{key.seed}_{punctuation}"
    cipher = encode(secret_text, key)
    return {"header": header, "cipher": cipher, "full": f"{header}\n{cipher}"}


def parse_message(message: str, key: Key = None) -> dict:
    """If `key` is omitted, it's derived straight from the header's cipher
    field and seed -- no separately saved key file needed, as long as
    GOD_CODES is shared/known (see README). A lone "#" line is skipped:
    messages written when this tool used to append one still read fine, it
    just isn't written any more."""
    lines = [l for l in message.splitlines() if l.strip() and l.strip() != "#"]
    if not lines:
        raise ValueError("empty message")
    header = lines[0]
    body = " ".join(lines[1:])
    parts = header.split("_")
    # 4 fields = current grammar, 5 = the older mood_slotA_slotB_seed_punct
    # one. The two can't be confused: the count differs even when mood and
    # punctuation are both empty.
    if len(parts) == 5:
        mood, slot_a, slot_b, seed, punctuation = parts
        parsed_header = {"mood": mood, "cipher_field": f"{slot_a}_{slot_b}",
                         "seed": seed, "punctuation": punctuation}
        if key is None:
            key = key_from_legacy_header(slot_a, slot_b, seed)
    elif len(parts) == 4:
        mood, field, seed, punctuation = parts
        parsed_header = {"mood": mood, "cipher_field": field,
                         "seed": seed, "punctuation": punctuation}
        if key is None:
            key = key_from_header(field, seed)
    else:
        raise ValueError("not a message header: expected mood_cipher_seed_punctuation")
    return {"header": parsed_header, "plaintext": decode(body, key)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def default_key_path(name: str) -> Path:
    return KEYS_DIR / f"{name}.json"


def _cmd_generate(args):
    key = Key.generate(args.grid9, args.diamond4, args.seed)
    path = Path(args.out) if args.out else default_key_path(args.name or "key")
    key.save(path)
    print(f"Generated key (seed={key.seed}) -> {path}")
    print(f"  grid9:    {key.grid9_gods}")
    print(f"  diamond4: {key.diamond4_gods}")
    if args.chart:
        chart_path = path.with_suffix(".svg")
        chart_path.write_text(alphabet_chart_svg(key, chart_path), encoding="utf-8")
        print(f"Alphabet chart -> {chart_path}")


def _cmd_encode(args):
    key = Key.load(args.key)
    coded = encode(args.text, key)
    print(coded)
    if args.svg:
        svg_path = Path(args.svg)
        svg_path.write_text(render_message_svg(coded, key, svg_path), encoding="utf-8")
        print(f"SVG -> {args.svg}")


def _cmd_decode(args):
    key = Key.load(args.key)
    print(decode(args.codes, key))


def _cmd_message(args):
    key = Key.load(args.key)
    result = compose_message(args.mood, args.punct, args.text, key)
    print(result["full"])


def _cmd_parse(args):
    key = Key.load(args.key) if args.key else None
    result = parse_message(Path(args.file).read_text(encoding="utf-8"), key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(description="Gods' Lies -- pigpen-style swap-character tool")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate a new randomized alphabet key")
    g.add_argument("--grid9", nargs=2, metavar=("GOD1", "GOD2"), required=True,
                   choices=GODS, help="which 2 gods' 9-grid styles to use")
    g.add_argument("--diamond4", nargs=2, metavar=("GOD1", "GOD2"), required=True,
                   choices=GODS, help="which 2 gods' 4-diamond styles to use")
    g.add_argument("--seed", help="reuse this seed for a reproducible alphabet")
    g.add_argument("--name", help="key file name (default keys/key.json)")
    g.add_argument("--out", help="explicit output key path")
    g.add_argument("--chart", action="store_true", help="also write an A-Z cheat-sheet SVG")
    g.set_defaults(func=_cmd_generate)

    e = sub.add_parser("encode", help="encode plaintext into pigpen codes")
    e.add_argument("key", help="path to a key JSON file")
    e.add_argument("text", help="text to encode")
    e.add_argument("--svg", help="also render the result to this SVG path")
    e.set_defaults(func=_cmd_encode)

    d = sub.add_parser("decode", help="decode pigpen codes back to text")
    d.add_argument("key", help="path to a key JSON file")
    d.add_argument("codes", help="space-separated code string, e.g. 'G5 D2. /'")
    d.set_defaults(func=_cmd_decode)

    m = sub.add_parser("message", help="build a full mood_cipher_seed_punctuation message")
    m.add_argument("key", help="path to a key JSON file")
    m.add_argument("--mood", default="")
    m.add_argument("--punct", default="")
    m.add_argument("--text", required=True)
    m.set_defaults(func=_cmd_message)

    pa = sub.add_parser("parse", help="parse a composed message file back apart")
    pa.add_argument("file")
    pa.add_argument("--key", help="path to a key JSON file; omit to derive the key "
                                  "straight from the header's own codes/names + seed")
    pa.set_defaults(func=_cmd_parse)

    lg = sub.add_parser("gods", help="list available god ids")
    lg.set_defaults(func=lambda args: print("\n".join(f"{g:12s} {GOD_LABELS[g]}" for g in GODS)))

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
