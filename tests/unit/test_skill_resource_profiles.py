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
