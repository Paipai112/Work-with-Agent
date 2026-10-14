"""Exercise governance routing at the checker and renderer process boundaries.

These tests establish CLI behavior. They do not measure an Agent's decisions
from the frozen pressure prompts in tests/skill_eval/governance-routing.
"""

import json
import subprocess
import sys

import pytest


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-c", "user.name=Governance fixture", "-c", "user.email=fixture@example.invalid",
         *arguments],
        cwd=repository, text=True, capture_output=True, check=True,
    ).stdout


def tracked_entry(tmp_path, fixture_bytes, path, installation_link=False):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    entry = repository / path
    entry.parent.mkdir(parents=True, exist_ok=True)
    before = fixture_bytes("managed-block/existing-valid.md")
    if installation_link:
        before = before.replace(
            b"Keep this content unchanged.",
            b"[Install Skill](.github/agent-collaboration/INSTALL_SKILL.md)",
        )
    entry.write_bytes(before)
    git(repository, "add", "--", path)
    git(repository, "commit", "-m", "fixture baseline")
    return repository, entry


@pytest.mark.parametrize(("case_id", "path", "registered", "rename_to", "patch_available"), [
    ("registered-entry-outside-block", "AGENTS.md", "AGENTS.md", None, True),
    ("nested-entry-installation-link", "src/AGENTS.md", "AGENTS.md", None, True),
    ("registered-entry-rename", "docs/team-entry.md", "docs/team-entry.md", "docs/project-notes.md", True),
    ("registered-entry-missing-diff", "TEAM.md", "TEAM.md", None, False),
])
def test_real_entry_diffs_require_governance_review(
    case_id, path, registered, rename_to, patch_available,
    fixture_bytes, fixture_path, run_metadata_check, tmp_path,
):
    repository, entry = tracked_entry(
        tmp_path, fixture_bytes, path, installation_link=case_id == "nested-entry-installation-link"
    )
    if rename_to:
        git(repository, "mv", path, rename_to)
    elif case_id == "nested-entry-installation-link":
        entry.write_bytes(entry.read_bytes().replace(
            b"[Install Skill](.github/agent-collaboration/INSTALL_SKILL.md)", b"Installation link removed."
        ))
    else:
        entry.write_bytes(entry.read_bytes().replace(
            b"Keep this content unchanged.", b"Run pytest -q."
        ))
    change = git(repository, "diff", "--name-status", "--find-renames", "HEAD").strip().split("\t")
    file = {"filename": change[-1], "status": "renamed" if change[0].startswith("R") else "modified"}
    if rename_to:
        file["previous_filename"] = change[1]
    if patch_available:
        file["patch"] = git(repository, "diff", "HEAD", "--", path, rename_to or path)

    data = json.loads(fixture_path("github/pr-valid.json").read_text())
    data["config"]["managed_paths"]["entry_files"] = [registered]
    data["files"] = [file]
    payload = tmp_path / "entry-diff.json"
    payload.write_text(json.dumps(data))
    result = run_metadata_check(payload)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "governance files require a separate setup PR" in result.stdout


def test_dirty_entry_preview_preserves_user_bytes_and_index(
    fixture_bytes, repo_root, tmp_path,
):
    repository, entry = tracked_entry(tmp_path, fixture_bytes, "AGENTS.md")
    entry.write_bytes(entry.read_bytes().replace(
        b"# Existing project instructions", b"# User staged project instructions"
    ))
    git(repository, "add", "--", "AGENTS.md")
    entry.write_bytes(entry.read_bytes() + b"User unstaged note.\n")
    before = entry.read_bytes()
    staged_before = git(repository, "diff", "--cached", "--", "AGENTS.md")
    unstaged_before = git(repository, "diff", "--", "AGENTS.md")
    body = tmp_path / "block-body.md"
    body.write_text("Updated approved collaboration entry\n")
    candidate = tmp_path / "AGENTS.candidate.md"
    result = subprocess.run(
        [sys.executable, str(repo_root / "shared/scripts/managed_block.py"), "plan",
         "--path", str(entry), "--body-file", str(body), "--version", "0.1.1",
         "--candidate", str(candidate)],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "planned"
    start = b"<!-- github-agent-collaboration:start"
    end = b"<!-- github-agent-collaboration:end -->"
    after = candidate.read_bytes()
    assert after.split(start, 1)[0] == before.split(start, 1)[0]
    assert after.split(end, 1)[1] == before.split(end, 1)[1]
    assert entry.read_bytes() == before
    assert git(repository, "diff", "--cached", "--", "AGENTS.md") == staged_before
    assert git(repository, "diff", "--", "AGENTS.md") == unstaged_before
