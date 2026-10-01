import json

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


SCHEMAS = {
    "config.schema.json": "config/valid-config.yml",
    "authorization.schema.json": "config/valid-authorization.yml",
    "managed-resources.schema.json": "config/valid-managed-resources.yml",
    "collaboration-event.schema.json": "events/claim.yml",
}


def load_schema(repo_root, name):
    return json.loads((repo_root / "schemas" / name).read_text(encoding="utf-8"))


def errors_for(repo_root, name, data):
    validator = Draft202012Validator(
        load_schema(repo_root, name), format_checker=FormatChecker()
    )
    return list(validator.iter_errors(data))


def test_schemas_are_draft_2020_12_with_versioned_stable_ids(repo_root):
    for name in SCHEMAS:
        schema = load_schema(repo_root, name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == f"https://schemas.github-agent-collaboration.dev/v1/{name}"
        assert schema["additionalProperties"] is True


def test_valid_examples_satisfy_their_schema(repo_root, fixture_bytes):
    for name, fixture in SCHEMAS.items():
        data = yaml.safe_load(fixture_bytes(fixture))
        assert not errors_for(repo_root, name, data)

    resume = yaml.safe_load(fixture_bytes("events/resume.yml"))
    assert not errors_for(repo_root, "collaboration-event.schema.json", resume)


def test_config_requires_version_paths_labels_and_enforcement(repo_root):
    data = {
        "schema_version": 1,
        "protocol_version": "0.1.0",
        "minimum_runtime_skill_version": "0.1.0",
        "setup_skill_version": "0.1.0",
    }
    messages = " ".join(error.message for error in errors_for(repo_root, "config.schema.json", data))
    assert "managed_paths" in messages
    assert "label_namespace" in messages
    assert "enforcement" in messages


@pytest.mark.parametrize("branches, valid", [
    ([], True),
    (["agent/release-coordination/issue-7-integration"], True),
    (["*"], False),
    (["agent/backend-api/issue-7-fix", "agent/backend-api/issue-7-fix"], False),
    (["../other"], False),
])
def test_integration_branch_policy_requires_exact_unique_refs(repo_root, fixture_bytes, branches, valid):
    data = yaml.safe_load(fixture_bytes("config/valid-config.yml"))
    data["branch_policy"] = {"integration_branches": branches}
    errors = errors_for(repo_root, "config.schema.json", data)
    assert (not errors) is valid


def test_authorization_rejects_leader_without_frozen_ceiling(repo_root):
    data = {
        "schema_version": 1,
        "repository": {
            "hostname": "github.com",
            "repository_id": 42,
            "default_branch": "main",
            "default_branch_source_sha": "a" * 40,
        },
        "leader_delegations": [{
            "actor_id": "release-coordination",
            "controlled_by": "github-user",
            "controlled_by_id": 1234,
            "account_permission_at_grant": "maintain",
            "approval_evidence": {
                "github_pr_url": "https://github.com/example/repo/pull/1",
                "approved_by": "repository-owner",
                "approved_at": "2026-09-17T15:30:00+08:00",
                "approved_head_sha": "b" * 40,
            },
            "status": "active",
            "granted_at": "2026-09-17T15:30:00+08:00",
        }],
    }
    errors = errors_for(repo_root, "authorization.schema.json", data)
    assert any("permission_ceiling" in error.message for error in errors)


@pytest.mark.parametrize(
    ("account_permission_at_grant", "permission_ceiling"),
    [("read", "read"), ("read", "admin"), ("maintain", "admin")],
)
def test_authorization_rejects_grants_below_maintain_or_above_grant(
    repo_root, account_permission_at_grant, permission_ceiling
):
    data = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-authorization.yml").read_text(encoding="utf-8")
    )
    delegation = data["leader_delegations"][0]
    delegation["account_permission_at_grant"] = account_permission_at_grant
    delegation["permission_ceiling"] = permission_ceiling
    assert errors_for(repo_root, "authorization.schema.json", data)


