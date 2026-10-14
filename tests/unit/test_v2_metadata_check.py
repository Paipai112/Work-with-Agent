"""Run the deployed checker CLI, with only its own mapped resources available."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


SHA = "a" * 40
HEAD = "b" * 40
PRIOR = "c" * 40
CLAIM = "https://github.com/sample/repo/issues/7#issuecomment-1"
DEPLOYED = ".github/agent-collaboration/"


@pytest.fixture
def deployed_checker(repo_root, tmp_path):
    package = tmp_path / "standalone-setup"
    synchronized = subprocess.run([sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
                                   "--destination", str(package), "--profile", "github-collaboration-setup"],
                                  text=True, capture_output=True, check=False)
    assert synchronized.returncode == 0, synchronized.stdout + synchronized.stderr
    project = tmp_path / "consumer"
    shutil.copytree(package / "assets/templates/project", project)
    directory = project / DEPLOYED
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(data, *arguments, extra_environment=None):
        path = tmp_path / "input.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return subprocess.run([sys.executable, str(directory / "check_pr_metadata.py"),
                               str(path), str(tmp_path / "report"), *arguments],
                              text=True, capture_output=True, check=False, cwd=project,
                              env={**environment, **(extra_environment or {})})
    return run, directory


def test_legacy_payload_without_snapshot_cannot_get_a_formal_v2_pass(deployed_checker, fixture_path):
    run, _ = deployed_checker
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    result = run(data)
    assert result.returncode == 2
    assert "RESULT=unknown" in result.stdout
    assert "RESULT=pass" not in result.stdout


def metadata(data):
    raw = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n", 1)[1].split("\n-->", 1)[0]
    return json.loads(raw)


def set_metadata(data, **changes):
    before, raw = data["pull"]["body"].split("<!-- agent-collaboration:metadata\n", 1)
    value = json.loads(raw.split("\n-->", 1)[0])
    value.update(changes)
    data["pull"]["body"] = before + "<!-- agent-collaboration:metadata\n" + json.dumps(value) + "\n-->"


@pytest.fixture
def v2_input(deployed_checker, fixture_path):
    _, directory = deployed_checker
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["pull"].update(draft=True, state="open", updated_at="2026-10-14T01:00:00Z")
    data["pull"]["base"].update(sha=SHA, repo={"id": 123, "full_name": "sample/repo"})
    data["files"][0]["status"] = "modified"
    delivery = {"development_base_sha": SHA, "net_diff_base_sha": SHA,
                "predecessors": [], "merge_order": [12]}
    set_metadata(data, schema_version=2, skill_version="0.2.0", delivery=delivery)
    claim = {"event": "claim", "event_id": "claim-7", "previous_event_id": None,
             "controlled_by": "developer", "controlled_by_id": 1001, "actor_id": "backend-api",
             "session_id": "run-1", "runtime": "codex", "scope": ["src/**"],
             "branch": data["pull"]["head"]["ref"], "base_head": SHA,
             "expected_handoff": "pull-request"}
    record = {"id": 1, "url": CLAIM, "user_id": 1001, "login": "developer", "issue_number": 7,
              "body": yaml.safe_dump(claim, sort_keys=False), "updated_at": "2026-10-14T00:00:00Z"}
    data["claim_comments"] = {CLAIM: record}
    data["issue_comments"] = {"7": [record]}
    data["predecessor_pulls"] = []
    data["net_diff"] = {"base_sha": SHA, "head_sha": HEAD, "merge_base_sha": SHA,
                        "status": "ahead", "commits": [HEAD], "files": copy.deepcopy(data["files"]), "complete": True}
    data["development_compare"] = copy.deepcopy(data["net_diff"])
    data["config"] = (directory / "config.yml").read_text()
    auth = yaml.safe_dump(data["authorization"], sort_keys=False)
    data["authorization"] = auth
    (directory / "authorization.yml").write_text(auth)
    data["snapshot"] = {"version": 2, "check_contract": 2, "source": "github-get",
                        "repository_id": 123, "default_branch": "main", "trusted_sha": SHA,
                        "pull_number": 12, "head_sha": HEAD, "base_ref": "main",
                        "collected_at": "2026-10-14T01:00:00Z", "verified_at": "2026-10-14T01:01:00Z",
                        "trusted_resources": {DEPLOYED + name: {"sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
                                                              "bytes": len((directory / name).read_bytes())}
                                              for name in ("run_pr_metadata_check.py", "collect_pr_metadata.py", "check_pr_metadata.py",
                                                           "collaboration_event.py", "collaboration_scope.py", "collaboration-event.schema.json",
                                                           "requirements-helpers.txt", "config.yml", "authorization.yml")},
                        "unverified": ["human_approval", "effective_account_permissions", "native_branch_protection",
                                       "actual_skill_loading", "unlisted_issue_claim_conflicts"]}
    return data


def test_valid_deployed_v2_claim_and_net_scope_can_pass(deployed_checker, v2_input):
    run, _ = deployed_checker
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("RESULT=pass\n")


@pytest.mark.parametrize("template_path", [
    "templates/project/.github/PULL_REQUEST_TEMPLATE/agent-change.md",
    "skills/github-collaboration/templates/pull-request-body.md",
])
def test_real_pr_template_filled_with_v2_delivery_runs_formal_deployed_checker(repo_root, deployed_checker, v2_input, template_path):
    run, _ = deployed_checker
    template = (repo_root / template_path).read_text()
    before, block = template.split("<!-- agent-collaboration:metadata\n")
    candidate = json.loads(block.split("\n-->")[0])
    assert candidate["schema_version"] == 2 and "delivery" in candidate
    v2_input["pull"]["body"] = before + "<!-- agent-collaboration:metadata\n" + json.dumps(metadata(v2_input)) + "\n-->\nCloses #7"
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("field,value", [
    ("controlled_by_id", 999), ("controlled_by", "someone-else"),
    ("actor_id", "frontend-web"), ("session_id", "other-session"),
    ("branch", "agent/backend-api/issue-7-other"), ("base_head", PRIOR),
    ("scope", ["docs/**"]),
])
def test_claim_body_cannot_disagree_with_actual_identity_and_delivery(deployed_checker, v2_input, field, value):
    run, _ = deployed_checker
    event = yaml.safe_load(v2_input["claim_comments"][CLAIM]["body"])
    event[field] = value
    v2_input["claim_comments"][CLAIM]["body"] = yaml.safe_dump(event, sort_keys=False)
    result = run(v2_input)
    assert result.returncode == 1
    assert result.stdout.endswith("RESULT=fail\n")


@pytest.mark.parametrize("failure", ["invalid_body", "wrong_url", "wrong_id", "duplicate_event"])
def test_claim_structure_and_real_comment_envelope_are_verified(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    record = v2_input["claim_comments"][CLAIM]
    if failure == "invalid_body":
        record["body"] = "event: claim\nmissing-fields: true\n"
    elif failure == "wrong_url":
        record["url"] = "https://github.com/other/repo/issues/7#issuecomment-1"
    elif failure == "wrong_id":
        record["id"] = 99
    else:
        duplicate = copy.deepcopy(record)
        duplicate.update(id=2, url="https://github.com/sample/repo/issues/7#issuecomment-2")
        v2_input["issue_comments"]["7"].append(duplicate)
    result = run(v2_input)
    assert result.returncode == 1
    assert result.stdout.endswith("RESULT=fail\n")


def append_event(data, event, identifier, issue_number=7):
    record = {"id": identifier, "url": f"https://github.com/sample/repo/issues/{issue_number}#issuecomment-{identifier}",
              "user_id": event["controlled_by_id"], "login": event["controlled_by"], "issue_number": issue_number,
              "body": yaml.safe_dump(event, sort_keys=False), "updated_at": "2026-10-14T00:30:00Z"}
    data["issue_comments"].setdefault(str(issue_number), []).append(record)
    return record


def child_event(data, kind, identifier, predecessor=None, **changes):
    record = predecessor or data["claim_comments"][CLAIM]
    event = yaml.safe_load(record["body"])
    event.pop("expected_handoff", None)
    event.update(event=kind, event_id=f"{kind}-{identifier}", previous_event_id=event["event_id"],
                 github_comment_id=record["id"], github_comment_url=record["url"])
    if kind in {"handoff", "resume"}:
        event["head_sha"] = HEAD
    if kind == "release":
        event["release_mode"] = "self"
    if kind == "resume":
        event["handoff_event_id"] = event["previous_event_id"]
    event.update(changes)
    return event


@pytest.mark.parametrize("kind", ["release", "handoff"])
def test_terminal_later_event_removes_claim_from_current_delivery(deployed_checker, v2_input, kind):
    run, _ = deployed_checker
    append_event(v2_input, child_event(v2_input, kind, 2), 2)
    result = run(v2_input)
    assert result.returncode == 1


def test_verified_same_branch_resume_changes_the_active_session(deployed_checker, v2_input):
    run, _ = deployed_checker
    handoff = append_event(v2_input, child_event(v2_input, "handoff", 2), 2)
    append_event(v2_input, child_event(v2_input, "resume", 3, handoff, session_id="run-2"), 3)
    set_metadata(v2_input, session_id="run-2")
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["predecessor_id", "predecessor_url", "old_session", "stale_child", "known_conflict"])
def test_lineage_and_known_active_conflicts_do_not_use_latest_comment_wins(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    if failure == "known_conflict":
        event = yaml.safe_load(v2_input["claim_comments"][CLAIM]["body"])
        event.update(event_id="other-claim", actor_id="frontend-web", session_id="other-session",
                     branch="agent/frontend-web/issue-7-ui")
        append_event(v2_input, event, 2)
    else:
        handoff = append_event(v2_input, child_event(v2_input, "handoff", 2), 2)
        if failure == "stale_child":
            append_event(v2_input, child_event(v2_input, "release", 3), 3)
        else:
            resume = child_event(v2_input, "resume", 3, handoff, session_id="run-2")
            if failure == "predecessor_id":
                resume["github_comment_id"] = 99
            elif failure == "predecessor_url":
                resume["github_comment_url"] = "https://github.com/other/repo/issues/7#issuecomment-2"
            append_event(v2_input, resume, 3)
            if failure != "old_session":
                set_metadata(v2_input, session_id="run-2")
    result = run(v2_input)
    assert result.returncode == 1


def baseline_revision(data, identifier=2):
    original = data["claim_comments"][CLAIM]
    event = child_event(data, "claim", identifier, base_head=PRIOR, expected_handoff="pull-request")
    event["revision"] = {"schema_version": 1, "kind": "baseline", "original_event_id": "claim-7",
                         "github_comment_id": 1, "github_comment_url": CLAIM,
                         "old_body_sha256": hashlib.sha256(original["body"].encode()).hexdigest(),
                         "reason": "Explicitly revise the development baseline after predecessor integration",
                         "from_base_head": SHA, "to_base_head": PRIOR}
    delivery = metadata(data)["delivery"]
    delivery["development_base_sha"] = PRIOR
    set_metadata(data, delivery=delivery)
    data["development_compare"].update(base_sha=PRIOR, merge_base_sha=PRIOR)
    return event


def test_linked_baseline_revision_updates_only_the_development_baseline(deployed_checker, v2_input):
    run, _ = deployed_checker
    append_event(v2_input, baseline_revision(v2_input), 2)
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["digest", "target_id", "target_url", "from_base", "to_base", "scope", "blank_reason", "no_version"])
def test_baseline_revision_cannot_rewrite_provenance_or_authorize_larger_scope(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    event = baseline_revision(v2_input)
    if failure == "digest":
        event["revision"]["old_body_sha256"] = "f" * 64
    elif failure == "target_id":
        event["revision"]["github_comment_id"] = 99
    elif failure == "target_url":
        event["revision"]["github_comment_url"] = "https://github.com/other/repo/issues/7#issuecomment-1"
    elif failure == "from_base":
        event["revision"]["from_base_head"] = "d" * 40
    elif failure == "to_base":
        event["revision"]["to_base_head"] = "d" * 40
    elif failure == "scope":
        event["scope"].append("docs/**")
        v2_input["net_diff"]["files"].append({"filename": "docs/new.md", "status": "added"})
        v2_input["files"].append({"filename": "docs/new.md", "status": "added"})
    elif failure == "blank_reason":
        event["revision"]["reason"] = "   "
    else:
        del event["revision"]["schema_version"]
    append_event(v2_input, event, 2)
    result = run(v2_input)
    assert result.returncode == 1


@pytest.mark.parametrize("failure", ["api_extra", "net_other_path", "status_disagrees", "development_not_ancestor"])
def test_fixed_diff_and_api_delivery_facts_must_agree(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    if failure == "api_extra":
        v2_input["files"].append({"filename": "docs/hidden.md", "status": "added"})
    elif failure == "net_other_path":
        v2_input["net_diff"]["files"][0]["filename"] = "src/hidden.py"
    elif failure == "status_disagrees":
        v2_input["net_diff"]["files"][0]["status"] = "added"
    else:
        v2_input["development_compare"].update(status="diverged", merge_base_sha=PRIOR)
    result = run(v2_input)
    assert result.returncode == 1


@pytest.mark.parametrize("field", ["development_compare", "net_diff", "predecessor_pulls", "issue_comments"])
def test_missing_v2_facts_do_not_fall_back_to_legacy(deployed_checker, v2_input, field):
    run, _ = deployed_checker
    del v2_input[field]
    result = run(v2_input)
    assert result.returncode == 2
    assert "RESULT=pass" not in result.stdout


@pytest.mark.parametrize("failure", ["no_contract", "no_version", "wrong_repo", "wrong_sha", "wrong_head", "missing_resource", "stale_default_target"])
def test_snapshot_binding_and_deployment_contract_are_required(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    snapshot = v2_input["snapshot"]
    if failure == "no_contract":
        del snapshot["check_contract"]
    elif failure == "no_version":
        del snapshot["version"]
    elif failure == "wrong_repo":
        snapshot["repository_id"] = 999
    elif failure == "wrong_sha":
        snapshot["trusted_sha"] = PRIOR
    elif failure == "wrong_head":
        snapshot["head_sha"] = PRIOR
    elif failure == "stale_default_target":
        v2_input["pull"]["base"]["sha"] = PRIOR
        delivery = metadata(v2_input)["delivery"]
        delivery["net_diff_base_sha"] = PRIOR
        set_metadata(v2_input, delivery=delivery)
        v2_input["net_diff"]["base_sha"] = PRIOR
    else:
        del snapshot["trusted_resources"][DEPLOYED + "collaboration_scope.py"]
    result = run(v2_input)
    assert result.returncode == 2


def trusted_authorization(data, **changes):
    value = yaml.safe_load(data["authorization"])
    value.update(changes)
    data["authorization"] = yaml.safe_dump(value, sort_keys=False)
    source = data["authorization"].encode()
    data["snapshot"]["trusted_resources"][DEPLOYED + "authorization.yml"] = {
        "sha256": hashlib.sha256(source).hexdigest(), "bytes": len(source)}


def reassignment(data, predecessor=None, identifier=2):
    owner = yaml.safe_load(data["claim_comments"][CLAIM]["body"])
    current = yaml.safe_load(predecessor["body"]) if predecessor else owner
    identity = {key: current[key] for key in ("controlled_by", "controlled_by_id", "actor_id", "session_id")}
    successor = {"controlled_by": "new-developer", "controlled_by_id": 1002,
                 "actor_id": "backend-successor", "session_id": "new-run"}
    leader = {"controlled_by": "maintainer", "controlled_by_id": 2001,
              "actor_id": "repository-governance", "session_id": "leader-run"}
    event = child_event(data, "reassign", identifier, predecessor, **leader,
                        target={**identity, "claim_event_id": owner["event_id"],
                                "claim_comment_id": 1, "claim_comment_url": CLAIM},
                        successor=successor, approval_url="https://github.com/sample/repo/issues/7#issuecomment-50",
                        reason="Owner is unavailable; preserve checkpoint on a separate branch",
                        old_process_status="unknown", stop_evidence=None)
    event.pop("revision", None)
    record = append_event(data, event, identifier)
    claim = child_event(data, "claim", identifier + 1, record, **successor,
                        branch="agent/backend-successor/issue-7-resume", expected_handoff="pull-request")
    for key in ("target", "successor", "approval_url", "reason", "old_process_status", "stop_evidence"):
        claim.pop(key)
    successor_record = append_event(data, claim, identifier + 1)
    data["pull"]["user"] = {"login": successor["controlled_by"], "id": successor["controlled_by_id"]}
    data["pull"]["head"]["ref"] = claim["branch"]
    set_metadata(data, **successor, claim_urls=[successor_record["url"]])
    data["claim_comments"] = {successor_record["url"]: successor_record}
    trusted_authorization(data, leader_delegations=[{
        "actor_id": leader["actor_id"], "controlled_by": leader["controlled_by"],
        "controlled_by_id": leader["controlled_by_id"], "permission_ceiling": "maintain",
        "account_permission_at_grant": "maintain", "approval_evidence": {
            "github_pr_url": "https://github.com/sample/repo/pull/5", "approved_by": "repository-owner",
            "approved_at": "2026-10-13T00:00:00Z", "approved_head_sha": SHA},
        "status": "active", "granted_at": "2026-10-13T00:00:00Z"}])
    return event, successor_record


@pytest.fixture
def deployed_event_helper(deployed_checker, v2_input, monkeypatch):
    _, directory = deployed_checker
    specification = importlib.util.spec_from_file_location("deployed_event_helper", directory / "collaboration_event.py")
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)

    def get_comment(plan, method, endpoint):
        assert method == "GET", "predecessor verification must not write to GitHub"
        identifier = int(endpoint.rsplit("/", 1)[-1])
        record = next(item for item in v2_input["issue_comments"]["7"] if item["id"] == identifier)
        return {"id": identifier, "html_url": record["url"],
                "user": {"id": record["user_id"], "login": record["login"]},
                "body": record["body"], "updated_at": record["updated_at"]}

    monkeypatch.setattr(helper, "github", get_comment)
    plan = {"repository": {"hostname": "github.com", "id": 123, "owner": "sample", "name": "repo"},
            "issue_number": 7}
    return helper, plan


def test_reassignment_after_resume_binds_current_session_and_original_claim(deployed_checker, v2_input, deployed_event_helper):
    run, _ = deployed_checker
    helper, plan = deployed_event_helper
    handoff = append_event(v2_input, child_event(v2_input, "handoff", 2), 2)
    resumed = append_event(v2_input, child_event(v2_input, "resume", 3, handoff, session_id="run-2"), 3)
    event, _ = reassignment(v2_input, resumed, 4)
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr
    helper.verify_predecessors(plan, event)


@pytest.mark.parametrize("failure", ["old_session", "root_identity", "root_url", "unrelated_root", "cycle", "ancestor_pointer"])
def test_resumed_reassignment_cannot_replace_current_session_or_original_root(deployed_checker, v2_input, deployed_event_helper, failure):
    run, _ = deployed_checker
    helper, plan = deployed_event_helper
    original = v2_input["claim_comments"][CLAIM]
    handoff = append_event(v2_input, child_event(v2_input, "handoff", 2), 2)
    resumed = append_event(v2_input, child_event(v2_input, "resume", 3, handoff, session_id="run-2"), 3)
    if failure == "unrelated_root":
        unrelated = yaml.safe_load(original["body"])
        unrelated["event_id"] = "unrelated-claim"
        other = append_event(v2_input, unrelated, 4)
    event, _ = reassignment(v2_input, resumed, 5)
    if failure == "old_session":
        event["target"]["session_id"] = "run-1"
    elif failure == "root_identity":
        root_event = yaml.safe_load(original["body"])
        root_event["actor_id"] = "different-responsibility"
        original["body"] = yaml.safe_dump(root_event, sort_keys=False)
    elif failure == "root_url":
        event["target"]["claim_comment_url"] = "https://github.com/other/repo/issues/7#issuecomment-1"
    elif failure == "unrelated_root":
        event["target"].update(claim_event_id="unrelated-claim", claim_comment_id=other["id"], claim_comment_url=other["url"])
    else:
        ancestor = yaml.safe_load(handoff["body"])
        ancestor["previous_event_id"] = "resume-3"
        if failure == "cycle":
            ancestor.update(github_comment_id=resumed["id"], github_comment_url=resumed["url"])
        handoff["body"] = yaml.safe_dump(ancestor, sort_keys=False)
    v2_input["issue_comments"]["7"][-2]["body"] = yaml.safe_dump(event, sort_keys=False)
    result = run(v2_input)
    assert result.returncode == 1, result.stdout + result.stderr
    with pytest.raises(helper.EventError):
        helper.verify_predecessors(plan, event)


def test_verified_leader_reassignment_allows_successor_on_a_separate_branch(deployed_checker, v2_input):
    run, _ = deployed_checker
    reassignment(v2_input)
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "process termination is not proven" in result.stdout


@pytest.mark.parametrize("failure", ["target", "successor", "same_branch", "old_claim", "unverified_leader", "malformed_delegation"])
def test_reassignment_rejects_old_owner_and_unverified_transfers(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    original = copy.deepcopy(v2_input["claim_comments"][CLAIM])
    reassignment(v2_input)
    event = yaml.safe_load(v2_input["issue_comments"]["7"][1]["body"])
    if failure == "unverified_leader":
        trusted_authorization(v2_input, leader_delegations=[])
    elif failure == "malformed_delegation":
        value = yaml.safe_load(v2_input["authorization"])
        del value["leader_delegations"][0]["approval_evidence"]["approved_head_sha"]
        trusted_authorization(v2_input, leader_delegations=value["leader_delegations"])
    elif failure == "old_claim":
        v2_input["pull"]["user"] = {"login": "developer", "id": 1001}
        v2_input["pull"]["head"]["ref"] = "agent/backend-api/issue-7-fix-timeout"
        v2_input["claim_comments"] = {CLAIM: original}
        set_metadata(v2_input, controlled_by="developer", controlled_by_id=1001,
                     actor_id="backend-api", session_id="run-1", claim_urls=[CLAIM])
    elif failure == "same_branch":
        current = v2_input["issue_comments"]["7"][2]
        claim = yaml.safe_load(current["body"])
        claim["branch"] = event["branch"]
        current["body"] = yaml.safe_dump(claim, sort_keys=False)
    else:
        event[failure]["session_id"] = "wrong-session"
        v2_input["issue_comments"]["7"][1]["body"] = yaml.safe_dump(event, sort_keys=False)
    result = run(v2_input)
    assert result.returncode == (2 if failure in {"unverified_leader", "malformed_delegation"} else 1)


def stacked(data, merged=False, ready=False, prior_files=None):
    delivery = metadata(data)["delivery"]
    delivery.update(development_base_sha=PRIOR, net_diff_base_sha=SHA if merged else PRIOR,
                    predecessors=[{"pull_number": 11, "head_sha": PRIOR}], merge_order=[11, 12])
    set_metadata(data, delivery=delivery)
    event = yaml.safe_load(data["claim_comments"][CLAIM]["body"])
    event["base_head"] = PRIOR
    data["claim_comments"][CLAIM]["body"] = yaml.safe_dump(event, sort_keys=False)
    data["development_compare"].update(base_sha=PRIOR, merge_base_sha=PRIOR)
    data["net_diff"].update(base_sha=SHA if merged else PRIOR, merge_base_sha=PRIOR,
                            status="diverged" if merged else "ahead")
    data["predecessor_pulls"] = [{"number": 11, "head": {"sha": PRIOR},
                                  "base": {"ref": "main", "sha": SHA, "repo": {"id": 123}},
                                  "state": "closed" if merged else "open", "merged": merged,
                                  "merge_commit_sha": "d" * 40 if merged else None,
                                  "merged_at": "2026-10-14T00:20:00Z" if merged else None}]
    data["predecessor_files"] = {"11": prior_files or [{"filename": "docs/predecessor.md", "status": "added"}]}
    data["predecessor_compares"] = []
    data["pull"]["draft"] = not ready
    if not merged:
        data["files"] += copy.deepcopy(data["predecessor_files"]["11"])
    if ready:
        data["reviews"] = [{"id": 1, "state": "APPROVED", "commit_id": HEAD,
                            "user": {"id": 1002}, "submitted_at": "2026-10-14T00:40:00Z"}]


@pytest.mark.parametrize("merged,ready", [(False, False), (True, False), (True, True)])
def test_stacked_delivery_handles_draft_increment_and_normal_merge(deployed_checker, v2_input, merged, ready):
    run, _ = deployed_checker
    stacked(v2_input, merged=merged, ready=ready)
    result = run(v2_input)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["ready_before_merge", "closed_unmerged", "head_changed", "order", "net_base",
                                    "missing_files", "unexplained_total", "old_review"])
def test_stacked_delivery_does_not_assume_predecessor_convergence(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    merged = failure == "old_review"
    stacked(v2_input, merged=merged, ready=merged)
    predecessor = v2_input["predecessor_pulls"][0]
    if failure == "ready_before_merge":
        v2_input["pull"]["draft"] = False
    elif failure == "closed_unmerged":
        predecessor["state"] = "closed"
    elif failure == "head_changed":
        predecessor["head"]["sha"] = "e" * 40
    elif failure == "order":
        delivery = metadata(v2_input)["delivery"]
        delivery["merge_order"][-1] = 99
        set_metadata(v2_input, delivery=delivery)
    elif failure == "net_base":
        delivery = metadata(v2_input)["delivery"]
        delivery["net_diff_base_sha"] = SHA
        set_metadata(v2_input, delivery=delivery)
        v2_input["net_diff"]["base_sha"] = SHA
    elif failure == "missing_files":
        del v2_input["predecessor_files"]
    elif failure == "unexplained_total":
        v2_input["files"].append({"filename": "docs/hidden.md", "status": "added"})
    elif failure == "old_review":
        v2_input["reviews"][0]["submitted_at"] = "2026-10-14T00:10:00Z"
    result = run(v2_input)
    assert result.returncode == (2 if failure in {"missing_files", "unexplained_total"} else 1), result.stdout


def test_ready_without_native_review_is_metadata_only_not_merge_authorization(deployed_checker, v2_input):
    run, _ = deployed_checker
    stacked(v2_input, merged=True, ready=True)
    v2_input["reviews"] = []
    result = run(v2_input)
    assert result.returncode == 0, result.stdout
    assert "protocol current-HEAD review" in result.stdout
    assert "not merge authorization" in result.stdout


def test_draft_cannot_reuse_review_before_a_baseline_revision(deployed_checker, v2_input):
    run, _ = deployed_checker
    append_event(v2_input, baseline_revision(v2_input), 2)
    v2_input["reviews"] = [{"id": 1, "state": "APPROVED", "commit_id": HEAD,
                            "user": {"id": 1002}, "submitted_at": "2026-10-14T00:10:00Z"}]
    result = run(v2_input)
    assert result.returncode == 1


def review_revision(data, kind="baseline"):
    revision = baseline_revision(data)
    if kind == "baseline":
        revision["base_head"] = SHA
        revision["revision"].update(from_base_head=PRIOR, to_base_head=SHA)
        delivery = metadata(data)["delivery"]
        delivery["development_base_sha"] = SHA
        set_metadata(data, delivery=delivery)
        data["development_compare"].update(base_sha=SHA, merge_base_sha=SHA)
    else:
        revision["revision"]["kind"] = "correction"
        revision["revision"].pop("from_base_head")
        revision["revision"].pop("to_base_head")
    return append_event(data, revision, 2)


def test_revision_review_threshold_survives_handoff_and_resume(deployed_checker, v2_input, deployed_event_helper):
    run, _ = deployed_checker
    helper, plan = deployed_event_helper
    stacked(v2_input, merged=True, ready=True)
    v2_input["reviews"][0]["submitted_at"] = "2026-10-14T00:25:00Z"
    revision = review_revision(v2_input)
    before = run(v2_input)
    assert before.returncode == 1 and "recorded review is stale" in before.stdout, before.stdout + before.stderr
    event = child_event(v2_input, "handoff", 3, revision)
    event.pop("revision")  # The real handoff and resume templates have no revision field.
    helper.verify_predecessors(plan, helper.validate_event(event))
    handoff = append_event(v2_input, event, 3)
    handoff["updated_at"] = "2026-10-14T00:45:00Z"
    event = child_event(v2_input, "resume", 4, handoff, session_id="run-2")
    helper.verify_predecessors(plan, helper.validate_event(event))
    resumed = append_event(v2_input, event, 4)
    resumed["updated_at"] = "2026-10-14T00:50:00Z"
    set_metadata(v2_input, session_id="run-2")
    result = run(v2_input)
    assert result.returncode == 1 and "recorded review is stale" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("kind", ["baseline", "correction"])
@pytest.mark.parametrize("route", ["resume", "handoff_claim", "release_claim", "reassign", "resumed_reassign"])
@pytest.mark.parametrize("review_at,expected", [("00:25:00", 1), ("00:30:00", 0), ("00:40:00", 0)])
def test_review_revision_timestamp_is_inherited_by_every_successor(deployed_checker, v2_input, deployed_event_helper, kind, route, review_at, expected):
    run, _ = deployed_checker
    helper, plan = deployed_event_helper
    stacked(v2_input, merged=True, ready=True)
    v2_input["reviews"][0].update(user={"id": 3001}, submitted_at=f"2026-10-14T{review_at}Z")
    predecessor = review_revision(v2_input, kind)
    if route != "reassign":
        terminal_kind = "release" if route == "release_claim" else "handoff"
        event = child_event(v2_input, terminal_kind, 3, predecessor)
        event.pop("revision")
        helper.verify_predecessors(plan, helper.validate_event(event))
        predecessor = append_event(v2_input, event, 3)
        predecessor["updated_at"] = "2026-10-14T00:45:00Z"
    if route in {"resume", "resumed_reassign"}:
        event = child_event(v2_input, "resume", 4, predecessor, session_id="run-2")
        helper.verify_predecessors(plan, helper.validate_event(event))
        predecessor = append_event(v2_input, event, 4)
        predecessor["updated_at"] = "2026-10-14T00:50:00Z"
        set_metadata(v2_input, session_id="run-2")
    if route in {"reassign", "resumed_reassign"}:
        event, _ = reassignment(v2_input, predecessor, predecessor["id"] + 1)
        helper.verify_predecessors(plan, helper.validate_event(event))
    elif route in {"handoff_claim", "release_claim"}:
        event = child_event(v2_input, "claim", 4, predecessor, session_id="run-2", expected_handoff="pull-request")
        for field in ("head_sha", "release_mode"):
            event.pop(field, None)
        helper.verify_predecessors(plan, helper.validate_event(event))
        claim = append_event(v2_input, event, 4)
        claim["updated_at"] = "2026-10-14T00:50:00Z"
        v2_input["claim_comments"] = {claim["url"]: claim}
        set_metadata(v2_input, session_id="run-2", claim_urls=[claim["url"]])
    result = run(v2_input)
    assert result.returncode == expected, result.stdout + result.stderr
    if expected == 1:
        assert "recorded review is stale" in result.stdout


def test_claim_cannot_expand_scope_through_a_correction_revision(deployed_checker, v2_input):
    run, _ = deployed_checker
    event = baseline_revision(v2_input)
    event["revision"]["kind"] = "correction"
    event["revision"].pop("from_base_head")
    event["revision"].pop("to_base_head")
    event["base_head"] = SHA
    event["scope"].append("docs/**")
    append_event(v2_input, event, 2)
    delivery = metadata(v2_input)["delivery"]
    delivery["development_base_sha"] = SHA
    set_metadata(v2_input, delivery=delivery)
    v2_input["development_compare"].update(base_sha=SHA, merge_base_sha=SHA)
    result = run(v2_input)
    assert result.returncode == 1


@pytest.mark.parametrize("failure", ["file_cap", "duplicate_commits", "last_commit", "checkpoint"])
def test_truncated_comparisons_and_wrong_checkpoint_cannot_pass_offline_formal(deployed_checker, v2_input, failure):
    run, _ = deployed_checker
    if failure == "file_cap":
        v2_input["net_diff"]["files"] = [{"filename": f"src/{n}.py", "status": "added"} for n in range(300)]
    elif failure == "duplicate_commits":
        v2_input["development_compare"]["commits"] = [HEAD, HEAD]
    elif failure == "last_commit":
        v2_input["development_compare"]["commits"] = [PRIOR]
    else:
        handoff = append_event(v2_input, child_event(v2_input, "handoff", 2, head_sha=PRIOR), 2)
        append_event(v2_input, child_event(v2_input, "resume", 3, handoff, session_id="run-2", head_sha=PRIOR), 3)
        set_metadata(v2_input, session_id="run-2")
    result = run(v2_input)
    assert result.returncode == (1 if failure == "checkpoint" else 2), result.stdout


def test_draft_inherited_added_path_can_be_current_net_modified(deployed_checker, v2_input):
    run, _ = deployed_checker
    stacked(v2_input, prior_files=[{"filename": "src/api.py", "status": "added"}])
    v2_input["files"] = [{"filename": "src/api.py", "status": "added"}]
    result = run(v2_input)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("rebuilt", [False, True])
def test_squash_or_rebase_requires_current_baseline_scope_and_fresh_review(deployed_checker, v2_input, rebuilt):
    run, _ = deployed_checker
    stacked(v2_input, merged=True, ready=True)
    # A squash result has a different commit identity; old ancestry alone does not prove convergence.
    v2_input["predecessor_pulls"][0]["merge_commit_sha"] = "e" * 40
    if rebuilt:
        revision = baseline_revision(v2_input)
        revision["base_head"] = SHA
        revision["revision"].update(from_base_head=PRIOR, to_base_head=SHA)
        delivery = metadata(v2_input)["delivery"]
        delivery["development_base_sha"] = SHA
        set_metadata(v2_input, delivery=delivery)
        v2_input["development_compare"].update(base_sha=SHA, merge_base_sha=SHA)
        append_event(v2_input, revision, 2)
    else:
        extra = {"filename": "docs/predecessor.md", "status": "added"}
        v2_input["net_diff"]["files"].append(extra)
        v2_input["files"].append(copy.deepcopy(extra))
    result = run(v2_input)
    assert result.returncode == (0 if rebuilt else 1), result.stdout


def test_rename_requires_old_and_new_paths_in_active_claim_scope(deployed_checker, v2_input):
    run, _ = deployed_checker
    item = {"filename": "src/api.py", "previous_filename": "docs/secret.md", "status": "renamed"}
    v2_input["files"] = [item]
    v2_input["net_diff"]["files"] = [copy.deepcopy(item)]
    result = run(v2_input)
    assert result.returncode == 1


@pytest.mark.parametrize("ancestor", [True, False])
def test_multiple_predecessor_order_needs_actual_fixed_head_ancestry(deployed_checker, v2_input, ancestor):
    run, _ = deployed_checker
    stacked(v2_input)
    second = copy.deepcopy(v2_input["predecessor_pulls"][0])
    second.update(number=10)
    second["head"]["sha"] = "e" * 40
    v2_input["predecessor_pulls"].append(second)
    v2_input["predecessor_files"]["10"] = [{"filename": "docs/second.md", "status": "added"}]
    v2_input["files"] += copy.deepcopy(v2_input["predecessor_files"]["10"])
    delivery = metadata(v2_input)["delivery"]
    delivery.update(development_base_sha="e" * 40, net_diff_base_sha="e" * 40,
                    predecessors=delivery["predecessors"] + [{"pull_number": 10, "head_sha": "e" * 40}],
                    merge_order=[11, 10, 12])
    set_metadata(v2_input, delivery=delivery)
    event = yaml.safe_load(v2_input["claim_comments"][CLAIM]["body"])
    event["base_head"] = "e" * 40
    v2_input["claim_comments"][CLAIM]["body"] = yaml.safe_dump(event, sort_keys=False)
    for field in ("development_compare", "net_diff"):
        v2_input[field].update(base_sha="e" * 40, merge_base_sha="e" * 40)
    v2_input["predecessor_compares"] = [{"base_sha": PRIOR, "head_sha": "e" * 40,
                                       "merge_base_sha": PRIOR if ancestor else SHA,
                                       "status": "ahead" if ancestor else "diverged", "commits": ["e" * 40],
                                       "files": [], "complete": True}]
    result = run(v2_input)
    assert result.returncode == (0 if ancestor else 1), result.stdout
