// In-browser font generator: builds a real, installable .ttf from the
// current key entirely client-side (no server, no Python) -- the same idea
// as make_font.py, using GLYPH_CONTOURS (baked ahead of time by
// `python make_font.py --bake-html`; see glyph-render.js's comment for why
// tracing can't happen here at runtime instead) rather than re-tracing
// images. Hand-rolled minimal TrueType writer, not a vendored font library
// -- this page stays a single self-contained file with no build step, and
// a from-scratch simple-glyph-only TTF (no hinting, no composites, no
// curves -- these are traced line art, straight-line contours only) is a
// modest amount of code for what it buys.
import { FONT_CANVAS, glyphContoursFor } from "../ui/glyph-render.js";
import { PUA_BASE } from "./encode-decode.js";

const FONT_UNITS_PER_EM = 1000;
const FONT_GLYPH_TOP = 720;   // every symbol scales to fit under this height, sitting on the baseline
const FONT_ADVANCE = 820;
const FONT_SPACE_ADVANCE = 500;
const FONT_ASCENT = 900;
const FONT_DESCENT = -200;

// --- minimal big-endian binary writer (TrueType is big-endian throughout) ---
class ByteWriter {
  constructor() { this.chunks = []; this.length = 0; }
  u8(v) { this.chunks.push(Uint8Array.of(v & 0xFF)); this.length += 1; return this; }
  u16(v) { const b = new Uint8Array(2); new DataView(b.buffer).setUint16(0, v & 0xFFFF, false); this.chunks.push(b); this.length += 2; return this; }
  i16(v) { const b = new Uint8Array(2); new DataView(b.buffer).setInt16(0, v, false); this.chunks.push(b); this.length += 2; return this; }
  u32(v) { const b = new Uint8Array(4); new DataView(b.buffer).setUint32(0, v >>> 0, false); this.chunks.push(b); this.length += 4; return this; }
  tag(s) { this.chunks.push(new TextEncoder().encode((s + "    ").slice(0, 4))); this.length += 4; return this; }
  bytes(arr) { this.chunks.push(arr); this.length += arr.length; return this; }
  toUint8Array() {
    const out = new Uint8Array(this.length);
    let off = 0;
    for (const c of this.chunks) { out.set(c, off); off += c.length; }
    return out;
  }
}

function padTo4(bytes) {
  const rem = bytes.length % 4;
  if (rem === 0) return bytes;
  const out = new Uint8Array(bytes.length + (4 - rem));
  out.set(bytes);
  return out;
}

function tableChecksum(bytes) {
  let sum = 0;
  const len4 = Math.ceil(bytes.length / 4) * 4;
  for (let i = 0; i < len4; i += 4) {
    const b0 = bytes[i] || 0, b1 = bytes[i + 1] || 0, b2 = bytes[i + 2] || 0, b3 = bytes[i + 3] || 0;
    sum = (sum + (((b0 << 24) | (b1 << 16) | (b2 << 8) | b3) >>> 0)) >>> 0;
  }
  return sum >>> 0;
}