def test_authorization_rejects_invalid_approval_url_and_timestamp(repo_root):
    data = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-authorization.yml").read_text(encoding="utf-8")
    )
    evidence = data["leader_delegations"][0]["approval_evidence"]
    evidence["github_pr_url"] = "not a URL"
    evidence["approved_at"] = "not a timestamp"
    messages = " ".join(error.message for error in errors_for(
        repo_root, "authorization.schema.json", data
    ))
    assert "uri" in messages
    assert "date-time" in messages


@pytest.mark.parametrize(
    "actor_id", ["codex", "claude-code", "pi", "leader", "member", "member-01", "backend-api-01"]
)
def test_authorization_rejects_platform_role_and_code_number_actor_ids(repo_root, actor_id):
    data = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-authorization.yml").read_text(encoding="utf-8")
    )
    data["leader_delegations"][0]["actor_id"] = actor_id
    assert errors_for(repo_root, "authorization.schema.json", data)


def test_collaboration_event_rejects_responsibility_name_with_encoded_suffix(repo_root):
    data = yaml.safe_load((repo_root / "tests/fixtures/events/claim.yml").read_text(encoding="utf-8"))
    data["actor_id"] = "backend-api-01"
    assert errors_for(repo_root, "collaboration-event.schema.json", data)


def test_authorization_rejects_non_github_permission(repo_root):
    data = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-authorization.yml").read_text(encoding="utf-8")
    )
    data["leader_delegations"][0]["permission_ceiling"] = "owner"
    assert errors_for(repo_root, "authorization.schema.json", data)


def test_authorization_proposal_is_valid_with_approved_head_before_merge(repo_root, fixture_bytes):
    data = yaml.safe_load(fixture_bytes("config/valid-authorization.yml"))
    evidence = data["leader_delegations"][0]["approval_evidence"]
    evidence.pop("merged_commit_sha", None)
    evidence["approved_head_sha"] = "c" * 40

    assert not errors_for(repo_root, "authorization.schema.json", data)


@pytest.mark.parametrize("approved_head_sha", [None, "not-a-commit-sha"])
def test_authorization_cannot_replace_approved_head_with_merge_evidence(
    repo_root, fixture_bytes, approved_head_sha
):
    data = yaml.safe_load(fixture_bytes("config/valid-authorization.yml"))
    evidence = data["leader_delegations"][0]["approval_evidence"]
    evidence.pop("approved_head_sha", None)
    evidence["merged_commit_sha"] = "b" * 40
    if approved_head_sha is not None:
        evidence["approved_head_sha"] = approved_head_sha

    errors = errors_for(repo_root, "authorization.schema.json", data)

    assert any("approved_head_sha" in error.message or
               list(error.path)[-1:] == ["approved_head_sha"] for error in errors)


@pytest.mark.parametrize("path", [
    r"C:\outside.md", "C:/outside.md", "C:outside.md",
    r"\\server\share\outside.md", "//server/share/outside.md",
    r"folder\file.md", r"..\outside.md", r"folder\..\outside.md",
    "/outside.md", "../outside.md", "folder/../outside.md", "folder/..",
])
def test_config_rejects_non_repository_relative_posix_paths(repo_root, fixture_bytes, path):
    data = yaml.safe_load(fixture_bytes("config/valid-config.yml"))
    data["managed_paths"].update(
        protocol=path, authorization=path, managed_resources=path, entry_files=[path]
    )

    errors = errors_for(repo_root, "config.schema.json", data)

    invalid_fields = {list(error.path)[1] for error in errors
                      if list(error.path)[:1] == ["managed_paths"]}
    assert invalid_fields == {"protocol", "authorization", "managed_resources", "entry_files"}


