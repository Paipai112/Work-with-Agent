"""Process-level contracts for event and scope helpers; external API only is faked."""

import json
import hashlib
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


def run_helper(repo_root, name, *arguments, env=None):
    return subprocess.run(
        [sys.executable, str(repo_root / "shared/scripts" / name), *map(str, arguments)],
        text=True, capture_output=True, check=False, env=env,
    )


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_scope_reports_both_rename_paths_and_every_delivery_change(repo_root, tmp_path):
    input_path = write_json(tmp_path / "scope.json", {
        "scope": ["src/**", "tests/*.py"],
        "changes": [
            {"status": "added", "path": "src/new.py"},
            {"status": "deleted", "path": "docs/old.md"},
            {"status": "renamed", "previous_path": "legacy/api.py", "path": "src/api.py"},
            {"status": "untracked", "path": "tests/nested/new.py"},
            {"status": "modified", "path": "src/core.py"},
        ],
        "other_claims": [{"claim_url": "https://github.com/acme/repo/issues/4#issuecomment-41", "scope": ["src/api.py"]}],
    })
    result = run_helper(repo_root, "collaboration_scope.py", "--input", input_path)
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["status"] == "fail"
    assert report["out_of_scope"] == ["docs/old.md", "legacy/api.py", "tests/nested/new.py"]
    assert report["conflicts"] == [{
        "path": "src/api.py", "claim_url": "https://github.com/acme/repo/issues/4#issuecomment-41",
    }]
    assert report["paths"] == ["docs/old.md", "legacy/api.py", "src/api.py", "src/core.py", "src/new.py", "tests/nested/new.py"]
    assert report["authorization_verified"] is False


def test_scope_collects_commits_index_worktree_and_untracked_from_local_git(repo_root, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(project), *args], text=True, capture_output=True, check=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "Scope Test")
    git("config", "user.email", "scope@example.invalid")
    (project / "old.txt").write_text("same contents\n")
    (project / "deleted.txt").write_text("deleted\n")
    (project / "modified.txt").write_text("before\n")
    git("add", "--", "old.txt", "deleted.txt", "modified.txt")
    git("commit", "-qm", "fixture")
    base = git("rev-parse", "HEAD")
    git("mv", "--", "old.txt", "new.txt")
    git("commit", "-qm", "rename")
    (project / "deleted.txt").unlink()
    (project / "modified.txt").write_text("after\n")
    (project / "added.txt").write_text("staged\n")
    git("add", "--", "added.txt")
    (project / "untracked.txt").write_text("pending\n")
    before = git("status", "--porcelain=v1")
    scope = write_json(tmp_path / "patterns.json", ["*.txt"])
    result = run_helper(repo_root, "collaboration_scope.py", "--repo", project, "--base", base, "--scope", scope)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["paths"] == ["added.txt", "deleted.txt", "modified.txt", "new.txt", "old.txt", "untracked.txt"]
    assert report["status"] == "pass"
    assert git("status", "--porcelain=v1") == before


def test_scope_keeps_staged_change_when_unstaged_change_cancels_its_net_diff(repo_root, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(project), *args], text=True, capture_output=True, check=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "Scope Test")
    git("config", "user.email", "scope@example.invalid")
    original = project / "outside.txt"
    original.write_text("version A\n")
    git("add", "--", "outside.txt")
    git("commit", "-qm", "fixture")
    base = git("rev-parse", "HEAD")
    original.write_text("version B\n")
    git("add", "--", "outside.txt")
    original.write_text("version A\n")
    assert git("diff", "HEAD", "--name-only") == ""
    before = git("status", "--porcelain=v1")
    patterns = write_json(tmp_path / "scope.json", ["src/**"])
    result = run_helper(repo_root, "collaboration_scope.py", "--repo", project, "--base", base, "--scope", patterns)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["out_of_scope"] == ["outside.txt"]
    assert git("status", "--porcelain=v1") == before
    assert git("show", ":outside.txt") == "version B"
    assert original.read_text() == "version A\n"


