from pathlib import Path


def _cases(load_eval):
    document = load_eval("daily/git-pr-cases.yml")
    assert document["version"] == 1
    cases = {case["id"]: case for case in document["cases"]}
    assert len(cases) == len(document["cases"])
    return cases


def test_git_pr_contract_blocks_broad_and_governance_changes(load_eval):
    cases = _cases(load_eval)
    assert cases["git-add-all"]["decision"] == "reject-and-list-explicit-paths"
    assert cases["governance-file-in-business-pr"]["decision"] == "split-and-route-to-setup"
    assert cases["remote-head-moved"]["decision"] == "stop-no-force-push"


def test_branch_and_stage_boundaries(load_eval):
    cases = _cases(load_eval)
    assert cases["wrong-branch-name"]["required_branch"] == "agent/backend-api/issue-51-timeout"
    assert cases["local-main-stale"]["command"] == (
        "git switch -c agent/backend-api/issue-55-payment-timeout-retry "
        "ffffffffffffffffffffffffffffffffffffffff"
    )
    assert cases["direct-default-work"]["decision"] == "stop-create-issue-branch"
    assert cases["git-add-all"]["approved_paths"] == ["src/api/retry.py", "tests/api/test_retry.py"]
    assert cases["scoped-add-a"]["decision"] == "allow-after-diff-review"
    assert cases["scoped-add-a"]["command"] == "git add -A -- src/api/retry.py tests/api/test_retry.py"
    assert cases["template-protocol-forbids-add-a"]["decision"] == "reject-use-git-add-explicit-paths"


def test_push_requires_fresh_claim_and_remote_head(load_eval):
    cases = _cases(load_eval)
    for case_id in ("stale-claim-before-push", "remote-head-moved"):
        assert cases[case_id]["before_push"] == ["recheck-active-claim", "fetch-and-compare-remote-head"]
    assert cases["stale-claim-before-push"]["decision"] == "stop-no-push"
    assert cases["uncertain-push-response"]["decision"] == "read-back-before-retry"
    assert cases["simultaneous-overlapping-claims"]["decision"] == "stop-for-leader-resolution"


def test_pr_and_governance_boundary(load_eval):
    cases = _cases(load_eval)
    assert cases["governance-file-in-business-pr"]["route"] == "github-collaboration-setup-independent-pr"
    assert cases["entry-reachability-in-business-pr"]["route"] == "github-collaboration-setup-independent-pr"
    assert cases["actions-trigger-on-push"]["decision"] == "disclose-before-push"
    assert cases["draft-pr-with-project-template"]["decision"] == "read-template-and-create-draft"


def test_git_pr_reference_and_template_exist(repo_root: Path, skill_text):
    assert (repo_root / "skills/github-collaboration/references/git-and-pull-requests.md").is_file()
    assert (repo_root / "skills/github-collaboration/templates/pull-request-body.md").is_file()
    assert "references/git-and-pull-requests.md" in skill_text("github-collaboration/SKILL.md")
    assert "仅当已确认项目协议显式允许" in skill_text("github-collaboration/SKILL.md")
