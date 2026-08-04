import { STRINGS } from "./data-loader.js";

export let currentLang = localStorage.getItem("godslies-lang") || "en";

export function t(key, vars) {
  let s = (STRINGS[currentLang] && STRINGS[currentLang][key]) ?? STRINGS.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{{${k}}}`, v);
  return s;
}

// Anything that needs to re-render language-dependent content it built
// itself (rather than a static data-i18n* sweep covers) registers here --
// the cipher panel, the Write/Read tabs, etc. -- and gets called once per
// applyLanguage(), after the static sweep below runs.
const languageChangeListeners = [];
export function onLanguageChange(fn) { languageChangeListeners.push(fn); }

// --- language toggle: sweeps every data-i18n* element, then asks
// everything registered via onLanguageChange() to refresh whatever
// language-dependent text isn't covered by a static sweep. ---
export function applyLanguage(lang) {
  currentLang = lang;
  localStorage.setItem("godslies-lang", lang);
  document.documentElement.lang = lang;

  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (STRINGS[lang][key] !== undefined) el.textContent = STRINGS[lang][key];
  });
  document.querySelectorAll("[data-i18n-html]").forEach(el => {
    const key = el.dataset.i18nHtml;
    if (STRINGS[lang][key] !== undefined) el.innerHTML = STRINGS[lang][key];
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (STRINGS[lang][key] !== undefined) el.placeholder = STRINGS[lang][key];
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const key = el.dataset.i18nTitle;
    if (STRINGS[lang][key] !== undefined) el.title = STRINGS[lang][key];
  });
  // footer_text is deliberately English-only in both languages (see the fr
  // STRINGS block) -- the sweep above skips it when the key is missing, so
  // force it here rather than leaving a blank span on first fr load.
  document.querySelector('[data-i18n="footer_text"]').textContent = STRINGS.en.footer_text;

  const toggleBtn = document.getElementById("langToggleBtn");
  toggleBtn.textContent = lang === "en" ? t("lang_switch_to_fr") : t("lang_switch_to_en");

  for (const fn of languageChangeListeners) fn(lang);
}

document.getElementById("langToggleBtn").onclick = () => {
  applyLanguage(currentLang === "en" ? "fr" : "en");
};
