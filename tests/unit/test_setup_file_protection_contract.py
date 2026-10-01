"""Decision fixtures for preserving project files during setup.

Agent pressure evaluations exercise the written procedure. These assertions
keep the reviewable decision table from silently treating ambiguity as an
automatic edit.
"""


def _cases(load_eval):
    cases = load_eval("setup/file-protection-cases.yml")["cases"]
    return {case["id"]: case for case in cases}


def test_ambiguous_files_and_stale_approval_stop_for_a_choice(load_eval):
    cases = _cases(load_eval)
    required = {
        "dirty-entry-file",
        "duplicate-block",
        "broken-marker",
        "similar-unmanaged-rule",
        "suspicious-symlink",
        "unknown-template-owner",
        "approval-digest-drift",
        "missing-managed-baseline",
    }

    assert required <= cases.keys()
    for case_id in required:
        case = cases[case_id]
        assert case["decision"] == "stop-and-ask", case_id
        assert case["write_allowed"] is False, case_id
        assert case["next_action"], case_id


def test_managed_markdown_candidates_preserve_outer_bytes(load_eval, fixture_bytes):
    from shared.scripts.managed_block import plan_managed_block

    cases = _cases(load_eval)
    for case_id in (
        "clean-lf-entry",
        "clean-crlf-entry",
        "clean-bom-entry",
        "clean-no-final-newline-entry",
    ):
        case = cases[case_id]
        before = fixture_bytes(case["fixture"])
        result = plan_managed_block(before, "Project collaboration entry", "0.1.0")

        assert case["decision"] == "show-candidate-and-request-diff-approval", case_id
        assert case["write_allowed"] is False, case_id
        assert result.candidate.startswith(before), case_id


def test_remote_same_name_and_network_uncertainty_are_not_overwrite_permission(load_eval):
    cases = _cases(load_eval)

    assert cases["same-name-unmanaged-ruleset"]["decision"] == "stop-and-ask"
    assert cases["same-name-unmanaged-ruleset"]["write_allowed"] is False
    assert cases["network-result-unknown"]["decision"] == "query-stable-id-before-retry"
    assert cases["network-result-unknown"]["write_allowed"] is False


def test_dirty_entry_guidance_separates_preservation_from_commit_ownership(repo_root):
    guidance = (repo_root / "skills/github-collaboration-setup/references/local-configuration.md").read_text(
        encoding="utf-8"
    )

    assert "preserving the original bytes" in guidance
    assert "whether those uncommitted edits enter this governance Commit" in guidance
    assert "proposed staged diff" in guidance
    assert "inseparable hunk" in guidance
    assert "Do not stage the whole file" in guidance


def test_each_case_has_observable_state_and_recovery_direction(load_eval):
    cases = load_eval("setup/file-protection-cases.yml")["cases"]

    assert len(cases) == len({case["id"] for case in cases})
    assert all(case["resource"] and case["observed_state"] for case in cases)
    assert all(case["next_action"] for case in cases)
