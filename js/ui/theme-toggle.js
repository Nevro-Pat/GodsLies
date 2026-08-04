// --- theme toggle: manual override for the OS-level prefers-color-scheme
// default, stored the same way the language choice is. js/theme-init.js
// already applies any saved choice before first paint. ---
import { t } from "../i18n.js";

export function effectiveTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function updateThemeToggleLabel() {
  const eff = effectiveTheme();
  document.getElementById("themeToggleBtn").textContent =
    eff === "dark" ? t("theme_switch_to_light") : t("theme_switch_to_dark");
}

export function initThemeToggle() {
  document.getElementById("themeToggleBtn").onclick = () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("godslies-theme", next);
    updateThemeToggleLabel();
  };
}
