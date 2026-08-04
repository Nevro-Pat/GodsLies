// Renders the current encoded result to an image (the "copy image" /
// "download image" buttons).
import { t } from "../i18n.js";
import { parseCode, nameFor } from "../cipher/gods.js";
import { drawGlyphPath } from "./glyph-render.js";

const IMG_CELL = 64;
const IMG_GAP = 8;
const IMG_PAD = 14;
const IMG_MAX_WIDTH = 900;
const IMG_FONT = "600 20px ui-sans-serif, system-ui, sans-serif";
const IMG_CAPTION_H = 38;
const IMG_CAPTION_FONT = "600 16px ui-sans-serif, system-ui, sans-serif";

// Renders the current encoded result (the same tokens renderGlyphStream
// shows on screen) to an offscreen canvas built entirely from vector paths
// and fillText -- no <img>, so toBlob()/toDataURL() stay untainted (see
// drawGlyphPath in glyph-render.js). Used by both the "copy image" and
// "download image" buttons. Mood/punctuation are a caption line under the
// symbols, the same envelope-not-ciphertext role .tag-row gives them on
// screen.
export function buildEncodedImageCanvas(coded, mood, punct, key) {
  const tokens = coded.split(/\s+/).filter(Boolean);
  const items = [];
  for (const tok of tokens) {
    if (tok === "/") { items.push({ type: "space" }); continue; }
    if (/^[GD]/i.test(tok) && tok.length >= 2) {
      try {
        const [seg, which, pos] = parseCode(tok);
        items.push({ type: "glyph", god: nameFor(key, seg, which), seg, pos });
        continue;
      } catch { /* not actually a slot code -- fall through to literal */ }
    }
    items.push({ type: "text", text: tok });
  }

  const measure = document.createElement("canvas").getContext("2d");
  measure.font = IMG_FONT;
  const cells = items.map(item => {
    if (item.type === "glyph") return { ...item, w: IMG_CELL };
    if (item.type === "space") return { ...item, w: IMG_CELL / 2 };
    return { ...item, w: Math.max(IMG_CELL * 0.55, measure.measureText(item.text).width + 20) };
  });
  measure.font = IMG_CAPTION_FONT;

  // wrap into rows the same way the on-screen flex-wrap glyph-stream
  // does, just computed up front since a canvas can't reflow after draw
  const rows = [[]];
  let rowW = IMG_PAD;
  for (const cell of cells) {
    if (rows[rows.length - 1].length && rowW + cell.w + IMG_PAD > IMG_MAX_WIDTH) {
      rows.push([]);
      rowW = IMG_PAD;
    }
    rows[rows.length - 1].push(cell);
    rowW += cell.w + IMG_GAP;
  }

  // The mood/punctuation caption: its own row of solid pills under the
  // message, drawn only when at least one of the two is set (a picture
  // captioned "Mood — · Punctuation —" would be noise). Pills, not plain
  // text: decodeImageToTokens tells captions from symbols by their solid
  // fill, so a bare text line would be read back as a row of stray marks.
  const capCells = ((mood || punct)
    ? [`${t("mood_label_short")} ${mood || "—"}`, `${t("punct_label_short")} ${punct || "—"}`]
    : []
  ).map(text => ({ text, w: measure.measureText(text).width + 24 }));
  const capW = capCells.length
    ? IMG_PAD * 2 + capCells.reduce((s, c) => s + c.w, 0) + IMG_GAP * (capCells.length - 1) : 0;

  const rowWidths = rows.map(r => IMG_PAD * 2 + r.reduce((s, c) => s + c.w, 0) + IMG_GAP * Math.max(0, r.length - 1));
  const canvasW = Math.max(...rowWidths, capW, IMG_CELL + IMG_PAD * 2);
  const canvasH = IMG_PAD * 2 + rows.length * IMG_CELL + IMG_GAP * (rows.length - 1)
    + (capCells.length ? IMG_CAPTION_H + IMG_GAP : 0);

  // read the page's own current theme colors (light or dark, whichever is
  // active) rather than hardcoding, so the exported image always matches
  // what's on screen right now
  const style = getComputedStyle(document.documentElement);
  const colors = {
    bg: style.getPropertyValue("--bg-card").trim(),
    ink: style.getPropertyValue("--ink").trim(),
    border: style.getPropertyValue("--border").trim(),
    tag: style.getPropertyValue("--accent-soft").trim(),
  };

  const canvas = document.createElement("canvas");
  canvas.width = canvasW;
  canvas.height = canvasH;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = colors.bg;
  ctx.fillRect(0, 0, canvasW, canvasH);
  ctx.font = IMG_FONT;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  let y = IMG_PAD;
  for (const row of rows) {
    let x = IMG_PAD;
    for (const cell of row) {
      if (cell.type === "glyph") {
        ctx.strokeStyle = colors.border;
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, cell.w - 1, IMG_CELL - 1);
        ctx.fillStyle = colors.ink;
        const pad = cell.w * 0.08;
        drawGlyphPath(ctx, cell.god, cell.seg, cell.pos, x + pad, y + pad, cell.w - pad * 2);
      } else if (cell.type === "text") {
        ctx.fillStyle = colors.tag;
        ctx.fillRect(x, y, cell.w, IMG_CELL);
        ctx.fillStyle = colors.ink;
        ctx.fillText(cell.text, x + cell.w / 2, y + IMG_CELL / 2 + 1);
      } else if (cell.type === "space") {
        // A thin divider, mirroring the on-screen .space rule. Drawn rather
        // than left blank so a word break is still visible (and still
        // readable back by decodeImageToTokens) when it happens to fall at
        // the very start or end of a wrapped row, where an empty cell would
        // leave no gap to infer it from.
        ctx.fillStyle = colors.border;
        ctx.fillRect(x + cell.w / 2 - 1.5, y + IMG_CELL * 0.25, 3, IMG_CELL * 0.5);
      }
      x += cell.w + IMG_GAP;
    }
    y += IMG_CELL + IMG_GAP;
  }

  if (capCells.length) {
    ctx.font = IMG_CAPTION_FONT;
    let x = IMG_PAD;
    for (const cell of capCells) {
      ctx.fillStyle = colors.tag;
      ctx.fillRect(x, y, cell.w, IMG_CAPTION_H);
      ctx.fillStyle = colors.ink;
      ctx.fillText(cell.text, x + cell.w / 2, y + IMG_CAPTION_H / 2 + 1);
      x += cell.w + IMG_GAP;
    }
  }
  return canvas;
}
