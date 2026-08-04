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
cell's content-fill fraction to `assets/manifest.json`, fetched by the
browser at startup (see "Files" below), and the UI uses it to boost
undersized glyphs toward a comfortable minimum on-screen size — capped,
and never shrinking an already-large glyph — everywhere a single
cell/arm image is shown (chart, write/read results).

## Files

- `extract_assets.py` — crop/build script. Re-run it if you replace
  `archive/CRYPTO2.jpg` with a new scan, or after editing any of its
  cropping/cleanup logic — it regenerates `assets/manifest.json`, which
  the browser fetches directly (see "Browser usage" below).
- `assets/<name>/grid9_<1-9>.png`, `diamond4_<N/E/S/W>.png` — the 182
  individual real cell images (black ink on transparent background, so
  the UI can invert them for dark mode), plus `grid9_tile.png` /
  `diamond4_tile.png` whole-tile previews per name
- `assets/manifest.json` — each cell's content-fill fraction, used for
  clamped glyph sizing (see above)
- `assets/glyph-contours.json` — every glyph's traced vector outline,
  generated by `make_font.py --bake-html` (see "Custom font" below);
  fetched by the browser at startup, same as `manifest.json`
- `godslies.py` — CLI / importable Python library
- `godslies.html` + `css/`, `js/` — browser version. `godslies.html`
  holds only markup; all styling lives in `css/*.css` and all behavior in
  `js/**/*.js` (loaded as ES modules from `js/app.js`), with translations
  and the gods/seed-word lists in `js/data/*.json`. One shared gallery +
  slot picker (Hermès/Áte set apart in their own "classic pigpen" column)
  and one live alphabet chart/key, used by both **Write** and **Read**
  below it (small tabs, not separate keys). Write encodes plaintext
  (mood/punctuation are plain optional fields next to it) straight to
  symbols, with the full text version (header + codes) shown in a box
  right below — exactly what its "Copy as codes" button copies. Read's
  alphabet chart doubles as the decode input — click each symbol you
  recognize, in order — or paste a whole message to decode instead (its
  header, if present, is optional: with one, its own codes/names and
  seed rebuild the key on the spot; without one, the key selected above
  is used instead)
- `make_font.py` — builds a real, installable Windows `.ttf` font from a
  key file: type normally in any app and see the cipher symbols instead
  of A-Z. Also generates `assets/glyph-contours.json` (`--bake-html`),
  which is what powers the browser's own **Download font** button. See
  "Custom font" below.
- `keys/` — generated alphabet keys, saved as JSON. **Keep these safe** —
  losing a key means anything encoded with it can't be decoded again.

Both tools use the same key JSON format (`grid9_gods`, `diamond4_gods`,
`seed`, `letter_to_slot`) *and* the same seeded-shuffle algorithm, so the
same seed string reproduces the same shuffle whether the key was
generated in the browser or via the CLI, and a key generated by either
tool loads fine in the other. `godslies.html` must stay next to `assets/`,
`css/`, and `js/` (it loads them via relative paths); the same applies to
any SVG written by the CLI — keep it under this project folder (e.g. in
`keys/`).

## Browser usage

`godslies.html` fetches its own data (translations, the gods list,
glyph/font data) at startup, so it needs to be served over http(s) rather
than opened directly as a local `file://` page — browsers block that kind
of request for local files. Either open it via the GitHub Pages link
below, or, for local development, run a small local server from this
folder and open the page through it, e.g.:

```bash
python -m http.server
```

then visit `http://localhost:8000/godslies.html`. One cipher + key setup
is shared by both **Write** and **Read** (small tabs near the bottom, not
separate keys).

