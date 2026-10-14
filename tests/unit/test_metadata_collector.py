"""Public CLI tests with GitHub replaced only at the process/API boundary."""

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import shutil

import pytest
import yaml


DEPLOYED = ".github/agent-collaboration/"
SHA = "a" * 40
HEAD = "b" * 40
CLAIM = "https://github.com/sample/repo/issues/7#issuecomment-1"


@pytest.fixture
def github_cli(repo_root, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["pull"]["base"].update({"sha": SHA, "repo": {"id": 123, "full_name": "sample/repo"}})
    data["pull"].update({"state": "open", "draft": True, "updated_at": "2026-10-14T00:00:00Z", "changed_files": 101})
    metadata = json.loads(data["pull"]["body"].split("<!-- agent-collaboration:metadata\n")[1].split("\n-->")[0])
    metadata.update(schema_version=2, skill_version="0.2.0", delivery={"development_base_sha": SHA,
                    "net_diff_base_sha": SHA, "predecessors": [], "merge_order": [12]})
    data["pull"]["body"] = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n")[0] + "<!-- agent-collaboration:metadata\n" + json.dumps(metadata) + "\n-->"
    data["files"] = [{"filename": f"src/file-{n}.py", "status": "modified"} for n in range(101)]
    reviews = [{"id": n, "state": "COMMENTED", "commit_id": HEAD,
                "user": {"id": 2000 + n, "login": f"reviewer-{n}"}} for n in range(101)]
    comments = [{"id": n, "html_url": f"https://github.com/sample/repo/issues/7#issuecomment-{n}",
                 "issue_url": "https://api.github.com/repos/sample/repo/issues/7",
                 "body": f"comment {n}",
                 "updated_at": "2026-10-14T00:00:00Z",
                 "user": {"id": 1001, "login": "developer"}} for n in range(1, 102)]
    event = {"event": "claim", "event_id": "claim-1", "previous_event_id": None,
             "controlled_by": "developer", "controlled_by_id": 1001, "actor_id": "backend-api",
             "session_id": "run-1", "runtime": "codex", "scope": ["src/**"],
             "branch": data["pull"]["head"]["ref"], "base_head": SHA, "expected_handoff": "pull-request"}
    comments[0]["body"] = yaml.safe_dump(event, sort_keys=False)
    event.update(event_id="other-claim", scope=["docs/**"])
    comments[1]["body"] = yaml.safe_dump(event, sort_keys=False)
    event.update(event="release", event_id="release-101", previous_event_id="other-claim", release_mode="self",
                 github_comment_id=2, github_comment_url=comments[1]["html_url"])
    event.pop("expected_handoff")
    comments[-1]["body"] = yaml.safe_dump(event, sort_keys=False)
    auth_path = DEPLOYED + "grants.yml"
    data["config"]["managed_paths"]["authorization"] = auth_path
    package = tmp_path / "standalone-setup"
    synchronized = subprocess.run([sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
                                   "--destination", str(package), "--profile", "github-collaboration-setup"],
                                  text=True, capture_output=True, check=False)
    assert synchronized.returncode == 0, synchronized.stdout + synchronized.stderr
    consumer = tmp_path / "consumer"
    shutil.copytree(package / "assets/templates/project", consumer)
    source_root = consumer / DEPLOYED
    data["config"] = yaml.safe_load((source_root / "config.yml").read_text())
    data["config"]["managed_paths"]["authorization"] = auth_path
    class IndentedListDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    sources = {
        DEPLOYED + "config.yml": yaml.dump(data["config"], Dumper=IndentedListDumper).encode(),
        auth_path: yaml.dump(data["authorization"], Dumper=IndentedListDumper).encode(),
        DEPLOYED + "check_pr_metadata.py": (source_root / "check_pr_metadata.py").read_bytes(),
    }
    for name in ("collect_pr_metadata.py", "run_pr_metadata_check.py", "collaboration_event.py", "collaboration_scope.py",
                 "collaboration-event.schema.json", "requirements-helpers.txt"):
        path = source_root / name
        if path.exists():
            sources[DEPLOYED + name] = path.read_bytes()
    responses = {
        "repos/sample/repo": data["repository"],
        "repos/sample/repo/git/ref/heads/main": {"object": {"sha": SHA}},
        "repos/sample/repo/pulls/12": data["pull"],
        "repos/sample/repo/issues/7": data["issues"][0],
        "repos/sample/repo/issues/comments/1": comments[0],
        f"repos/sample/repo/compare/{SHA}...{HEAD}?per_page=100&page=1": {
            "status": "ahead", "base_commit": {"sha": SHA}, "merge_base_commit": {"sha": SHA}, "total_commits": 1,
            "commits": [{"sha": HEAD}], "files": data["files"]},
    }
    for endpoint, values in (("pulls/12/files", data["files"]),
                             ("pulls/12/reviews", reviews), ("issues/7/comments", comments)):
        for page in range(1, 3):
            responses[f"repos/sample/repo/{endpoint}?per_page=100&page={page}"] = values[(page-1)*100:page*100]
    for path, content in sources.items():
        digest = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
        responses[f"repos/sample/repo/contents/{path}?ref={SHA}"] = {
            "type": "file", "path": path, "encoding": "base64", "sha": digest,
            "size": len(content), "content": base64.b64encode(content).decode(),
        }
    responses[f"repos/sample/repo/git/trees/{SHA}?recursive=1"] = {
        "truncated": False, "tree": [{"path": path, "type": "blob", "mode": "100644",
            "sha": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()}
            for path, content in sources.items()],
    }
    fixture = tmp_path / "github.json"
    log = tmp_path / "requests.jsonl"
    counts = tmp_path / "counts.json"
    executable = tmp_path / "gh"
    executable.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:5] != ["api", "--method", "GET", "--hostname", "github.com"] or len(args) != 6:
    raise SystemExit("only explicit GitHub GET is allowed")
