import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
EVIDENCE_TRADITIONS = {
    "christianity", "islam", "hinduism", "buddhism",
    "taoism", "legalism", "confucianism", "mohism",
}


def _load_portable_retriever():
    """Load the portable retriever by path (stdlib-only, not an installed module)."""
    import importlib.util

    path = ROOT / "skills" / "worldwide-council" / "scripts" / "retrieve.py"
    spec = importlib.util.spec_from_file_location("rc_retrieve_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryValidationTest(unittest.TestCase):
    def test_release_version_is_beta(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "v0.1.0-beta.1")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("version: v0.1.0-beta.1", readme)
        controller = (ROOT / "orchestrator" / "debate_controller.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('CONTROLLER_VERSION = "0.1.0-beta.1"', controller)

    def test_plugin_manifests_match_the_repository(self):
        # The repo doubles as a Claude Code plugin + self-hosted marketplace. Pin the parts that
        # drift silently: the plugin version tracks VERSION (release prep bumps both), every
        # declared agent path exists, the 38-agent roster is the plugin's roster, the skill dir the
        # portable skill, and the marketplace entry names the same plugin from the repo root.
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(plugin["name"], "worldwide-council")  # migrated from religion-council (Worldwide Council machine-id migration; CHANGELOG [Unreleased])
        self.assertEqual(plugin["displayName"], "Worldwide Council")
        self.assertEqual("v" + plugin["version"], version)
        agents = plugin["agents"]
        self.assertEqual(len(agents), 38)
        for rel in agents:
            self.assertTrue(rel.startswith("./.claude/agents/council-"), rel)
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertEqual(
            sorted(Path(rel).name for rel in agents),
            sorted(p.name for p in (ROOT / ".claude" / "agents").glob("council-*.md")),
        )
        self.assertTrue((ROOT / "skills" / "worldwide-council" / "SKILL.md").is_file())
        server = plugin["mcpServers"]["worldwide-council-controller"]
        args = server["args"]
        # Behaviour pins, not layout pins: the controller runs from the installed plugin root, its run
        # state lives in the per-plugin data dir (never inside ${CLAUDE_PLUGIN_ROOT}, which is replaced
        # on update), and the server subcommand is `serve`.
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/orchestrator/debate_controller.py", args)
        self.assertIn("--state-dir", args)
        self.assertTrue(args[args.index("--state-dir") + 1].startswith("${CLAUDE_PLUGIN_DATA}/"))
        self.assertEqual(args[-1], "serve")
        entries = marketplace["plugins"]
        self.assertEqual([e["name"] for e in entries], ["worldwide-council"])
        self.assertEqual(entries[0]["source"], "./")

    def test_current_canonical_display_name_is_worldwide_council(self):
        # October 2026 docs-only rebrand: the CURRENT canonical product/display name is
        # "Worldwide Council". This audit is deliberately FIELD-SCOPED to the current-state display
        # surfaces, not a repo-wide denylist: historical records (CHANGELOG history, ADRs, the frozen
        # product review), versioned protocol IDs (`religion-council/retrieval/v1`, `.../claim/v1`),
        # the external repo slug, and skill trigger aliases may and must still mention the older names.
        current = "Worldwide Council"
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["displayName"], current)
        self.assertEqual(plugin["author"]["name"], current + " contributors")
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        # the marketplace *name* is a machine identifier, migrated to `worldwide-council` (was `worldview-council`)
        self.assertEqual(marketplace["name"], "worldwide-council")
        self.assertTrue(marketplace["metadata"]["description"].startswith(current + ":"))
        self.assertTrue(marketplace["plugins"][0]["description"].startswith(current + ":"))
        openai_yaml = (
            ROOT / "skills" / "worldwide-council" / "agents" / "openai.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn('display_name: "{}"'.format(current), openai_yaml)
        for old in ("Worldview Council", "Religion Council"):
            self.assertNotIn('display_name: "{}"'.format(old), openai_yaml)
        readme_first_line = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(readme_first_line, "# {} · 多傳統哲學議會".format(current))
        disclaimer = (ROOT / "DISCLAIMER.md").read_text(encoding="utf-8")
        self.assertIn("{} stages".format(current), disclaimer)
        for skill_rel in (
            "skills/worldwide-council/SKILL.md",
            ".claude/skills/worldwide-council/SKILL.md",
        ):
            self.assertIn(current, (ROOT / skill_rel).read_text(encoding="utf-8"), skill_rel)

    def test_agent_bodies_use_plugin_root_paths(self):
        # T5 (installed-copy runtime acceptance): a plugin install runs the agents from a cached
        # copy in an unrelated working directory, so a repo-relative resource path in an agent body
        # is a dead path there. Every voice carries the dual-mode note and only
        # `${CLAUDE_PLUGIN_ROOT}/…` resource paths; the moderator additionally carries the dispatch
        # rules (resource-root handoff + namespaced member names in plugin mode).
        bare = re.compile(r"`(?:\.claude/skills/worldwide-council/|references/|policies/|orchestrator/panelists/)")
        for path in sorted((ROOT / ".claude" / "agents").glob("council-*.md")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/", text, path.name)
            self.assertIn("路徑", text, path.name)  # the 路徑說明 / 路徑與成員名稱說明 note
            self.assertIsNone(bare.search(text), (path.name, "bare repo-relative resource path"))
        moderator = (ROOT / ".claude" / "agents" / "council-moderator.md").read_text(encoding="utf-8")
        self.assertIn("資源根目錄:", moderator)
        self.assertIn("worldwide-council:council-", moderator)

    def test_markdown_relative_links_exist(self):
        missing = []
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_RE.findall(text):
                target = target.strip("<>")
                if (
                    not target
                    or target.startswith("#")
                    or "://" in target
                    or target.startswith("mailto:")
                ):
                    continue
                relative = target.split("#", 1)[0]
                if relative and not (path.parent / relative).exists():
                    missing.append("{} -> {}".format(path.relative_to(ROOT), target))
        self.assertEqual(missing, [])

    def test_no_unresolved_public_placeholders(self):
        forbidden = ("<your-fork-url>", "TODO:", "FIXME:")
        failures = []
        for name in ("README.md", "INSTALL.md", "docs/ORCHESTRATION.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for value in forbidden:
                if value in text:
                    failures.append("{} contains {}".format(name, value))
        self.assertEqual(failures, [])

    def test_roster_counts_and_unique_ids(self):
        expectations = {
            "orchestrator/panelists/religion-8.json": 8,
            "orchestrator/panelists/worldwide-10.json": 10,
            "orchestrator/panelists/thirty-member-example.json": 30,
        }
        for relative, expected in expectations.items():
            data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            panelists = data["panelists"]
            ids = [item["id"] for item in panelists]
            self.assertEqual(len(panelists), expected, relative)
            self.assertEqual(len(ids), len(set(ids)), relative)

    def test_claude_agent_roster_is_one_moderator_plus_37_voices(self):
        # Gate A: exactly 38 council agent files = 1 moderator + 37 voices (was 1 + 36 before the
        # October 2026 coverage remediation added council-judaism).
        paths = sorted((ROOT / ".claude" / "agents").glob("council-*.md"))
        self.assertEqual(len(paths), 38)
        self.assertEqual(sum(path.name == "council-moderator.md" for path in paths), 1)
        self.assertEqual(sum(path.name != "council-moderator.md" for path in paths), 37)
        self.assertIn("council-judaism.md", [p.name for p in paths])
        names = []
        for path in paths:
            match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, path)
            name_line = next(
                line for line in match.group(1).splitlines() if line.startswith("name:")
            )
            name = name_line.split(":", 1)[1].strip()
            self.assertEqual(path.stem, name)
            names.append(name)
        self.assertEqual(len(names), len(set(names)))

    def test_default_council_roster_is_ten_with_judaism_and_secular(self):
        # Gate B: the default council roster is exactly ten = the eight evidence-backed tradition
        # voices + secular humanism + Judaism. religion-8.json stays the eight-evidence subset.
        default = json.loads(
            (ROOT / "orchestrator" / "panelists" / "worldwide-10.json").read_text(encoding="utf-8")
        )
        ids = [p["id"] for p in default["panelists"]]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("secular-humanist", ids)
        self.assertIn("judaism", ids)
        # retains the original eight default tradition voices
        self.assertTrue(EVIDENCE_TRADITIONS.issubset(set(ids)), ids)
        # the two additions over the eight-evidence set are exactly the interpretive voices
        self.assertEqual(set(ids) - EVIDENCE_TRADITIONS, {"secular-humanist", "judaism"})
        # and the eight-evidence roster is untouched (still eight, same ids)
        eight = json.loads(
            (ROOT / "orchestrator" / "panelists" / "religion-8.json").read_text(encoding="utf-8")
        )
        self.assertEqual({p["id"] for p in eight["panelists"]}, EVIDENCE_TRADITIONS)

    def test_evidence_backed_traditions_remain_eight_and_independent_of_default(self):
        # Gate C: the evidence layer (retrieval TRADITIONS) stays exactly eight and is an
        # INDEPENDENT contract from the ten-voice default council. The two interpretive default
        # voices must never be classified as evidence-backed (never enter TRADITIONS).
        retriever = _load_portable_retriever()
        traditions = set(retriever.TRADITIONS)
        self.assertEqual(len(traditions), 8)
        self.assertEqual(traditions, EVIDENCE_TRADITIONS)
        self.assertNotIn("judaism", traditions)
        self.assertNotIn("secular-humanist", traditions)
        # independence: default roster count (10) does NOT imply evidence-backed count (8)
        default_ids = {
            p["id"]
            for p in json.loads(
                (ROOT / "orchestrator" / "panelists" / "worldwide-10.json").read_text(
                    encoding="utf-8"
                )
            )["panelists"]
        }
        self.assertEqual(len(default_ids), 10)
        self.assertEqual(len(traditions), 8)
        self.assertNotEqual(len(default_ids), len(traditions))
        # known-bad arm: a voice is evidence-backed IFF it is in TRADITIONS; mis-labelling the two
        # interpretive voices as evidence-backed is caught here.
        evidence_backed = lambda vid: vid in traditions  # noqa: E731
        self.assertFalse(evidence_backed("judaism"))
        self.assertFalse(evidence_backed("secular-humanist"))
        for vid in EVIDENCE_TRADITIONS:
            self.assertTrue(evidence_backed(vid), vid)

    def test_public_copy_reflects_current_roster(self):
        # Gate D (field-scoped, not a repo-wide denylist): current-facing public copy states the
        # current roster (37 voices / 38 agents), does not label Judaism evidence-backed, and no
        # longer describes secular humanism as outside the default. Historical records keep their
        # period-correct counts and are not inspected here.
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("36 voices", readme)
        self.assertNotIn("36 個聲音", readme)
        self.assertNotIn("outside the default eight", readme)
        self.assertIn("1 moderator + 37 voices", readme)
        # Judaism appears only as an interpretive voice, never promoted into the evidence-backed row
        self.assertIn(
            "**Traditions** (8) — *evidence-backed* | Christianity · Islam · Hinduism · "
            "Buddhism · Taoism · Legalism",
            readme,
        )
        self.assertIn("Judaism — *a tradition-level interpretive voice", readme)
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertIn("37 voices", plugin["description"])
        self.assertNotIn("36 voices", plugin["description"])
        self.assertIn("37 voices", marketplace["plugins"][0]["description"])

    def test_manifest_roster_gate_detects_missing_judaism(self):
        # Gate E known-bad arm (ground-truth): prove the manifest/glob consistency gate has teeth.
        # The real manifest matches the agent-file glob; dropping council-judaism from either side
        # must make the comparison fail, so a future roster that forgets Judaism goes RED.
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        manifest_names = sorted(Path(rel).name for rel in plugin["agents"])
        glob_names = sorted(
            p.name for p in (ROOT / ".claude" / "agents").glob("council-*.md")
        )
        self.assertIn("council-judaism.md", manifest_names)
        self.assertEqual(manifest_names, glob_names)  # real roster: passes
        mutated = [n for n in manifest_names if n != "council-judaism.md"]
        self.assertNotEqual(mutated, glob_names)  # mutation (Judaism dropped): fails the gate

    def test_moderator_can_complete_the_strict_finalization_workflow(self):
        moderator = ROOT / ".claude" / "agents" / "council-moderator.md"
        text = moderator.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        self.assertIn(
            "mcp__worldwide-council-controller__debate_finalize", match.group(1)
        )
        self.assertIn("`assurance_footer`", text)

    def test_portable_skill_frontmatter_and_references(self):
        skill = ROOT / "skills" / "worldwide-council" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        keys = {
            line.split(":", 1)[0].strip()
            for line in match.group(1).splitlines()
            if ":" in line
        }
        self.assertEqual(keys, {"name", "description"})
        self.assertIn("name: worldwide-council", match.group(1))
        references = set(re.findall(r"`(references/[^`]+\.md)`", text))
        self.assertEqual(len(references), 16)
        for relative in references:
            self.assertTrue((skill.parent / relative).is_file(), relative)

    def test_reference_bodies_match_between_distributions(self):
        portable = ROOT / "skills" / "worldwide-council" / "references"
        claude = ROOT / ".claude" / "skills" / "worldwide-council" / "references"
        portable_names = sorted(path.name for path in portable.glob("*.md"))
        claude_names = sorted(path.name for path in claude.glob("*.md"))
        self.assertEqual(portable_names, claude_names)
        for name in portable_names:
            portable_body = (portable / name).read_text(encoding="utf-8").split(
                "## 引用紀律", 1
            )[0]
            claude_body = (claude / name).read_text(encoding="utf-8").split(
                "## 引用紀律", 1
            )[0]
            self.assertEqual(portable_body, claude_body, name)

    def test_project_mcp_registration(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["worldwide-council-controller"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("debate_controller.py", " ".join(server["args"]))


if __name__ == "__main__":
    unittest.main()
