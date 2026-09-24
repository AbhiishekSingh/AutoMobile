"""Loose name matching for the lookup tables (enquiry mode, bike model,
opportunity status, disposition, lost reason).

Why this exists
---------------
LeadSquared exports and hand-made Excel sheets spell the same value in
different ways, e.g.

    "Cross-Sell"     vs  "Cross Sell"      (hyphen vs space)
    "Walk-In"        vs  "Walk-in"         (case)
    "250 Duke"       vs  "DUKE 250"        (word order)
    "390 Adventure"  vs  "ADV 390"         (abbreviation + word order)

The importer used to match with a case-insensitive exact comparison, so each
spelling variant silently created a NEW lookup row — which is how the Leads
screen ended up with both a "CROSS SELL" and a "CROSS-SELL" tile.

`lookup_key()` turns any spelling into one comparison key:
  1. uppercase
  2. split on anything that isn't a letter/digit  (hyphens, dots, brackets…)
  3. expand known abbreviations                   (ADVENTURE -> ADV)
  4. sort the words                               ("250 DUKE" == "DUKE 250")

    lookup_key("Cross-Sell")      == lookup_key("CROSS SELL")   == "CROSS SELL"
    lookup_key("390 Adventure R") == lookup_key("ADV 390 R")    == "390 ADV R"

For names that genuinely differ in wording (not just spelling), add an entry
to NAME_ALIASES below.
"""
import re

# Single words that mean the same thing. Keys and values are UPPERCASE.
WORD_ALIASES = {
    "ADVENTURE": "ADV",
    "WALKIN": "WALK IN",     # "Walkin" -> "Walk In"
    "CROSSSELL": "CROSS SELL",
    "TELEIN": "TELE IN",
}

# Whole-name aliases, for values whose wording differs and can't be fixed
# by the word rules above. Left side = the spelling that arrives in a file,
# right side = the existing name it should map to. Case/punctuation on both
# sides doesn't matter. Example (uncomment only if these really are the
# same bike in your showroom):
#   "390 Adventure X":      "ADV 390 X PLUS",
#   "200 Duke (with TFT)":  "DUKE 200 BS VI",
#   "RC 390 (MotoGP)":      "RC 390",
NAME_ALIASES: dict[str, str] = {
    # Lost reasons — LeadSquared wording -> seed wording
    "Incorrect number": "Incorrect No.",
    "Enquiry from out of city": "Out of city",
}

_TOKEN_RE = re.compile(r"[A-Z0-9]+")


def _raw_key(name: str) -> str:
    words: list[str] = []
    for tok in _TOKEN_RE.findall((name or "").upper()):
        words.extend(WORD_ALIASES.get(tok, tok).split())
    return " ".join(sorted(words))


_ALIAS_KEYS = {_raw_key(src): _raw_key(dst) for src, dst in NAME_ALIASES.items()}


def lookup_key(name: str | None) -> str:
    """Spelling-insensitive comparison key for a lookup value ('' if blank)."""
    key = _raw_key(name or "")
    return _ALIAS_KEYS.get(key, key)


def build_index(rows) -> dict[str, object]:
    """{lookup_key: row} for a list of lookup rows. If two rows already share
    a key (legacy duplicates), the one with the lowest id wins, so matching is
    stable and points at the original/seeded row."""
    index: dict[str, object] = {}
    for row in sorted(rows, key=lambda r: r.id):
        index.setdefault(lookup_key(row.name), row)
    return index