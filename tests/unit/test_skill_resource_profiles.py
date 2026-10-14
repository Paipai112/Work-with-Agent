"""Public sync CLI boundaries for three explicitly selected product packages."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def sync(repo_root: Path, destination: Path, *extra: str):
    return subprocess.run([
        sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
        "--repo-root", str(repo_root), "--destination", str(destination), *extra,
    ], capture_output=True, text=True)


def test_unknown_package_does_not_inherit_setup_resources(repo_root, tmp_path):
    target = tmp_path / "misspelled-skill"
    result = sync(repo_root, target)
    assert result.returncode != 0
    assert "profile" in result.stderr.lower()
    assert not target.exists()


def test_check_profile_is_readonly_not_a_setup_package(repo_root, tmp_path):
    target = tmp_path / "github-collaboration-check"
    result = sync(repo_root, target)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((target / "RESOURCE_MANIFEST.json").read_text())
    assert manifest["profile"] == "github-collaboration-check"
    assert (target / "references/schemas/config.schema.json").is_file()
    assert not (target / "assets/templates").exists()
    assert not (target / "scripts/managed_block.py").exists()


def test_explicit_setup_profile_supports_an_isolated_output_directory(repo_root, tmp_path):
    target = tmp_path / "reviewed-output"
    result = sync(repo_root, target, "--profile", "github-collaboration-setup")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((target / "RESOURCE_MANIFEST.json").read_text())
    assert manifest["profile"] == "github-collaboration-setup"
    assert (target / "assets/templates/managed-blocks/AGENTS.md.block").is_file()
    assert (target / "scripts/managed_block.py").is_file()


def test_named_package_rejects_a_conflicting_profile_before_output(repo_root, tmp_path):
    target = tmp_path / "github-collaboration-check"
    result = sync(repo_root, target, "--profile", "github-collaboration-setup")
    assert result.returncode != 0
    assert not target.exists()


def test_internal_destination_symlink_is_rejected_before_any_resource_write(repo_root, tmp_path):
    target = tmp_path / "github-collaboration-check"
    target.mkdir()
    redirect = target / "user-owned"
    redirect.mkdir()
    (redirect / "note.txt").write_bytes(b"preserve\r\n")
    (target / "references").symlink_to(redirect, target_is_directory=True)
    result = sync(repo_root, target)
    assert result.returncode != 0
    assert "symbolic link" in result.stderr
    assert sorted(path.name for path in redirect.iterdir()) == ["note.txt"]
    assert (redirect / "note.txt").read_bytes() == b"preserve\r\n"
    assert not (target / "RESOURCE_MANIFEST.json").exists()


def test_verifier_rejects_even_an_internal_package_symlink(repo_root, tmp_path):
    target = tmp_path / "github-collaboration-check"
    result = sync(repo_root, target)
    assert result.returncode == 0, result.stderr
    (target / "SKILL.md").write_text("---\nname: github-collaboration-check\ndescription: Test\n---\n")
    (target / "linked.json").symlink_to(target / "references/schemas/config.schema.json")
    checked = subprocess.run([
        sys.executable, str(repo_root / "scripts/verify_skill_packages.py"),
        "--repo-root", str(repo_root), str(target),
    ], capture_output=True, text=True)
    assert checked.returncode != 0
    assert "symlink" in checked.stderr


@pytest.mark.parametrize("profile", ["github-collaboration", "github-collaboration-setup", "github-collaboration-check"])
def test_each_package_has_its_own_readonly_launch_and_byte_verification(repo_root, tmp_path, profile):
    target = tmp_path / profile
    result = sync(repo_root, target)
    assert result.returncode == 0, result.stderr
    for helper in ("run_pr_metadata_check.py", "verify_installed_skill.py"):
        copied = target / "scripts" / helper
        assert copied.is_file()
        help_result = subprocess.run([sys.executable, str(copied), "--help"],
                                     cwd=tmp_path, capture_output=True, text=True)
        assert help_result.returncode == 0, help_result.stderr
    if profile == "github-collaboration-check":
        assert not (target / "scripts/collaboration_event.py").exists()
        assert not (target / "templates/events").exists()


@pytest.mark.parametrize("profile", ["github-collaboration", "github-collaboration-setup"])
def test_construct_event_runs_from_an_isolated_package(repo_root, tmp_path, profile):
    target = tmp_path / profile
    result = sync(repo_root, target)
    assert result.returncode == 0, result.stderr
    fields = tmp_path / "fields.json"
    fields.write_text(json.dumps({"event_id": "isolated-package-claim"}))
    constructed = subprocess.run([
        sys.executable, str(target / "scripts/collaboration_event.py"), "construct",
        "--template", "claim", "--fields", str(fields),
    ], cwd=tmp_path, capture_output=True, text=True)
    assert constructed.returncode == 0, constructed.stdout + constructed.stderr
    report = json.loads(constructed.stdout)
    assert report["event"]["event_id"] == "isolated-package-claim"
    assert report["authorization_verified"] is False
    assert (target / "scripts/collaboration_scope.py").is_file()
    assert (target / "scripts/requirements-helpers.txt").read_bytes() == (repo_root / "shared/requirements-helpers.txt").read_bytes()


def test_setup_deploys_shared_helpers_as_real_project_candidates(repo_root, tmp_path):
    target = tmp_path / "github-collaboration-setup"
    result = sync(repo_root, target)
    assert result.returncode == 0, result.stderr
    deployed = target / "assets/templates/project/.github/agent-collaboration"
    expected = {
        "collaboration_event.py": "shared/scripts/collaboration_event.py",
        "collaboration_scope.py": "shared/scripts/collaboration_scope.py",
        "collaboration-event.schema.json": "schemas/collaboration-event.schema.json",
        "requirements-helpers.txt": "shared/requirements-helpers.txt",
    }
    for destination, source in expected.items():
        assert (deployed / destination).is_file(), destination
        assert (deployed / destination).read_bytes() == (repo_root / source).read_bytes()
    body = repo_root / "skills/github-collaboration/templates/events/claim.yml"
    validated = subprocess.run([
        sys.executable, str(deployed / "collaboration_event.py"), "validate", "--body", str(body),
    ], cwd=tmp_path, capture_output=True, text=True)
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert json.loads(validated.stdout)["authorization_verified"] is False


def test_duplicate_canonical_deployment_target_fails_before_output(repo_root, tmp_path):
    source = tmp_path / "source"
    for name in ("schemas", "templates", "shared", "skills/github-collaboration/templates/events"):
        shutil.copytree(repo_root / name, source / name)
    # A second handwritten copy must not silently override the shared source.
    duplicate = source / "templates/project/.github/agent-collaboration/collaboration_event.py"
    duplicate.write_text("raise RuntimeError('different canonical copy')\n")
    target = tmp_path / "github-collaboration-setup"
    result = subprocess.run([
        sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
        "--repo-root", str(source), "--destination", str(target),
    ], capture_output=True, text=True)
    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()
    assert not target.exists()
