// The 14 gods (names, display labels, header codes) and the slot/key
// generation grammar built on top of them. Data itself lives in
// js/data/gods.json (see data-loader.js); this module is the logic layer.
import { t } from "../i18n.js";
import { GODS_DATA } from "../data-loader.js";

// Hermès + Áte are shown in their own "classic pigpen" column, separate from
// the other 12, so the tool presents with a familiar/recognizable look
// before showing the exotic variants. List position has no bearing on
// the key/slot mapping -- it's display order only. Names are proper nouns
// and stay the same in both languages.
export const CLASSIC_GODS = GODS_DATA.CLASSIC_GODS;
export const OTHER_GODS = GODS_DATA.OTHER_GODS;
export const GODS = [...CLASSIC_GODS, ...OTHER_GODS];
export const GOD_LABEL = Object.fromEntries(GODS);

// Two-digit reference codes for the notebook message header (see README
// "Message format"). Mirrors godslies.py's GOD_CODES exactly -- keep the
// two in sync if this ever changes. First 9 are the real notebook's own
// numbers (grid=N0, diamond=NN); the last 5 extend that "round" spirit
// with digit-reversal pairs instead of the notebook's original plain
// sequential tail.
export const GOD_CODES = GODS_DATA.GOD_CODES;
export const CODE_TO_GOD = Object.fromEntries(
  Object.entries(GOD_CODES).flatMap(([god, codes]) => codes.map(code => [code, god]))
);

// Accent-stripped god names, the form the header writes ("Dolos", "Ate")
// so it stays plain ASCII however it's typed or pasted. Same folding
// encode() does, spelled out separately because this map is built at load
// time, before foldForCipher's tables exist.
export function asciiName(label) { return label.normalize("NFD").replace(/\p{Diacritic}/gu, ""); }
export const NAME_TO_GOD = Object.fromEntries(
  GODS.map(([id, label]) => [asciiName(label).toLowerCase(), id])
);

// The canonical order of one set of picks, shared by the key, the four
// selection boxes and the header so all three describe the same thing
// (see normalizeSelection): a god filling a grid slot AND a diamond slot
// is a "godblock" and goes last with its two halves on the same index,
// independent picks keep their order in front. Without it the header
// couldn't say which grid slot a god sits in, and two different keys
// could share one header.
export function canonicalOrder(grid9Gods, diamond4Gods) {
  const blocks = grid9Gods.filter(g => diamond4Gods.includes(g));
  return [
    [...grid9Gods.filter(g => !blocks.includes(g)), ...blocks],
    [...diamond4Gods.filter(g => !blocks.includes(g)), ...blocks],
  ];
}

// The header's cipher field: one dot-joined list covering all 4 picks --
// a godblock written once as its NAME (it is that whole god), every other
// pick as its 2-digit code, grid code then diamond code per slot. So codes
// always precede names, and the list is always 2 or 4 tokens, never 1 or 3.
//
// It reads back unambiguously because a code carries its own segment: the
// 14 grid codes {10,20,...,65} and 14 diamond codes {11,22,...,56} are
// disjoint, so each token says which list it joins, and its position in
// that list is its slot.
export function cipherField(grid9Gods, diamond4Gods) {
  const [grid, diamond] = canonicalOrder(grid9Gods, diamond4Gods);
  const codes = [], names = [];
  for (let i = 0; i < 2; i++) {
    if (grid[i] === diamond[i]) names.push(asciiName(GOD_LABEL[grid[i]]));
    else codes.push(GOD_CODES[grid[i]][0], GOD_CODES[diamond[i]][1]);
  }
  return [...codes, ...names].join(".");
}

// Reverse of cipherField -> [grid9Gods, diamond4Gods], already in
// canonical order (names last land last in both lists).
export function parseCipherField(field) {
  const grid = [], diamond = [];
  for (const raw of field.split(".")) {
    const tok = raw.trim();
    const named = NAME_TO_GOD[asciiName(tok).toLowerCase()];
    if (named) { grid.push(named); diamond.push(named); continue; }
    const god = CODE_TO_GOD[tok];
    if (!god) throw new Error(t("unknown_god_code_error"));
    (GOD_CODES[god][0] === tok ? grid : diamond).push(god);
  }
  if (grid.length !== 2 || diamond.length !== 2) throw new Error(t("incomplete_header_error"));
  return [grid, diamond];
}
// Is this text a cipher field at all? Used to tell a real header line from
// an ordinary first line of coded body, before committing to parsing it.
export function looksLikeCipherField(field) {
  try { parseCipherField(field); return true; } catch { return false; }
}

// A plain-language reading of the same field, printed under the header so
// nothing about the key is left to code-table lookup.
export function cipherFieldSummary(grid9Gods, diamond4Gods, seed) {
  const [grid, diamond] = canonicalOrder(grid9Gods, diamond4Gods);
  const parts = [];
  for (let i = 0; i < 2; i++) {
    if (grid[i] === diamond[i]) parts.push(t("header_whole_god", { god: GOD_LABEL[grid[i]] }));
    else parts.push(t("header_grid_only", { god: GOD_LABEL[grid[i]] }),
                    t("header_diamond_only", { god: GOD_LABEL[diamond[i]] }));
  }
  return [...parts, t("header_seed", { seed })].join("   ·   ");
}

