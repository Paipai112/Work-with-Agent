from pathlib import Path
import json

from jsonschema import Draft202012Validator, FormatChecker


def _cases(load_eval):
    document = load_eval("daily/permission-cases.yml")
    assert document["version"] == 1
    cases = {case["id"]: case for case in document["cases"]}
    assert len(cases) == len(document["cases"])
    return cases


def test_permission_cases_cover_member_default_and_frozen_ceiling(load_eval):
    cases = _cases(load_eval)

    assert cases["admin-without-delegation"]["effective_role"] == "member"
    assert cases["maintain-leader-account-upgraded-admin"]["effective_permission"] == "maintain"
    assert cases["admin-leader-account-downgraded-maintain"]["effective_permission"] == "maintain"
    assert cases["admin-leader-account-downgraded-write"]["effective_role"] == "member"
    assert cases["permission-query-failed"]["effective_role"] == "read-only"


def test_permission_cases_bind_grant_to_relevant_identity_and_source(load_eval):
    cases = _cases(load_eval)
    for case_id in (
        "different-repository-id",
        "different-hostname",
        "different-default-branch",
        "different-controlled-account",
        "different-actor",
        "untrusted-working-branch-delegation",
        "revoked-delegation",
    ):
        assert cases[case_id]["effective_role"] != "leader", case_id

    valid = cases["maintain-leader"]
    assert valid["authorization_source"]["repository"] == {
        "hostname": "github.com",
        "repository_id": 501,
        "owner": "acme",
        "name": "payments",
        "default_branch": "main",
        "default_branch_source_sha": "a" * 40,
    }
    assert valid["authorization_source"]["ref"] == "default-branch"
    assert valid["effective_role"] == "leader"
    assert valid["effective_permission"] == "maintain"


def test_permission_cases_keep_session_out_of_grant_and_protection_in_force(load_eval):
    cases = _cases(load_eval)
    assert cases["same-actor-new-session"]["effective_role"] == "leader"
    assert cases["same-actor-new-session"]["claim_write"] == "resume-required"
    assert cases["protected-branch-forbids-direct-write"]["effective_role"] == "leader"
    assert cases["protected-branch-forbids-direct-write"]["branch_write"] == "blocked-by-protection"


def test_permission_cases_have_nonempty_explanations_and_complete_inputs(load_eval):
    cases = _cases(load_eval)
    assert len(cases) >= 15
    for case in cases.values():
        assert case["reason"].strip(), case["id"]
        assert case["repository"]["hostname"] and case["repository"]["repository_id"]
        assert case["account"]["id"] and case["account"]["permission"]
        assert case["actor"]["actor_id"] and case["actor"]["controlled_by_id"]
        assert case["actor"]["session_id"]
        assert case["effective_role"] in ("read-only", "member", "leader")


def test_all_authorization_records_are_complete_and_schema_valid(load_eval, repo_root: Path):
    authorization_schema = json.loads((repo_root / "schemas/authorization.schema.json").read_text(encoding="utf-8"))
    config_schema = json.loads((repo_root / "schemas/config.schema.json").read_text(encoding="utf-8"))
    authorization_validator = Draft202012Validator(authorization_schema, format_checker=FormatChecker())
    config_validator = Draft202012Validator(config_schema, format_checker=FormatChecker())
    for case in _cases(load_eval).values():
        assert not list(authorization_validator.iter_errors(case["authorization"])), case["id"]
        assert not list(config_validator.iter_errors(case["config"])), case["id"]
        assert case["authorization_source"]["path"] == case["config"]["managed_paths"]["authorization"]


def test_fixture_role_expectations_match_the_permission_contract(load_eval):
    # This checks fixture consistency, not behavior of an Agent or an unavailable CLI.
    rank = {permission: index for index, permission in enumerate(("read", "triage", "write", "maintain", "admin"))}
    for case in _cases(load_eval).values():
        repo = case["repository"]
        source = case["authorization_source"]
        auth_repo = case["authorization"]["repository"]
        account = case["account"]
        actor = case["actor"]
        source_trusted = (
            source["ref"] == "default-branch"
            and source["path"] == case["config"]["managed_paths"]["authorization"]
            and source["read_at_sha"] == repo["head_sha"]
            and source["approval_verified"] is True
            and source["repository"] == auth_repo
            and all(auth_repo[key] == repo[key] for key in ("hostname", "repository_id", "default_branch"))
        )
        if account["permission"] not in rank or not source_trusted:
            assert (case["effective_role"], case["effective_permission"]) == ("read-only", "none"), case["id"]
            continue

        matches = [
            grant for grant in case["authorization"]["leader_delegations"]
            if grant["status"] == "active"
            and grant["controlled_by_id"] == account["id"] == actor["controlled_by_id"]
            and grant["controlled_by"] == account["login"] == actor["controlled_by"]
            and grant["actor_id"] == actor["actor_id"]
        ]
        if account["permission"] in ("maintain", "admin") and len(matches) == 1:
            expected = min((matches[0]["permission_ceiling"], account["permission"]), key=rank.get)
            assert (case["effective_role"], case["effective_permission"]) == ("leader", expected), case["id"]
        else:
            expected = min(("write", account["permission"]), key=rank.get)
            assert (case["effective_role"], case["effective_permission"]) == ("member", expected), case["id"]


def test_nondefault_authorization_path_is_valid_and_used(load_eval, repo_root: Path):
    case = _cases(load_eval)["configured-nondefault-authorization-path"]
    schema = json.loads((repo_root / "schemas/config.schema.json").read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(case["config"]))
    assert case["config"]["managed_paths"]["authorization"] == ".github/agent-collaboration/leader-grants.yml"
    assert case["authorization_source"]["path"] == case["config"]["managed_paths"]["authorization"]
    assert case["effective_role"] == "leader"


def test_permission_reference_exists(repo_root: Path):
    assert (repo_root / "skills/github-collaboration/references/identity-and-permissions.md").is_file()


def test_daily_entrypoint_routes_to_permission_reference(skill_text):
    text = skill_text("github-collaboration/SKILL.md")
    assert "references/identity-and-permissions.md" in text
