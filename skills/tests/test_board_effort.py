import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _path
import adolib
import ado_sync_state
import effort
import plans
from fakeaz import COLUMNS

COLS = COLUMNS["value"]
UTC = dt.timezone.utc


class Place(unittest.TestCase):
    def test_default_column_for_state(self):
        self.assertEqual(adolib.place(COLS, "User Story", "New"), "New")
        self.assertEqual(adolib.place(COLS, "User Story", "Active"), "In development")

    def test_named_column_must_match_state(self):
        self.assertEqual(adolib.place(COLS, "User Story", "Active", "Test/Design review"), "Test/Design review")
        with self.assertRaisesRegex(ValueError, "holds User Story in state 'Active'"):
            adolib.place(COLS, "User Story", "New", "In development")
        with self.assertRaisesRegex(ValueError, "no column 'Review'"):
            adolib.place(COLS, "User Story", "Active", "Review")

    def test_state_without_column_is_refused(self):
        # The lesson: no Resolved column, so a Resolved story would vanish from the board.
        with self.assertRaisesRegex(ValueError, "drop off the board"):
            adolib.place(COLS, "User Story", "Resolved")

    def test_closed_refused_unless_allowed(self):
        with self.assertRaisesRegex(ValueError, "never set"):
            adolib.place(COLS, "User Story", "Closed")
        self.assertEqual(adolib.place(COLS, "User Story", "Closed", allow_done=True), "Closed")
        with self.assertRaises(ValueError):
            adolib.place(COLS, "User Story", "Removed", allow_done=True)

    def test_type_not_on_board_gets_no_column(self):
        self.assertIsNone(adolib.place(COLS, "Feature", "Active"))
        self.assertIsNone(adolib.place([], "User Story", "Active"))


class AzWrapper(unittest.TestCase):
    def test_windows_prefers_bundled_python_over_az_cmd(self):
        with tempfile.TemporaryDirectory() as t:
            wbin = Path(t) / "wbin"
            wbin.mkdir()
            (wbin / "az.cmd").write_text("@echo off\n", encoding="utf-8")
            (Path(t) / "python.exe").write_text("", encoding="utf-8")
            want = [str(Path(t) / "python.exe"), "-IBm", "azure.cli"]  # built before os.name is patched
            with mock.patch.object(adolib.shutil, "which", return_value=str(wbin / "az.cmd")), \
                    mock.patch.object(adolib.os, "name", "nt"):
                self.assertEqual(adolib.az_command(), want)

    def test_az_cmd_fallback_refuses_cmd_metacharacters(self):
        az = adolib.Az(prefix=["C:/az/wbin/az.cmd"], runner=lambda argv: self.fail("must not run"))
        with mock.patch.object(adolib.os, "name", "nt"):
            with self.assertRaisesRegex(adolib.AzError, "cmd.exe would mangle"):
                az("boards", "work-item", "create", "--title", "Search & filter")

    def test_missing_az(self):
        with mock.patch.object(adolib.shutil, "which", return_value=None):
            self.assertIsNone(adolib.az_command())
            self.assertFalse(adolib.Az().available)

    def test_project_slug(self):
        self.assertEqual(adolib.project_slug("Demo Prototype / Nordic"), "demo-prototype-nordic")
        self.assertEqual(adolib.project_slug("!!!"), "default")


PLAN = (_path.FIXTURES / "plan.md").read_text(encoding="utf-8")


class Plans(unittest.TestCase):
    def test_parse(self):
        items = plans.parse_plan(PLAN)
        self.assertEqual([(m, i) for m, i, _ in items],
                         [("x", "1.1"), ("x", "1.2"), (" ", "2.1"), ("~", "2.2"), ("x", "S.1"), ("x", "9.9")])
        self.assertIn("0badc0de", items[1][2])

    def test_first_match_wins_and_stem_prefix(self):
        pats = {"T5": ["5.7"], "T7": ["5.7*"], "B": ["fidelity:S.*"]}
        self.assertEqual(plans.key_for(pats, "nordic", "5.7"), "T5")
        self.assertEqual(plans.key_for(pats, "nordic", "5.7.1"), "T7")
        self.assertIsNone(plans.key_for(pats, "nordic", "S.1"))
        self.assertEqual(plans.key_for(pats, "fidelity", "S.1"), "B")

    def test_rules(self):
        rules = [{"when": "none", "state": "New"}, {"when": "some", "state": "Active", "column": "In development"},
                 {"when": "all", "state": "Active", "column": "Test/Design review"}]
        self.assertEqual(plans.target(rules, 0, 3), ("New", None))
        self.assertEqual(plans.target(rules, 1, 3), ("Active", "In development"))
        self.assertEqual(plans.target(rules, 3, 3), ("Active", "Test/Design review"))
        self.assertEqual(plans.target(rules, 0, 0), ("New", None))

    def test_sync_decide_refuses_unplaceable(self):
        rules = [{"when": "all", "state": "Resolved"}, {"when": "some", "state": "Active"}, {"when": "none", "state": "New"}]
        self.assertEqual(ado_sync_state.decide(rules, ["x", " "], COLS, "User Story", False), ("Active", None, "1/2 done"))
        with self.assertRaises(ValueError):
            ado_sync_state.decide(rules, ["x", "x"], COLS, "User Story", False)
        # A Task is not on the Stories board: state only.
        self.assertEqual(ado_sync_state.decide(rules, ["x", "x"], COLS, "Task", False)[0], "Resolved")