// glyf, simple glyphs only: every point on-curve (straight lines between
// them, no quadratic curves -- these are traced line art, not calligraphy),
// and always 2-byte coordinate deltas (never the compact 1-byte "short"
// form). Less compact, but removes an entire class of off-by-one risk for
// a few hundred extra bytes on a font that's a few dozen KB either way.
function encodeSimpleGlyph(contours) {
  // contours: array of arrays of [x, y] integer font-unit points, not
  // repeating the first point at the end of each contour.
  if (contours.length === 0) return { data: new Uint8Array(0), xMin: 0, yMin: 0, xMax: 0, yMax: 0, numPoints: 0, numContours: 0 };
  const allPoints = [];
  const endPts = [];
  for (const c of contours) {
    for (const p of c) allPoints.push(p);
    endPts.push(allPoints.length - 1);
  }
  let xMin = Infinity, yMin = Infinity, xMax = -Infinity, yMax = -Infinity;
  for (const [x, y] of allPoints) {
    if (x < xMin) xMin = x; if (x > xMax) xMax = x;
    if (y < yMin) yMin = y; if (y > yMax) yMax = y;
  }
  const w = new ByteWriter();
  w.i16(contours.length);
  w.i16(xMin); w.i16(yMin); w.i16(xMax); w.i16(yMax);
  for (const e of endPts) w.u16(e);
  w.u16(0); // instructionLength
  for (let i = 0; i < allPoints.length; i++) w.u8(0x01); // on-curve, not-short x, not-short y
  let prevX = 0;
  for (const [x] of allPoints) { w.i16(x - prevX); prevX = x; }
  let prevY = 0;
  for (const [, y] of allPoints) { w.i16(y - prevY); prevY = y; }
  return { data: w.toUint8Array(), xMin, yMin, xMax, yMax, numPoints: allPoints.length, numContours: contours.length };
}

// Raw baked pixel-space contours ([x,y,x,y,...] flat per polygon, from
// GLYPH_CONTOURS) -> font-unit point lists for one glyph. Mirrors
// make_font.py's build_glyph() exactly (same GLYPH_TOP/CANVAS constants,
// same y-flip -- images are top-down, font em-space is bottom-up from the
// baseline) so the browser-built font matches the Python one for the same
// key.
function contoursToFontPoints(flatContours) {
  const scale = FONT_GLYPH_TOP / FONT_CANVAS;
  return flatContours.map(flat => {
    const pts = [];
    for (let i = 0; i < flat.length; i += 2) {
      const x = flat[i], y = flat[i + 1];
      pts.push([Math.round(x * scale), Math.round((FONT_CANVAS - y) * scale)]);
    }
    return pts;
  });
}

// cmap format 4, one segment per mapped codepoint. Less compact than
// merging consecutive codepoints that happen to share a constant
// glyph-index delta into shared segments, but trivially correct for any
// mapping pattern without having to detect which runs are safe to merge
// -- including many-to-one accent folding (à/á/â/... all landing on the
// same "A" glyph), which a naive constant-delta run can't represent.
function buildCmapFormat4(cmapEntries) {
  const codes = [...cmapEntries.keys()].sort((a, b) => a - b);
  const segments = codes.map(cp => {
    const gid = cmapEntries.get(cp);
    let delta = gid - cp;
    while (delta < -32768) delta += 65536;
    while (delta > 32767) delta -= 65536;
    return { start: cp, end: cp, delta };
  });
  segments.push({ start: 0xFFFF, end: 0xFFFF, delta: 1 }); // required terminator segment
  const segCount = segments.length;
  const pow2 = 2 ** Math.floor(Math.log2(segCount));
  const searchRange = 2 * pow2;
  const entrySelector = Math.floor(Math.log2(segCount));
  const rangeShift = 2 * segCount - searchRange;

  const w = new ByteWriter();
  w.u16(4);
  const lengthPos = w.length; w.u16(0); // patched below, once the final byte length is known
  w.u16(0); // language
  w.u16(segCount * 2);
  w.u16(searchRange);
  w.u16(entrySelector);
  w.u16(rangeShift);
  for (const s of segments) w.u16(s.end);
  w.u16(0); // reservedPad
  for (const s of segments) w.u16(s.start);
  for (const s of segments) w.i16(s.delta);
  for (const s of segments) w.u16(0); // idRangeOffset -- always 0, we only ever use idDelta
  const bytes = w.toUint8Array();
  new DataView(bytes.buffer).setUint16(lengthPos, bytes.length, false);
  return bytes;
}

function buildCmapTable(cmapEntries) {
  const sub = buildCmapFormat4(cmapEntries);
  const headerSize = 4 + 2 * 8;
  const w = new ByteWriter();
  w.u16(0); w.u16(2);
  w.u16(3); w.u16(1); w.u32(headerSize); // Windows, Unicode BMP
  w.u16(0); w.u16(3); w.u32(headerSize); // Unicode, BMP
  w.bytes(sub);
  return w.toUint8Array();
}

