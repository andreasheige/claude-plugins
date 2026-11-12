import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401  (puts scripts/ on sys.path)
import backlog as bl

FIXTURE = json.loads((_path.FIXTURES / "backlog.json").read_text(encoding="utf-8"))


def fresh():
    return copy.deepcopy(FIXTURE)


class Validate(unittest.TestCase):
    def test_fixture_is_valid(self):
        self.assertEqual(bl.validate(fresh()), [])

    def test_unknown_fields_and_missing_title(self):
        d = fresh()
        d["extra"] = 1
        d["items"][1]["colour"] = "red"
        d["items"][1]["title"] = " "
        errs = bl.validate(d)
        self.assertTrue(any("unknown top-level field 'extra'" in e for e in errs))
        self.assertTrue(any("unknown field 'colour'" in e for e in errs))
        self.assertTrue(any("title is required" in e for e in errs))

    def test_unknown_reference_and_bad_ado_ref(self):
        d = fresh()
        d["items"][1]["dependsOn"] = ["NOPE", "#12x"]
        errs = bl.validate(d)
        self.assertTrue(any("unknown item 'NOPE'" in e for e in errs))
        self.assertTrue(any("bad reference '#12x'" in e for e in errs))

    def test_cycle(self):
        d = fresh()
        d["items"][1]["dependsOn"] = ["S2"]  # S2 already depends on S1
        errs = bl.validate(d)
        self.assertTrue(any(e.startswith("cycle") for e in errs), errs)

    def test_related_both_ways_is_not_a_cycle(self):
        d = fresh()
        d["items"][1]["related"] = ["S2"]
        d["items"][2]["related"] = ["S1"]
        self.assertEqual(bl.validate(d), [])

    def test_forbidden_state_and_duplicate_key(self):
        d = fresh()
        d["items"][2]["state"] = "Closed"
        d["items"].append(dict(d["items"][0]))
        errs = bl.validate(d)
        self.assertTrue(any("'Closed' is never set" in e for e in errs))
        self.assertTrue(any("duplicate key 'F1'" in e for e in errs))

    def test_structured_criterion_needs_all_three(self):
        d = fresh()
        d["items"][1]["acceptanceCriteria"] = [{"given": "a", "when": "b"}]
        self.assertTrue(any("given/when/then" in e for e in bl.validate(d)))

    def test_tag_with_semicolon(self):
        d = fresh()
        d["items"][1]["tags"] = ["a;b"]
        self.assertTrue(any("without ';'" in e for e in bl.validate(d)))


class SchemaAgreement(unittest.TestCase):
    """The JSON Schema in references/ and the stdlib validator must describe the same file."""

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((_path.SKILL / "references" / "backlog.schema.json").read_text(encoding="utf-8"))

    def test_top_level(self):
        self.assertEqual(set(self.schema["properties"]) | {"$schema"}, bl.TOP_KEYS)
        self.assertEqual(set(self.schema["required"]), {"version", "project", "items"})

    def test_item_fields_and_types(self):
        item = self.schema["$defs"]["item"]
        self.assertEqual(set(item["properties"]), bl.ITEM_KEYS)
        self.assertEqual(tuple(item["properties"]["type"]["enum"]), bl.TYPES)
        self.assertEqual(set(item["properties"]["state"]["not"]["enum"]), bl.FORBIDDEN_STATES)
        self.assertTrue(set(bl.PUBLISHED) <= bl.ITEM_KEYS)


class Keys(unittest.TestCase):
    def test_tag_is_stable_and_ignores_title(self):
        a = bl.idempotency_tag("Demo Prototype", "S1")
        self.assertEqual(a, bl.idempotency_tag("demo prototype ", "S1"))
        self.assertRegex(a, r"^ptb-[0-9a-f]{10}$")

    def test_tag_differs_per_key_and_project(self):
        tags = {bl.idempotency_tag(p, k) for p in ("A", "B") for k in ("S1", "S2")}
        self.assertEqual(len(tags), 4)

    def test_content_hash_ignores_refinement_and_approval(self):
        d = fresh()
        it = d["items"][1]
        h = bl.content_hash(it, d)
        it["refinement"] = {"status": "refined", "rounds": 1}
        it["approval"] = {"at": "x", "hash": "0" * 16}
        self.assertEqual(bl.content_hash(it, d), h)
        it["title"] += "!"
        self.assertNotEqual(bl.content_hash(it, d), h)

    def test_approval_binds_target_inherited_defaults_and_identity(self):
        for change in (lambda d: d["ado"].__setitem__("area", "Other\\Area"),
                       lambda d: d["ado"].__setitem__("organization", "https://dev.azure.com/other-org"),
                       lambda d: d["ado"].__setitem__("project", "Other"),
                       lambda d: d["ado"].__setitem__("assignedTo", "someone@example.com"),
                       lambda d: d.__setitem__("project", "Another backlog")):
            d = fresh()
            bl.approve(d, "Ann", None)
            change(d)
            self.assertFalse(bl.is_approved(d["items"][1], d))

    def test_item_override_shields_from_default_change(self):
        d = fresh()
        d["items"][1]["area"] = "Example\\Own"
        bl.approve(d, "Ann", None)
        d["ado"]["area"] = "Example\\Changed"
        self.assertTrue(bl.is_approved(d["items"][1], d))
        self.assertFalse(bl.is_approved(d["items"][2], d))