def test_scope_fixed_base_ignores_local_git_replace_objects(repo_root, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(project), *args], text=True,
                              capture_output=True, check=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "Scope Test")
    git("config", "user.email", "scope@example.invalid")
    changed = project / "outside.txt"
    changed.write_text("original\n")
    git("add", "--", "outside.txt")
    git("commit", "-qm", "fixture: original")
    base = git("rev-parse", "HEAD")
    changed.write_text("outside claim\n")
    git("add", "--", "outside.txt")
    git("commit", "-qm", "fixture: outside change")
    git("replace", base, git("rev-parse", "HEAD"))
    assert git("diff", base, "HEAD", "--name-only") == ""
    before = git("status", "--porcelain=v1")
    scope = write_json(tmp_path / "scope.json", ["src/**"])
    result = run_helper(repo_root, "collaboration_scope.py", "--repo", project,
                        "--base", base, "--scope", scope)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["out_of_scope"] == ["outside.txt"]
    assert git("status", "--porcelain=v1") == before


def test_scope_does_not_fetch_missing_git_objects(repo_root, tmp_path, monkeypatch):
    commands = tmp_path / "bin"
    commands.mkdir()
    sentinel = tmp_path / "download-attempt"
    fake = commands / "git"
    fake.write_text(
        f"#!{sys.executable}\nimport pathlib, sys\n"
        f"if '--no-lazy-fetch' not in sys.argv: pathlib.Path({str(sentinel)!r}).write_text('fetch')\n"
        "sys.exit(1)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ.get("PATH", ""))
    scope = write_json(tmp_path / "scope.json", ["src/**"])
    result = run_helper(repo_root, "collaboration_scope.py", "--repo", tmp_path,
                        "--base", "a" * 40, "--scope", scope)
    assert result.returncode == 2
    assert not sentinel.exists(), "read-only scope inspection attempted a download"


@pytest.mark.parametrize("template", ["claim", "research-claim", "handoff", "reassign", "release", "resume"])
def test_constructs_and_validates_real_event_templates(repo_root, tmp_path, template):
    source = repo_root / "skills/github-collaboration/templates/events" / f"{template}.yml"
    event = yaml.safe_load(source.read_text())
    fields = write_json(tmp_path / "fields.json", {"event_id": f"validated-{template}"})
    result = run_helper(repo_root, "collaboration_event.py", "construct", "--template", template, "--fields", fields)
    assert result.returncode == 0, result.stdout + result.stderr
    candidate = json.loads(result.stdout)
    assert candidate["status"] == "pass"
    assert candidate["event"]["event_id"] == f"validated-{template}"
    assert candidate["event"]["event"] == event["event"]
    assert candidate["authorization_verified"] is False
    body = tmp_path / "comment.md"
    body.write_text("说明文字\n```yaml\n" + candidate["body"] + "```\n后续说明\n")
    validation = run_helper(repo_root, "collaboration_event.py", "validate", "--body", body)
    assert validation.returncode == 0, validation.stdout + validation.stderr
    assert json.loads(validation.stdout)["event"] == candidate["event"]


@pytest.mark.parametrize("mutation", ["duplicate", "alias", "tag", "multi-document", "mixed-markdown", "two-fences", "outside-candidate", "unterminated", "ambiguous-scalar"])
def test_event_validation_rejects_unsafe_yaml_or_ambiguous_comment(repo_root, tmp_path, mutation):
    source = (repo_root / "skills/github-collaboration/templates/events/claim.yml").read_text()
    bodies = {
        "duplicate": source + "event: claim\n",
        "alias": source + "extra: &value {nested: 1}\ncopy: *value\n",
        "tag": source.replace("event: claim", "event: !!str claim"),
        "multi-document": source + "---\n" + source,
        "mixed-markdown": source + "这是无法解析的后续 Markdown 说明。\n",
        "two-fences": "```yaml\n" + source + "```\n```yaml\n" + source + "```\n",
        "outside-candidate": "event: claim\n```yaml\n" + source + "```\n",
        "unterminated": "```yaml\n" + source + "```\n```yaml\nevent: claim\n",
        "ambiguous-scalar": source + "extra: yes\n",
    }
    body = tmp_path / "comment.md"
    body.write_text(bodies[mutation])
    result = run_helper(repo_root, "collaboration_event.py", "validate", "--body", body)
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "fail"


def publication_plan(repo_root):
    event = yaml.safe_load((repo_root / "skills/github-collaboration/templates/events/claim.yml").read_text())
    event.update(event_id="claim-real-123", controlled_by="alex", controlled_by_id=1234)
    return {
        "operation": "publish",
        "repository": {"hostname": "github.com", "id": 42, "owner": "acme", "name": "repo"},
        "issue_number": 123,
        "expected_author": {"user_id": 1234, "login": "alex"},
        "body": yaml.safe_dump(event, sort_keys=False),
    }


def test_event_write_defaults_to_preview_and_requires_exact_approval(repo_root, tmp_path):
    plan = publication_plan(repo_root)
    input_path = write_json(tmp_path / "plan.json", plan)
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", input_path)
    assert result.returncode == 0, result.stdout + result.stderr
    preview = json.loads(result.stdout)
    assert preview["mode"] == "preview"
    assert preview["remote_write_performed"] is False
    rejected = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", input_path, "--write")
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["status"] == "fail"


def approve(plan):
    plan["approval"] = {"confirmed": True, "operation": plan["operation"], "repository_id": plan["repository"]["id"],
                        "issue_number": plan["issue_number"], "comment_id": plan.get("comment_id"),
                        "body_sha256": hashlib.sha256(plan["body"].encode()).hexdigest(), "old_body_sha256": plan.get("old_body_sha256")}
    return plan


@pytest.fixture
def fake_github(tmp_path):
    directory = tmp_path / "fake-bin"
    directory.mkdir()
    state_file = tmp_path / "github-state.json"
    state = {"repository": {"id": 42, "full_name": "acme/repo"}, "user": {"id": 1234, "login": "alex"},
             "issue": {"number": 123, "state": "open"}, "comments": [], "log": []}
    write_json(state_file, state)
    script = directory / "gh"
    script.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ["FAKE_GH_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
method = args[args.index("--method") + 1]
endpoint = args[1]
state["log"].append([method, endpoint])
result = None
if method == "GET":
    if endpoint == "repos/acme/repo": result = state["repository"]
    elif endpoint == "user": result = state["user"]
    elif endpoint == "repos/acme/repo/issues/123": result = state["issue"]
    elif endpoint.startswith("repos/acme/repo/issues/123/comments?"):
        result = state["comments"] if "page=1" in endpoint else []
    elif endpoint.startswith("repos/acme/repo/issues/comments/"):
        result = next((c for c in state["comments"] if c["id"] == int(endpoint.rsplit("/", 1)[1])), None)
else:
    body = json.loads(sys.stdin.read())["body"]
    if method == "POST":
        new_id = 456 + len(state["comments"])
        result = {"id": new_id, "html_url": f"https://github.com/acme/repo/issues/123#issuecomment-{new_id}",
                  "issue_url": "https://api.github.com/repos/acme/repo/issues/123", "user": state["user"],
                  "body": body, "updated_at": "2026-10-14T00:00:00Z"}
        if state.get("mode") != "timeout-without-save": state["comments"].append(result)
    elif method == "PATCH":
        result = next(c for c in state["comments"] if c["id"] == int(endpoint.rsplit("/", 1)[1]))
        result["body"] = body
        if state.get("mode") == "changed-after-edit": result["user"] = {"id": 999, "login": "other"}
path.write_text(json.dumps(state))
if method != "GET" and state.get("mode", "").startswith("timeout"):
    sys.exit(2)
if result is None: sys.exit(3)
print(json.dumps(result))
''')
    script.chmod(0o755)
    environment = {"PATH": str(directory) + os.pathsep + os.environ["PATH"], "FAKE_GH_STATE": str(state_file), "PYTHONDONTWRITEBYTECODE": "1"}
    return state_file, environment


@pytest.mark.parametrize("mode", ["normal", "timeout-after-save"])
def test_publication_reads_back_actual_comment_and_recovers_without_duplicate_post(repo_root, tmp_path, fake_github, mode):
    state_file, environment = fake_github
    state = json.loads(state_file.read_text())
    state["mode"] = mode
    write_json(state_file, state)
    plan = write_json(tmp_path / "plan.json", approve(publication_plan(repo_root)))
    receipt = tmp_path / "receipt.json"
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan, "--write", "--receipt", receipt, env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["state"] == "read-back-verified"
    assert report["comment"]["id"] == 456
    assert report["comment"]["url"] == "https://github.com/acme/repo/issues/123#issuecomment-456"
    assert report["comment"]["user_id"] == 1234
    assert report["comment"]["issue_number"] == 123
    retry = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan, "--write", "--receipt", receipt, env=environment)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    saved = json.loads(state_file.read_text())
    assert len(saved["comments"]) == 1
    assert sum(method == "POST" for method, _ in saved["log"]) == 1


def existing_comment(body):
    return {"id": 456, "html_url": "https://github.com/acme/repo/issues/123#issuecomment-456",
            "issue_url": "https://api.github.com/repos/acme/repo/issues/123", "user": {"id": 1234, "login": "alex"},
            "body": body, "updated_at": "2026-10-14T00:00:00Z"}


def edit_plan(repo_root):
    plan = publication_plan(repo_root)
    original = plan["body"]
    event = yaml.safe_load(original)
    event["scope"] = ["src/api/**", "tests/api/**", "docs/api.md"]
    plan.update(operation="edit", body=yaml.safe_dump(event, sort_keys=False), comment_id=456,
                comment_url="https://github.com/acme/repo/issues/123#issuecomment-456",
                old_body_sha256=hashlib.sha256(original.encode()).hexdigest())
    return approve(plan), existing_comment(original)


def test_authorized_edit_binds_original_comment_and_reads_back_exact_new_body(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    plan, original = edit_plan(repo_root)
    state = json.loads(state_file.read_text())
    state["comments"] = [original]
    write_json(state_file, state)
    plan_path = write_json(tmp_path / "edit.json", plan)
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan_path, "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["comment"]["body"] == plan["body"]
    saved = json.loads(state_file.read_text())
    assert len(saved["comments"]) == 1
    mutations = [(method, path) for method, path in saved["log"] if method != "GET"]
    assert mutations == [("PATCH", "repos/acme/repo/issues/comments/456")]
    assert saved["log"][-1] == ["GET", "repos/acme/repo/issues/comments/456"]


@pytest.mark.parametrize("mismatch", ["repository", "issue", "comment-id", "comment-url", "author-id", "author-login", "old-digest"])
def test_edit_mismatch_stops_before_any_mutation(repo_root, tmp_path, fake_github, mismatch):
    state_file, environment = fake_github
    plan, original = edit_plan(repo_root)
    state = json.loads(state_file.read_text())
    state["comments"] = [original]
    if mismatch == "repository": state["repository"]["id"] = 99
    elif mismatch == "issue": state["issue"]["number"] = 124
    elif mismatch == "comment-id": original["id"] = 457
    elif mismatch == "comment-url": original["html_url"] = "https://github.com/acme/repo/issues/124#issuecomment-456"
    elif mismatch == "author-id": original["user"]["id"] = 999
    elif mismatch == "author-login": original["user"]["login"] = "other"
    elif mismatch == "old-digest": original["body"] += "# concurrent update\n"
    write_json(state_file, state)
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "edit.json", plan), "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode != 0
    assert all(method == "GET" for method, _ in json.loads(state_file.read_text())["log"])


def test_correction_requires_linked_revision_and_preserves_original_comment(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    plan, original = edit_plan(repo_root)
    plan["operation"] = "append-correction"
    event = yaml.safe_load(plan["body"])
    event["event_id"] = "claim-correction-123"
    # An append request without a verifiable original-event relationship must fail even in preview.
    plan["body"] = yaml.safe_dump(event, sort_keys=False)
    missing = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "missing.json", approve(plan)))
    assert missing.returncode == 1
    event["revision"] = {"schema_version": 1, "kind": "correction", "original_event_id": "claim-real-123", "github_comment_id": 456,
                         "github_comment_url": plan["comment_url"], "old_body_sha256": plan["old_body_sha256"], "reason": "Correct omitted documentation path."}
    plan["body"] = yaml.safe_dump(event, sort_keys=False)
    state = json.loads(state_file.read_text())
    state["comments"] = [original]
    write_json(state_file, state)
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "correction.json", approve(plan)), "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode == 0, result.stdout + result.stderr
    saved = json.loads(state_file.read_text())
    assert saved["comments"][0]["body"] == original["body"]
    assert len(saved["comments"]) == 2
    assert json.loads(result.stdout)["comment"]["id"] == 457


def test_checkpoint_records_progress_and_keeps_unknown_process_and_claim_state(repo_root, tmp_path):
    checkpoint = write_json(tmp_path / "checkpoint.json", {
        "repository": "acme/repo", "issue_number": 123, "actor_id": "backend-api", "session_id": "old-session",
        "claim_url": "https://github.com/acme/repo/issues/123#issuecomment-456",
        "branch": "agent/backend-api/issue-123-timeout", "head_sha": "b" * 40,
        "completed": ["Implemented API retry."], "tests": [{"command": "python -m pytest tests/api", "status": "pass"}],
        "uncommitted_changes": [{"status": "untracked", "path": "tests/api/new.py"}],
        "remaining_steps": ["Review uncommitted test before commit."],
        "process_observation": {"pid": 9123, "found": False, "observed_at": "2026-10-14T00:00:00Z"},
    })
    result = subprocess.run([sys.executable, "-S", str(repo_root / "shared/scripts/collaboration_scope.py"), "--checkpoint", str(checkpoint)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["checkpoint"]["remaining_steps"] == ["Review uncommitted test before commit."]
    assert report["checkpoint"]["uncommitted_changes"] == [{"status": "untracked", "path": "tests/api/new.py"}]
    assert report["old_process_status"] == "unknown"
    assert report["claim_released"] is False
    assert report["push_authorized"] is False
    assert report["authorization_verified"] is False


def test_missing_event_dependencies_reports_unknown_without_installing(repo_root, tmp_path):
    body = repo_root / "skills/github-collaboration/templates/events/claim.yml"
    result = subprocess.run([sys.executable, "-S", str(repo_root / "shared/scripts/collaboration_event.py"), "validate", "--body", str(body)], capture_output=True, text=True)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["status"] == "unknown"
    assert "requirements-helpers.txt" in report["error"]


def test_unknown_publication_receipt_prevents_cross_process_repeat_post(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    state = json.loads(state_file.read_text())
    state["mode"] = "timeout-without-save"
    write_json(state_file, state)
    plan = write_json(tmp_path / "plan.json", approve(publication_plan(repo_root)))
    receipt = tmp_path / "receipt.json"
    for attempt in range(2):
        result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan, "--write", "--receipt", receipt, env=environment)
        assert result.returncode == 2, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["state"] == "write-sent-result-unknown"
        assert report["remote_write_performed"] is (None if attempt == 0 else False)
    saved = json.loads(state_file.read_text())
    assert saved["comments"] == []
    assert sum(method == "POST" for method, _ in saved["log"]) == 1
    recorded = json.loads(receipt.read_text())
    assert recorded["state"] == "write-sent-result-unknown"
    assert "body" not in recorded["binding"]


@pytest.mark.parametrize("receipt_kind", ["symlink", "different-target"])
def test_untrusted_receipt_is_preserved_and_never_sends_remote_write(repo_root, tmp_path, fake_github, receipt_kind):
    state_file, environment = fake_github
    target = tmp_path / "original.json"
    target.write_text('{"private": "preserve"}')
    receipt = tmp_path / "receipt.json"
    if receipt_kind == "symlink": receipt.symlink_to(target)
    else: receipt.write_text('{"binding": {"repository": "other"}, "state": "write-sent-result-unknown"}')
    before = receipt.read_bytes()
    plan = write_json(tmp_path / "plan.json", approve(publication_plan(repo_root)))
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan, "--write", "--receipt", receipt, env=environment)
    assert result.returncode == 1
    assert receipt.read_bytes() == before
    assert json.loads(state_file.read_text())["log"] == []


def test_event_predecessor_link_must_resolve_to_exact_issue_comment(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    plan = publication_plan(repo_root)
    event = yaml.safe_load(plan["body"])
    event.update(previous_event_id="old-claim", github_comment_id=999,
                 github_comment_url="https://github.com/other/repo/issues/123#issuecomment-999")
    plan["body"] = yaml.safe_dump(event, sort_keys=False)
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "plan.json", approve(plan)), "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode == 1
    assert all(method == "GET" for method, _ in json.loads(state_file.read_text())["log"])


def test_receipt_directory_symlink_cannot_redirect_operation_record(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    plan = write_json(tmp_path / "plan.json", approve(publication_plan(repo_root)))
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", plan, "--write", "--receipt", link / "receipt.json", env=environment)
    assert result.returncode == 1
    assert list(real.iterdir()) == []
    assert json.loads(state_file.read_text())["log"] == []


def test_numeric_approval_flag_is_not_explicit_confirmation(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    plan = approve(publication_plan(repo_root))
    plan["approval"]["confirmed"] = 1
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "plan.json", plan), "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode == 1
    assert json.loads(state_file.read_text())["log"] == []


def test_plan_binding_refuses_unexpected_secret_fields_before_receipt(repo_root, tmp_path, fake_github):
    state_file, environment = fake_github
    plan = approve(publication_plan(repo_root))
    plan["repository"]["token"] = "fake-do-not-record"
    result = run_helper(repo_root, "collaboration_event.py", "apply", "--plan", write_json(tmp_path / "plan.json", plan), "--write", "--receipt", tmp_path / "receipt.json", env=environment)
    assert result.returncode == 1
    assert "fake-do-not-record" not in result.stdout + result.stderr
    assert not (tmp_path / "receipt.json").exists()
    assert json.loads(state_file.read_text())["log"] == []


def test_deployed_helper_uses_only_colocated_versioned_event_schema(repo_root, tmp_path):
    deployed = tmp_path / "consumer/.github/agent-collaboration"
    deployed.mkdir(parents=True)
    script = deployed / "collaboration_event.py"
    schema = deployed / "collaboration-event.schema.json"
    shutil.copyfile(repo_root / "shared/scripts/collaboration_event.py", script)
    shutil.copyfile(repo_root / "schemas/collaboration-event.schema.json", schema)
    body = repo_root / "skills/github-collaboration/templates/events/research-claim.yml"
    def validate():
        return subprocess.run([sys.executable, str(script), "validate", "--body", str(body)], capture_output=True, text=True)
    result = validate()
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["event"]["task_kind"] == "research"
    schema.write_text('{}')
    invalid = validate()
    assert invalid.returncode == 1
    assert json.loads(invalid.stdout)["status"] == "fail"
    schema.unlink()
    unrelated = deployed.parent / "references/schemas/collaboration-event.schema.json"
    unrelated.parent.mkdir(parents=True)
    shutil.copyfile(repo_root / "schemas/collaboration-event.schema.json", unrelated)
    missing = validate()
    assert missing.returncode == 1
    assert json.loads(missing.stdout)["status"] == "fail"


@pytest.mark.parametrize("version, valid", [(None, False), (2, False), (1, True)])
def test_correction_revision_cli_requires_supported_explicit_local_version(repo_root, tmp_path, version, valid):
    event = yaml.safe_load(publication_plan(repo_root)["body"])
    event["event_id"] = "versioned-correction"
    event["revision"] = {"kind": "correction", "original_event_id": "original-claim", "github_comment_id": 456,
                         "github_comment_url": "https://github.com/acme/repo/issues/123#issuecomment-456",
                         "old_body_sha256": "a" * 64, "reason": "Correct event details."}
    if version is not None:
        event["revision"]["schema_version"] = version
    body = tmp_path / "revision.yml"
    body.write_text(yaml.safe_dump(event, sort_keys=False))
    result = run_helper(repo_root, "collaboration_event.py", "validate", "--body", body)
    assert result.returncode == (0 if valid else 1), result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == ("pass" if valid else "fail")
