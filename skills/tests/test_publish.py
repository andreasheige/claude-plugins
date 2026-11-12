import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
import adolib
import ado_publish as pub
import backlog as bl
from fakeaz import FakeAz

FIXTURE = json.loads((_path.FIXTURES / "backlog.json").read_text(encoding="utf-8"))


def approved(ids=None):
    d = copy.deepcopy(FIXTURE)
    bl.approve(d, "Ann", ids)
    return d


class Run:
    def __init__(self, data, fake, ids_path, apply, effort=None, online=True):
        self.lines = []
        az = adolib.Az(prefix=["az"], runner=fake) if online else None
        self.p = pub.Publisher(data, az, apply, ids_path, effort, out=self.lines.append)
        self.rc = self.p.run()

    @property
    def text(self):
        return "\n".join(self.lines)


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ids = Path(self.tmp.name) / "proj" / "ids.json"
        self.fake = FakeAz()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_reads_but_never_writes(self):
        r = Run(approved(), self.fake, self.ids, apply=False)
        self.assertEqual(r.rc, 0, r.text)
        self.assertEqual(self.fake.writes(), [])
        self.assertFalse(self.ids.exists())
        self.assertIn('F1: would create Feature "Verktygskatalog i nya designen"', r.text)
        self.assertIn("S2: would set state Active, column In development", r.text)
        self.assertIn("T1: would link parent -> #19184", r.text)
        self.assertIn("DRY RUN", r.text)

    def test_offline_dry_run(self):
        r = Run(approved(), self.fake, self.ids, apply=False, online=False)
        self.assertEqual(r.rc, 0, r.text)
        self.assertEqual(self.fake.calls, [])
        self.assertIn("offline", r.text)

    def test_apply_creates_in_order_links_and_places(self):
        r = Run(approved(), self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 0, r.text)
        ids = json.loads(self.ids.read_text(encoding="utf-8"))
        self.assertEqual(ids, {"F1": 1000, "S1": 1001, "S2": 1002, "T1": 1003})
        s1 = self.fake.items[1001]["fields"]
        self.assertIn(bl.idempotency_tag("Demo Prototype", "S1"), s1["System.Tags"])
        self.assertIn("FE", s1["System.Tags"])
        self.assertIn("<b>Given</b> katalogen är öppen", s1["Microsoft.VSTS.Common.AcceptanceCriteria"])
        self.assertIn("&quot;lön&quot;", s1["Microsoft.VSTS.Common.AcceptanceCriteria"])
        self.assertIn("<ul><li>Sökfält överst</li>", s1["System.Description"])
        self.assertEqual(s1["Microsoft.VSTS.Scheduling.StoryPoints"], "3")
        s2 = self.fake.items[1002]["fields"]
        self.assertEqual((s2["System.State"], s2["System.BoardColumn"]), ("Active", "In development"))
        rels = {(wid, r["rel"].split(".")[-1], r["url"].rsplit("/", 1)[1])
                for wid, it in self.fake.items.items() for r in it["relations"]}
        self.assertEqual(rels, {
            (1001, "Hierarchy-Reverse", "1000"), (1002, "Hierarchy-Reverse", "1000"),
            (1002, "Dependency-Reverse", "1001"), (1003, "Hierarchy-Reverse", "19184"),
            (1003, "Dependency-Reverse", "1002")})
        create = [c for c in self.fake.calls if c[:3] == ["boards", "work-item", "create"]][0]
        self.assertIn("--org", create)
        self.assertEqual(create[create.index("--iteration") + 1], "Example\\Sprint 1")

    def test_second_apply_creates_nothing(self):
        Run(approved(), self.fake, self.ids, apply=True)
        before = len(self.fake.items)
        n_writes = len(self.fake.writes())
        r = Run(approved(), self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 0, r.text)
        self.assertEqual(len(self.fake.items), before)
        self.assertEqual(len(self.fake.writes()), n_writes, "re-run must not write")
        self.assertIn("0 created, 4 already in ADO", r.text)

    def test_lost_ids_file_finds_items_by_tag(self):
        Run(approved(), self.fake, self.ids, apply=True)
        self.ids.unlink()
        r = Run(approved(), self.fake, self.ids, apply=True)
        self.assertEqual(len(self.fake.items), 4, r.text)
        self.assertEqual(json.loads(self.ids.read_text(encoding="utf-8"))["S2"], 1002)

    def test_removed_item_in_ids_file_is_recreated(self):
        Run(approved(), self.fake, self.ids, apply=True)
        self.fake.items[1001]["fields"]["System.State"] = "Removed"
        r = Run(approved(), self.fake, self.ids, apply=True)
        self.assertIn("gone or Removed", r.text)
        self.assertEqual(json.loads(self.ids.read_text(encoding="utf-8"))["S1"], 1004)

    def test_only_approved_items_and_edits_void(self):
        d = approved(["F1", "S1"])
        d["items"][1]["title"] = "Changed after approval"
        r = Run(d, self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 0, r.text)
        self.assertEqual([it["fields"]["System.Title"] for it in self.fake.items.values()], ["Verktygskatalog i nya designen"])
        self.assertIn("S1: edited after approval", r.text)
        self.assertIn("S2: not approved", r.text)

    def test_reference_to_unapproved_unpublished_item_is_refused(self):
        r = Run(approved(["S1"]), self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 2)
        self.assertIn("S1 -> F1", r.text)
        self.assertEqual(self.fake.writes(), [])

    def test_unplaceable_state_is_refused_before_any_write(self):
        d = copy.deepcopy(FIXTURE)
        d["items"][2]["state"] = "Resolved"
        d["items"][2].pop("column")
        bl.approve(d, "Ann", None)
        r = Run(d, self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 2)
        self.assertIn("drop off the board", r.text)
        self.assertEqual(self.fake.writes(), [])

    def test_nothing_approved(self):
        r = Run(copy.deepcopy(FIXTURE), self.fake, self.ids, apply=True)
        self.assertEqual(r.rc, 1)

    def test_effort_line_on_create_and_update(self):
        Run(approved(), self.fake, self.ids, apply=True, effort={"S1": "Effort so far: 1.0 h"})
        self.assertIn("<p><em>Effort so far: 1.0 h</em></p>", self.fake.items[1001]["fields"]["System.Description"])
        Run(approved(), self.fake, self.ids, apply=True, effort={"S1": "Effort so far: 2.5 h"})
        desc = self.fake.items[1001]["fields"]["System.Description"]
        self.assertIn("2.5 h", desc)
        self.assertNotIn("1.0 h", desc)