class Effort(unittest.TestCase):
    def test_claude_project_dir(self):
        home = Path("/home/u")
        self.assertEqual(effort.claude_project_dir(Path("/Users/a/Knowit/my.repo"), home),
                         home / ".claude" / "projects" / "-Users-a-Knowit-my-repo")
        self.assertEqual(effort.claude_project_dir("C:\\Users\\a\\repo", home).name, "C--Users-a-repo")

    def test_parse_usage_dedupes_and_sums(self):
        rec = {"timestamp": "2026-11-10T14:00:00Z", "requestId": "r1",
               "message": {"id": "m1", "usage": {"input_tokens": 10, "cache_creation_input_tokens": 5,
                                                 "cache_read_input_tokens": 100, "output_tokens": 7}}}
        lines = [json.dumps(rec), json.dumps(rec), "not json \"usage\"", json.dumps({"type": "user"})]
        u = effort.parse_usage(lines)
        self.assertEqual(u, [(dt.datetime(2026, 11, 10, 14, tzinfo=UTC), 115, 7, 100)])

    def test_aggregate_intervals(self):
        def t(h):
            return dt.datetime(2026, 11, 10, h, tzinfo=UTC)

        done = [(t(15), "B", "2.1"), (t(14), "A", "1.1"), (t(14), "A", "1.2")]
        usage = [(t(13), 1, 1, 0), (t(14), 10, 2, 5), (t(15), 100, 3, 50), (t(16), 999, 9, 9)]
        agg = effort.aggregate(done, usage, t(12))
        self.assertAlmostEqual(agg["A"]["h"], 2.0)
        self.assertEqual((agg["A"]["in"], agg["A"]["out"], agg["A"]["cr"]), (11, 3, 5))
        self.assertEqual(agg["A"]["items"], ["1.1", "1.2"])
        self.assertAlmostEqual(agg["B"]["h"], 1.0)
        self.assertEqual(agg["B"]["in"], 100)
        self.assertIn("2.0 h wall-clock", effort.line(agg["A"], t(15)))
        self.assertTrue(effort.total_line(agg, t(15)).startswith("Total effort so far"))
        self.assertIn("3.0 h", effort.total_line(agg, t(15)))
        self.assertEqual(effort.line(None, t(15)), "")

    def test_compute_with_injected_git_and_transcripts(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "plan.md").write_text(PLAN, encoding="utf-8")
            mp = Path(t) / "map.json"
            mp.write_text(json.dumps({"plans": ["plan.md"], "items": {"T1": ["1.*"], "T2": ["S.*"]},
                                      "effort": {"repo": t, "since": "2026-11-10T12:00:00Z"}}), encoding="utf-8")
            times = {"abc1234f": "2026-11-10T13:00:00+00:00", "deadbeef": "2026-11-10T13:30:00+00:00",
                     "0badc0de": "2026-11-10T14:00:00+00:00", "1234abcd": "2026-11-10T11:00:00+00:00"}

            def ct(repo, h):
                return effort.parse_ts(times[h]) if h in times else None

            agg, asof = effort.compute(plans.load_mapping(mp), commit_time=ct, usage_lines=[])
            self.assertAlmostEqual(agg["T1"]["h"], 2.0)       # 12:00 -> 13:30 (1.1), 13:30 -> 14:00 (1.2)
            self.assertNotIn("T2", agg)                         # its only commit predates `since`
            self.assertEqual(asof, effort.parse_ts("2026-11-10T14:00:00+00:00"))


if __name__ == "__main__":
    unittest.main()
