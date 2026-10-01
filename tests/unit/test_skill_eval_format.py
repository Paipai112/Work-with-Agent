from copy import deepcopy
from collections import Counter

import pytest


REQUIRED_SETUP_CASES = {
    "new-repository-bootstrap",
    "existing-maintain-bootstrap",
    "member-attempts-setup",
    "dirty-entry-file",
    "dirty-entry-staging-choice",
    "duplicate-managed-block",
    "workflow-before-approval",
    "same-name-unmanaged-ruleset",
    "lost-last-leader",
}

REQUIRED_DAILY_CASES = {
    "missing-skill",
    "duplicate-claim",
    "same-actor-two-sessions",
    "direct-default-branch",
    "broad-staging",
    "governance-file-in-business-pr",
    "self-approve-same-account",
    "head-changed-after-review",
    "network-uncertain-push",
}


def _has_text(value):
    return isinstance(value, str) and bool(value.strip())


def _has_text_list(value, minimum=1):
    return isinstance(value, list) and len(value) >= minimum and all(_has_text(item) for item in value)


def test_setup_evaluations_cover_security_boundaries(load_eval):
    document = load_eval("setup/scenarios.yml")
    cases = document["cases"]
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
    assert REQUIRED_SETUP_CASES <= set(ids)
    for case in cases:
        fixture = case["fixture"]
        assert _has_text(fixture["git_state"])
        assert _has_text(fixture["github_account_permission"])
        assert _has_text(fixture["default_branch_protection"])
        existing_files = fixture["existing_files"]
        assert isinstance(existing_files, dict) and existing_files
        assert all(_has_text(path) and _has_text(description) for path, description in existing_files.items())
        assert _has_text_list(fixture["approvals_granted"])
        assert _has_text(case["user_request"])
        assert _has_text_list(case["pressures"], minimum=3)
        assert _has_text_list(case["expected_behavior"])
        assert _has_text_list(case["forbidden_behavior"])


@pytest.mark.parametrize(
    ("field_path", "bad_value"),
    [
        (("fixture", "existing_files"), {}),
        (("fixture", "existing_files"), {"AGENTS.md": " "}),
        (("fixture", "approvals_granted"), []),
        (("fixture", "approvals_granted"), [" "]),
        (("expected_behavior",), "must stop"),
        (("expected_behavior",), [" "]),
        (("forbidden_behavior",), 42),
        (("forbidden_behavior",), [" "]),
        (("pressures",), "abc"),
        (("user_request",), " "),
    ],
)
def test_setup_evaluations_reject_incomplete_cases(load_eval, field_path, bad_value):
    document = deepcopy(load_eval("setup/scenarios.yml"))
    target = document["cases"][0]
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = bad_value

    with pytest.raises(AssertionError):
        test_setup_evaluations_cover_security_boundaries(lambda _path: document)


def test_setup_rubric_scores_evidence_and_decision(load_eval):
    rubric = load_eval("setup/rubric.yml")
    criteria = rubric["criteria"]
    ids = [criterion["id"] for criterion in criteria]

    assert len(ids) == len(set(ids))
    assert {"authorization", "file-safety", "remote-approval", "recovery"} <= set(ids)
    assert all(criterion["pass_evidence"] and criterion["violation_evidence"] for criterion in criteria)
    assert set(rubric["outcomes"]) == {"pass", "fail", "indeterminate"}
    assert Counter(rubric["result_fields"])["evidence"] == 1
    assert Counter(rubric["result_fields"])["violations"] == 1
    assert Counter(rubric["result_fields"])["decision"] == 1


def test_daily_evaluations_cover_write_boundaries(load_eval):
    document = load_eval("daily/scenarios.yml")
    cases = document["cases"]
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
    assert REQUIRED_DAILY_CASES <= set(ids)
    for case in cases:
        fixture = case["fixture"]
        assert _has_text(fixture["repository"])
        assert _has_text(fixture["default_branch"])
        assert len(fixture["protocol_sha"]) == 40
        assert all(character in "0123456789abcdef" for character in fixture["protocol_sha"])
        assert len(fixture["remote_head"]) == 40
        assert all(character in "0123456789abcdef" for character in fixture["remote_head"])

        account = fixture["authenticated_account"]
        assert _has_text(account["login"])
        assert isinstance(account["id"], int) and account["id"] > 0
        assert account["permission"] in {"read", "triage", "write", "maintain", "admin"}

        actor = fixture["actor"]
        for field in ("actor_id", "session_id", "runtime", "controlled_by"):
            assert _has_text(actor[field])
        assert actor["controlled_by"] == account["login"]

        records = fixture["active_authorization_records"]
        assert isinstance(records, list) and records
        for record in records:
            assert _has_text(record["actor_id"])
            assert isinstance(record["controlled_by_id"], int) and record["controlled_by_id"] > 0
            assert record["permission_ceiling"] in {"maintain", "admin"}
            assert record["status"] == "active"

        assert isinstance(fixture["installed_daily_skill"], bool)
        assert fixture["installed_daily_skill"] is (case["id"] != "missing-skill")
        assert _has_text(fixture["project_entry"])

        open_records = fixture["open_records"]
        for field in ("issues", "pull_requests", "claim_events"):
            assert isinstance(open_records[field], list)
            assert all(_has_text(item) for item in open_records[field])
        assert _has_text(fixture["local_git"]["branch"])
        assert isinstance(fixture["local_git"]["dirty_paths"], list)
        assert all(_has_text(path) for path in fixture["local_git"]["dirty_paths"])
        assert _has_text(case["user_request"])
        assert _has_text_list(case["pressures"], minimum=3)
        assert _has_text_list(case["expected_behavior"])
        assert _has_text_list(case["forbidden_behavior"])


@pytest.mark.parametrize(
    ("field_path", "bad_value"),
    [
        (("fixture", "protocol_sha"), "unknown"),
        (("fixture", "authenticated_account", "id"), "alice"),
        (("fixture", "actor", "session_id"), " "),
        (("fixture", "active_authorization_records"), []),
        (("fixture", "installed_daily_skill"), "yes"),
        (("fixture", "open_records", "claim_events"), "none"),
        (("fixture", "local_git", "dirty_paths"), [" "]),
        (("expected_behavior",), []),
        (("forbidden_behavior",), [" "]),
    ],
)
def test_daily_evaluations_reject_incomplete_cases(load_eval, field_path, bad_value):
    document = deepcopy(load_eval("daily/scenarios.yml"))
    target = document["cases"][0]
    for key in field_path[:-1]:
        target = target[key]
    target[field_path[-1]] = bad_value

    with pytest.raises(AssertionError):
        test_daily_evaluations_cover_write_boundaries(lambda _path: document)


def test_daily_rubric_scores_evidence_and_decision(load_eval):
    rubric = load_eval("daily/rubric.yml")
    criteria = rubric["criteria"]
    ids = [criterion["id"] for criterion in criteria]

    assert len(ids) == len(set(ids))
    assert {"skill-presence", "claim-ownership", "scoped-git", "review-eligibility", "uncertain-remote"} <= set(ids)
    assert all(criterion["pass_evidence"] and criterion["violation_evidence"] for criterion in criteria)
    assert set(rubric["outcomes"]) == {"pass", "fail", "indeterminate"}
    assert Counter(rubric["result_fields"])["evidence"] == 1
    assert Counter(rubric["result_fields"])["violations"] == 1
    assert Counter(rubric["result_fields"])["decision"] == 1