endpoint = args[-1]
log = Path(os.environ["FAKE_GH_LOG"])
with log.open("a") as stream:
    stream.write(json.dumps(args) + "\\n")
responses = json.loads(Path(os.environ["FAKE_GH_RESPONSES"]).read_text())
counter_path = Path(os.environ["FAKE_GH_COUNTS"])
counts = json.loads(counter_path.read_text()) if counter_path.exists() else {}
count = counts.get(endpoint, 0)
counts[endpoint] = count + 1
counter_path.write_text(json.dumps(counts))
response = responses.get(endpoint, {"error": "HTTP 404"})
if isinstance(response, dict) and "responses" in response:
    sequence = response["responses"]
    response = sequence[min(count, len(sequence) - 1)]
if isinstance(response, dict) and "error" in response:
    print(response["error"], file=sys.stderr)
    raise SystemExit(1)
print(json.dumps(response))
''')
    executable.chmod(0o700)
    environment = {**{key: value for key, value in os.environ.items() if key != "PYTHONPATH"}, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
                   "FAKE_GH_RESPONSES": str(fixture), "FAKE_GH_LOG": str(log),
                   "FAKE_GH_COUNTS": str(counts), "PYTHONDONTWRITEBYTECODE": "1"}

    def run(*arguments, launcher=False, executable_path=None, extra_environment=None):
        fixture.write_text(json.dumps(responses))
        name = "run_pr_metadata_check.py" if launcher else "collect_pr_metadata.py"
        command = [sys.executable, str(executable_path or source_root / name),
                   "--repository", "sample/repo", "--pull-number", "12", *arguments]
        return subprocess.run(command, text=True, capture_output=True,
                              env={**environment, **(extra_environment or {})}, cwd=consumer, check=False)

    return run, responses, log, data, sources


def test_collector_cli_preserves_paginated_facts_and_comment_text(github_cli):
    run, responses, log, _, _ = github_cli
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert (len(payload["files"]), len(payload["reviews"]), len(payload["issue_comments"]["7"])) == (101, 101, 101)
    assert payload["claim_comments"][CLAIM] == {
        "id": 1, "url": CLAIM, "user_id": 1001, "login": "developer", "issue_number": 7,
        "body": responses["repos/sample/repo/issues/comments/1"]["body"], "updated_at": "2026-10-14T00:00:00Z",
    }
    assert yaml.safe_load(payload["issue_comments"]["7"][-1]["body"])["event"] == "release"
    assert payload["snapshot"]["version"] == 2
    assert payload["snapshot"]["check_contract"] == 2
    assert payload["net_diff"]["commits"] == [HEAD]
    assert payload["development_compare"]["base_sha"] == SHA
    assert payload["predecessor_pulls"] == [] and payload["predecessor_files"] == {} and payload["predecessor_compares"] == []
    assert payload["snapshot"]["trusted_resources"][DEPLOYED + "grants.yml"]["sha256"]
    assert payload["trusted_sha"] == SHA and payload["trusted_ref_verified"] is True
    requests = [json.loads(line) for line in log.read_text().splitlines()]
    assert all(request[:5] == ["api", "--method", "GET", "--hostname", "github.com"] for request in requests)
    assert all(f"?ref={SHA}" in request[-1] for request in requests if "/contents/" in request[-1])
    assert len(payload["snapshot"]["trusted_resources"]) == 9


@pytest.mark.parametrize("failure", ["files_cap", "commit_truncation", "wrong_base", "changed_comparison", "changed_files"])
def test_compare_and_fixed_file_collection_fail_closed(github_cli, failure):
    run, responses, _, _, _ = github_cli
    endpoint = f"repos/sample/repo/compare/{SHA}...{HEAD}?per_page=100&page=1"
    value = responses[endpoint]
    if failure == "files_cap":
        value["files"] = [{"filename": f"src/{n}.py", "status": "added"} for n in range(300)]
    elif failure == "commit_truncation":
        value["total_commits"] = 101
    elif failure == "wrong_base":
        value["base_commit"]["sha"] = "c" * 40
    else:
        if failure == "changed_files":
            endpoint = "repos/sample/repo/pulls/12/files?per_page=100&page=2"
            value = responses[endpoint]
            changed = copy.deepcopy(value)
            changed[0]["filename"] = "src/changed.py"
        else:
            changed = copy.deepcopy(value)
            changed["files"][0]["filename"] = "src/changed.py"
        responses[endpoint] = {"responses": [copy.deepcopy(value), changed]}
    result = run()
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["result"] == "unknown"


def test_compare_commits_are_paginated_and_bound_to_fixed_head(github_cli):
    run, responses, log, _, _ = github_cli
    endpoint = f"repos/sample/repo/compare/{SHA}...{HEAD}?per_page=100&page="
    first = responses[endpoint + "1"]
    first["total_commits"] = 101
    first["commits"] = [{"sha": f"{n:040x}"} for n in range(1, 101)]
    responses[endpoint + "2"] = {**copy.deepcopy(first), "commits": [{"sha": HEAD}]}
    responses[endpoint + "2"].pop("files")
    result = run()
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload["net_diff"]["commits"]) == 101
    assert payload["net_diff"]["commits"][-1] == HEAD
    assert sum(json.loads(line)[-1] == endpoint + "2" for line in log.read_text().splitlines()) >= 2


@pytest.mark.parametrize("name", ["collaboration_event.py", "collaboration_scope.py", "collaboration-event.schema.json", "requirements-helpers.txt"])
def test_missing_trusted_helper_schema_or_requirements_returns_unknown(github_cli, name):
    run, responses, _, _, _ = github_cli
    del responses[f"repos/sample/repo/contents/{DEPLOYED}{name}?ref={SHA}"]
    result = run(launcher=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def stacked_responses(responses, data):
    prior = "c" * 40
    before, raw = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n")
    metadata = json.loads(raw.split("\n-->")[0])
    metadata["delivery"].update(development_base_sha=prior, net_diff_base_sha=prior,
                                predecessors=[{"pull_number": 11, "head_sha": prior}], merge_order=[11, 12])
    data["pull"]["body"] = before + "<!-- agent-collaboration:metadata\n" + json.dumps(metadata) + "\n-->"
    event = yaml.safe_load(responses["repos/sample/repo/issues/comments/1"]["body"])
    event["base_head"] = prior
    responses["repos/sample/repo/issues/comments/1"]["body"] = yaml.safe_dump(event, sort_keys=False)
    predecessor_files = [{"filename": f"docs/prior-{n}.md", "status": "added"} for n in range(101)]
    responses["repos/sample/repo/pulls/11"] = {"number": 11, "head": {"sha": prior},
        "base": {"ref": "main", "sha": SHA, "repo": {"id": 123}}, "state": "open", "merged": False,
        "changed_files": len(predecessor_files), "merged_at": None, "merge_commit_sha": None}
    for page in (1, 2):
        responses[f"repos/sample/repo/pulls/11/files?per_page=100&page={page}"] = predecessor_files[(page-1)*100:page*100]
    files = data["files"] + predecessor_files
    data["pull"]["changed_files"] = len(files)
    for page in (1, 2, 3):
        responses[f"repos/sample/repo/pulls/12/files?per_page=100&page={page}"] = files[(page-1)*100:page*100]
    responses[f"repos/sample/repo/compare/{prior}...{HEAD}?per_page=100&page=1"] = {
        "status": "ahead", "base_commit": {"sha": prior}, "merge_base_commit": {"sha": prior},
        "total_commits": 1, "commits": [{"sha": HEAD}], "files": data["files"]}
    return prior


def test_collector_and_launcher_bind_complete_predecessor_files_to_fixed_head(github_cli):
    run, responses, log, data, _ = github_cli
    prior = stacked_responses(responses, data)
    collected = run()
    assert collected.returncode == 0, collected.stdout[:3000]
    payload = json.loads(collected.stdout)
    assert payload["predecessor_pulls"][0]["head"]["sha"] == prior
    assert len(payload["predecessor_files"]["11"]) == 101
    assert payload["net_diff"]["base_sha"] == prior
    endpoints = [json.loads(line)[-1] for line in log.read_text().splitlines()]
    assert endpoints.count("repos/sample/repo/pulls/11/files?per_page=100&page=2") == 2
    result = run(launcher=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("change", ["head", "merge_state", "files", "comparison"])
def test_predecessor_or_net_facts_drift_discards_the_entire_snapshot(github_cli, change):
    run, responses, _, data, _ = github_cli
    prior = stacked_responses(responses, data)
    endpoint = ("repos/sample/repo/pulls/11/files?per_page=100&page=2" if change == "files" else
                f"repos/sample/repo/compare/{prior}...{HEAD}?per_page=100&page=1" if change == "comparison" else
                "repos/sample/repo/pulls/11")
    before = copy.deepcopy(responses[endpoint])
    after = copy.deepcopy(before)
    if change == "head":
        after["head"]["sha"] = "d" * 40
    elif change == "merge_state":
        after.update(state="closed", merged=True, merged_at="2026-10-14T00:20:00Z")
    elif change == "files":
        after[0]["filename"] = "docs/changed.md"
    else:
        after["files"][0]["filename"] = "src/changed.py"
    responses[endpoint] = {"responses": [before, after]}
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["snapshot"] is None


@pytest.mark.parametrize("dependency", ["yaml", "jsonschema"])
def test_missing_runtime_dependency_is_unknown_and_local_launcher_never_installs(github_cli, tmp_path, dependency):
    run, _, log, _, _ = github_cli
    site = tmp_path / "missing-dependency"
    site.mkdir()
    marker = tmp_path / "forbidden-install"
    (site / "sitecustomize.py").write_text(f'''import builtins, subprocess
