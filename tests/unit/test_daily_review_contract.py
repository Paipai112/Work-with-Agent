from pathlib import Path


def _cases(load_eval):
    document = load_eval("daily/review-cases.yml")
    assert document["version"] == 1
    cases = {case["id"]: case for case in document["cases"]}
    assert len(cases) == len(document["cases"])
    return cases


def test_protocol_record_and_native_approval_are_separate(load_eval):
    cases = _cases(load_eval)
    assert cases["same-account-other-actor"]["native_approval_satisfied"] is False
    assert cases["same-account-other-actor"]["decision"] == "blocked-native-review"
    assert cases["implementation-actor-only-review"]["decision"] == "blocked"
    assert cases["new-commit-after-approval"]["decision"] == "re-review-current-head"
    assert cases["leader-account-now-write"]["decision"] == "member-no-merge"


def test_protocol_merge_requires_valid_current_head_approve(load_eval):
    cases = _cases(load_eval)
    assert cases["protocol-comment-only"]["decision"] == "blocked-no-protocol-approve"
    assert cases["request-changes-unresolved"]["decision"] == "blocked-open-request-changes"
    assert cases["request-changes-resolved-current-head"]["decision"] == "merge-eligible-after-other-gates"
    assert cases["valid-current-head-approve"]["decision"] == "merge-eligible-after-other-gates"


def test_protocol_comment_provenance_is_verified_from_github_envelope(load_eval):
    cases = _cases(load_eval)
    for case_id in (
        "reviewer-body-impersonation",
        "review-comment-wrong-repository",
        "review-comment-wrong-pr",
        "review-comment-id-url-mismatch",
        "reviewer-delegation-revoked",
    ):
        assert cases[case_id]["decision"] == "reject-untrusted-record", case_id
    valid = cases["valid-current-head-approve"]
    assert valid["verified_envelope"] == [
        "repository_id", "pull_request_number", "comment_id", "comment_url",
        "user.id", "user.login", "reviewer_account_id", "reviewer_account_login",
        "current_account_permission", "current_default_branch_delegation",
    ]


def test_merge_requires_fresh_current_head_evidence(load_eval):
    cases = _cases(load_eval)
    assert cases["stale-checks-after-new-head"]["decision"] == "recheck-current-head"
    assert cases["unresolved-conversation"]["decision"] == "blocked"
    assert cases["conflicting-claim"]["decision"] == "blocked"
    assert cases["governance-in-business-pr"]["decision"] == "split-and-route-to-setup"
    assert cases["merge-head-moved"]["decision"] == "blocked-head-mismatch"
    assert cases["merge-success-unverified"]["decision"] == "read-back-before-issue-update"


def test_recovery_keeps_work_and_resolves_unknown_remote_outcome(load_eval):
    cases = _cases(load_eval)
    assert cases["merge-timeout"]["decision"] == "read-back-before-retry"
    assert cases["push-diverged"]["decision"] == "preserve-work-and-coordinate"
    assert cases["post-merge-issue-update-failed"]["decision"] == "verify-merge-then-retry-idempotently"


def test_review_record_template_binds_provenance_and_head(load_yaml):
    record = load_yaml("skills/github-collaboration/templates/review-record.yml")
    assert record["record_type"] == "protocol-review"
    assert record["repository_id"] == 501
    assert record["pull_request_number"] == 87
    assert record["reviewed_head_sha"] == "a" * 40
    assert record["implementation_actor_id"] != record["reviewer_actor_id"]
    assert record["reviewer_account_id"]
    assert record["decision"] in ("comment", "approve", "request-changes")
    assert record["scope_reviewed"] and record["evidence"]
    assert record["reviewed_at"]


def test_review_route_and_procedures_exist(repo_root: Path, skill_text):
    skill = skill_text("github-collaboration/SKILL.md")
    assert "references/review-and-merge.md" in skill
    assert "references/failure-recovery.md" in skill
    assert (repo_root / "skills/github-collaboration/references/review-and-merge.md").is_file()
    assert (repo_root / "skills/github-collaboration/references/failure-recovery.md").is_file()