class Approval(unittest.TestCase):
    def test_approve_listed_ids_and_edit_voids(self):
        d = fresh()
        chosen = bl.approve(d, "Ann", ["S1", "F1"], "ok")
        self.assertEqual(chosen, ["S1", "F1"])
        by = {it["key"]: it for it in d["items"]}
        self.assertTrue(bl.is_approved(by["S1"], d))
        self.assertFalse(bl.is_approved(by["S2"], d))
        self.assertEqual(d["approvals"][-1]["scope"], "ids")
        by["S1"]["acceptanceCriteria"].append("one more")
        self.assertFalse(bl.is_approved(by["S1"], d))
        self.assertEqual(bl.validate(d), [])

    def test_approve_all(self):
        d = fresh()
        bl.approve(d, "Ann", None)
        self.assertTrue(all(bl.is_approved(it, d) for it in d["items"]))
        self.assertEqual(d["approvals"][0]["scope"], "all")

    def test_unknown_id_raises_and_changes_nothing(self):
        d = fresh()
        with self.assertRaises(KeyError):
            bl.approve(d, "Ann", ["S1", "S9"])
        self.assertNotIn("approvals", d)
        self.assertFalse(any("approval" in it for it in d["items"]))


class Order(unittest.TestCase):
    def test_parents_and_predecessors_first(self):
        items = list(reversed(fresh()["items"]))
        keys = [it["key"] for it in bl.publish_order(items)]
        self.assertLess(keys.index("F1"), keys.index("S1"))
        self.assertLess(keys.index("S1"), keys.index("S2"))
        self.assertLess(keys.index("S2"), keys.index("T1"))


class Ready(unittest.TestCase):
    def test_complete_story_is_ready(self):
        self.assertEqual(bl.ready_problems(fresh()["items"][1]), [])

    def test_gaps_are_named(self):
        it = fresh()["items"][1]
        it["description"] = "Search."
        it["acceptanceCriteria"] = ["works"]
        del it["parent"], it["screenshots"]
        p = " | ".join(bl.ready_problems(it))
        for word in ("user-story sentence", "fewer than 2", "Given/When/Then", "parent", "screenshot"):
            self.assertIn(word, p)

    def test_english_sentence_and_non_story(self):
        it = fresh()["items"][1]
        it["description"] = "As a user I want to search so that I find tools."
        self.assertEqual(bl.ready_problems(it), [])
        self.assertEqual(bl.ready_problems(fresh()["items"][0]), [])


class RenderAndFiles(unittest.TestCase):
    def test_render_shows_everything_and_survives_utf8(self):
        d = fresh()
        bl.approve(d, "Åsa Öberg", ["S1"])
        md = bl.render_markdown(d)
        self.assertIn("## S1 · User Story: Sök verktyg i katalogen  (approved)", md)
        self.assertIn("(not approved)", md)
        self.assertIn("**Given** katalogen är öppen", md)
        self.assertIn("Approved", md)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "b.json"
            bl.save(p, d)
            self.assertEqual(bl.load(p), d)
            self.assertIn("Sök", p.read_bytes().decode("utf-8"))

    def test_cli_approve_and_status(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "b.json"
            bl.save(p, fresh())
            quiet = contextlib.ExitStack()
            quiet.enter_context(contextlib.redirect_stdout(io.StringIO()))
            quiet.enter_context(contextlib.redirect_stderr(io.StringIO()))
            self.addCleanup(quiet.close)
            self.assertEqual(bl.main(["approve", str(p), "--by", "Ann", "--ids", "F1,S1"]), 0)
            loaded = bl.load(p)
            self.assertTrue(bl.is_approved(loaded["items"][1], loaded))
            self.assertEqual(bl.main(["approve", str(p), "--by", "Ann", "--ids", "X"]), 2)
            self.assertEqual(bl.main(["render", str(p)]), 0)
            self.assertTrue((Path(t) / "b.md").is_file())


if __name__ == "__main__":
    unittest.main()
