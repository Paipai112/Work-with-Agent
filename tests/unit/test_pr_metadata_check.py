import importlib.util
import json

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


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
    update_metadata(data, skill_version="0.1.1")
    data["authorization"] = fixture_path("config/valid-authorization.yml").read_text().replace(
        "123456789", "123"
    ).replace("example-org", "sample").replace("example-repo", "repo")
    path = tmp_path / "yaml.json"
    path.write_text(json.dumps(data))
    result = run_metadata_check(path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_setup_template_candidates_accept_equivalent_list_indentation(
    run_metadata_check, fixture_path, repo_root, tmp_path
):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    templates = repo_root / "templates/project/.github/agent-collaboration"
    integration = "agent/release-coordination/issue-7-integration"
    config = (templates / "config.yml").read_text().replace(
        "label_namespace: agent-collaboration/", "label_namespace: project-agents/"
    ).replace("integration_branches: []", f"integration_branches:\n    - {integration}")
    authorization = (templates / "authorization.yml").read_text()
    for field, value in {
        "hostname": "github.com", "repository_id": "123", "owner": "sample",
        "name": "repo", "default_branch": "main", "default_branch_source_sha": "a" * 40,
    }.items():
        authorization = authorization.replace(f"{field}: __SETUP_REQUIRED__", f"{field}: {value}")
    assert "__SETUP_REQUIRED__" not in authorization
    update_metadata(
        data, skill_version=yaml.safe_load(config)["minimum_runtime_skill_version"],
        base_branch=integration,
    )
    data["pull"]["base"]["ref"] = integration
    data["authorization"] = authorization
    auth_schema = json.loads((repo_root / "schemas/authorization.schema.json").read_text())
    Draft202012Validator(auth_schema, format_checker=FormatChecker()).validate(
        yaml.safe_load(authorization)
    )
    config_schema = json.loads((repo_root / "schemas/config.schema.json").read_text())

    results = []
    for candidate in (config, config.replace("    - ", "  - ")):
        Draft202012Validator(config_schema, format_checker=FormatChecker()).validate(
            yaml.safe_load(candidate)
        )
        data["config"] = candidate
        result = run_case(data, run_metadata_check, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(result.stdout)
    assert results[0] == results[1]


def test_authorization_mapping_lists_accept_equivalent_root_indentation(
    run_metadata_check, fixture_path, tmp_path
):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    authorization = fixture_path("config/valid-authorization.yml").read_text().replace(
        "123456789", "123"
    ).replace("example-org", "sample").replace("example-repo", "repo")
    prefix, mappings = authorization.split("leader_delegations:\n")
    indentless = prefix + "leader_delegations:\n" + "\n".join(
        line[2:] for line in mappings.splitlines()
    ) + "\n"
    results = []
    for candidate in (authorization, indentless):
        data["authorization"] = candidate
        result = run_case(data, run_metadata_check, tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(result.stdout)
    assert results[0] == results[1]


@pytest.mark.parametrize(("original", "replacement", "message"), [
    ("  authorization: .github/agent-collaboration/authorization.yml\n", "",
     "trusted managed paths unsupported"),
    ("integration_branches: []", "integration_branches: false", "invalid integration branch policy"),
])
def test_edited_setup_config_candidates_keep_missing_field_and_type_checks(
    original, replacement, message, run_metadata_check, fixture_path, repo_root, tmp_path
):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    config = (repo_root / "templates/project/.github/agent-collaboration/config.yml").read_text()
    update_metadata(data, skill_version=yaml.safe_load(config)["minimum_runtime_skill_version"])
    assert original in config
    data["config"] = config.replace(original, replacement)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert message in result.stdout


@pytest.mark.parametrize(("field", "source", "line"), [
    ("config", "schema_version: 1\nschema_version: 1\n", 4),
    ("authorization", "schema_version: 1\nrepository: *shared\n", 4),
    ("authorization", "schema_version: 1\nrepository: &shared value\n", 4),
    ("authorization", "schema_version: 1\nrepository: !vault REDACTED_CANARY\n", 4),
    ("config", "schema_version: 1\n<<: *shared\n", 4),
    ("config", "schema_version: 1\n---\n", 4),
    ("config", "schema_version: 1\n...\n", 4),
    ("config", "schema_version: yes\n", 3),
    ("config", 'schema_version: "\\q_REDACTED_CANARY"\n', 3),
    ("config", "schema_version: 1\n bad: 2\n", 4),
    ("config", "managed_paths:\n  entry_files:\n  - AGENTS.md\n  entry_files: []\n", 6),
    ("authorization", "leader_delegations:\n- actor_id: release-coordination\n  actor_id: backend-api\n", 5),
])
def test_rejected_yaml_reports_original_line_without_echoing_values(
    field, source, line, run_metadata_check, fixture_path, tmp_path
):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data[field] = "# Candidate configuration\n\n" + source
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert f"{field} YAML:" in result.stdout
    assert f"line {line}" in result.stdout
    assert "REDACTED_CANARY" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr


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
    data["claim_comments"]["https://github.com/sample/repo/issues/8#issuecomment-2"] = {
        "user_id": 1001, "login": "developer", "issue_number": 8,
    }
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
    data["claim_comments"]["https://github.com/sample/repo/issues/8#issuecomment-2"] = {
        "user_id": 1001, "login": "developer", "issue_number": 8,
    }
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
    {"filename": ".agents/skills/x/SKILL.md", "status": "added"},
    {"filename": ".claude/skills/x/SKILL.md", "status": "added"},
    {"filename": ".pi/agent/skills/x/SKILL.md", "status": "added"},
    {"filename": ".pi/skills/x/SKILL.md", "status": "added"},
    {"filename": ".github/copilot-instructions.md", "status": "modified"},
    {"filename": ".github/actions/a/action.yml", "status": "added"},
    {"filename": "AGENTS.md", "status": "modified", "patch": "@@ -1 +1 @@\n+<!-- hide instructions"},
])
def test_instruction_reachability_and_template_paths_require_governance(file, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["files"].append(file)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert "governance files require a separate setup PR" in result.stdout


@pytest.mark.parametrize("entry", ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"])
@pytest.mark.parametrize("with_patch", [False, True])
def test_any_root_entry_edit_requires_governance(entry, with_patch, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    file = {"filename": entry, "status": "modified"}
    if with_patch:
        file["patch"] = "@@ -1 +1 @@\n-Run pytest tests/api\n+Run pytest tests/api -q"
    data["files"].append(file)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1, result.stdout
    assert "governance files require a separate setup PR" in result.stdout


@pytest.mark.parametrize("statement", ["Closes: #10", "CLOSES #10", "CLOSES: #10", "Fixes: #10", "Resolves: #10"])
def test_colon_and_uppercase_closing_keywords_are_counted(statement, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, closes_issues=[10])
    data["pull"]["body"] = data["pull"]["body"].replace("Closes #7", statement)
    data["issues"].append({"number": 10, "state": "open"})
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout
    update_metadata(data, closes_issues=[])
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert "closing statements differ from closes_issues" in result.stdout


@pytest.mark.parametrize("statement, closes", [("Closes:#10", []), ("Closes #7, #10", [7])])
def test_unsupported_closing_syntax_is_not_counted(statement, closes, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, closes_issues=closes)
    data["pull"]["body"] = data["pull"]["body"].replace("Closes #7", statement)
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("target", ["https://github.com/sample/repo/issues/10", "sample/repo#10"])
def test_colon_url_and_cross_repository_closing_syntax_is_rejected(target, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["pull"]["body"] = f"Closes: {target}\n" + data["pull"]["body"]
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1
    assert "cross-repository or URL closing syntax is unsupported" in result.stdout


@pytest.mark.parametrize("failure, message", [
    ("missing_mapping", "claim comments unverified"),
    ("invalid_mapping", "claim comments unverified"),
    ("missing_url", "claim comment does not exist or is unverifiable"),
    ("null", "claim comment does not exist or is unverifiable"),
    ("author", "claim comment author differs from controlling account"),
    ("issue", "claim comment issue mismatch"),
])
def test_claim_comments_must_be_verified(failure, message, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    url = "https://github.com/sample/repo/issues/7#issuecomment-1"
    if failure == "missing_mapping":
        del data["claim_comments"]
    elif failure == "invalid_mapping":
        data["claim_comments"] = []
    elif failure == "missing_url":
        del data["claim_comments"][url]
    elif failure == "null":
        data["claim_comments"][url] = None
    elif failure == "author":
        data["claim_comments"][url]["user_id"] = 1002
    else:
        data["claim_comments"][url]["issue_number"] = 8
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1, result.stdout
    assert message in result.stdout


def test_claim_comment_ids_are_sorted_and_reject_invalid_metadata(repo_root, fixture_path):
    spec = importlib.util.spec_from_file_location(
        "metadata_checker", repo_root / "templates/project/.github/agent-collaboration/check_pr_metadata.py"
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    update_metadata(data, claim_urls=[
        "https://github.com/sample/repo/issues/8#issuecomment-20",
        "https://github.com/sample/repo/issues/7#issuecomment-1",
        "https://github.com/sample/repo/issues/9#issuecomment-3",
    ])
    assert checker.claim_comment_ids(data["pull"]["body"]) == [1, 3, 20]
    with pytest.raises(ValueError, match="exactly one collaboration metadata block"):
        checker.claim_comment_ids("invalid metadata")


@pytest.mark.parametrize("valid", [False, True])
def test_report_always_states_verification_limits(valid, run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    if not valid:
        data["trusted_ref_verified"] = False
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == (0 if valid else 1)
    assert result.stdout.startswith(
        "::notice::metadata check does not verify human approval, effective account permissions, or real Skill loading\n"
    )
    assert "::notice::closing keywords in commit messages are not checked; read back Issue state after merge" in result.stdout


def test_missing_linked_issue_and_malformed_input_fail_cleanly(run_metadata_check, fixture_path, tmp_path):
    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["issues"] = []
    result = run_case(data, run_metadata_check, tmp_path)
    assert result.returncode == 1 and "linked Issue metadata unverified" in result.stdout
    result = run_case([], run_metadata_check, tmp_path)
    assert result.returncode == 1 and "malformed input" in result.stdout
