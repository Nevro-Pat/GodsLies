// Applied before first paint (this is a classic, non-module, non-deferred
// script placed before the CSS <link> tags, so it blocks rendering) so a
// saved manual theme choice takes effect immediately -- otherwise the page
// would flash the OS-default theme, then flip. Deliberately NOT a module:
// module scripts always run deferred (after parsing), which would be too
// late to prevent the flash.
try {
  var savedTheme = localStorage.getItem("godslies-theme");
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
} catch { /* localStorage unavailable (e.g. blocked) -- falls back to OS theme */ }
