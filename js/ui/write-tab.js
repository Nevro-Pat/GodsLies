// --- Write tab ---
import { t } from "../i18n.js";
import { SAMPLE_MESSAGES } from "../data-loader.js";
import { cipherField, cipherFieldSummary } from "../cipher/gods.js";
import { encode, textToCipherFontText } from "../cipher/encode-decode.js";
import { renderGlyphStream, renderTagRow } from "./glyph-render.js";
import { buildEncodedImageCanvas } from "./image-export.js";
import { downloadBlob } from "./download-utils.js";
import { wireCopy } from "../copy-utils.js";

// Seed the plaintext field with a random sample so there's something to
// Encode right away -- cleared the first time it's actually focused (only
// while still the untouched sample, so tabbing back into a real message
// never wipes it). Mood and punctuation deliberately get no sample:
// pre-filled values vanishing on focus was half of why those two fields
// felt like they came and went.
function seedSampleField(id, pool) {
  const el = document.getElementById(id);
  el.value = pool[Math.floor(Math.random() * pool.length)];
  let isSample = true;
  el.addEventListener("focus", () => {
    if (isSample) { el.value = ""; isSample = false; }
  });
}

export function initWriteTab(cipher) {
  let lastWriteCoded = "";
  let lastWriteFull = "";
  let lastWriteMood = "";
  let lastWritePunct = "";
  let lastWritePlainText = "";
  // Tracks "Encode has been pressed at least once since the last Clear" --
  // separately from lastWritePlainText, which is legitimately empty when an
  // empty message was encoded, and would then leave the result area frozen
  // on the old key's header.
  let hasWriteResult = false;

  seedSampleField("write-plainText", SAMPLE_MESSAGES);

  const writeGlyphsEl = document.getElementById("write-encodeGlyphs");
  const writeTagRowEl = document.getElementById("write-tagRow");
  const writeHeaderEl = document.getElementById("write-headerLine");
  const writeSummaryEl = document.getElementById("write-headerSummary");
  const writeFullTextEl = document.getElementById("write-fullTextOut");

  // Draws (or redraws) the whole Write result from the current key: glyph
  // stream, mood/punctuation row, header, its plain-language reading, and
  // the text box "Copy as codes" copies verbatim. One function for all of
  // it, so the parts can't drift out of step with each other or the key.
  function renderWriteResult(key) {
    const coded = encode(lastWritePlainText, key);
    lastWriteCoded = coded;
    hasWriteResult = true;
    renderGlyphStream(coded.split(/\s+/).filter(Boolean), key, writeGlyphsEl);
    renderTagRow(writeTagRowEl, lastWriteMood, lastWritePunct);

    const header = `${lastWriteMood}_${cipherField(key.grid9_gods, key.diamond4_gods)}_${key.seed}_${lastWritePunct}`;
    lastWriteFull = `${header}\n${coded}`;
    writeHeaderEl.textContent = t("header_line", { header });
    writeSummaryEl.textContent = cipherFieldSummary(key.grid9_gods, key.diamond4_gods, key.seed);
    writeFullTextEl.value = lastWriteFull;
  }

  // Wipes it back to "nothing written yet" when the key goes away -- every
  // glyph on screen was drawn from that key, and would otherwise sit there
  // describing a cipher that no longer exists.
  function resetWriteResult() {
    lastWriteCoded = ""; lastWriteFull = ""; lastWritePlainText = "";
    lastWriteMood = ""; lastWritePunct = ""; hasWriteResult = false;
    renderGlyphStream([], null, writeGlyphsEl);
    writeTagRowEl.innerHTML = "";
    writeHeaderEl.textContent = "";
    writeSummaryEl.textContent = "";
    writeFullTextEl.value = "";
  }

  document.getElementById("write-encodeBtn").onclick = () => {
    const key = cipher.getKey();
    if (!key) { alert(t("alert_choose_4_styles")); return; }
    lastWritePlainText = document.getElementById("write-plainText").value;
    lastWriteMood = document.getElementById("write-moodInput").value.trim();
    lastWritePunct = document.getElementById("write-punctInput").value.trim();
    renderWriteResult(key);
  };

  // "Copy as codes" copies exactly what the text box below the result shows
  // (header + coded body) -- one text, one button, instead of the two
  // near-identical copy paths this used to have.
  wireCopy("write-copyGlyphsBtn", () => lastWriteFull);
  wireCopy("write-copyFontTextBtn", () => textToCipherFontText(lastWritePlainText));

  function encodedImageFilename(key) { return `gods-lies-message-${key.seed}.png`; }

  document.getElementById("write-downloadImageBtn").onclick = () => {
    const key = cipher.getKey();
    if (!key || !lastWriteCoded) { alert(t("alert_generate_key_first")); return; }
    buildEncodedImageCanvas(lastWriteCoded, lastWriteMood, lastWritePunct, key)
      .toBlob(blob => downloadBlob(blob, encodedImageFilename(key)), "image/png");
  };

  // Best-effort clipboard image write -- navigator.clipboard.write with an
  // image ClipboardItem needs a secure context and (depending on browser/
  // permissions) can fail even when writeText works fine elsewhere on this
  // page, so this always falls back to the guaranteed download path on any
  // failure rather than leaving the click looking like it did nothing.
  document.getElementById("write-copyImageBtn").onclick = () => {
    const key = cipher.getKey();
    if (!key || !lastWriteCoded) { alert(t("alert_generate_key_first")); return; }
    const btn = document.getElementById("write-copyImageBtn");
    const original = btn.textContent;
    buildEncodedImageCanvas(lastWriteCoded, lastWriteMood, lastWritePunct, key).toBlob(async blob => {
      try {
        if (!navigator.clipboard || !window.ClipboardItem) throw new Error("unsupported");
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        btn.textContent = t("copy_copied");
      } catch {
        btn.textContent = t("copy_image_unsupported");
        downloadBlob(blob, encodedImageFilename(key));
      }
      setTimeout(() => { btn.textContent = original; }, 1600);
    }, "image/png");
  };

  return {
    // A new/changed key re-draws what's already on screen: the Write
    // result is drawn from the key, so after a re-roll it would otherwise
    // keep showing the previous cipher's symbols.
    renderIfHasResult(key) { if (hasWriteResult) renderWriteResult(key); },
    reset() { resetWriteResult(); },
  };
}
