"""An in-memory stand-in for az: records every call, keeps work items, never touches the network."""
import json
import subprocess

COLUMNS = {"value": [
    {"name": "New", "columnType": "incoming", "stateMappings": {"User Story": "New", "Bug": "New"}},
    {"name": "In development", "columnType": "inProgress", "stateMappings": {"User Story": "Active", "Bug": "Active"}},
    {"name": "Test/Design review", "columnType": "inProgress", "stateMappings": {"User Story": "Active", "Bug": "Active"}},
    {"name": "Closed", "columnType": "outgoing", "stateMappings": {"User Story": "Closed", "Bug": "Closed"}},
]}
BOARD = {"fields": {"columnField": {"referenceName": "WEF_TEST_Kanban.Column"}}}
WRITES = ("create", "update", "add")


def opt(argv, name):
    i = argv.index(name)
    return argv[i + 1]


def opts_after(argv, name):
    """Values after `name` up to the next --flag."""
    i = argv.index(name) + 1
    out = []
    while i < len(argv) and not argv[i].startswith("-"):
        out.append(argv[i])
        i += 1
    return out


class FakeAz:
    def __init__(self, next_id=1000):
        self.calls = []
        self.items = {}  # id -> {"id", "fields", "relations"}
        self.next_id = next_id

    def writes(self):
        return [c for c in self.calls if c[2] in WRITES or (len(c) > 3 and c[3] in WRITES)]

    def __call__(self, argv):
        a = argv[1:]
        self.calls.append(a)
        out = self.handle(a)
        if isinstance(out, subprocess.CompletedProcess):
            return out
        return subprocess.CompletedProcess(argv, 0, json.dumps(out) if out is not None else "", "")

    def handle(self, a):
        if a[:2] == ["devops", "invoke"]:
            return COLUMNS if opt(a, "--resource") == "columns" else BOARD
        if a[:3] == ["boards", "work-item", "create"]:
            wid = self.next_id
            self.next_id += 1
            fields = {"System.Title": opt(a, "--title"), "System.WorkItemType": opt(a, "--type"),
                      "System.State": "New"}
            if "--project" in a:
                fields["System.TeamProject"] = opt(a, "--project")
            for f in opts_after(a, "--fields"):
                k, v = f.split("=", 1)
                fields[k] = v
            self.items[wid] = {"id": wid, "fields": fields, "relations": []}
            return self.items[wid]
        if a[:3] == ["boards", "work-item", "show"]:
            wid = int(opt(a, "--id"))
            if wid not in self.items:
                return subprocess.CompletedProcess(a, 1, "", "ERROR: work item does not exist")
            return self.items[wid]
        if a[:3] == ["boards", "work-item", "update"]:
            it = self.items[int(opt(a, "--id"))]
            if "--state" in a:
                it["fields"]["System.State"] = opt(a, "--state")
            if "--fields" in a:
                for f in opts_after(a, "--fields"):
                    k, v = f.split("=", 1)
                    it["fields"][k] = v
                    if k.endswith("Kanban.Column"):
                        it["fields"]["System.BoardColumn"] = v
            return it
        if a[:4] == ["boards", "work-item", "relation", "add"]:
            rel = {"parent": "System.LinkTypes.Hierarchy-Reverse", "predecessor": "System.LinkTypes.Dependency-Reverse",
                   "related": "System.LinkTypes.Related"}[opt(a, "--relation-type")]
            it = self.items[int(opt(a, "--id"))]
            it["relations"].append({"rel": rel, "url": f"https://dev.azure.com/x/_apis/wit/workItems/{opt(a, '--target-id')}"})
            return it
        if a[:2] == ["boards", "query"]:
            wiql = opt(a, "--wiql")
            hits = [{"id": i, "fields": {}} for i, it in self.items.items()
                    if "CONTAINS '" in wiql and wiql.split("CONTAINS '")[1].split("'")[0] in it["fields"].get("System.Tags", "")
                    and it["fields"]["System.State"] != "Removed"]
            return hits
        raise AssertionError(f"unexpected az call: {a}")
