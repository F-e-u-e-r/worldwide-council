#!/usr/bin/env python3
"""Curation-side citation check for a showcase transcript (docs/showcase/*.md).

Scope: ONLY the debate body — the lines between the ``# 議會逐字稿`` heading and the first
``## 執行資訊`` (run metadata), ``## 引文複核`` (curation record) heading or ``---`` rule that follows
it. Header tables, run metadata and curation notes are never scanned, so prose that merely mentions
〔據典〕 cannot register as a missed citation.

Rule: on every body line tagged 〔據典〕, each 「…」 quotation must appear verbatim (after
normalizing full-width punctuation) in the bundled references of the named tradition files, and
each 《work》locator pair must occur in those files.

This is a one-off curation check that a transcript quoted the bundled references verbatim. It is
NOT strict mode: no B2 span verification, no B3 fail-closed boundary, no runtime guarantee.

Usage: python scripts/check_showcase_citations.py docs/showcase/<transcript>.md 04-佛教.md 05-道教.md ...
Exit status 0 when every quotation and locator is found, 1 otherwise (or on a malformed transcript).
"""
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = ROOT / ".claude" / "skills" / "worldwide-council" / "references"
BODY_START = "# 議會逐字稿"
# The debate body ends at the moderator's run-metadata section (執行資訊), the curation record, or a rule.
BODY_END_MARKERS = ("---", "## 引文複核", "## 執行資訊")
QUOTE_RE = re.compile(r"「([^」]+)」")
LOCATOR_RE = re.compile(r"——(《[^》]+》[^。;\s〔]*)")
PUNCT = str.maketrans({"，": ",", "；": ";", "：": ":", "（": "(", "）": ")", "！": "!", "？": "?"})


def normalize(text):
    return unicodedata.normalize("NFC", text).translate(PUNCT)


def transcript_body(text):
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == BODY_START)
    except StopIteration:
        raise ValueError("transcript has no '{}' heading".format(BODY_START))
    body = []
    for line in lines[start + 1:]:
        stripped = line.strip()
        if stripped == "---" or any(stripped.startswith(m) for m in BODY_END_MARKERS[1:]):
            break
        body.append(line)
    return body


def check(transcript_path, reference_names):
    corpus = normalize(
        "".join((REFERENCES_DIR / name).read_text(encoding="utf-8") for name in reference_names)
    )
    body = transcript_body(Path(transcript_path).read_text(encoding="utf-8"))
    tagged = [line for line in body if "〔據典〕" in line]
    quotes, locators, missing = 0, 0, []
    for line in tagged:
        for quote in QUOTE_RE.findall(line):
            quotes += 1
            core = normalize(quote).strip("。.;:,!?")
            if core and core not in corpus:
                missing.append(("quote", core, line.strip()[:80]))
        for locator in LOCATOR_RE.findall(line):
            locators += 1
            key = normalize(locator).rstrip("。.,;")
            # A locator may carry a trailing gloss "(初轉法輪,南傳)"; require the work + first token.
            head = key.split("(")[0].strip()
            if head not in corpus:
                missing.append(("locator", head, line.strip()[:80]))
    return tagged, quotes, locators, missing


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    tagged, quotes, locators, missing = check(argv[1], argv[2:])
    print(
        "body lines tagged 〔據典〕: {}; quotations checked: {}; locators checked: {}; missing: {}".format(
            len(tagged), quotes, locators, len(missing)
        )
    )
    for kind, value, line in missing:
        print("  MISSING {}: {} | in: {}".format(kind, value[:60], line))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