// Derive a full key straight from a message's own header -- no need for
// the selected slots to match, or even be filled in at all.
export function keyFromHeader(field, seed) {
  const [grid, diamond] = parseCipherField(field);
  return generateKey(grid, diamond, seed);
}

// Messages written before the header became one dot-joined field used two
// separate slotA/slotB fields, each either a single "godblock" code or a
// dot-joined grid.diamond pair. Kept read-only (nothing writes this form
// any more) so anything already sent still decodes.
export function parseLegacyGodRef(ref) {
  if (ref.includes(".")) {
    const [gridCode, diamondCode] = ref.split(".");
    return [CODE_TO_GOD[gridCode], CODE_TO_GOD[diamondCode]];
  }
  const god = CODE_TO_GOD[ref];
  return [god, god];
}
export function keyFromLegacyHeader(slotA, slotB, seed) {
  const [g0, d0] = parseLegacyGodRef(slotA);
  const [g1, d1] = parseLegacyGodRef(slotB);
  if (!g0 || !d0 || !g1 || !d1) throw new Error(t("unknown_god_code_error"));
  return generateKey([g0, g1], [d0, d1], seed, false);
}

export const GRID9_POS = [1,2,3,4,5,6,7,8,9];
export const DIAMOND4_POS = ["N","E","S","W"];

function allSlots() {
  const slots = [];
  for (const which of [0,1]) for (const p of GRID9_POS) slots.push(["grid9", which, p]);
  for (const which of [0,1]) for (const p of DIAMOND4_POS) slots.push(["diamond4", which, p]);
  return slots;
}
export const ALL_SLOTS = allSlots();
export const SLOT_ORDER = ["g0", "g1", "d0", "d1"];
export const SLOT_LABEL_KEY = { g0: "slot_grid1", g1: "slot_grid2", d0: "slot_diamond1", d1: "slot_diamond2" };
// The other slot of the same segment type -- used to block picking the
// same god for both grid slots (or both diamond slots): doing so would
// mean 18 of the alphabet's 26 letters reuse just one visual style,
// making the symbol pool needlessly easy to pattern-match.
export const OTHER_SLOT_OF_TYPE = { g0: "g1", g1: "g0", d0: "d1", d1: "d0" };

// One color per slot (matches the .block-tile[data-target] tints below) used
// to colorize whichever gallery card/thumbnail is filling that slot -- solid
// for borders, a softer alpha version for tinted button backgrounds.
export const SLOT_COLORS = { g0: "#a8621f", g1: "#8a4a4a", d0: "#4a7f5e", d1: "#4a6b7f" };
export const SLOT_TINTS = {
  g0: "rgba(168,98,31,.22)", g1: "rgba(138,74,74,.22)",
  d0: "rgba(74,127,94,.22)", d1: "rgba(74,107,127,.22)",
};
// A single slot's color/tint applies directly; 2+ (the same god filling more
// than one slot -- e.g. a full godblock using one god for both its grid and
// diamond) blend into a gradient instead of letting one plain color hide
// that it's doing double duty.
export function blend(colors) {
  if (colors.length === 0) return "";
  if (colors.length === 1) return colors[0];
  return `linear-gradient(135deg, ${colors.join(", ")})`;
}

export function slotCode(seg, which, pos) { return (seg === "grid9" ? "G" : "D") + pos + (which ? "." : ""); }
export function parseCode(code) {
  code = code.trim();
  const which = code.endsWith(".") ? 1 : 0;
  if (which) code = code.slice(0, -1);
  const seg = code[0].toUpperCase() === "G" ? "grid9" : "diamond4";
  const posStr = code.slice(1);
  const pos = seg === "grid9" ? parseInt(posStr, 10) : posStr.toUpperCase();
  return [seg, which, pos];
}

export function seededRng(seedStr) {
  let h = 1779033703 ^ seedStr.length;
  for (let i = 0; i < seedStr.length; i++) {
    h = Math.imul(h ^ seedStr.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return function () {
    h = Math.imul(h ^ (h >>> 16), 2246822519);
    h = Math.imul(h ^ (h >>> 13), 3266489917);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };
}

// `canonical` puts the picks in the order the header writes them (see
// canonicalOrder), so a header always rebuilds exactly this key. Only the
// legacy header reader passes false: its grammar recorded the slot order
// itself, so re-ordering would decode already-sent messages into garbage.
export function generateKey(grid9Names, diamond4Names, seed, canonical = true) {
  if (canonical) [grid9Names, diamond4Names] = canonicalOrder(grid9Names, diamond4Names);
  seed = seed || String(Math.floor(Math.random() * 1e9));
  const rng = seededRng(seed);
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
  for (let i = letters.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [letters[i], letters[j]] = [letters[j], letters[i]];
  }
  const letter_to_slot = {};
  letters.forEach((letter, i) => { letter_to_slot[letter] = ALL_SLOTS[i]; });
  return { grid9_gods: grid9Names, diamond4_gods: diamond4Names, seed, letter_to_slot };
}

export function nameFor(key, seg, which) {
  return (seg === "grid9" ? key.grid9_gods : key.diamond4_gods)[which];
}
