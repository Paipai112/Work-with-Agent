import json

import pytest


MARKER = "<!-- agent-collaboration:metadata\n"


def update_metadata(data, **changes):
    prefix, raw = data["pull"]["body"].split(MARKER)
    metadata = json.loads(raw.split("\n-->", 1)[0])
    metadata.update(changes)
    data["pull"]["body"] = prefix + MARKER + json.dumps(metadata, indent=2) + "\n-->"


def run_case(data, run_metadata_check, tmp_path):
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data))
    return run_metadata_check(path)


def test_valid_business_pr_passes(run_metadata_check, fixture_path):
    result = run_metadata_check(fixture_path("github/pr-valid.json"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("RESULT=pass\n")


def test_missing_metadata_fields_fail(run_metadata_check, fixture_path):
    result = run_metadata_check(fixture_path("github/pr-missing-fields.json"))
    assert result.returncode == 1
    assert "missing or unknown collaboration metadata fields" in result.stdout


def test_stale_review_and_branch_mismatch_fail(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["pull"]["head"]["ref"] = "agent/backend-api/issue-9-wrong"
    data["reviews"] = [{"state": "APPROVED", "commit_id": "c" * 40, "user": {"id": 1002}}]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "branch mismatch" in result.stdout
    assert "stale review SHA" in result.stdout


def test_unverified_trusted_ref_fails_closed(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["trusted_ref_verified"] = False
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "trusted default-branch source unverified" in result.stdout


def test_real_template_yaml_subset_is_accepted(run_metadata_check, fixture_path, repo_root, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["config"] = (repo_root / "templates/project/.github/agent-collaboration/config.yml").read_text()
    data["authorization"] = fixture_path("config/valid-authorization.yml").read_text().replace(
        "123456789", "123"
    ).replace("example-org", "sample").replace("example-repo", "repo")
    path = tmp_path / "yaml.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_duplicate_yaml_key_fails_closed(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["config"] = "schema_version: 1\nschema_version: 1\n"
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "metadata or trusted config unverified" in result.stdout


def test_yaml_alias_fails_closed(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["authorization"] = "schema_version: 1\nrepository: *shared\n"
    path = tmp_path / "alias.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "metadata or trusted config unverified" in result.stdout


def test_governance_pr_cannot_self_authorize_leader(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["files"] = [{"filename": ".github/agent-collaboration/authorization.yml"}]
    update_metadata(data, workflow="setup")
    path = tmp_path / "leader.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "invalid Leader claim" in result.stdout


def test_nonstandard_authorization_path_fails_instead_of_ignoring_grants(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["config"]["managed_paths"]["authorization"] = ".github/other/grants.yml"
    path = tmp_path / "moved.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "trusted managed paths unsupported" in result.stdout


def test_unknown_authorization_field_fails_closed(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["authorization"]["privileged_override"] = True
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "unknown trusted authorization field" in result.stdout


def test_renamed_governance_file_is_not_hidden_by_new_business_path(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["files"].append({
        "filename": "src/old-protocol.md", "previous_filename": ".github/agent-collaboration/PROTOCOL.md",
        "status": "renamed",
    })
    path = tmp_path / "rename.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 1
    assert "governance files require a separate setup PR" in result.stdout


def test_multiple_issues_can_close_in_one_pr(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, closes_issues=[7, 8], claim_urls=[
        "https://github.com/sample/repo/issues/7#issuecomment-1",
        "https://github.com/sample/repo/issues/8#issuecomment-2",
    ])
    data["pull"]["body"] = "Closes #8\n\n" + data["pull"]["body"]
    data["issues"].append({"number": 8, "state": "open"})
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("state", ["open", "closed"])
def test_related_claim_issue_need_not_be_closed_by_this_pr(state, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, claim_urls=[
        "https://github.com/sample/repo/issues/7#issuecomment-1",
        "https://github.com/sample/repo/issues/8#issuecomment-2",
    ])
    data["issues"].append({"number": 8, "state": state})
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("failure", ["missing", "pull_request", "no_primary", "duplicate"])
def test_claim_issue_links_must_be_unambiguous_and_verified(failure, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    primary = "https://github.com/sample/repo/issues/7#issuecomment-1"
    related = "https://github.com/sample/repo/issues/8#issuecomment-2"
    urls = [primary, related]
    if failure != "missing":
        data["issues"].append({"number": 8, "state": "open"})
    if failure == "pull_request":
        data["issues"][-1]["pull_request"] = {"url": "https://api.github.com/repos/sample/repo/pulls/8"}
    if failure == "no_primary":
        urls = [related]
    if failure == "duplicate":
        urls.append(primary)
    update_metadata(data, claim_urls=urls)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1, result.stdout


def test_partial_delivery_does_not_close_primary_issue(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, closes_issues=[])
    data["pull"]["body"] = data["pull"]["body"].replace("Closes #7", "Related to #7")
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("closed_issue", [7, 8])
def test_primary_and_closing_issues_must_still_be_open(closed_issue, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, closes_issues=[8])
    data["pull"]["body"] = data["pull"]["body"].replace("Closes #7", "Closes #8")
    data["issues"].append({"number": 8, "state": "open"})
    next(issue for issue in data["issues"] if issue["number"] == closed_issue)["state"] = "closed"
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1, result.stdout
    assert "not an open Issue" in result.stdout


@pytest.mark.parametrize("change, message", [
    ({"closes_issues": []}, "closing statements differ"),
    ({"closes_issues": [7, 7]}, "duplicate closes_issues"),
    ({"primary_issue": True}, "invalid primary_issue"),
    ({"controlled_by_id": 1002}, "differs from PR author"),
    ({"head_sha": "c" * 40}, "differs from current PR HEAD"),
    ({"skill_version": "0.0.9"}, "below minimum"),
    ({"claim_urls": ["https://github.com/other/repo/issues/7#issuecomment-1"]}, "claim URL"),
    ({"base_branch": "elsewhere"}, "mismatched PR base"),
])
def test_metadata_contradictions_fail(change, message, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, **change)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert message in result.stdout


@pytest.mark.parametrize("duplicate", ["block", "key", "fenced"])
def test_ambiguous_or_example_metadata_is_not_accepted(duplicate, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    body = data["pull"]["body"]
    if duplicate == "block":
        body += "\n\n" + MARKER + body.split(MARKER)[1]
    elif duplicate == "key":
        body = body.replace('"actor_id": "backend-api",', '"actor_id": "backend-api",\n"actor_id": "release-coordination",')
    else:
        prefix, raw = body.split(MARKER)
        body = prefix + chr(96) * 3 + "\n" + MARKER + raw + "\n" + chr(96) * 3
    data["pull"]["body"] = body
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1, result.stdout


@pytest.mark.parametrize("approved", [False, True])
def test_integration_base_requires_default_branch_policy(approved, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    integration = "agent/release-coordination/issue-5-integration"
    data["pull"]["base"]["ref"] = integration
    update_metadata(data, base_branch=integration)
    if approved:
        data["config"]["branch_policy"]["integration_branches"] = [integration]
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == (0 if approved else 1), result.stdout


def test_configured_authorization_filename_is_supported(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["config"]["managed_paths"]["authorization"] = ".github/agent-collaboration/grants.yml"
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("file", [
    {"filename": "docs/old-entry.md", "previous_filename": "AGENTS.md", "status": "renamed"},
    {"filename": "src/AGENTS.md", "status": "added"},
    {"filename": "AGENTS.override.md", "status": "added"},
    {"filename": ".claude/rules/development.md", "status": "added"},
    {"filename": "docs/pull_request_template.md", "status": "added"},
    {"filename": "PULL_REQUEST_TEMPLATE/change.md", "status": "added"},
    {"filename": "AGENTS.md", "status": "modified", "patch": "@@ -1 +1 @@\n+<!-- hide instructions"},
])
def test_instruction_reachability_and_template_paths_require_governance(file, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["files"].append(file)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert "governance files require a separate setup PR" in result.stdout


def test_unrelated_root_entry_content_remains_business_change(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["files"].append({
        "filename": "AGENTS.md", "status": "modified",
        "patch": "@@ -1 +1 @@\n-Run pytest tests/api\n+Run pytest tests/api -q",
    })
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


def test_missing_linked_issue_and_malformed_input_fail_cleanly(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["issues"] = []
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1 and "linked Issue metadata unverified" in result.stdout
    result = run_case([], run_metadata_check, tmp_path)
    assert result.returncode == 1 and "malformed input" in result.stdout