function buildHeadTable(unitsPerEm, xMin, yMin, xMax, yMax, indexToLocFormat) {
  const w = new ByteWriter();
  w.u16(1); w.u16(0);          // version 1.0
  w.u16(1); w.u16(0);          // fontRevision 1.0
  w.u32(0);                    // checkSumAdjustment -- patched in after the whole font is assembled
  w.u32(0x5F0F3CF5);           // magicNumber
  w.u16(0);                    // flags
  w.u16(unitsPerEm);
  w.u32(0); w.u32(0);          // created
  w.u32(0); w.u32(0);          // modified
  w.i16(xMin); w.i16(yMin); w.i16(xMax); w.i16(yMax);
  w.u16(0);                    // macStyle
  w.u16(8);                    // lowestRecPPEM
  w.i16(2);                    // fontDirectionHint
  w.i16(indexToLocFormat);
  w.i16(0);                    // glyphDataFormat
  return w.toUint8Array();
}

function buildHheaTable(ascent, descent, advanceWidthMax, minLSB, minRSB, xMaxExtent, numberOfHMetrics) {
  const w = new ByteWriter();
  w.u16(1); w.u16(0);
  w.i16(ascent); w.i16(descent); w.i16(0); // lineGap
  w.u16(advanceWidthMax);
  w.i16(minLSB); w.i16(minRSB); w.i16(xMaxExtent);
  w.i16(1); w.i16(0); w.i16(0); // caretSlopeRise/Run/Offset
  w.i16(0); w.i16(0); w.i16(0); w.i16(0); // reserved
  w.i16(0); // metricDataFormat
  w.u16(numberOfHMetrics);
  return w.toUint8Array();
}

function buildMaxpTable(numGlyphs, maxPoints, maxContours) {
  const w = new ByteWriter();
  w.u32(0x00010000);
  w.u16(numGlyphs);
  w.u16(maxPoints); w.u16(maxContours);
  w.u16(0); w.u16(0); // maxCompositePoints/Contours -- no composite glyphs
  w.u16(2);           // maxZones
  w.u16(0); w.u16(0); w.u16(0); w.u16(0); w.u16(0); // maxTwilightPoints, maxStorage, maxFunctionDefs, maxInstructionDefs, maxStackElements
  w.u16(0); w.u16(0); w.u16(0); // maxSizeOfInstructions, maxComponentElements, maxComponentDepth
  return w.toUint8Array();
}

function buildHmtxTable(metrics) {
  const w = new ByteWriter();
  for (const [aw, lsb] of metrics) { w.u16(aw); w.i16(lsb); }
  return w.toUint8Array();
}

function buildLocaTableLong(offsets) {
  const w = new ByteWriter();
  for (const o of offsets) w.u32(o);
  return w.toUint8Array();
}

function buildNameTable(strings) {
  const nameIDs = [1, 2, 3, 4, 5, 6];
  const records = [];
  const blobs = [];
  let offset = 0;
  for (const id of nameIDs) {
    const str = strings[id];
    const bytes = new Uint8Array(str.length * 2);
    const dv = new DataView(bytes.buffer);
    for (let i = 0; i < str.length; i++) dv.setUint16(i * 2, str.charCodeAt(i), false);
    records.push({ nameID: id, length: bytes.length, offset });
    blobs.push(bytes);
    offset += bytes.length;
  }
  const w = new ByteWriter();
  w.u16(0); // format
  w.u16(records.length);
  w.u16(6 + records.length * 12); // storageOffset: 6-byte header + 12 bytes/record
  for (const r of records) w.u16(3).u16(1).u16(0x0409).u16(r.nameID).u16(r.length).u16(r.offset);
  for (const b of blobs) w.bytes(b);
  return w.toUint8Array();
}

