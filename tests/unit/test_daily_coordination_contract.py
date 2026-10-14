import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


EVENTS = ("claim", "handoff", "release", "resume")


def _cases(load_eval):
    document = load_eval("daily/coordination-cases.yml")
    assert document["version"] == 1
    cases = {case["id"]: case for case in document["cases"]}
    assert len(cases) == len(document["cases"])
    return cases


def test_coordination_cases_never_treat_comments_as_atomic_lock(load_eval):
    cases = _cases(load_eval)
    assert cases["simultaneous-overlapping-claims"]["decision"] == "stop-for-leader-resolution"
    assert cases["old-session-silent"]["decision"] == "read-only-until-confirmed-stopped"
    assert cases["resume-after-handoff"]["required_links"] == [
        "previous_event_id", "github_comment_id", "branch", "head_sha"
    ]


def test_coordination_cases_cover_post_comment_readback_and_push_recheck(load_eval):
    cases = _cases(load_eval)
    assert cases["claim-post-then-conflict"]["decision"] == "stop-for-leader-resolution"
    assert cases["claim-post-then-conflict"]["post_steps"] == [
        "capture-comment-id-and-url", "reread-related-claims-and-prs", "compare-overlapping-scopes"
    ]
    assert cases["push-after-claim-moved"]["decision"] == "stop-no-push"
    assert cases["push-after-remote-head-moved"]["decision"] == "stop-no-force-push"
    assert cases["push-after-remote-head-moved"]["before_push"] == [
        "recheck-active-claim", "fetch-and-compare-remote-head"
    ]


def test_coordination_cases_require_explicit_transfer_or_process_stop(load_eval):
    cases = _cases(load_eval)
    assert cases["resume-after-handoff"]["decision"] == "resume-after-readback"
    assert cases["resume-after-explicit-stop"]["decision"] == "resume-after-readback"
    assert cases["same-actor-concurrent-sessions"]["decision"] == "stop-for-leader-resolution"
    assert cases["member-releases-others-claim"]["decision"] == "blocked-member-cannot-release-other"


def test_coordination_cases_reject_untrusted_event_envelopes_and_unproven_leader_release(load_eval):
    cases = _cases(load_eval)
    for case_id in (
        "comment-author-id-does-not-match-body",
        "comment-url-points-to-other-issue",
        "previous-comment-link-does-not-match-event",
        "leader-release-without-stop-proof",
        "leader-release-with-stale-delegation",
        "leader-own-stop-statement-is-not-proof",
        "proxy-release-required-fields-missing",
        "proxy-release-target-session-mismatch",
        "proxy-release-faked-evidence-author",
    ):
        assert cases[case_id]["decision"] == "reject-event-no-write", case_id
    assert cases["leader-release-with-current-authorization-and-own-assertion"]["decision"] == "reject-event-no-write"
    assert cases["same-account-agent-comment-without-direct-user-confirmation"]["decision"] == "read-only"
    assert cases["skill-schema-missing"]["decision"] == "read-only"
    assert cases["proxy-release-impersonates-target"]["decision"] == "reject-event-no-write"
    assert cases["resume-after-unverified-proxy-release"]["decision"] == "read-only"


