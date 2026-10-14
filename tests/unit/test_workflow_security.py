import ast
import json
import sys
from pathlib import Path
import yaml

import pytest
from test_metadata_collector import github_cli, SHA


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
    assert '"-m", "venv"' in text
    assert '"-m", "pip", "install"' in text
    assert "requirements-helpers.txt" in text


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


@pytest.mark.parametrize("integration_target", [False, True])
def test_workflow_and_local_launcher_use_same_deployed_chain(
    repo_root, tmp_path, github_cli, integration_target
):
    run, responses, log, data, sources = github_cli
    prefix, raw = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n")
    metadata = json.loads(raw.split("\n-->", 1)[0])
    metadata["closes_issues"] = [7, 8]
    related_claim = "https://github.com/sample/repo/issues/9#issuecomment-1003"
    metadata["claim_urls"].append(related_claim)
    for number in (8, 9):
        responses[f"repos/sample/repo/issues/{number}"] = {"number": number, "state": "open"}
    claim_event = yaml.safe_load(responses["repos/sample/repo/issues/comments/1"]["body"])
    claim_event["event_id"] = "claim-9"
    related_comment = {"id": 1003, "html_url": related_claim,
                       "issue_url": "https://api.github.com/repos/sample/repo/issues/9",
                       "body": yaml.safe_dump(claim_event, sort_keys=False), "updated_at": "2026-10-14T00:00:00Z",
                       "user": {"id": 1001, "login": "developer"}}
    responses["repos/sample/repo/issues/8/comments?per_page=100&page=1"] = []
    responses["repos/sample/repo/issues/9/comments?per_page=100&page=1"] = [related_comment]
    responses["repos/sample/repo/issues/comments/1003"] = related_comment
    if integration_target:
        data["pull"]["base"]["ref"] = "agent/release-coordination/issue-5-integration"
        metadata["base_branch"] = data["pull"]["base"]["ref"]
    data["pull"]["body"] = (
        prefix + "Closes #8\n\n<!-- agent-collaboration:metadata\n"
        + json.dumps(metadata) + "\n-->"
    )
    data["pull"]["base"]["repo"] = {"id": 123}
    event = {"repository": {"id": 123, "full_name": "sample/repo"}, "pull_request": data["pull"]}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    workflow = (repo_root / "templates/project/.github/workflows/agent-collaboration-check.yml").read_text()
    script = workflow.split("python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    source = "\n".join(line[10:] for line in script.splitlines())
    script_path = tmp_path / "workflow.py"
    script_path.write_text(source)
    site = tmp_path / "explicit-dependencies"
    site.mkdir()
    dependency_log = tmp_path / "dependency-commands.jsonl"
    (site / "sitecustomize.py").write_text('''
import json, os, subprocess, sys
from pathlib import Path
original_run = subprocess.run
def run(command, *args, **kwargs):
    if len(command) > 3 and command[1:3] == ["-m", "venv"]:
        directory = Path(command[3]) / "bin"
        directory.mkdir(parents=True)
        (directory / "python").symlink_to(sys.executable)
    elif len(command) > 4 and command[1:4] == ["-m", "pip", "install"]:
        assert "--requirement" in command
        manifest = Path(command[command.index("--requirement") + 1])
        assert manifest.is_file() and "PyYAML" in manifest.read_text() and "jsonschema" in manifest.read_text()
    else:
        return original_run(command, *args, **kwargs)
    with Path(os.environ["DEPENDENCY_LOG"]).open("a") as stream:
        stream.write(json.dumps(command) + "\\n")
    return subprocess.CompletedProcess(command, 0)
subprocess.run = run
''')
    result = run(executable_path=script_path, extra_environment={
        "GITHUB_REPOSITORY": "sample/repo", "GITHUB_SHA": SHA, "GITHUB_EVENT_PATH": str(event_path),
        "PYTHONPATH": str(site), "DEPENDENCY_LOG": str(dependency_log),
    })
    assert result.returncode == (2 if integration_target else 0), result.stdout + result.stderr
    if not integration_target:
        assert json.loads(result.stdout)["result"] == "pass"
        endpoints = [json.loads(line)[-1] for line in log.read_text().splitlines()]
        assert all(f"repos/sample/repo/contents/{path}?ref={SHA}" in endpoints for path in sources)
        assert "repos/sample/repo/issues/7/comments?per_page=100&page=2" in endpoints
        assert {f"repos/sample/repo/issues/{number}" for number in (7, 8, 9)} <= set(endpoints)
        assert {"repos/sample/repo/issues/comments/1", "repos/sample/repo/issues/comments/1003"} <= set(endpoints)
        dependency_commands = [json.loads(line) for line in dependency_log.read_text().splitlines()]
        assert dependency_commands[0][1:3] == ["-m", "venv"]
        assert dependency_commands[1][1:4] == ["-m", "pip", "install"]
        local = run(launcher=True)
        assert json.loads(local.stdout)["result"] == "pass"