from pathlib import Path
original_import = builtins.__import__
def unavailable(name, *args, **kwargs):
    if name == {dependency!r} or name.startswith({dependency!r} + "."):
        raise ImportError("dependency unavailable")
    return original_import(name, *args, **kwargs)
builtins.__import__ = unavailable
original_run = subprocess.run
def no_install(command, *args, **kwargs):
    if "pip" in command or Path(command[0]).name in {{"pip", "pip3", "uv"}}:
        Path({str(marker)!r}).write_text("unexpected dependency installation")
        raise AssertionError("local installation is forbidden")
    return original_run(command, *args, **kwargs)
subprocess.run = no_install
''')
    result = run(launcher=True, extra_environment={"PYTHONPATH": str(site)})
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert not marker.exists()
    assert all("pip" not in json.loads(line) for line in log.read_text().splitlines())


def test_collector_rejects_default_sha_changed_during_collection(github_cli):
    run, responses, _, _, _ = github_cli
    responses["repos/sample/repo/git/ref/heads/main"] = {"responses": [
        {"object": {"sha": SHA}}, {"object": {"sha": SHA}}, {"object": {"sha": "c" * 40}},
    ]}
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert json.loads(result.stdout)["snapshot"] is None


def test_collector_rejects_an_already_stale_default_target_base(github_cli):
    run, _, _, data, _ = github_cli
    data["pull"]["base"]["sha"] = "c" * 40
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["snapshot"] is None


@pytest.mark.parametrize("change", ["head", "base", "body", "repository_id", "default_branch"])
def test_collector_rejects_target_facts_changed_during_collection(github_cli, change):
    run, responses, _, data, _ = github_cli
    endpoint = "repos/sample/repo/pulls/12" if change in {"head", "base", "body"} else "repos/sample/repo"
    before = copy.deepcopy(responses[endpoint])
    after = copy.deepcopy(before)
    if change == "head":
        after["head"]["sha"] = "c" * 40
    elif change == "base":
        after["base"]["sha"] = "c" * 40
    elif change == "body":
        after["body"] += "\nCloses #8\n"
    elif change == "repository_id":
        after["id"] = 999
    else:
        after["default_branch"] = "new-default"
    responses[endpoint] = {"responses": [before, after]}
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert "refresh" in json.loads(result.stdout)["errors"][0]


@pytest.mark.parametrize("change", ["review", "later_event", "comment_edit", "claim_deleted", "issue_state"])
def test_collector_rejects_issue_and_review_changes_before_emitting_snapshot(github_cli, change):
    run, responses, _, _, _ = github_cli
    endpoint = {
        "review": "repos/sample/repo/pulls/12/reviews?per_page=100&page=2",
        "later_event": "repos/sample/repo/issues/7/comments?per_page=100&page=2",
        "comment_edit": "repos/sample/repo/issues/7/comments?per_page=100&page=1",
        "claim_deleted": "repos/sample/repo/issues/comments/1",
        "issue_state": "repos/sample/repo/issues/7",
    }[change]
    before = copy.deepcopy(responses[endpoint])
    after = copy.deepcopy(before)
    if change == "review":
        after[0]["state"] = "APPROVED"
    elif change == "later_event":
        extra = copy.deepcopy(after[0])
        extra.update({"id": 102, "html_url": "https://github.com/sample/repo/issues/7#issuecomment-102",
                      "body": "event: reassign"})
        after.append(extra)
    elif change == "comment_edit":
        after[0]["body"] = "event: release"
    elif change == "claim_deleted":
        after = {"error": "HTTP 404"}
    else:
        after["state"] = "closed"
    responses[endpoint] = {"responses": [before, after]}
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert "refresh" in json.loads(result.stdout)["errors"][0]


def replace_trusted_source(responses, path, content):
    responses[f"repos/sample/repo/contents/{path}?ref={SHA}"] = {
        "type": "file", "path": path, "encoding": "base64", "size": len(content),
        "sha": hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest(),
        "content": base64.b64encode(content).decode(),
    }
    for item in responses[f"repos/sample/repo/git/trees/{SHA}?recursive=1"]["tree"]:
        if item["path"] == path:
            item["sha"] = responses[f"repos/sample/repo/contents/{path}?ref={SHA}"]["sha"]


def test_invalid_deployed_program_returns_machine_readable_unknown(github_cli):
    run, responses, _, _, _ = github_cli
    replace_trusted_source(responses, DEPLOYED + "collect_pr_metadata.py", b"def invalid(\n")
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert "Traceback" not in result.stderr


def test_launcher_does_not_turn_checker_crash_into_a_completed_fail(github_cli):
    run, responses, _, _, sources = github_cli
    source = sources[DEPLOYED + "check_pr_metadata.py"].replace(
        b"raise SystemExit(main())", b"raise SystemExit(42)")
    replace_trusted_source(responses, DEPLOYED + "check_pr_metadata.py", source)
    result = run(launcher=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


@pytest.mark.parametrize("kind", ["files", "reviews"])
def test_repeated_page_records_are_not_accepted_as_complete_collection(github_cli, kind):
    run, responses, _, _, _ = github_cli
    endpoint = f"repos/sample/repo/pulls/12/{kind}?per_page=100&page=2"
    responses[endpoint] = [copy.deepcopy(responses[f"repos/sample/repo/pulls/12/{kind}?per_page=100&page=1"][0])]
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def test_contents_api_symlink_dereference_cannot_supply_trusted_program(github_cli):
    run, responses, _, _, _ = github_cli
    for item in responses[f"repos/sample/repo/git/trees/{SHA}?recursive=1"]["tree"]:
        if item["path"] == DEPLOYED + "collect_pr_metadata.py":
            item["mode"] = "120000"
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


@pytest.mark.parametrize("fault", ["missing", "bytes", "tree_sha", "truncated_tree", "ambiguous_tree", "gitlink", "version", "rate_limit"])
def test_incomplete_or_incompatible_deployment_never_produces_a_snapshot(github_cli, fault):
    run, responses, _, _, sources = github_cli
    endpoint = f"repos/sample/repo/contents/{DEPLOYED}collect_pr_metadata.py?ref={SHA}"
    tree = responses[f"repos/sample/repo/git/trees/{SHA}?recursive=1"]
    if fault == "missing":
        del responses[endpoint]
    elif fault == "bytes":
        responses[endpoint]["content"] = base64.b64encode(b"unexpected bytes").decode()
    elif fault == "tree_sha":
        tree["tree"][1]["sha"] = "d" * 40
    elif fault == "truncated_tree":
        tree["truncated"] = True
    elif fault == "ambiguous_tree":
        tree["tree"].append(copy.deepcopy(tree["tree"][1]))
    elif fault == "gitlink":
        tree["tree"][1].update({"type": "commit", "mode": "160000"})
    elif fault == "version":
        replace_trusted_source(responses, DEPLOYED + "check_pr_metadata.py",
                              sources[DEPLOYED + "check_pr_metadata.py"].replace(b"COLLECTOR_INPUT_VERSION = 2", b"COLLECTOR_INPUT_VERSION = 1"))
    else:
        responses["repos/sample/repo/pulls/12"] = {"error": "HTTP 403 rate limited token-secret-value"}
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert json.loads(result.stdout)["snapshot"] is None
    assert "token-secret-value" not in result.stdout + result.stderr


@pytest.mark.parametrize("kind", ["files_cap", "files_count", "reviews_limit", "comments_limit"])
def test_pagination_limits_and_possible_truncation_return_unknown(github_cli, kind):
    run, responses, _, data, _ = github_cli
    if kind == "files_count":
        responses["repos/sample/repo/pulls/12/files?per_page=100&page=2"] = []
    elif kind == "files_cap":
        data["pull"]["changed_files"] = 3000
        for page in range(1, 31):
            responses[f"repos/sample/repo/pulls/12/files?per_page=100&page={page}"] = [
                {"filename": f"src/large-{page}-{n}.py"} for n in range(100)]
        responses["repos/sample/repo/pulls/12/files?per_page=100&page=31"] = []
    else:
        endpoint = "pulls/12/reviews" if kind == "reviews_limit" else "issues/7/comments"
        batch = responses[f"repos/sample/repo/{endpoint}?per_page=100&page=1"]
        for page in range(1, 32):
            responses[f"repos/sample/repo/{endpoint}?per_page=100&page={page}"] = batch
    result = run()
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def test_local_copies_cannot_replace_the_deployed_checker(github_cli, tmp_path):
    run, _, _, _, sources = github_cli
    launcher = tmp_path / "run_pr_metadata_check.py"
    launcher.write_bytes(sources[DEPLOYED + "run_pr_metadata_check.py"])
    marker = tmp_path / "untrusted-program-executed"
    for name in ("collect_pr_metadata.py", "check_pr_metadata.py"):
        (tmp_path / name).write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\nraise SystemExit(0)\n")
    result = run(launcher=True, executable_path=launcher)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["result"] == "pass"
    assert not marker.exists()


def test_local_launcher_mismatch_requires_update(github_cli, tmp_path):
    run, _, _, _, sources = github_cli
    launcher = tmp_path / "run_pr_metadata_check.py"
    launcher.write_bytes(sources[DEPLOYED + "run_pr_metadata_check.py"] + b"\n# local edit\n")
    result = run(launcher=True, executable_path=launcher)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


@pytest.mark.parametrize("expected", ["--expected-head", "--expected-trusted-sha"])
def test_caller_sha_cannot_substitute_for_live_verification(github_cli, expected):
    run, _, _, _, _ = github_cli
    result = run(expected, "c" * 40)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def test_actual_claim_author_is_preserved_and_checker_rejects_mismatch(github_cli):
    run, responses, _, _, _ = github_cli
    responses["repos/sample/repo/issues/comments/1"]["user"]["id"] = 999
    collected = run()
    assert json.loads(collected.stdout)["claim_comments"][CLAIM]["user_id"] == 999
    result = run(launcher=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["result"] == "fail"
    assert "human_approval" in json.loads(result.stdout)["unverified"]


def test_invalid_cli_arguments_have_a_machine_readable_error(github_cli):
    run, _, _, _, _ = github_cli
    result = run("--pull-number", "not-a-number", launcher=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def test_direct_collector_reports_a_missing_local_launcher(github_cli, tmp_path):
    run, _, _, _, sources = github_cli
    directory = tmp_path / "incomplete-install"
    directory.mkdir()
    collector = directory / "collect_pr_metadata.py"
    collector.write_bytes(sources[DEPLOYED + "collect_pr_metadata.py"])
    result = run(executable_path=collector)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"


def test_requested_artifacts_match_the_public_launcher_report(github_cli, tmp_path):
    run, _, _, _, _ = github_cli
    destination = tmp_path / "metadata-output"
    result = run("--output-dir", str(destination), launcher=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert json.loads((destination / "check-report.json").read_text()) == report
    payload = json.loads((destination / "metadata.json").read_text())
    assert payload["snapshot"] == report["snapshot"]
    assert yaml.safe_load(payload["claim_comments"][CLAIM]["body"])["event"] == "claim"


@pytest.mark.parametrize("case", ["metadata", "report", "other_file", "directory_symlink", "parent_symlink"])
def test_output_location_conflicts_return_unknown_and_preserve_original_bytes(github_cli, tmp_path, case):
    run, _, _, _, _ = github_cli
    original = tmp_path / "original-output"
    original.mkdir()
    destination = original
    if case in {"metadata", "report", "other_file"}:
        name = {"metadata": "metadata.json", "report": "check-report.json", "other_file": "user.txt"}[case]
        (original / name).write_bytes(b"original user bytes\r\n")
    else:
        link = tmp_path / "linked-output"
        link.symlink_to(original, target_is_directory=True)
        destination = link if case == "directory_symlink" else link / "nested-output"
    before = {path.name: path.read_bytes() for path in original.iterdir()}
    result = run("--output-dir", str(destination), launcher=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert {path.name: path.read_bytes() for path in original.iterdir()} == before


def test_existing_empty_regular_directory_can_receive_artifacts(github_cli, tmp_path):
    run, _, _, _, _ = github_cli
    destination = tmp_path / "empty-output"
    destination.mkdir()
    result = run("--output-dir", str(destination), launcher=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((destination / "check-report.json").read_text())["result"] == "pass"


@pytest.mark.parametrize("limitation", ["flag", "dir_fd", "not_implemented"])
def test_unsupported_output_safety_capabilities_return_unknown(github_cli, tmp_path, limitation):
    run, _, _, _, _ = github_cli
    site = tmp_path / "limited-os"
    site.mkdir()
    source = {
        "flag": "import os\ndel os.O_NOFOLLOW\n",
        "dir_fd": "import os\nos.supports_dir_fd.discard(os.open)\n",
        "not_implemented": "import os\noriginal = os.open\ndef unsupported(*args, **kwargs):\n    raise NotImplementedError('directory descriptors unsupported')\nos.open = unsupported\nos.supports_dir_fd.add(unsupported)\n",
    }[limitation]
    (site / "sitecustomize.py").write_text(source)
    destination = tmp_path / "unsupported-output"
    result = run("--output-dir", str(destination), launcher=True, extra_environment={"PYTHONPATH": str(site)})
    assert result.returncode == 2
    assert json.loads(result.stdout)["result"] == "unknown"
    assert not destination.exists()


def test_temporary_check_does_not_require_persistent_output_capabilities(github_cli, tmp_path):
    run, _, _, _, _ = github_cli
    site = tmp_path / "temporary-only-os"
    site.mkdir()
    (site / "sitecustomize.py").write_text("import os\ndel os.O_NOFOLLOW\n")
    result = run(launcher=True, extra_environment={"PYTHONPATH": str(site)})
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["result"] == "pass"
