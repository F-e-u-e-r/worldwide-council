import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOWCASE = ROOT / "docs" / "showcase"
SCRIPT = ROOT / "scripts" / "check_showcase_citations.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("check_showcase_citations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShowcaseCitationCheckTest(unittest.TestCase):
    """The public showcase transcripts must quote the bundled references verbatim (curation-side
    check, not strict mode), and the checker must be able to fail — a fabricated quotation or a
    fabricated locator in the transcript BODY is reported, while header/curation prose is ignored."""

    @classmethod
    def setUpClass(cls):
        cls.checker = load_checker()

    def test_committed_claude_only_showcase_is_fully_matched(self):
        transcript = SHOWCASE / "2026-09-28-claude-only-meaning-of-life.md"
        tagged, quotes, locators, missing = self.checker.check(
            transcript, ["04-佛教.md", "05-道教.md", "07-儒家.md"]
        )
        self.assertGreaterEqual(quotes, 12)
        self.assertGreaterEqual(locators, 12)
        self.assertEqual(missing, [])

    def test_fabricated_quote_and_locator_in_body_are_reported(self):
        text = (
            "| 保證層級 | 標頭提到〔據典〕與「引文複核」不得被掃描 |\n\n"
            "# 議會逐字稿\n\n"
            "**B1-P1**:〔據典〕「此句並不存在於任何 references 檔案之中。」——《偽經》99。\n"
            "**T1-P1**:〔據典〕「人法地,地法天,天法道,道法自然。」——《道德經》25。\n\n"
            "## 執行資訊\n- 〔據典〕僅取自「A 主張」區塊……(run metadata, not scanned)\n\n"
            "---\n\n## 引文複核\n〔據典〕「這一行在本體之外,不得被掃描。」\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.md"
            path.write_text(text, encoding="utf-8")
            tagged, quotes, locators, missing = self.checker.check(path, ["05-道教.md"])
        self.assertEqual(len(tagged), 2)  # header + curation lines were not scanned
        kinds = sorted(kind for kind, _, _ in missing)
        self.assertEqual(kinds, ["locator", "quote"])  # the fabricated pair, and only that pair

    def test_missing_body_heading_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.md"
            path.write_text("no transcript here\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.checker.check(path, ["05-道教.md"])


if __name__ == "__main__":
    unittest.main()
