"""Public sync CLI boundaries for three explicitly selected product packages."""
import json
from pathlib import Path
import subprocess
import sys


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
