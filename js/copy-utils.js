// --- copy-to-clipboard, with a file:// -safe fallback ---
import { t } from "./i18n.js";

export function copyViaExec(text) {
  const ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.focus(); ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  document.body.removeChild(ta);
  return ok;
}
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try { await navigator.clipboard.writeText(text); return true; } catch { /* fall through */ }
  }
  return copyViaExec(text);
}
export function wireCopy(btnId, getText) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.onclick = async () => {
    const original = btn.textContent;
    const text = getText();
    if (!text) { btn.textContent = t("copy_nothing_yet"); setTimeout(() => { btn.textContent = original; }, 1000); return; }
    const ok = await copyText(text);
    btn.textContent = ok ? t("copy_copied") : t("copy_failed");
    setTimeout(() => { btn.textContent = original; }, 1200);
  };
}
