# Gods' Lies

A pigpen-style cipher built directly from your Crypto notebook's real
hand-drawn symbols — not a redrawn approximation. `extract_assets.py`
crops every real glyph straight out of `archive/CRYPTO2.jpg` (the master
sheet) into `assets/<name>/*.png`, and both `godslies.py` and
`godslies.html` render those exact images.

## The 14 names

The source sheet's 14 Olympian tiles are renamed here to real (or
Greek-word-derived) minor deities and personifications that already
embody a lie or deception — so the cast is still gods, just not the same
14 the sheet started with:

| Name | Original | Why it fits |
|---|---|---|
| **Hermès** | Hermès | kept as-is — the messenger/trickster god; the plain "vanilla" style |
| **Áte** | Dionysos | goddess of delusion, ruin and blind folly — pigpen's "dotted" half |
| **Hórkos** | Zeus | the Oath personified — invoked against those who break it (perjury) |
| **Árnesis** | Héra | Greek "denial / refusal" |
| **Phántasos** | Poséidon | minor god of unreal, inanimate dream-images (illusion, mirage) |
| **Dólos** | Athéna | god of trickery and guile |
| **Apáte** | Arès | goddess of deceit and fraud |
| **Kólax** | Aphrodite | Greek "flatterer" |
| **Léthe** | Hadès | river/spirit of forgetting and concealment |
| **Limós** | Déméter | personification of hunger and famine — the harvest goddess's blight |
| **Lóchos** | Artémis | Greek "ambush, hidden armed party" |
| **Daídalos** | Héphaïstos | master craftsman of illusions and the labyrinth (facade) |
| **Mnémon** | Hestia | "the rememberer" — a private, counted account (alibi) |
| **Loxías** | Apollon | a real epithet of Apollo, "the ambiguous/oblique one" (his riddling oracle) |

Hermès and Áte lead the list (and the browser gallery) since they're the
classic plain/dotted pigpen pair — the most immediately recognizable
starting point. List/table order is display only; it has no bearing on
the key/slot mapping.

`extract_assets.py`'s `NAME_MAP` keeps this table in code, in case the
sheet is ever re-cropped from a fresh scan.

## Structure

- **segment of 9** — a name's 3x3 grid tile, 9 real cell images
- **segment of 4** — a name's X/diamond tile, 4 real triangular arm crops
  (N/E/S/W)
- **bloc** = one name's own 9-segment + 4-segment = 13 real symbols. In
  the sheet each name's two tiles sit vertically stacked (e.g. Léthe =
  the 9-grid tile directly above its diamond tile)
- **full alphabet** = 2 grid9 segments + 2 diamond4 segments = 26 symbols

