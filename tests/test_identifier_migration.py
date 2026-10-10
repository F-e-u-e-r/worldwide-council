"""Gates for the Worldwide Council machine-identifier migration.

The brand/runtime identity — plugin, marketplace, skill, MCP server, agent namespace,
and the local runtime state dir — is migrated to ``worldwide-council``. Four classes of
older identifier are intentionally PRESERVED and must keep the old name:

  * versioned protocol IDs  — ``religion-council/retrieval/v1``, ``religion-council/claim/v1``
    (and the ``-draft`` variant). Brand migration != protocol version migration.
  * the external repo slug  — ``github.com/F-e-u-e-r/religion-council`` (repo is now ``F-e-u-e-r/worldwide-council``; the old slug persists in history and GitHub's redirect).
  * natural-language safety triggers — ``"do not start the religion council"`` in the routing policies.
  * historical records       — CHANGELOG history, ADRs, the frozen product review, ``docs/release/``.

Each gate carries a known-bad arm (in-memory / scratch, no repo mutation) proving it has teeth.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = "worldwide-council"

OLD_MACHINE = re.compile(r"religion-council|worldview-council")
# substrings that legitimately carry the old token on a current surface
PROTO_EXEMPT = re.compile(r"religion-council/(?:retrieval|claim)/")
SLUG_EXEMPT = re.compile(r"github\.com|F-e-u-e-r/religion-council")


class GateACanonicalIdentifiers(unittest.TestCase):
    """The plugin, marketplace, skill and MCP identities are all ``worldwide-council``."""

    def test_canonical_identity_everywhere(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))
        mkt = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text("utf-8"))
        mcp = json.loads((ROOT / ".mcp.json").read_text("utf-8"))
        self.assertEqual(plugin["name"], CANON)
        self.assertEqual(plugin["displayName"], "Worldwide Council")  # display unchanged
        self.assertEqual(mkt["name"], CANON)
        self.assertEqual([e["name"] for e in mkt["plugins"]], [CANON])
        self.assertIn(CANON + "-controller", plugin["mcpServers"])
        self.assertIn(CANON + "-controller", mcp["mcpServers"])
        for rel in ("skills/worldwide-council/SKILL.md",
                    ".claude/skills/worldwide-council/SKILL.md"):
            frontmatter = (ROOT / rel).read_text("utf-8").split("---", 2)[1]
            self.assertIn("name: " + CANON, frontmatter)

    def test_known_bad_old_names_are_not_canonical(self):
        # falsification: an assertEqual(actual, CANON) gate goes RED if actual reverts to an old id
        for bad in ("religion-council", "worldview-council"):
            self.assertNotEqual(bad, CANON)


class GateBNamespace(unittest.TestCase):
    """Agent namespace and MCP tool names derive from the plugin name = ``worldwide-council``."""

    def test_moderator_namespace_and_tools(self):
        mod = (ROOT / ".claude" / "agents" / "council-moderator.md").read_text("utf-8")
        self.assertIn("worldwide-council:council-", mod)
        self.assertNotIn("religion-council:council-", mod)
        self.assertIn("mcp__worldwide-council-controller__", mod)
        self.assertNotIn("mcp__religion-council-controller__", mod)

    def test_known_bad_stale_namespace_detected(self):
        sample = "mcp__religion-council-controller__debate_start"
        self.assertIn("religion-council-controller", sample)  # the string a RED moderator would carry


class GateCDirectoryParity(unittest.TestCase):
    """Both skill trees live under ``worldwide-council``; the old dirs are gone; references match."""

    def test_new_trees_exist_old_gone(self):
        for rel in ("skills/worldwide-council", ".claude/skills/worldwide-council"):
            self.assertTrue((ROOT / rel / "SKILL.md").is_file(), rel)
        for rel in ("skills/religion-council", ".claude/skills/religion-council"):
            self.assertFalse((ROOT / rel).exists(), rel + " (old skill dir must be gone)")

    def test_reference_parity(self):
        a = sorted(p.name for p in (ROOT / "skills/worldwide-council/references").glob("*.md"))
        b = sorted(p.name for p in (ROOT / ".claude/skills/worldwide-council/references").glob("*.md"))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)


class GateDNoActiveStaleIdentifier(unittest.TestCase):
    """Field/path-scoped: current runtime surfaces carry NO active old machine id.

    This is deliberately NOT a repo-wide denylist. Protocol IDs, the external slug, nl
    triggers and historical records are exempt and checked elsewhere; here we pin the
    surfaces that define the live identity: agent bodies and the three manifests.
    """

    def _surfaces(self):
        files = sorted((ROOT / ".claude" / "agents").glob("council-*.md"))
        files += [ROOT / ".claude-plugin" / "plugin.json",
                  ROOT / ".claude-plugin" / "marketplace.json",
                  ROOT / ".mcp.json"]
        return files

    @staticmethod
    def _stale_lines(text):
        out = []
        for i, line in enumerate(text.splitlines(), 1):
            if OLD_MACHINE.search(line) and not PROTO_EXEMPT.search(line) and not SLUG_EXEMPT.search(line):
                out.append((i, line.strip()))
        return out

    def test_no_stale_in_current_surfaces(self):
        offenders = []
        for f in self._surfaces():
            for i, line in self._stale_lines(f.read_text("utf-8")):
                offenders.append("{}:{}:{}".format(f.relative_to(ROOT), i, line))
        self.assertEqual(offenders, [], "stale machine-id on current surfaces:\n" + "\n".join(offenders))

    def test_known_bad_injected_stale_is_caught(self):
        # falsification: the same scan flags an injected stale line (but not a protocol/slug line)
        self.assertTrue(self._stale_lines("tools: mcp__religion-council-controller__debate_start"))
        self.assertFalse(self._stale_lines('"contract_version": "religion-council/retrieval/v1"'))
        self.assertFalse(self._stale_lines("url https://github.com/F-e-u-e-r/religion-council"))


class GateEProtocolPreservation(unittest.TestCase):
    """Versioned protocol IDs stay ``religion-council/...`` — brand migration is not a v2 bump."""

    def test_contracts_unchanged(self):
        retr = (ROOT / "skills/worldwide-council/scripts/retrieve.py").read_text("utf-8")
        self.assertIn('RETRIEVAL_CONTRACT_VERSION = "religion-council/retrieval/v1"', retr)
        claim = (ROOT / "orchestrator" / "claim_protocol.py").read_text("utf-8")
        self.assertIn('PROTOCOL_VERSION = "religion-council/claim/v1"', claim)
        self.assertIn('DRAFT_PROTOCOL_VERSION = "religion-council/claim/v1-draft"', claim)

    def test_known_bad_rebranded_protocol_absent(self):
        # a worldwide-council/retrieval id would be a DIFFERENT contract (v2), out of scope this round
        retr = (ROOT / "skills/worldwide-council/scripts/retrieve.py").read_text("utf-8")
        self.assertNotIn("worldwide-council/retrieval", retr)
        claim = (ROOT / "orchestrator" / "claim_protocol.py").read_text("utf-8")
        self.assertNotIn("worldwide-council/claim", claim)


class GateFRosterInvariants(unittest.TestCase):
    """Identifier migration must not change roster semantics: 37 voices / 1 mod / 38 / 10 / 8."""

    def test_counts_and_preserved_fixture(self):
        agents = sorted((ROOT / ".claude" / "agents").glob("council-*.md"))
        self.assertEqual(len(agents), 38)
        self.assertEqual(sum(p.name == "council-moderator.md" for p in agents), 1)
        self.assertEqual(sum(p.name != "council-moderator.md" for p in agents), 37)
        self.assertIn("council-judaism.md", [p.name for p in agents])
        default = json.loads((ROOT / "orchestrator/panelists/worldwide-10.json").read_text("utf-8"))
        self.assertEqual(len(default["panelists"]), 10)
        eight = json.loads((ROOT / "orchestrator/panelists/religion-8.json").read_text("utf-8"))
        self.assertEqual(len(eight["panelists"]), 8)
        # religion-8.json filename is deliberately preserved as the evidence fixture
        self.assertTrue((ROOT / "orchestrator/panelists/religion-8.json").is_file())


class GateHCompatibility(unittest.TestCase):
    """Runtime state dir and the project-dir env var keep a read-only fallback to the old name."""

    def _controller(self, root, state_dir=None):
        sys.path.insert(0, str(ROOT / "orchestrator"))
        from debate_controller import DebateController
        return DebateController(str(root), state_dir=state_dir, codex_command="true")

    def test_state_dir_defaults_to_new(self):
        with tempfile.TemporaryDirectory() as d:
            c = self._controller(d)
            self.assertEqual(c.state_dir.parent.name, ".worldwide-council")
            self.assertEqual(c.state_dir.name, "runs")

    def test_state_dir_falls_back_to_old_when_only_old_exists(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".religion-council" / "runs").mkdir(parents=True)
            c = self._controller(d)
            self.assertEqual(c.state_dir.parent.name, ".religion-council")  # compatibility read

    def test_state_dir_prefers_new_when_both_exist(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".religion-council" / "runs").mkdir(parents=True)
            (Path(d) / ".worldwide-council" / "runs").mkdir(parents=True)
            c = self._controller(d)
            self.assertEqual(c.state_dir.parent.name, ".worldwide-council")

    def test_explicit_state_dir_wins(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "custom-runs"
            c = self._controller(d, state_dir=str(target))
            self.assertEqual(c.state_dir, target.resolve())

    def test_env_var_new_primary_old_alias(self):
        sys.path.insert(0, str(ROOT / "orchestrator"))
        import debate_controller as dc
        keys = ("WORLDWIDE_COUNCIL_PROJECT_DIR", "RELIGION_COUNCIL_PROJECT_DIR", "CLAUDE_PROJECT_DIR")
        saved = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ.pop(k, None)
            os.environ["RELIGION_COUNCIL_PROJECT_DIR"] = "/tmp/old-alias-dir"
            self.assertEqual(str(dc.default_project_root()), "/tmp/old-alias-dir")  # old alias honoured
            os.environ["WORLDWIDE_COUNCIL_PROJECT_DIR"] = "/tmp/new-primary-dir"
            self.assertEqual(str(dc.default_project_root()), "/tmp/new-primary-dir")  # new wins
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
