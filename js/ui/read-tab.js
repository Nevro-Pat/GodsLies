// --- Read tab: the alphabet chart above (in "Your key") is the
// click-to-build decode surface -- clicking a symbol there appends it to
// the sequence. ---
import { t } from "../i18n.js";
import {
  slotCode, looksLikeCipherField, parseLegacyGodRef, keyFromHeader, keyFromLegacyHeader,
} from "../cipher/gods.js";
import { decode } from "../cipher/encode-decode.js";
import { renderGlyphStream, renderTagRow } from "./glyph-render.js";
import { decodeImageToTokens } from "./image-decode.js";
import { wireCopy } from "../copy-utils.js";

export function initReadTab(cipher) {
  let readDecodeSeq = [];

  function renderReadSequence() {
    const key = cipher.getKey();
    renderGlyphStream(readDecodeSeq, key, document.getElementById("read-sequenceStrip"), (i) => {
      readDecodeSeq.splice(i, 1);
      renderReadSequence();
    });
    document.getElementById("read-plainOut").value = key ? decode(readDecodeSeq.join(" "), key) : "";
  }

  cipher.setChartClickHandler((seg, which, pos) => {
    readDecodeSeq.push(slotCode(seg, which, pos));
    renderReadSequence();
  });

  document.getElementById("read-spaceBtn").onclick = () => { readDecodeSeq.push("/"); renderReadSequence(); };
  document.getElementById("read-undoBtn").onclick = () => { readDecodeSeq.pop(); renderReadSequence(); };
  document.getElementById("read-clearSeqBtn").onclick = () => { readDecodeSeq = []; renderReadSequence(); };

  wireCopy("read-copyPlainBtn", () => document.getElementById("read-plainOut").value);

  let lastPasteMood = "", lastPastePunct = "", lastPasteHadHeader = false;
  const pasteOutEl = document.getElementById("read-pasteOut");
  const pasteTagRowEl = document.getElementById("read-pasteMoodPunct");

  // --- Read: one paste box, header optional. If the first line parses as a
  // mood_cipherField_seed_punctuation header, its own codes/names rebuild the
  // key (even a different one than what's selected above); otherwise the whole
  // paste is treated as coded body and decoded with the key selected above.
  // A lone "#" line is still skipped -- messages written when this tool used
  // to append one still read fine, it just isn't written any more. ---
  document.getElementById("read-pasteBtn").onclick = () => {
    const lines = document.getElementById("read-pasteIn").value
      .split("\n").map(l => l.trim()).filter(l => l && l !== "#");
    if (!lines.length) { alert(t("alert_paste_first")); return; }

    const parts = lines[0].split("_");
    let mood = "", punct = "", key = null, body = "";
    // 4 fields = current grammar, 5 = the older mood_slotA_slotB_seed_punct
    // one. The two can never be confused: the count differs even when mood
    // and punctuation are both empty.
    const isHeader = (parts.length === 4 && looksLikeCipherField(parts[1]))
      || (parts.length === 5 && parseLegacyGodRef(parts[1])[0] && parseLegacyGodRef(parts[2])[0]);

    lastPasteHadHeader = isHeader;
    if (isHeader) {
      const seed = parts[parts.length - 2];
      [mood, punct] = [parts[0], parts[parts.length - 1]];
      try {
        key = parts.length === 4 ? keyFromHeader(parts[1], seed)
                                 : keyFromLegacyHeader(parts[1], parts[2], seed);
      } catch (e) {
        pasteOutEl.value = t("couldnt_derive_key", { msg: e.message });
        pasteTagRowEl.innerHTML = "";
        lastPasteHadHeader = false;
        return;
      }
      body = lines.slice(1).join(" ");
    } else {
      key = cipher.getKey();
      if (!key) { alert(t("alert_no_header_no_key")); return; }
      body = lines.join(" ");
    }

    lastPasteMood = mood; lastPastePunct = punct;
    pasteOutEl.value = decode(body, key);
    // Only a header carries these two, so the row shows up exactly when the
    // pasted message had one -- and then always, "—" included.
    if (isHeader) renderTagRow(pasteTagRowEl, mood, punct);
    else pasteTagRowEl.innerHTML = "";
  };

  wireCopy("read-copyPasteBtn", () => pasteOutEl.value);

  // --- Read: decode a message image (see decodeImageToTokens) ---
  const imageDrop = document.getElementById("read-imageDrop");
  const imageInput = document.getElementById("read-imageInput");
  const imageStatus = document.getElementById("read-imageStatus");
  const imageOut = document.getElementById("read-imageOut");
  const imageGlyphs = document.getElementById("read-imageGlyphs");

  function handleImageFile(file) {
    const key = cipher.getKey();
    if (!key) { imageStatus.textContent = t("alert_choose_4_styles"); return; }
    if (!file || !file.type.startsWith("image/")) { imageStatus.textContent = t("image_not_an_image"); return; }
    imageStatus.textContent = t("image_reading");
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      let result = null;
      try { result = decodeImageToTokens(img, key); }
      catch { result = null; }
      if (!result || !result.matched) {
        imageStatus.textContent = t("image_failed");
        imageOut.value = "";
        renderGlyphStream([], key, imageGlyphs);
        return;
      }
      imageOut.value = decode(result.coded, key);
      renderGlyphStream(result.coded.split(/\s+/).filter(Boolean), key, imageGlyphs);
      imageStatus.textContent = t("image_decoded", { count: result.matched, skipped: result.skippedText });
    };
    img.onerror = () => { URL.revokeObjectURL(url); imageStatus.textContent = t("image_failed"); };
    img.src = url;
  }

  imageDrop.onclick = () => imageInput.click();
  imageInput.onchange = () => { if (imageInput.files[0]) handleImageFile(imageInput.files[0]); };
  ["dragenter", "dragover"].forEach(evt =>
    imageDrop.addEventListener(evt, e => { e.preventDefault(); imageDrop.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(evt =>
    imageDrop.addEventListener(evt, e => { e.preventDefault(); imageDrop.classList.remove("dragover"); }));
  imageDrop.addEventListener("drop", e => {
    const file = e.dataTransfer.files[0];
    if (file) handleImageFile(file);
  });
  wireCopy("read-copyImageTextBtn", () => imageOut.value);

  return {
    // A new/changed key re-draws what's already on screen: the Read
    // sequence is drawn from the key, so after a re-roll it would
    // otherwise keep showing the previous cipher's symbols.
    rerender() { renderReadSequence(); },
    resetSequence() { readDecodeSeq = []; renderReadSequence(); },
    // Only a header carries mood/punctuation, so this only redraws
    // anything when the last paste actually had one.
    refreshPasteTag() {
      if (lastPasteHadHeader) renderTagRow(pasteTagRowEl, lastPasteMood, lastPastePunct);
    },
  };
}