function buildPostTable() {
  const w = new ByteWriter();
  w.u32(0x00030000); // version 3.0 -- no per-glyph names, smallest valid form
  w.u32(0); w.i16(0); w.i16(0);
  w.u32(0);
  w.u32(0); w.u32(0); w.u32(0); w.u32(0);
  return w.toUint8Array();
}

function buildOS2Table(ascent, descent, avgCharWidth) {
  const w = new ByteWriter();
  w.u16(4);
  w.i16(Math.round(avgCharWidth));
  w.u16(400); w.u16(5); w.u16(0);                 // usWeightClass, usWidthClass, fsType
  w.i16(650); w.i16(700); w.i16(0); w.i16(140);   // subscript size/offset (rough defaults)
  w.i16(650); w.i16(700); w.i16(0); w.i16(480);   // superscript size/offset
  w.i16(50); w.i16(260);                          // strikeout size/position
  w.i16(0);                                       // sFamilyClass
  for (let i = 0; i < 10; i++) w.u8(0);           // panose ("any")
  w.u32(0b1111); w.u32(0); w.u32(0); w.u32(0);    // unicodeRange1-4: Basic Latin + Latin-1 Supp + Latin Ext-A/B
  w.tag("NONE");                                   // achVendID
  w.u16(0x0040);                                   // fsSelection: REGULAR
  w.u16(0x0020); w.u16(0x017F);                    // usFirstCharIndex/usLastCharIndex
  w.i16(ascent); w.i16(descent); w.i16(90);        // sTypoAscender/Descender/LineGap
  w.u16(ascent); w.u16(-descent);                  // usWinAscent/Descent
  w.u32(1); w.u32(0);                              // ulCodePageRange1/2: Latin1
  w.i16(500); w.i16(ascent);                       // sxHeight, sCapHeight (rough)
  w.u16(0); w.u16(0x0020); w.u16(1);               // usDefaultChar, usBreakChar, usMaxContext
  return w.toUint8Array();
}

// Assembles the full sfnt binary: table directory (sorted by tag, as
// required) + each table padded to a 4-byte boundary, then patches in the
// whole-font checksum adjustment that `head` reserves space for -- per
// spec, computed treating that field as 0, which is exactly the state
// `bytes` is still in at the point tableChecksum(bytes) runs below.
function assembleFont(tables) {
  const tags = Object.keys(tables).sort();
  const numTables = tags.length;
  const entrySelector = Math.floor(Math.log2(numTables));
  const searchRange = (2 ** entrySelector) * 16;
  const rangeShift = numTables * 16 - searchRange;

  const headerSize = 12 + numTables * 16;
  const padded = {};
  let offset = headerSize;
  const dir = [];
  for (const t of tags) {
    const raw = tables[t];
    const p = padTo4(raw);
    padded[t] = p;
    dir.push({ tag: t, checksum: tableChecksum(p), offset, length: raw.length });
    offset += p.length;
  }

  const w = new ByteWriter();
  w.u32(0x00010000);
  w.u16(numTables); w.u16(searchRange); w.u16(entrySelector); w.u16(rangeShift);
  for (const e of dir) { w.tag(e.tag); w.u32(e.checksum); w.u32(e.offset); w.u32(e.length); }
  for (const t of tags) w.bytes(padded[t]);

  const bytes = w.toUint8Array();
  const headEntry = dir.find(e => e.tag === "head");
  const wholeFontSum = tableChecksum(bytes);
  const adjustment = (0xB1B0AFBA - wholeFontSum) >>> 0;
  new DataView(bytes.buffer).setUint32(headEntry.offset + 8, adjustment, false);
  return bytes;
}