Click any name's grid or diamond tile to fill the next open slot (grid·1,
diamond·1, grid·2, diamond·2) — grid and diamond fill independently, and
once both of a type are full, clicking again replaces the first, then
the second, and so on, so there's never a need to target a slot first.
The same god can't fill both grid slots (or both diamond slots) — that
would mean 18 of the 26 letters reuse just one visual style, so a
same-type repeat is rejected (a brief red flash on the slot) instead.
Each of the 4 slot boxes shows its god's reference code underneath (the
same 2-digit code the message header uses); if a god ends up in both
slots of a *different* segment type (e.g. the same name for grid·1 and
diamond·1), showing its name there instead of two unrelated-looking
numbers is clearer. "Clear" resets all 4. Then set an optional seed (🎲
suggests a common word/name — since the seed word doubles as the message
header's seed, a memorable one is just as good as a random number)
and/or download the key or a matching installable font (see "Custom
font" below). Once all 4 slots are filled, the alphabet chart fills in
automatically. Accented letters (é, ç, ñ, ...) and common ligatures (œ,
æ, ß, ø) fold to their base letter before encoding — decoding a message
back returns the base letter, not the original accent.

**Write**: type plaintext, optionally set a mood tag/punctuation right
below it, and hit Encode — the result shows as symbols, with the mood and
punctuation on their own labelled row underneath (they're the envelope
around the message, not part of the ciphertext, and they read the same
way here, in Read, and in an exported image). Under that: the header, a
plain-language reading of it, and the full message as text (header +
codes) in a box — which is exactly what "Copy as codes" copies, for
pasting into Read or anywhere else.

**Read**: the alphabet chart (in "Your key") is the decode input — click
each symbol you recognize there, in order, to rebuild the message (shown
live below, with a copy button); "/ space", undo and clear help manage
the sequence. Or expand "Paste a message to decode instead": one box
handles a message with or without its own header — with one, its own
codes/names and seed rebuild the exact key needed (even a different one
than what's currently selected, and its mood/punctuation are shown on the
same labelled row under the decoded text that Write uses); without one,
the key currently selected above is used instead.

## Custom font

Both the browser tool and `make_font.py` build a real, installable
Windows `.ttf` font from a key, so you can type normally in any
application (Word, Notepad, a browser, ...) and see the cipher symbols
in place of A-Z. Either way, the font shows the same real hand-drawn
glyphs the browser/CLI render — not a redrawn approximation — and
covers A-Z/a-z (case-insensitive, same as the cipher) plus space and
accented Latin letters (é, ç, ñ, ... folded to their base letter, same
as `encode()` does — see "Browser usage" above). Digits, punctuation,
and ligatures (œ, æ, ß, ø) are left undefined, same as they pass
through unciphered/unfolded elsewhere.

**In the browser** (no install, no terminal): once a key is ready, click
**🔤 Download font** next to "Download key" in step 2. It's built
entirely client-side — vectorized outlines are pre-computed offline (see
below) into `assets/glyph-contours.json`, and a small hand-written
TrueType writer assembles the `.ttf` and downloads it directly, all in
JS, no server-side font generation involved.

**From the CLI**, e.g. for scripting or batch-generating several keys'
fonts at once:

```bash
python make_font.py keys/mykey.json
python make_font.py keys/mykey.json -o MyCipher.ttf --name "Gods Lies - mykey"
```

Then in Windows: right-click the `.ttf` → **Install**, and pick it from
the font list in any app. Requires
`pip install fonttools scikit-image numpy pillow`.

Both paths trace the same way (marching-squares contour trace via
scikit-image, simplified, then built into TrueType outlines) — the
browser just can't do that tracing itself at runtime (`canvas`'s
`getImageData()` throws a SecurityError on a cross-origin-loaded image,
so there's no reliable way to read a glyph PNG's pixels from JS). Instead,
`python make_font.py --bake-html` pre-traces every glyph once and writes
the result to `assets/glyph-contours.json`, fetched by the browser at
startup the same way it already fetches `assets/manifest.json`.
**Re-run it after `extract_assets.py`** whenever the source scan or
glyph-cleanup logic changes, so the browser's font button stays in sync
with the real assets.

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

# build the mood_cipher_seed_punctuation message format
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
<mood>_<cipher>_<seed>_<punctuation>
<enciphered body>
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

`cipher` is **one dot-joined list covering all four picks**, written so
nothing about the key is left out of it:

- a god filling a grid9 slot **and** a diamond4 slot is that whole god,
  so it's written once as its **name** — `Dolos` (plain ASCII, accents
  dropped), not as two codes
- every other pick is its own 2-digit code, grid code then diamond code
  per slot — `65.44` = Léthe's grid9 + Loxías's diamond4

so `65.44.Dolos` reads "Léthe's grid, Loxías's diamond, and Dólos for a
whole grid+diamond of its own". Codes always come before names, and the
list is always 2 or 4 tokens long — **never 1, never 3**.

That reads back unambiguously because a code carries its own segment: the
14 grid9 codes (`10 20 30 40 50 60 70 80 90 15 25 35 45 65`) and the 14
diamond4 codes (`11 22 33 44 55 66 77 88 99 51 52 53 54 56`) are disjoint
sets, so each token says which half it belongs to, and its position
within that half is its slot. Both tools order the picks the same
canonical way (independent picks first, whole gods last — `canonical_order`
in `godslies.py`, `canonicalOrder` in `godslies.html`), which is also the
order `godslies.html` settles its four selection boxes into once all of
them are filled, so the boxes, the key and the header always agree.

`seed` is always the key's real seed (not a separate decorative field) —
which means **the header alone can reconstruct the exact key needed to
decode the message**, with no separately shared key file required, as
long as `GOD_CODES` is known (it's fixed and built into both tools).
`mood`/`punctuation` are the only two fields that stay purely
free-text/contextual; they ride along in plain text and are never
enciphered.

Neither tool writes a trailing `#` any more — it was a personal
end-of-conversation mark from the notebook's legend ("Fin de
conversat."), not something every message needs. Both readers still skip
a lone `#` line, so anything written before still parses, and you can
still type one yourself.

Messages in the older `mood_slotA_slotB_seed_punctuation` form (five
underscore-separated fields, each slot either a single code or a
`grid.diamond` pair) are still read by both tools — the field count tells
the two grammars apart, even when mood and punctuation are empty.

`godslies.html`'s Write tab computes the whole header straight from
whatever key is currently set in its own picker, and prints a
plain-language reading of it underneath — you never have to work the
codes out by hand. Read's "paste a message" option derives the key
straight from a pasted header when one's present, independent of
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
