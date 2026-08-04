import { applyLanguage, currentLang, onLanguageChange } from "./i18n.js";
import { createCipherPanel } from "./ui/cipher-panel.js";
import { initWriteTab } from "./ui/write-tab.js";
import { initReadTab } from "./ui/read-tab.js";
import { initThemeToggle, updateThemeToggleLabel } from "./ui/theme-toggle.js";

const cipher = createCipherPanel();
const writeTab = initWriteTab(cipher);
const readTab = initReadTab(cipher);
initThemeToggle();

// A new/changed key re-draws what's already on screen: both the Write
// result and the Read sequence are drawn from the key, so after a re-roll
// they would otherwise keep showing the previous cipher's symbols.
cipher.onKeyReady((key) => {
  readTab.rerender();
  writeTab.renderIfHasResult(key);
});
cipher.onClear(() => {
  readTab.resetSequence();
  writeTab.reset();
});

// --- step-3 local tabs: Write / Read ---
document.querySelectorAll(".tabbtn").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll(".tabbtn").forEach(b => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tabpanel").forEach(p => p.classList.toggle("active", p.dataset.tab === btn.dataset.tab));
  };
});

// Everything that holds language-dependent content it built itself (rather
// than a static data-i18n* sweep covers) refreshes here, once per
// applyLanguage() call.
onLanguageChange(() => {
  updateThemeToggleLabel();
  cipher.refreshLanguage();
  readTab.rerender();
  // Guarded on the key still existing: after Clear there is nothing left
  // to redraw this from, and asking for a glyph without a key throws.
  const key = cipher.getKey();
  if (key) writeTab.renderIfHasResult(key);
  readTab.refreshPasteTag();
});

applyLanguage(currentLang);