def test_event_templates_validate_against_frozen_schema(repo_root: Path):
    schema = json.loads((repo_root / "schemas/collaboration-event.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    template_dir = repo_root / "skills/github-collaboration/templates/events"
    for event in EVENTS:
        data = yaml.safe_load((template_dir / f"{event}.yml").read_text(encoding="utf-8"))
        assert data["event"] == event
        assert not list(validator.iter_errors(data)), event
        assert data["event_id"].startswith("example-")
        assert data["actor_id"] == "backend-api"
        assert data["scope"] == ["src/api/**", "tests/api/**"]
    claim = yaml.safe_load((template_dir / "claim.yml").read_text(encoding="utf-8"))
    handoff = yaml.safe_load((template_dir / "handoff.yml").read_text(encoding="utf-8"))
    release = yaml.safe_load((template_dir / "release.yml").read_text(encoding="utf-8"))
    resume = yaml.safe_load((template_dir / "resume.yml").read_text(encoding="utf-8"))
    assert claim["previous_event_id"] is None
    assert handoff["previous_event_id"] == claim["event_id"]
    assert handoff["github_comment_id"] == 1001
    assert release["previous_event_id"] == handoff["event_id"]
    assert release["release_mode"] == "self"
    assert release["controlled_by_id"] == handoff["controlled_by_id"]
    assert release["actor_id"] == handoff["actor_id"]
    assert release["github_comment_id"] == 1002
    assert resume["previous_event_id"] == release["event_id"]
    assert resume["handoff_event_id"] == release["event_id"]
    assert resume["github_comment_id"] == 1003
    assert resume["head_sha"] == release["head_sha"]


def test_proxy_release_not_offered_in_v01(repo_root: Path):
    assert not (repo_root / "skills/github-collaboration/templates/events/proxy-release.yml").exists()


def _event_validator(repo_root):
    schema = json.loads((repo_root / "schemas/collaboration-event.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize("event", EVENTS)
def test_research_events_can_omit_code_branch_fields(repo_root, load_yaml, event):
    data = load_yaml(f"skills/github-collaboration/templates/events/{event}.yml")
    data["task_kind"] = "research"
    data["scope"] = ["decision: payment provider selection"]
    data["artifact_urls"] = ["https://github.com/acme/payments/issues/123#issuecomment-99"]
    for field in ("branch", "base_head", "head_sha"):
        data.pop(field, None)
    assert not list(_event_validator(repo_root).iter_errors(data))


@pytest.mark.parametrize("event", ["handoff", "release", "resume"])
def test_research_transfer_requires_durable_artifact(repo_root, load_yaml, event):
    data = load_yaml(f"skills/github-collaboration/templates/events/{event}.yml")
    data["task_kind"] = "research"
    for field in ("branch", "base_head", "head_sha"):
        data.pop(field, None)
    assert any("artifact_urls" in error.message for error in _event_validator(repo_root).iter_errors(data))


def test_research_claim_template_validates(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/research-claim.yml")
    assert not list(_event_validator(repo_root).iter_errors(data))
    assert data["expected_handoff"] == "accepted-result"


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("field", ["branch", "base_head"])
def test_code_events_still_require_branch_and_base(repo_root, load_yaml, event, field):
    data = load_yaml(f"skills/github-collaboration/templates/events/{event}.yml")
    data.pop(field)
    assert list(_event_validator(repo_root).iter_errors(data))


@pytest.mark.parametrize("event", ["handoff", "resume"])
def test_code_transfers_require_current_head(repo_root, load_yaml, event):
    data = load_yaml(f"skills/github-collaboration/templates/events/{event}.yml")
    data.pop("head_sha")
    assert list(_event_validator(repo_root).iter_errors(data))


def test_code_claim_cannot_substitute_result_acceptance_for_pr(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/claim.yml")
    data["expected_handoff"] = "accepted-result"
    assert list(_event_validator(repo_root).iter_errors(data))


def test_successor_claim_requires_published_predecessor_links(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/claim.yml")
    data["previous_event_id"] = "example-reassign-issue-123"
    validator = _event_validator(repo_root)
    assert list(validator.iter_errors(data))
    data["github_comment_id"] = 1005
    data["github_comment_url"] = "https://github.com/example-org/example-repo/issues/123#issuecomment-1005"
    assert not list(validator.iter_errors(data))


def test_reassign_template_identifies_leader_target_and_successor(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/reassign.yml")
    assert not list(_event_validator(repo_root).iter_errors(data))
    assert data["event"] == "reassign"
    assert data["actor_id"] != data["target"]["actor_id"]
    assert data["previous_event_id"] == data["target"]["claim_event_id"]
    assert data["old_process_status"] == "unknown"
    assert data["stop_evidence"] is None

    for field in ("target", "successor", "approval_url", "reason", "old_process_status"):
        invalid = deepcopy(data)
        invalid.pop(field)
        assert list(_event_validator(repo_root).iter_errors(invalid)), field
    for field in ("claim_event_id", "claim_comment_id", "claim_comment_url", "session_id"):
        invalid = deepcopy(data)
        invalid["target"].pop(field)
        assert list(_event_validator(repo_root).iter_errors(invalid)), field


def test_reassign_stop_and_identity_validation(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/reassign.yml")
    validator = _event_validator(repo_root)
    data["old_process_status"] = "stopped"
    assert list(validator.iter_errors(data))
    data["stop_evidence"] = "Current user directly confirmed office-session stopped."
    assert not list(validator.iter_errors(data))
    data["successor"]["actor_id"] = "member-01"
    assert list(validator.iter_errors(data))


def test_release_schema_rejects_proxy_mode(repo_root, load_yaml):
    data = load_yaml("skills/github-collaboration/templates/events/release.yml")
    data["release_mode"] = "leader-proxy"
    assert list(_event_validator(repo_root).iter_errors(data))


def test_entrypoint_routes_to_coordination_reference(skill_text):
    assert "references/claims-and-handoffs.md" in skill_text("github-collaboration/SKILL.md")


def test_coordination_reference_requires_bundled_schema_and_trusted_comment_envelope(skill_text):
    text = skill_text("github-collaboration/references/claims-and-handoffs.md")
    assert "references/schemas/collaboration-event.schema.json" in text
    assert "missing" in text.lower() and "read-only" in text.lower()
    # The instruction uses collector-normalized user_id/login, not GitHub's
    # nested user.id/user.login spelling. This checks documentation risk coverage,
    # not a model's actual compliance with envelope verification.
    for key in ("repository id", "issue", "id/url", "author id/login", "controlled_by_id", "controlled_by", "previous_event_id"):
        assert key in text.lower()
    assert "GET predecessors" in text
    assert "](event-helpers.md)" in text
    helper = skill_text("github-collaboration/references/event-helpers.md")
    for key in ("user_id", "login", "issue_number", "GET-verifies", "author/body"):
        assert key in helper