@pytest.mark.parametrize("path", [
    "AGENTS.md", ".github/agent-collaboration/PROTOCOL.md", "docs with spaces/说明.md",
])
def test_config_accepts_repository_relative_posix_paths(repo_root, fixture_bytes, path):
    data = yaml.safe_load(fixture_bytes("config/valid-config.yml"))
    data["managed_paths"]["entry_files"] = [path]

    assert not errors_for(repo_root, "config.schema.json", data)


@pytest.mark.parametrize("path, valid", [
    (".github/agent-collaboration/grants.yml", True),
    (".github/agent-collaboration/records/授权.yml", True),
    (".github/custom-governance/grants.yml", False),
    ("authorization.yml", False),
    (".github/agent-collaboration/./grants.yml", False),
    (".github/agent-collaboration//grants.yml", False),
    (".github/agent-collaboration/grants.yml/", False),
])
def test_governance_paths_match_runtime_directory_boundary(repo_root, fixture_bytes, path, valid):
    data = yaml.safe_load(fixture_bytes("config/valid-config.yml"))
    for field in ("protocol", "authorization", "managed_resources"):
        candidate = dict(data, managed_paths=dict(data["managed_paths"], **{field: path}))
        assert (not errors_for(repo_root, "config.schema.json", candidate)) is valid


def test_config_pr_template_path_is_optional_but_repository_relative(repo_root, fixture_bytes):
    data = yaml.safe_load(fixture_bytes("config/valid-config.yml"))
    assert "pull_request_template" not in data["managed_paths"]
    assert not errors_for(repo_root, "config.schema.json", data)

    data["managed_paths"]["pull_request_template"] = (
        ".github/PULL_REQUEST_TEMPLATE/agent-change.md"
    )
    assert not errors_for(repo_root, "config.schema.json", data)

    data["managed_paths"]["pull_request_template"] = "../outside.md"
    errors = errors_for(repo_root, "config.schema.json", data)
    assert any(
        list(error.path) == ["managed_paths", "pull_request_template"]
        for error in errors
    )


def test_managed_resources_requires_replay_safe_digests_and_baseline(repo_root):
    data = {
        "schema_version": 1,
        "installation_id": "install-001",
        "resources": [{"kind": "workflow", "stable_id": "agent-collaboration-check"}],
    }
    messages = " ".join(
        error.message for error in errors_for(repo_root, "managed-resources.schema.json", data)
    )
    assert "template_version" in messages
    assert "managed_fields_baseline_digest" in messages
    assert "applied_digest" in messages
    assert "baseline_reference" in messages


def test_claim_requires_account_event_and_base_head(repo_root):
    data = {"event": "claim", "actor_id": "backend-api", "session_id": "session-1"}
    errors = errors_for(repo_root, "collaboration-event.schema.json", data)
    missing = " ".join(error.message for error in errors)
    assert "controlled_by" in missing and "event_id" in missing and "base_head" in missing


def test_claim_requires_its_handoff_reference(repo_root):
    data = yaml.safe_load((repo_root / "tests/fixtures/events/claim.yml").read_text(encoding="utf-8"))
    data.pop("expected_handoff")
    assert any("expected_handoff" in error.message for error in errors_for(
        repo_root, "collaboration-event.schema.json", data
    ))


def test_resume_requires_handoff_and_comment_references(repo_root):
    data = yaml.safe_load((repo_root / "tests/fixtures/events/resume.yml").read_text(encoding="utf-8"))
    data.pop("handoff_event_id")
    data.pop("github_comment_id")
    messages = " ".join(error.message for error in errors_for(
        repo_root, "collaboration-event.schema.json", data
    ))
    assert "handoff_event_id" in messages
    assert "github_comment_id" in messages


def test_resume_rejects_invalid_comment_url(repo_root):
    data = yaml.safe_load((repo_root / "tests/fixtures/events/resume.yml").read_text(encoding="utf-8"))
    data["github_comment_url"] = "not a URL"
    assert any("uri" in error.message for error in errors_for(
        repo_root, "collaboration-event.schema.json", data
    ))