// Every precomposed Latin letter that NFD-decomposes to a plain A-Z/a-z
// base maps to that base letter's glyph too -- same idea as
// make_font.py's accented_cmap_extra(), so typing an ordinary accented
// letter doesn't show a blank box. Ligatures (no single-letter NFD
// decomposition -- œ's, if any, is to TWO letters) are left undefined,
// same as digits/punctuation.
function accentedCmapExtra(baseLetterGlyphId) {
  const extra = new Map();
  for (let cp = 0x00C0; cp < 0x0250; cp++) {
    const ch = String.fromCodePoint(cp);
    const base = ch.normalize("NFD")[0];
    if (base !== ch && baseLetterGlyphId.has(base)) extra.set(cp, baseLetterGlyphId.get(base));
  }
  return extra;
}

export function buildFontFromKey(key, familyName) {
  const glyphOrder = [".notdef", "space"];
  const glyphData = [encodeSimpleGlyph([]), encodeSimpleGlyph([])];
  const advances = [[FONT_ADVANCE, 0], [FONT_SPACE_ADVANCE, 0]];
  const cmap = new Map([[32, 1]]); // space -> glyph index 1
  const baseLetterGlyphId = new Map();

  let maxPoints = 0, maxContours = 0;
  let fxMin = 0, fyMin = 0, fxMax = 0, fyMax = 0;

  for (const letter of "ABCDEFGHIJKLMNOPQRSTUVWXYZ") {
    const [seg, which, pos] = key.letter_to_slot[letter];
    const god = (seg === "grid9" ? key.grid9_gods : key.diamond4_gods)[which];
    const contours = contoursToFontPoints(glyphContoursFor(god, seg, pos));
    const g = encodeSimpleGlyph(contours);
    const glyphIndex = glyphOrder.length;
    glyphOrder.push(`cipher.${letter}`);
    glyphData.push(g);
    advances.push([FONT_ADVANCE, g.xMin]);
    cmap.set(letter.charCodeAt(0), glyphIndex);
    cmap.set(letter.toLowerCase().charCodeAt(0), glyphIndex);
    cmap.set(PUA_BASE + (letter.charCodeAt(0) - 65), glyphIndex); // see textToCipherFontText() in encode-decode.js
    baseLetterGlyphId.set(letter, glyphIndex);
    baseLetterGlyphId.set(letter.toLowerCase(), glyphIndex);
    maxPoints = Math.max(maxPoints, g.numPoints);
    maxContours = Math.max(maxContours, g.numContours);
    if (g.numContours > 0) {
      fxMin = Math.min(fxMin, g.xMin); fyMin = Math.min(fyMin, g.yMin);
      fxMax = Math.max(fxMax, g.xMax); fyMax = Math.max(fyMax, g.yMax);
    }
  }
  for (const [cp, gid] of accentedCmapExtra(baseLetterGlyphId)) cmap.set(cp, gid);

  const numGlyphs = glyphOrder.length;
  const glyfWriter = new ByteWriter();
  const locaOffsets = [0];
  for (const g of glyphData) { glyfWriter.bytes(padTo4(g.data)); locaOffsets.push(glyfWriter.length); }

  const tables = {
    "cmap": buildCmapTable(cmap),
    "glyf": glyfWriter.toUint8Array(),
    "head": buildHeadTable(FONT_UNITS_PER_EM, fxMin, fyMin, fxMax, fyMax, 1),
    "hhea": buildHheaTable(FONT_ASCENT, FONT_DESCENT, FONT_ADVANCE, 0, 0, fxMax, numGlyphs),
    "hmtx": buildHmtxTable(advances),
    "loca": buildLocaTableLong(locaOffsets),
    "maxp": buildMaxpTable(numGlyphs, maxPoints, maxContours),
    "name": buildNameTable({
      1: familyName, 2: "Regular", 3: `${familyName};GodsLies;${key.seed}`,
      4: familyName, 5: "Version 1.0", 6: familyName.replace(/[^A-Za-z0-9]/g, "") + "-Regular",
    }),
    "post": buildPostTable(),
    "OS/2": buildOS2Table(FONT_ASCENT, FONT_DESCENT, FONT_ADVANCE),
  };
  return assembleFont(tables);
}
