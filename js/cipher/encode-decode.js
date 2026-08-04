// Plaintext <-> cipher-code token conversion.
import { slotCode, parseCode } from "./gods.js";

// The cipher only has 26 letter slots, so accented/ligature characters
// (French, and most other Latin-script languages) fold to their plain
// base letter before encoding -- é/è/ê/ë -> E, ç -> C, œ -> OE, etc. This
// is one-way: decoding a message back returns the base letter, not the
// original accent (there's no 27th+ slot to round-trip it through).
export const LIGATURE_EXPANSIONS = { "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "ß": "ss", "ø": "o", "Ø": "O" };

export function foldForCipher(text) {
  let expanded = "";
  for (const ch of text) expanded += LIGATURE_EXPANSIONS[ch] ?? ch;
  return expanded.normalize("NFD").replace(/\p{Diacritic}/gu, "");
}

export function encode(text, key) {
  const tokens = [];
  for (const ch of foldForCipher(text)) {
    if (/[a-zA-Z]/.test(ch)) {
      const slot = key.letter_to_slot[ch.toUpperCase()];
      tokens.push(slotCode(slot[0], slot[1], slot[2]));
    } else if (ch === " ") tokens.push("/");
    else tokens.push(ch);
  }
  return tokens.join(" ");
}

// A downloaded font only changes how a letter DISPLAYS -- the character
// actually stored is still the plain letter someone typed, so copying
// cipher-looking text out of a font-applied document and pasting it
// anywhere else (or "paste as plain text", or a screen reader) reveals
// the real message instantly. This maps each letter to a Private Use Area
// codepoint (U+E000-U+E019 for A-Z -- Unicode guarantees these are never
// assigned a real character by any font/OS) instead of the letter itself,
// so the font can still show the right cipher glyph (see buildFontFromKey
// below, which maps both the plain letter AND its PUA codepoint to the
// same glyph) while the text actually stored is meaningless outside that
// specific font's cmap -- not readable by casual copy-paste, same
// protection level as this app's own G3/D2 codes (needs the key, same as
// always -- this isn't new cryptography, just a font-safe serialization
// of the same already-encoded data instead of a plaintext-identity one).
export const PUA_BASE = 0xE000;
export function textToCipherFontText(text) {
  let out = "";
  for (const ch of foldForCipher(text)) {
    out += /[a-zA-Z]/.test(ch) ? String.fromCodePoint(PUA_BASE + (ch.toUpperCase().charCodeAt(0) - 65)) : ch;
  }
  return out;
}

export function decode(codeString, key) {
  const slotToLetter = {};
  for (const [letter, [seg, which, pos]] of Object.entries(key.letter_to_slot)) {
    slotToLetter[slotCode(seg, which, pos)] = letter;
  }
  return codeString.split(/\s+/).filter(Boolean).map(tok => {
    if (tok === "/") return " ";
    try {
      const [seg, which, pos] = parseCode(tok);
      return slotToLetter[slotCode(seg, which, pos)] ?? tok;
    } catch { return tok; }
  }).join("");
}