class Helpers(unittest.TestCase):
    def test_text_to_html_escapes(self):
        self.assertEqual(pub.text_to_html("a <b> & c\nd\n\n- x\n- y<"),
                         "<p>a &lt;b&gt; &amp; c<br>d</p><ul><li>x</li><li>y&lt;</li></ul>")
        self.assertEqual(pub.text_to_html(""), "")

    def test_with_effort(self):
        self.assertEqual(pub.with_effort("<p>x</p>", "E"), "<p>x</p><p><em>E</em></p>")
        self.assertEqual(pub.with_effort("<p>x</p><p><em>Effort so far old</em></p>", "Effort so far new"),
                         "<p>x</p><p><em>Effort so far new</em></p>")

    def test_existing_targets(self):
        rels = [{"rel": pub.REL["parent"], "url": "https://x/_apis/wit/workItems/42"},
                {"rel": pub.REL["related"], "url": "https://x/_apis/wit/workItems/7"}]
        self.assertEqual(pub.existing_targets(rels, pub.REL["parent"]), {42})
        self.assertEqual(pub.existing_targets(None, pub.REL["parent"]), set())

    def test_cli_offline_dry_run_on_fixture(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "b.json"
            bl.save(p, approved())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = pub.main([str(p), "--offline", "--ids-file", str(Path(t) / "ids.json")])
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn("4 to create", out.getvalue())
            self.assertFalse((Path(t) / "ids.json").exists())


class SyncAndLogin(unittest.TestCase):
    def test_sync_state_dry_run_then_apply(self):
        import ado_sync_state
        from unittest import mock
        fake = FakeAz()
        with tempfile.TemporaryDirectory() as t:
            ids = Path(t) / "ids.json"
            with contextlib.redirect_stdout(io.StringIO()):
                Run(approved(), fake, ids, apply=True)
            (Path(t) / "plan.md").write_text("- [x] 1.1 a\n- [ ] 1.2 b\n- [x] 2.1 c\n", encoding="utf-8")
            mp = Path(t) / "map.json"
            mp.write_text(json.dumps({
                "plans": ["plan.md"], "items": {"S1": ["1.*"], "S2": ["2.*"]},
                "ado": {"project": "Example", "team": "Example Team"},
                "rules": [{"when": "none", "state": "New"},
                          {"when": "some", "state": "Active", "column": "In development"},
                          {"when": "all", "state": "Active", "column": "Test/Design review"}]}), encoding="utf-8")
            real_az = adolib.Az
            make = lambda *a, **k: real_az(prefix=["az"], runner=fake)  # noqa: E731
            args = [str(mp), "--project", "Demo Prototype", "--ids-file", str(ids)]
            for apply in (False, True):
                out = io.StringIO()
                with mock.patch.object(ado_sync_state.adolib, "Az", make), contextlib.redirect_stdout(out):
                    self.assertEqual(ado_sync_state.main(args + (["--apply"] if apply else [])), 0)
                if not apply:
                    self.assertIn("(dry run)", out.getvalue())
                    self.assertEqual(fake.items[1001]["fields"]["System.State"], "New")
            self.assertEqual(fake.items[1001]["fields"]["System.State"], "Active")
            self.assertEqual(fake.items[1001]["fields"]["System.BoardColumn"], "In development")
            self.assertEqual(fake.items[1002]["fields"]["System.BoardColumn"], "Test/Design review")

    def test_login_without_az_prints_installer_and_exits_4(self):
        import ado_login
        from unittest import mock
        out = io.StringIO()
        with mock.patch.object(ado_login.adolib, "az_command", return_value=None), contextlib.redirect_stdout(out):
            rc = ado_login.main(["--org", "https://dev.azure.com/example-org", "--project", "Example"])
        self.assertEqual(rc, 4)
        self.assertIn(ado_login.install_hint(), out.getvalue())
        self.assertEqual(ado_login.install_hint("Darwin"), "brew install azure-cli")
        self.assertEqual(ado_login.install_hint("Windows"), "winget install -e --id Microsoft.AzureCLI")


if __name__ == "__main__":
    unittest.main()
