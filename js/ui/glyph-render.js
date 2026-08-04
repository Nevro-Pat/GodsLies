// Glyph image/canvas rendering shared by the chart, the write/read glyph
// streams, and the image export/decode paths.
import { t } from "../i18n.js";
import { FILL_MANIFEST, GLYPH_CONTOURS } from "../data-loader.js";
import { GOD_LABEL, nameFor, parseCode } from "../cipher/gods.js";

// Clamped/minimum-floor glyph scaling: boost a glyph that only fills a
// small fraction of its 160x160 canvas toward a comfortable minimum
// on-screen size, capped so it never grows to look as big as a full
// glyph -- keeps the underlying assets untouched (their true relative
// scale still matters, see extract_assets.py's clean_cell) while fixing
// the "some symbols huge, some tiny" side-by-side look in the chart.
//
// Diamond4 arms need a much higher cap than grid9 cells do: most of
// them are legitimately thin marks (a chevron, sometimes just a dot --
// e.g. Apáte's E arm, or Áte's chevron-plus-dot) with far less native
// ink than a full digit, so the old 1.8x cap left them looking tiny
// next to their own god's grid9 style. 3.0x brings ordinary diamond
// arms close to grid9's visual weight while still keeping an actual
// dot recognizable as a dot, not blown up into a blob -- grid9 cells
// almost never need more than ~1.4x anyway, so raising the shared cap
// only changes diamonds in practice.
const TARGET_FILL = 0.55;
const MAX_BOOST = 3.0;

export function assetPath(name, seg, pos) { return `assets/${name}/${seg}_${pos}.png`; }
export function fillScale(name, seg, pos) {
  const fill = FILL_MANIFEST[`${name}/${seg}_${pos}`];
  if (!fill) return 1;
  return Math.min(MAX_BOOST, Math.max(1, TARGET_FILL / fill));
}

export function glyphImg(seg, which, pos, key, cls = "glyph") {
  const name = nameFor(key, seg, which);
  const img = document.createElement("img");
  img.className = cls;
  img.src = assetPath(name, seg, pos);
  img.alt = `${name} ${seg} ${pos}`;
  const posLabel = seg === "grid9" ? t("title_glyph_cell", { pos }) : t("title_glyph_arm", { pos });
  img.title = `${GOD_LABEL[name] || name} — ${posLabel}`;
  const scale = fillScale(name, seg, pos);
  if (scale > 1) img.style.transform = `scale(${scale.toFixed(2)})`;
  return img;
}

// A literal text cell (not a glyph) -- used for pass-through punctuation
// and digits inside a coded token stream. Built with textContent (never
// innerHTML) since this carries raw user-typed text.
export function litCell(text) {
  const cell = document.createElement("div");
  cell.className = "cell";
  const span = document.createElement("span");
  span.className = "lit";
  span.textContent = text;
  cell.appendChild(span);
  return cell;
}

// Shared renderer for both the encode result (read-only) and the decode
// sequence being built (click-to-remove) -- smaller cells than the chart
// so a full message stays scannable at a glance, with a thin divider
// (not a blank gap) marking each word break.
export function renderGlyphStream(tokens, key, container, onRemove) {
  container.innerHTML = "";
  if (tokens.length === 0) {
    container.innerHTML = `<span class="empty-hint">${onRemove ? t("sequence_empty_hint") : t("nothing_encoded_yet")}</span>`;
    return;
  }
  tokens.forEach((tok, i) => {
    if (tok === "/") {
      const sp = document.createElement("div");
      sp.className = "space";
      if (onRemove) { sp.style.cursor = "pointer"; sp.title = t("title_click_to_remove"); sp.onclick = () => onRemove(i); }
      container.appendChild(sp);
      return;
    }
    let cell;
    if (/^[GD]/i.test(tok) && tok.length >= 2) {
      try {
        const [seg, which, pos] = parseCode(tok);
        cell = document.createElement(onRemove ? "button" : "div");
        cell.className = "cell";
        cell.appendChild(glyphImg(seg, which, pos, key));
      } catch { cell = litCell(tok); }
    } else {
      cell = litCell(tok);
    }
    if (onRemove) { cell.title = t("title_click_to_remove"); cell.onclick = () => onRemove(i); }
    container.appendChild(cell);
  });
}

// The one and only way mood/punctuation are ever displayed: a labelled row
// under the result, in Write and Read alike, "—" for an unset field. They
// used to be cells at the two ends of the glyph stream, which read as part
// of the ciphertext and had nowhere to appear at all on the Read side.
export function renderTagRow(container, mood, punct) {
  container.innerHTML = "";
  for (const [labelKey, value] of [["mood_label_short", mood], ["punct_label_short", punct]]) {
    const item = document.createElement("div");
    const label = document.createElement("span");
    label.className = "tag-label";
    label.textContent = t(labelKey);
    const val = document.createElement("span");
    val.className = "tag-value" + (value ? "" : " empty");
    val.textContent = value || "—";
    item.append(label, val);
    container.appendChild(item);
  }
}

// `onClick(seg, which, pos)`, when given, turns every cell into a button
// that appends its symbol to a sequence being built -- used by Read so
// the alphabet chart doubles as the decode input surface.
export function renderChart(key, container, onClick) {
  container.innerHTML = "";
  const letters = Object.keys(key.letter_to_slot).sort();
  for (const letter of letters) {
    const [seg, which, pos] = key.letter_to_slot[letter];
    const cell = document.createElement(onClick ? "button" : "div");
    cell.className = "cell" + (onClick ? " clickable" : "");
    if (onClick) { cell.type = "button"; cell.title = t("title_click_to_add", { letter }); }
    cell.appendChild(glyphImg(seg, which, pos, key));
    if (onClick) cell.onclick = () => onClick(seg, which, pos);
    container.appendChild(cell);
  }
}

// matches extract_assets.py's CANVAS -- the pixel space GLYPH_CONTOURS is
// traced in. Also used by cipher/font-builder.js's contoursToFontPoints().
export const FONT_CANVAS = 160;

export function glyphContoursFor(god, seg, pos) {
  return GLYPH_CONTOURS[`${god}/${seg}_${pos}`] || [];
}

// Draws one glyph straight from the baked vector contours (raw 160x160
// pixel space, same y-down orientation a canvas already uses -- no flip
// needed here, unlike contoursToFontPoints() in font-builder.js which flips
// for a font's bottom-up baseline space). Deliberately never draws an <img>
// -- canvas getImageData()/toBlob()/toDataURL() all throw a SecurityError
// once a file://-loaded image has touched the canvas (same constraint
// documented on GLYPH_CONTOURS in data-loader.js), so the "copy/download as
// image" feature (image-export.js) has to stay pure vector paths the whole
// way through, same as the font builder does.
export function drawGlyphPath(ctx, god, seg, pos, x, y, size) {
  const contours = glyphContoursFor(god, seg, pos);
  if (!contours.length) return;
  const scale = size / FONT_CANVAS;
  ctx.beginPath();
  for (const flat of contours) {
    for (let i = 0; i < flat.length; i += 2) {
      const px = x + flat[i] * scale, py = y + flat[i + 1] * scale;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
  }
  // evenodd, not the canvas default nonzero -- a glyph's contours can
  // include both an outer and inner boundary for a ring/hole shape (e.g.
  // Hermes' closed-box center cell), and evenodd is what makes the second
  // contour subtract a hole instead of filling solid, independent of
  // which way each contour happens to wind.
  ctx.fill("evenodd");
}
