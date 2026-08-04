/* --- reading a message image back (the Read tab's image upload) ---

   The reverse of buildEncodedImageCanvas: find each drawn cell, then work
   out which glyph it holds by re-rendering all 26 of the current key's
   glyphs and keeping the closest match. Pixel-reading an image is only
   possible here because an *uploaded* image (a blob/data URL from the
   file picker) does not taint the canvas -- unlike the page's own file://
   PNG assets, which do, and which is why glyph contours had to be baked
   at build time in the first place (see data-loader.js's GLYPH_CONTOURS).
   Verified directly rather than assumed, since the two cases look
   identical from the code's point of view and behave oppositely.

   Deliberately does not try to recover the mood/punctuation tags or
   pass-through punctuation: those are drawn as text, and reading them
   back would mean bundling character recognition for an arbitrary font.
   They're detected and counted (they're solid filled pills, ~100% ink,
   versus a glyph cell's thin strokes) so the caller can say how many were
   skipped instead of silently dropping them. */
import { ALL_SLOTS, nameFor, slotCode } from "../cipher/gods.js";
import { drawGlyphPath } from "./glyph-render.js";

const IMG_CELL = 64;
const IMG_DECODE_N = 48;        // normalized size glyphs are compared at
const IMG_COLOR_TOL2 = 900;     // squared RGB distance counting as "ink", ~30/channel

export function runsOf(flags) {
  const runs = [];
  let start = -1;
  for (let i = 0; i < flags.length; i++) {
    if (flags[i] && start < 0) start = i;
    else if (!flags[i] && start >= 0) { runs.push({ start, end: i }); start = -1; }
  }
  if (start >= 0) runs.push({ start, end: flags.length });
  return runs;
}

export function candidateGlyphMask(god, seg, pos) {
  const c = document.createElement("canvas");
  c.width = IMG_DECODE_N; c.height = IMG_DECODE_N;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#000";
  drawGlyphPath(ctx, god, seg, pos, 0, 0, IMG_DECODE_N);
  const d = ctx.getImageData(0, 0, IMG_DECODE_N, IMG_DECODE_N).data;
  const mask = new Uint8Array(IMG_DECODE_N * IMG_DECODE_N);
  for (let i = 0; i < mask.length; i++) mask[i] = d[i * 4 + 3] > 127 ? 1 : 0;
  return mask;
}

// Intersection-over-union complement rather than plain pixel difference:
// these glyphs are mostly empty space, so a raw pixel-match score would sit
// near 100% for every candidate and barely discriminate between them.
export function maskDistance(a, b) {
  let diff = 0, union = 0;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) diff++;
    if (a[i] || b[i]) union++;
  }
  return union ? diff / union : 1;
}

export function decodeImageToTokens(source, key) {
  const w = source.width, h = source.height;
  const work = document.createElement("canvas");
  work.width = w; work.height = h;
  const wctx = work.getContext("2d");
  wctx.drawImage(source, 0, 0);
  const px = wctx.getImageData(0, 0, w, h).data;

  // (0,0) is always padding in a generated image, so it defines the
  // background -- which varies with whichever theme was active when the
  // image was made, hence sampling it instead of hardcoding a colour.
  const bg = [px[0], px[1], px[2]];
  const inked = (x, y) => {
    const i = (y * w + x) * 4;
    const dr = px[i] - bg[0], dg = px[i + 1] - bg[1], db = px[i + 2] - bg[2];
    return dr * dr + dg * dg + db * db > IMG_COLOR_TOL2;
  };

  const rowHas = new Uint8Array(h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) { if (inked(x, y)) { rowHas[y] = 1; break; } }
  }
  const bands = runsOf(rowHas).filter(b => b.end - b.start > 8);
  if (!bands.length) return null;

  const candidates = ALL_SLOTS.map(([seg, which, pos]) => ({
    seg, which, pos,
    mask: candidateGlyphMask(nameFor(key, seg, which), seg, pos),
  }));

  const tokens = [];
  let skippedText = 0;
  let matched = 0;

  for (const band of bands) {
    const bandH = band.end - band.start;
    // A row's height is one cell, so it also tells us how much the image
    // was scaled from the 64px cells it was drawn with.
    const scale = bandH / IMG_CELL;
    const colHas = new Uint8Array(w);
    for (let x = 0; x < w; x++) {
      for (let y = band.start; y < band.end; y++) { if (inked(x, y)) { colHas[x] = 1; break; } }
    }
    const segs = runsOf(colHas);
    for (const s of segs) {
      const segW = s.end - s.start;
      // A word break is drawn as a narrow divider tick, so it segments out
      // on its own -- no need to infer it from the spacing between cells,
      // which silently lost any space that landed at a row boundary.
      if (segW / scale <= 8) { tokens.push("/"); continue; }

      let ink = 0;
      for (let y = band.start; y < band.end; y++) {
        for (let x = s.start; x < s.end; x++) if (inked(x, y)) ink++;
      }
      const fill = ink / (segW * bandH);
      // Text pills are filled solid; a glyph cell is a thin border plus
      // strokes, so it never comes close to this.
      if (fill > 0.8 || segW / scale < IMG_CELL * 0.55) { skippedText++; continue; }

      // Crop to exactly the box drawGlyphPath drew into (the cell inset by
      // the same 8% padding buildEncodedImageCanvas uses), so the crop and
      // the candidates share one coordinate system.
      const pad = segW * 0.08;
      const cell = document.createElement("canvas");
      cell.width = IMG_DECODE_N; cell.height = IMG_DECODE_N;
      const cctx = cell.getContext("2d");
      cctx.drawImage(work, s.start + pad, band.start + pad, segW - pad * 2, bandH - pad * 2,
                     0, 0, IMG_DECODE_N, IMG_DECODE_N);
      const cd = cctx.getImageData(0, 0, IMG_DECODE_N, IMG_DECODE_N).data;
      const mask = new Uint8Array(IMG_DECODE_N * IMG_DECODE_N);
      for (let i = 0; i < mask.length; i++) {
        const dr = cd[i * 4] - bg[0], dg = cd[i * 4 + 1] - bg[1], db = cd[i * 4 + 2] - bg[2];
        mask[i] = dr * dr + dg * dg + db * db > IMG_COLOR_TOL2 ? 1 : 0;
      }

      let best = null, bestD = Infinity;
      for (const cand of candidates) {
        const d = maskDistance(mask, cand.mask);
        if (d < bestD) { bestD = d; best = cand; }
      }
      if (best && bestD < 0.62) {
        tokens.push(slotCode(best.seg, best.which, best.pos));
        matched++;
      } else {
        tokens.push("?");
      }
    }
  }
  return { coded: tokens.join(" "), matched, skippedText };
}