You pick, completely independently, which of the 14 names' grid9 style to
use for each of the 2 grid9 slots, and which name's diamond4 style to use
for each of the 2 diamond4 slots — no requirement to use a name's
"official" partner (Hórkos doesn't have to pair with Léthe).

Cell/arm **positions are just labels** (`G1`..`G9`, `DN` etc.) — the
letter <-> position assignment is randomly shuffled per generated key.

## Border cleanup

For 12 of the 14, the sheet draws a full decorative table-grid box around
every single cell (identical on all 9 — pure clutter, the actual
differentiator is each cell's interior ink) and, for the diamonds, a full
triangle outline around every arm. `extract_assets.py` removes this: for
the grid9 tiles by row/column ink-density profiling (`strip_grid_frame`
— a true border/divider line covers most of a full row or column, while
even a cell stroke that happens to touch it only covers a small fraction,
so this can't accidentally merge with and erase real ink), and for the
diamond4 tiles by finding the single largest connected ink component
(`strip_frame` — the frame always spans tens of thousands of pixels while
each arm's own ornament is a separate, much smaller shape).

**Hermès** (the plain, undecorated "vanilla" pigpen) and **Áte** (the same
shapes plus a dot — pigpen's "dotted" half) are the two exceptions, and
they lead the gallery order for it: true classic pigpen has *no* outer
bounding box at all, just a "#" of 2 internal dividers, so a corner cell
reads as 2 sides, an edge cell as 3, and the center as a closed box.
`strip_outer_border_only` removes just the tile's own decorative outer
box and leaves the 2 internal dividers alone, and `crop_grid9_bands`
finds those dividers directly (rather than assuming they sit at an exact
1/3 and 2/3 split, which hand-drawn lines rarely do) so every cell
reliably keeps its own complete bordering line(s).

(Two earlier attempts at further "standardizing" stroke width —
skeletonize-and-redilate, and morphological open/close — were tried and
reverted: both actively destroyed real ink, either collapsing filled
shapes to their centerline or eroding away entire thin digits/border
lines. Consistency instead comes from uniform frame removal and scaling
from each cell's original size, not from redrawing strokes. Displayed
sizing is instead evened out at render time — see "Clamped glyph sizing"
below.)

## Clamped glyph sizing

Some symbols (a full digit) naturally occupy far more of their 160x160
canvas than others (Áte's lone dot) — that's real fidelity to the
notebook, not a bug, so it's not touched at the asset level. But shown
side by side in the alphabet chart it used to just look like "some
symbols are huge, some are tiny". `extract_assets.py` also records each
cell's content-fill fraction to `assets/manifest.json` (and bakes the
same data into a marked block inside `godslies.html`, since a local
`file://` page can't reliably `fetch()` a JSON file), and the UI uses it
to boost undersized glyphs toward a comfortable minimum on-screen size —
capped, and never shrinking an already-large glyph — everywhere a single
cell/arm image is shown (chart, write/read results).

## Files

- `extract_assets.py` — crop/build script. Re-run it if you replace
  `archive/CRYPTO2.jpg` with a new scan, or after editing any of its
  cropping/cleanup logic — it also regenerates `assets/manifest.json` and
  the matching baked-in data block inside `godslies.html`, so the two
  never drift out of sync.
- `assets/<name>/grid9_<1-9>.png`, `diamond4_<N/E/S/W>.png` — the 182
  individual real cell images (black ink on transparent background, so
  the UI can invert them for dark mode), plus `grid9_tile.png` /
  `diamond4_tile.png` whole-tile previews per name
- `assets/manifest.json` — each cell's content-fill fraction, used for
  clamped glyph sizing (see above)
- `godslies.py` — CLI / importable Python library
- `godslies.html` — browser version. One shared gallery + slot picker
  (Hermès/Áte set apart in their own "classic pigpen" column) and one
  live alphabet chart/key, used by both **Write** and **Read** below it
  (small tabs, not separate keys). Write encodes plaintext
  (mood/punctuation are plain optional fields next to it) straight to
  symbols, with the full text version (header + codes) tucked behind a
  "Show as text" arrow for copy-pasting elsewhere. Read's alphabet chart
  doubles as the decode input — click each symbol you recognize, in
  order — or paste a whole message to decode instead (its header, if
  present, is optional: with one, its own god-block codes and seed
  rebuild the key on the spot; without one, the key selected above is
  used instead)
- `make_font.py` — builds a real, installable Windows `.ttf` font from a
  key file: type normally in any app and see the cipher symbols instead
  of A-Z. See "Custom font" below.
- `keys/` — generated alphabet keys, saved as JSON. **Keep these safe** —
  losing a key means anything encoded with it can't be decoded again.

Both tools use the same key JSON format (`grid9_gods`, `diamond4_gods`,
`seed`, `letter_to_slot`) *and* the same seeded-shuffle algorithm, so the
same seed string reproduces the same shuffle whether the key was
generated in the browser or via the CLI, and a key generated by either
tool loads fine in the other. `godslies.html` must stay next to `assets/`
(it loads images via relative `assets/...` paths); the same applies to
any SVG written by the CLI — keep it under this project folder (e.g. in
`keys/`).

## Browser usage

Open `godslies.html` directly in a browser (fully offline, no server
needed). One cipher + key setup is shared by both **Write** and **Read**
(small tabs near the bottom, not separate keys).

Click any name's grid or diamond tile to fill the next open slot (Block
A's grid/diamond, then Block B's) — grid and diamond fill independently,
and once both of a type are full, clicking again replaces the first,
then the second, and so on, so there's never a need to target a slot
first. "Clear" resets all 4. Then set an optional seed (🎲 suggests a
common word/name — since the seed word doubles as the message header's
seed, a memorable one is just as good as a random number) and/or
download the key. Once all 4 slots are filled, the alphabet chart fills
in automatically. Accented letters (é, ç, ñ, ...) and common ligatures
(œ, æ, ß, ø) fold to their base letter before encoding — decoding a
message back returns the base letter, not the original accent.

**Write**: type plaintext, optionally set a mood tag/punctuation right
below it, and hit Encode — the result shows as symbols (mood and
punctuation framed at each end), with a copy button next to it (copies
the plain code text, since images can't be pasted as text elsewhere).
The full message (header + codes) sits behind a "Show as text" arrow,
also with its own copy button, for pasting into Read or anywhere else.

**Read**: the alphabet chart (in "Your key") is the decode input — click
each symbol you recognize there, in order, to rebuild the message (shown
live below, with a copy button); "/ space", undo and clear help manage
the sequence. Or expand "Paste a message to decode instead": one box
handles a message with or without its own header — with one, its own
god-block codes and seed rebuild the exact key needed (even a different
one than what's currently selected, and its mood/punctuation are shown
alongside the decoded text); without one, the key currently selected
above is used instead.

## Custom font

`make_font.py` builds a real, installable Windows `.ttf` font from a key
file, so you can type normally in any application (Word, Notepad, a
browser, ...) and see the cipher symbols in place of A-Z:

```bash
python make_font.py keys/mykey.json
python make_font.py keys/mykey.json -o MyCipher.ttf --name "Gods Lies - mykey"
```

Then in Windows: right-click the `.ttf` → **Install**, and pick it from
the font list in any app. It vectorizes the same real glyph PNGs the
browser/CLI render (marching-squares contour trace, via scikit-image,
built into TrueType outlines with fontTools) — same hand-drawn symbols,
not a redrawn approximation. Covers A-Z/a-z (case-insensitive, same as
the cipher) and space only; digits/punctuation are left undefined, same
as they pass through unciphered elsewhere. Requires
`pip install fonttools scikit-image numpy pillow`.

## CLI usage

```bash
# list the 14 available names
python godslies.py gods

# generate a key: 2 grid9 names + 2 diamond4 names, freely mixed
python godslies.py generate --grid9 lethe mnemon --diamond4 dolos horkos \
  --name custom1 --chart

# reuse a seed for a reproducible shuffle
python godslies.py generate --grid9 dolos daidalos --diamond4 arnesis loxias \
  --seed "my-secret-seed" --name custom2

# encode / decode
python godslies.py encode keys/custom1.json "Hello World" --svg keys/message.svg
python godslies.py decode keys/custom1.json "G5 G4 G3. / G9 G5. DW DN G9"

# build the mood_slotA_slotB_seed_punctuation message format
# (see "Message format" below, and page 2 of Cryptographie & Symbole.pdf)
python godslies.py message keys/custom1.json --mood ":c" --punct "!" \
  --text "Quel connard ce mec"

# parse a message file back apart -- pass --key to use a saved key, or
# omit it entirely to derive the key straight from the message's own header
python godslies.py parse message.txt --key keys/custom1.json
python godslies.py parse message.txt
```

Code-string notation: `G<1-9>` = a 9-grid cell, `D<N/E/S/W>` = a diamond
arm, a trailing `.` means the symbol comes from the *second* name you
picked for that segment type, `/` = word space. Anything else (digits,
punctuation) passes through unciphered.

## Message format

```
<mood>_<slotA>_<slotB>_<seed>_<punctuation>
<enciphered body>
#
```

Corrected from an earlier misreading of page 1/2 of
`Cryptographie & Symbole.pdf`: the numbers there (e.g. `30.03`) aren't a
date — they're 2-digit codes identifying which god's grid9/diamond4
styles were used, from a fixed per-god table (`GOD_CODES` in
`godslies.py`, mirrored as `GOD_CODES` in `godslies.html`):

| Name | grid9 | diamond4 | | Name | grid9 | diamond4 |
|---|---|---|---|---|---|---|
| Hermès | 10 | 11 | | Lóchos | 15 | 51 |
| Áte | 20 | 22 | | Árnesis | 25 | 52 |
| Kólax | 30 | 33 | | Limós | 35 | 53 |
| Loxías | 40 | 44 | | Hórkos | 45 | 54 |
| Apáte | 50 | 55 | | Léthe | 65 | 56 |
| Mnémon | 60 | 66 | | | | |
| Dólos | 70 | 77 | | | | |
| Daídalos | 80 | 88 | | | | |
| Phántasos | 90 | 99 | | | | |

(The first 9 are exactly the notebook's own numbers; the last 5 extend
that same "round, memorable" spirit with digit-reversal pairs instead of
the notebook's original plain-sequential tail.)

`slotA` and `slotB` each cover one of the key's two (grid9, diamond4)
pairs, and each can be written either as:
- a single code (**godblock**) — that god's grid9 *and* diamond4 both
  apply to this slot, e.g. `30` = Kólax for both
- two codes dot-joined, `grid.diamond` (**mixed**) — independent gods,
  e.g. `30.52` = Kólax's grid9 + Árnesis's diamond4

covering all 4 combinations (godblock/godblock, mixed/mixed, and the two
hybrids) with one grammar. `seed` is always the key's real seed (not a
separate decorative field) — which means **the header alone can
reconstruct the exact key needed to decode the message**, with no
separately shared key file required, as long as `GOD_CODES` is known
(it's fixed and built into both tools). `mood`/`punctuation` are the only
two fields that stay purely free-text/contextual. `#` marks
end-of-conversation (per your legend: "Fin de conversat.").

`godslies.html`'s Write tab computes `slotA`/`slotB` and the seed straight
from whatever key is currently set in its own picker — you never have to
work the codes out by hand. Read's "paste a message" option derives the
key straight from a pasted header when one's present, independent of
whatever's selected in Read's own picker.

## What happened to the old files in the Crypto folder

`Desktop/Crypto/` now holds exactly one reference document —
`Cryptographie & Symbole.pdf`, trimmed to its 2 relevant pages — plus this
project folder. Everything else that used to sit alongside it was a
duplicate:

- `Extract[1].pdf` was confirmed (rasterized and compared page-by-page)
  to be the *exact same chart* as page 1 of `Cryptographie & Symbole.pdf`,
  just exported landscape instead of portrait — fully redundant.
- `CRYPTO2.svg` was an SVG wrapping a base64 copy of the same raster image
  already in `archive/CRYPTO2.jpg` (not real vector paths) — also
  redundant with the file this tool actually crops from.

Both were moved into `Desktop/Crypto/archive/` rather than deleted, along
with everything else that was already there (26 individual tile crops,
`CRYPTO.png`/`.txt`, the page-3 PNG export, 2 "Nouveau Image bitmap"
files, and the un-trimmed 12-page PDF). Don't delete
`archive/CRYPTO2.jpg` — `extract_assets.py` reads it directly.

## Live demo

https://nevro-pat.github.io/GodsLies/

## License

All rights reserved — see [`LICENSE`](LICENSE). The source is public for
transparency, but no license is granted to reuse, modify, or redistribute
it without permission.
