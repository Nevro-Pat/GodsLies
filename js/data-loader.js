// Single fetch point for every piece of data this app needs before it can
// render anything: translations, the 14-god roster, the seed-word/sample
// pools, the per-glyph fill-fraction manifest, and the baked glyph vector
// contours (used for canvas drawing and the in-browser font builder --
// canvas getImageData()/toBlob()/toDataURL() throw a SecurityError on a
// cross-origin-loaded <img>, so those two can't be traced from the PNGs at
// runtime and are baked ahead of time instead, by extract_assets.py and
// `python make_font.py --bake-html` respectively).
//
// Every other module imports the parsed data from here rather than
// fetching it itself, so each JSON file is only ever requested once.
//
// This is also the one place that requires godslies.html to be served over
// http(s) -- fetch() of a local file is blocked by CORS under file://, so
// opening this page by double-clicking it no longer works (see README).
// If that happens, show a plain-language explanation instead of leaving a
// blank or silently broken page.
async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

let STRINGS, GODS_DATA, SEED_WORDS, SAMPLE_MESSAGES, FILL_MANIFEST, GLYPH_CONTOURS;

try {
  const [strings, gods, seedWords, fillManifest, glyphContours] = await Promise.all([
    loadJSON("js/data/strings.json"),
    loadJSON("js/data/gods.json"),
    loadJSON("js/data/seed-words.json"),
    loadJSON("assets/manifest.json"),
    loadJSON("assets/glyph-contours.json"),
  ]);
  STRINGS = strings;
  GODS_DATA = gods;
  SEED_WORDS = seedWords.SEED_WORDS;
  SAMPLE_MESSAGES = seedWords.SAMPLE_MESSAGES;
  FILL_MANIFEST = fillManifest;
  GLYPH_CONTOURS = glyphContours;
} catch (err) {
  document.body.innerHTML = `
    <div style="max-width:40em;margin:3rem auto;padding:1.5rem;font-family:ui-sans-serif,system-ui,sans-serif;line-height:1.5;">
      <h1 style="font-size:1.2rem;">Gods Lies needs to be served over http(s)</h1>
      <p>This page couldn't load its data (${err.message}). That happens when it's opened directly
      as a local file (<code>file://</code>) -- browsers block that kind of request for local files.</p>
      <p>Open it via its GitHub Pages link, or, for local development, run a small local server from
      this folder and open the page through it, e.g.:</p>
      <pre style="background:#0002;padding:.75rem 1rem;border-radius:8px;overflow-x:auto;">python -m http.server</pre>
    </div>`;
  throw err;
}

export { STRINGS, GODS_DATA, SEED_WORDS, SAMPLE_MESSAGES, FILL_MANIFEST, GLYPH_CONTOURS };
