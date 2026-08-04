// --- the one cipher picker + key generator, shared by Write and Read ---
import { t } from "../i18n.js";
import { SEED_WORDS } from "../data-loader.js";
import {
  SLOT_ORDER, SLOT_LABEL_KEY, SLOT_COLORS, SLOT_TINTS, OTHER_SLOT_OF_TYPE,
  CLASSIC_GODS, OTHER_GODS, GODS, GOD_LABEL, GOD_CODES,
  canonicalOrder, generateKey, blend,
} from "../cipher/gods.js";
import { buildFontFromKey } from "../cipher/font-builder.js";
import { assetPath, renderChart } from "./glyph-render.js";
import { downloadBlob } from "./download-utils.js";

export function createCipherPanel() {
  const classicStrip = document.querySelector(".classic-strip");
  const otherGallery = document.querySelector(".other-gallery");
  const randomBtn = document.querySelector(".randomize-selection-btn");
  const clearBtn = document.querySelector(".clear-selection-btn");
  const seedInput = document.querySelector(".seed-input");
  const genBtn = document.querySelector(".gen-btn");
  const seedWordBtn = document.querySelector(".seed-word-btn");
  const downloadBtn = document.querySelector(".download-key-btn");
  const downloadFontBtn = document.querySelector(".download-font-btn");
  const keyStatus = document.querySelector(".key-status");
  const chartEl = document.querySelector(".chart-glyphs");

  const selection = { g0: null, g1: null, d0: null, d1: null };
  let currentKey = null;
  let chartClickHandler = null;
  let onKeyReadyCb = null;
  let onClearCb = null;

  // Rotating "next slot" pointer per type -- clicking a grid tile always
  // fills whichever grid slot is next in rotation (grid·1 then grid·2, then
  // back to grid·1, ...), independently of the diamond rotation. No need to
  // pre-target a slot first; that's the whole point (see cipher_hint).
  // Peek/advance are separate (not one atomic step) so a *blocked* click
  // (see assignByType -- same god already fills the other slot of this
  // type) can leave the pointer exactly where it was instead of quietly
  // consuming a turn: without that, a blocked click would still advance
  // past the slot that's actually still empty, so the very next click
  // (of a different god) would overwrite the already-filled slot instead
  // of landing on the empty one.
  let nextGrid = "g0", nextDiamond = "d0";
  function peekSlotOfType(prefix) { return prefix === "g" ? nextGrid : nextDiamond; }
  function advanceSlotOfType(prefix) {
    if (prefix === "g") nextGrid = (nextGrid === "g0") ? "g1" : "g0";
    else nextDiamond = (nextDiamond === "d0") ? "d1" : "d0";
  }

  function chipFor(slot) { return document.querySelector(`.block-tile[data-target="${slot}"]`); }
  function captionFor(slot) { return document.querySelector(`.slot-caption[data-target="${slot}"]`); }

  // Re-lay the 4 boxes in the header's own order (see canonicalOrder), so
  // boxes, key and header always agree -- that's what lets the header
  // write a whole god's NAME once instead of two codes without losing
  // which slot anything sits in. Only runs on a complete selection:
  // re-ordering a half-filled row would make tiles jump mid-choice.
  function normalizeSelection() {
    if (!SLOT_ORDER.every(s => selection[s])) return;
    const [grid, diamond] = canonicalOrder(
      [selection.g0, selection.g1], [selection.d0, selection.d1]);
    [selection.g0, selection.g1] = grid;
    [selection.d0, selection.d1] = diamond;
    // Both rotations restart at slot 1, exactly where two clicks of each
    // type would have left them anyway.
    nextGrid = "g0"; nextDiamond = "d0";
  }

  // The classic pigpen reference: 4 plain tiles (Hermès grid/diamond, Áte
  // grid/diamond) using the very same .block-tile box the selection slots
  // use, rather than the bordered 2-thumbnail "name card" the 12-god
  // picker below uses. These two rows sit side by side and are read as one
  // comparison, so they have to be the same object at the same size --
  // as separate components they never matched and left dead space.
  function buildClassicStrip(container, gods) {
    container.innerHTML = "";
    for (const [id, label] of gods) {
      // One pair per god: its grid tile and diamond tile side by side under
      // a single shared name, rather than repeating the name under each.
      const pair = document.createElement("div");
      pair.className = "classic-pair";
      for (const [seg, prefix, titleKey] of [
        ["grid9", "g", "title_grid_style"],
        ["diamond4", "d", "title_diamond_style"],
      ]) {
        const btn = document.createElement("button");
        btn.className = "block-tile classic-tile";
        btn.dataset.name = id;
        btn.dataset.seg = prefix;
        btn.title = `${label} — ${t(titleKey)}`;
        const swatch = document.createElement("span");
        swatch.className = "swatch";
        const img = document.createElement("img");
        img.src = assetPath(id, seg, "tile");
        img.alt = `${label} ${seg}`;
        swatch.appendChild(img);
        btn.appendChild(swatch);
        btn.onclick = () => assignByType(prefix, id);
        pair.appendChild(btn);
      }
      const caption = document.createElement("div");
      caption.className = "slot-caption classic-pair-name";
      caption.textContent = label;
      pair.appendChild(caption);
      container.appendChild(pair);
    }
  }

  function buildGalleryInto(container, gods) {
    container.innerHTML = "";
    for (const [id, label] of gods) {
      const card = document.createElement("div");
      card.className = "name-card";
      card.dataset.name = id;
      card.innerHTML = `
        <span class="corner-tag g0">G1</span><span class="corner-tag g1">G2</span>
        <span class="corner-tag d0">D1</span><span class="corner-tag d1">D2</span>
        <div class="thumbs">
          <button class="g9" data-i18n-title="title_grid_style"><img src="${assetPath(id,'grid9','tile')}"></button>
          <button class="d4" data-i18n-title="title_diamond_style"><img src="${assetPath(id,'diamond4','tile')}"></button>
        </div>
        <div class="name">${label}</div>
      `;
      // Tooltips come from applyLanguage()'s data-i18n-title sweep, which
      // runs after this panel is built and on every language switch.
      card.querySelector(".g9").onclick = () => assignByType("g", id);
      card.querySelector(".d4").onclick = () => assignByType("d", id);
      container.appendChild(card);
    }
  }

  // "lit" = this thumbnail is filling a slot: solid tint for one, a
  // gradient when the same god fills both slots of that segment type.
  // Used by the classic tiles and both gallery thumbnails alike.
  function lightUp(el, prefix, name) {
    const tints = SLOT_ORDER
      .filter(s => s[0] === prefix && selection[s] === name)
      .map(s => SLOT_TINTS[s]);
    el.classList.toggle("lit", tints.length > 0);
    el.style.background = tints.length ? blend(tints) : "";
  }

  function refreshUI() {
    classicStrip.querySelectorAll(".classic-tile").forEach(
      btn => lightUp(btn, btn.dataset.seg, btn.dataset.name));

    [...otherGallery.children].forEach(card => {
      const id = card.dataset.name;
      card.querySelectorAll(".corner-tag").forEach(tag => tag.style.display = "none");
      const cardColors = [];
      for (const [slot, name] of Object.entries(selection)) {
        if (name === id) {
          cardColors.push(SLOT_COLORS[slot]);
          card.querySelector(`.corner-tag.${slot}`).style.display = "flex";
        }
      }
      // Whole-card border: solid for one slot, a gradient blend for more.
      card.style.borderColor = cardColors.length === 1 ? cardColors[0] : "";
      card.style.borderImage = cardColors.length > 1 ? `${blend(cardColors)} 1` : "";
      lightUp(card.querySelector(".g9"), "g", id);
      lightUp(card.querySelector(".d4"), "d", id);
    });
    for (const slot of SLOT_ORDER) {
      const name = selection[slot];
      const seg = slot[0] === "g" ? "grid9" : "diamond4";
      const chip = chipFor(slot);
      chip.classList.toggle("filled", !!name);
      const swatch = chip.querySelector(".swatch");
      const slotLabel = t(SLOT_LABEL_KEY[slot]);
      const caption = captionFor(slot);
      if (name) {
        swatch.innerHTML = `<img src="${assetPath(name, seg, 'tile')}">`;
        chip.title = `${slotLabel} — ${GOD_LABEL[name] || name}`;
        // Code AND name, always -- a god's grid and diamond codes are two
        // DIFFERENT numbers (Árnesis = 25 grid / 52 diamond), so the code
        // alone can't show one god filling two boxes, and the name alone
        // hides the code you need to read a header. Nothing conditional:
        // every box says the same two things, every time.
        caption.innerHTML = "";
        const codeEl = document.createElement("div");
        codeEl.className = "slot-code";
        codeEl.textContent = GOD_CODES[name][seg === "grid9" ? 0 : 1];
        const nameEl = document.createElement("div");
        nameEl.className = "slot-name";
        nameEl.textContent = GOD_LABEL[name] || name;
        caption.append(codeEl, nameEl);
      } else {
        swatch.innerHTML = "";
        chip.title = slotLabel;
        caption.innerHTML = "";
      }
    }
  }

  function flashBlocked(slot) {
    const chip = chipFor(slot);
    chip.classList.add("blocked");
    setTimeout(() => chip.classList.remove("blocked"), 450);
  }

  // Never let the same god fill both slots of one segment type -- see
  // OTHER_SLOT_OF_TYPE's comment. A blocked click is simply rejected
  // (with a brief flash so it doesn't look like a dead/unresponsive
  // tile) rather than e.g. silently bumping the other slot empty.
  function assignByType(prefix, name) {
    const slot = peekSlotOfType(prefix);
    if (selection[OTHER_SLOT_OF_TYPE[slot]] === name) {
      flashBlocked(slot);
      return;
    }
    advanceSlotOfType(prefix);
    selection[slot] = name;
    normalizeSelection();
    refreshUI();
    maybeAutoGenerate();
  }

  function updateKeyStatusText() {
    keyStatus.innerHTML = "";
    if (currentKey) {
      const g = currentKey.grid9_gods.map(n => GOD_LABEL[n] || n).join(" + ");
      const d = currentKey.diamond4_gods.map(n => GOD_LABEL[n] || n).join(" + ");
      const title = document.createElement("div");
      title.className = "key-status-title";
      title.textContent = t("key_ready_title");
      keyStatus.appendChild(title);
      const rows = document.createElement("div");
      rows.className = "key-status-rows";
      for (const [label, value] of [
        [t("key_grid_label"), g],
        [t("key_diamond_label"), d],
        [t("key_seed_label"), `"${currentKey.seed}"`],
      ]) {
        const row = document.createElement("div");
        row.className = "key-status-row";
        const l = document.createElement("span"); l.className = "key-status-label"; l.textContent = label;
        const v = document.createElement("span"); v.className = "key-status-value"; v.textContent = value;
        row.append(l, v);
        rows.appendChild(row);
      }
      keyStatus.appendChild(rows);
    } else {
      keyStatus.textContent = t("key_status_empty");
    }
  }

  function setKey(key) {
    currentKey = key;
    keyStatus.classList.add("ready");
    updateKeyStatusText();
    renderChart(currentKey, chartEl, chartClickHandler);
    if (onKeyReadyCb) onKeyReadyCb(currentKey);
  }

  const allFilled = () => SLOT_ORDER.every(s => selection[s]);
  // The one place a key is built from the picks: the seed box wins when
  // it holds anything, otherwise generateKey rolls a random one.
  function regenerate(seed = seedInput.value.trim()) {
    setKey(generateKey([selection.g0, selection.g1], [selection.d0, selection.d1], seed || null));
  }

  function maybeAutoGenerate() { if (allFilled()) regenerate(); }

  genBtn.onclick = () => {
    if (!allFilled()) { alert(t("alert_choose_4_slots")); return; }
    regenerate();
  };

  seedWordBtn.onclick = () => {
    seedInput.value = SEED_WORDS[Math.floor(Math.random() * SEED_WORDS.length)];
    if (allFilled()) regenerate();
  };

  downloadBtn.onclick = () => {
    if (!currentKey) { alert(t("alert_generate_key_first")); return; }
    downloadBlob(new Blob([JSON.stringify(currentKey, null, 2)], { type: "application/json" }),
                 `gods-lies-key-${currentKey.seed}.json`);
  };

  downloadFontBtn.onclick = () => {
    if (!currentKey) { alert(t("alert_generate_key_first")); return; }
    const original = downloadFontBtn.textContent;
    downloadFontBtn.textContent = t("generating_font");
    // One frame's delay so the button label above actually paints before
    // the (synchronous, if brief) build work blocks the main thread.
    setTimeout(() => {
      const bytes = buildFontFromKey(currentKey, `Gods Lies - ${currentKey.seed}`);
      downloadBlob(new Blob([bytes], { type: "font/ttf" }), `gods-lies-font-${currentKey.seed}.ttf`);
      downloadFontBtn.textContent = original;
    }, 30);
  };

  // Two different indices without rejection-sampling: pick j from a range
  // one shorter, then step it over i.
  function pickTwoDistinct(pool) {
    const i = Math.floor(Math.random() * pool.length);
    let j = Math.floor(Math.random() * (pool.length - 1));
    if (j >= i) j++;
    return [pool[i], pool[j]];
  }

  randomBtn.onclick = () => {
    const ids = GODS.map(([id]) => id);
    // Grid and diamond drawn independently: distinct within a type (the
    // OTHER_SLOT_OF_TYPE rule), but free to overlap across types so a
    // random roll can still land on a godblock -- assigning directly
    // (rather than four assignByType calls) avoids the same-type-duplicate
    // rejection and the four separate key regenerations that would cause.
    [selection.g0, selection.g1] = pickTwoDistinct(ids);
    [selection.d0, selection.d1] = pickTwoDistinct(ids);
    normalizeSelection();
    refreshUI();
    maybeAutoGenerate();
  };

  clearBtn.onclick = () => {
    for (const slot of SLOT_ORDER) selection[slot] = null;
    nextGrid = "g0"; nextDiamond = "d0";
    currentKey = null;
    keyStatus.classList.remove("ready");
    updateKeyStatusText();
    chartEl.innerHTML = "";
    refreshUI();
    if (onClearCb) onClearCb();
  };

  buildClassicStrip(classicStrip, CLASSIC_GODS);
  buildGalleryInto(otherGallery, OTHER_GODS);
  refreshUI();

  return {
    getKey: () => currentKey,
    setChartClickHandler(fn) { chartClickHandler = fn; },
    onKeyReady(fn) { onKeyReadyCb = fn; },
    onClear(fn) { onClearCb = fn; },
    // Called after a language switch: refresh anything holding
    // language-dependent text that isn't just a static data-i18n sweep.
    refreshLanguage() {
      updateKeyStatusText();
      // Rebuilt (not just swept) because each tile's tooltip is composed at
      // build time from the god's name + a translated style label; refreshUI
      // below then re-applies the "lit" state to the fresh tiles.
      buildClassicStrip(classicStrip, CLASSIC_GODS);
      refreshUI();
      if (currentKey) renderChart(currentKey, chartEl, chartClickHandler);
    },
  };
}
