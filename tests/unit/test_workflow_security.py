import ast
import base64
import json
import subprocess

import pytest
import yaml


def test_trusted_workflow_never_executes_pr_content(load_yaml, repo_root):
    workflow = load_yaml("templates/project/.github/workflows/agent-collaboration-check.yml")
    text = (repo_root / "templates/project/.github/workflows/agent-collaboration-check.yml").read_text()
    triggers = workflow.get("on", workflow.get(True))  # PyYAML 1.1 treats `on` as boolean.
    assert "pull_request_target" in triggers
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "read", "issues": "read"}
    assert "actions/checkout" not in text
    assert "secrets." not in text
    assert "${{ github.event.pull_request.body" not in text
    assert "ref: $GITHUB_SHA" not in text


def test_workflow_is_stable_and_only_runs_for_default_target(load_yaml):
    workflow = load_yaml("templates/project/.github/workflows/agent-collaboration-check.yml")
    job = workflow["jobs"]["agent-collaboration"]
    assert job["name"] == "agent-collaboration"
    assert job["if"] == "github.event.pull_request.base.ref == github.event.repository.default_branch"
    triggers = workflow.get("on", workflow.get(True))
    assert "paths" not in triggers["pull_request_target"]


def test_workflow_fetcher_is_valid_python_and_pins_default_branch(repo_root):
    text = (repo_root / "templates/project/.github/workflows/agent-collaboration-check.yml").read_text()
    script = text.split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    source = "\n".join(line[10:] for line in script.splitlines())
    ast.parse(source)
    assert 'ref.get("object", {}).get("sha") != sha' in source
    assert 'content(repo_name, ".github/agent-collaboration/check_pr_metadata.py", sha)' in source
    assert all(line.rstrip().endswith(", sha)") for line in source.splitlines() if "= content(repo_name," in line)
    assert 'pull.get("head", {}).get("sha") != event["pull_request"].get("head", {}).get("sha")' in source


@pytest.mark.parametrize("integration_target", [False, True])
def test_workflow_reads_configured_authorization_and_all_issues_at_pinned_sha(
    repo_root, fixture_path, tmp_path, monkeypatch, integration_target
):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    prefix, raw = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n")
    metadata = json.loads(raw.split("\n-->", 1)[0])
    metadata["closes_issues"] = [7, 8]
    metadata["claim_urls"].append("https://github.com/sample/repo/issues/9#issuecomment-3")
    if integration_target:
        data["pull"]["base"]["ref"] = "agent/release-coordination/issue-5-integration"
        metadata["base_branch"] = data["pull"]["base"]["ref"]
    data["pull"]["body"] = (
        prefix + "Closes #8\n\n<!-- agent-collaboration:metadata\n"
        + json.dumps(metadata) + "\n-->"
    )
    data["pull"]["base"]["repo"] = {"id": 123}
    custom_auth = ".github/agent-collaboration/grants.yml"
    data["config"]["managed_paths"]["authorization"] = custom_auth
    event = {"repository": {"id": 123, "full_name": "sample/repo"}, "pull_request": data["pull"]}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "sample/repo")
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    source_root = repo_root / "templates/project/.github/agent-collaboration"
    class IndentedListDumper(yaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    sources = {
        ".github/agent-collaboration/config.yml": yaml.dump(data["config"], Dumper=IndentedListDumper).encode(),
        custom_auth: yaml.dump(data["authorization"], Dumper=IndentedListDumper).encode(),
        ".github/agent-collaboration/check_pr_metadata.py": (source_root / "check_pr_metadata.py").read_bytes(),
    }
    endpoints, real_run = [], subprocess.run

    def fake_run(command, **kwargs):
        if command[0] != "gh":
            return real_run(command, **kwargs)
        assert command[:4] == ["gh", "api", "--method", "GET"]
        endpoint = command[4]
        endpoints.append(endpoint)
        assert endpoint.startswith("repos/sample/repo")
        suffix = endpoint.removeprefix("repos/sample/repo")
        if suffix == "":
            response = data["repository"]
        elif suffix == "/git/ref/heads/main":
            response = {"object": {"sha": "a" * 40}}
        elif suffix == "/pulls/12":
            response = data["pull"]
        elif suffix == "/pulls/12/files?per_page=100&page=1":
            response = data["files"]
        elif suffix == "/pulls/12/reviews?per_page=100&page=1":
            response = []
        elif suffix.startswith("/contents/"):
            path, ref = suffix.removeprefix("/contents/").split("?ref=")
            assert ref == "a" * 40
            response = {"type": "file", "encoding": "base64",
                        "content": base64.b64encode(sources[path]).decode()}
        elif suffix in {"/issues/7", "/issues/8", "/issues/9"}:
            response = {"number": int(suffix.rsplit("/", 1)[1]), "state": "open"}
        else:
            raise AssertionError(f"unexpected endpoint: {endpoint}")
        return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    workflow = (repo_root / "templates/project/.github/workflows/agent-collaboration-check.yml").read_text()
    script = workflow.split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    source = "\n".join(line[10:] for line in script.splitlines())
    with pytest.raises(SystemExit) as result:
        exec(compile(source, "<workflow>", "exec"), {"__name__": "__main__"})
    assert result.value.code == (1 if integration_target else 0)
    if not integration_target:
        assert f"repos/sample/repo/contents/{custom_auth}?ref={'a' * 40}" in endpoints
        assert {"repos/sample/repo/issues/7", "repos/sample/repo/issues/8", "repos/sample/repo/issues/9"} <= set(endpoints)
