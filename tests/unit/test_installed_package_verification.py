"""Compare installed bytes with pinned Git objects, not archive directory names."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def source_and_install(repo_root, tmp_path):
    source = tmp_path / "arbitrary-current-repository-name"
    source.mkdir()
    skill = "github-collaboration"
    shutil.copytree(repo_root / "skills" / skill, source / "skills" / skill)
    git(source, "init", "-q")
    git(source, "add", "--", "skills/github-collaboration")
    git(source, "-c", "user.name=Package verification fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "fixture: pin complete package bytes")
    sha = git(source, "rev-parse", "HEAD")
    install = tmp_path / "installed" / skill
    shutil.copytree(source / "skills" / skill, install)
    return source, sha, install


def verify(repo_root, source, sha, install):
    return subprocess.run([
        sys.executable, str(repo_root / "shared/scripts/verify_installed_skill.py"),
        "--source-repo", str(source), "--source-sha", sha,
        "--skill", "github-collaboration", "--installed", str(install),
    ], capture_output=True, text=True)


def test_identical_package_passes_against_git_objects_not_dirty_source(repo_root, source_and_install):
    source, sha, install = source_and_install
    (source / "skills/github-collaboration/SKILL.md").write_text("Uncommitted replacement is not trusted\n")
    result = verify(repo_root, source, sha, install)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "pass"
    assert report["source_sha"] == sha
    assert report["authorization_verified"] is False
    assert report["files_verified"] > 1


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra", "symlink"])
def test_drift_is_reported_without_repair(repo_root, source_and_install, mutation):
    source, sha, install = source_and_install
    path = install / "SKILL.md"
    original = path.read_bytes()
    if mutation == "changed":
        path.write_bytes(original + b"local change\n")
    elif mutation == "missing":
        path.rename(install.parent / "preserved-entry.md")
    elif mutation == "extra":
        (install / "unexpected.txt").write_bytes(b"retain this\n")
    else:
        target = install.parent / "preserved-entry.md"
        path.rename(target)
        path.symlink_to(target)
    before = {p.relative_to(install).as_posix(): ("link", str(p.readlink())) if p.is_symlink()
              else ("bytes", p.read_bytes()) for p in install.rglob("*") if p.is_symlink() or p.is_file()}
    result = verify(repo_root, source, sha, install)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] in {"fail", "unknown"}
    after = {p.relative_to(install).as_posix(): ("link", str(p.readlink())) if p.is_symlink()
             else ("bytes", p.read_bytes()) for p in install.rglob("*") if p.is_symlink() or p.is_file()}
    assert after == before


def test_floating_ref_is_not_an_immutable_source(repo_root, source_and_install):
    source, _, install = source_and_install
    result = verify(repo_root, source, "HEAD", install)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "unknown"


def test_git_replace_does_not_change_the_selected_object_bytes(repo_root, source_and_install):
    source, sha, install = source_and_install
    (source / "skills/github-collaboration/SKILL.md").write_text("replacement must not be read\n")
    git(source, "add", "--", "skills/github-collaboration/SKILL.md")
    git(source, "-c", "user.name=Package verification fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "fixture: replacement tree")
    replacement = git(source, "rev-parse", "HEAD")
    git(source, "replace", sha, replacement)
    result = verify(repo_root, source, sha, install)
    assert result.returncode == 0, result.stdout + result.stderr


def test_identical_but_broken_source_manifest_is_not_a_verified_package(repo_root, source_and_install):
    source, _, install = source_and_install
    path = source / "skills/github-collaboration/RESOURCE_MANIFEST.json"
    manifest = json.loads(path.read_text())
    manifest["resources"][0]["copied_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    (install / "RESOURCE_MANIFEST.json").write_bytes(path.read_bytes())
    git(source, "add", "--", "skills/github-collaboration/RESOURCE_MANIFEST.json")
    git(source, "-c", "user.name=Package verification fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "fixture: invalid manifest")
    result = verify(repo_root, source, git(source, "rev-parse", "HEAD"), install)
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "unknown"


def test_missing_promisor_object_is_not_automatically_downloaded(repo_root, source_and_install, tmp_path, monkeypatch):
    source, sha, install = source_and_install
    # Model the Git process boundary, not the verifier: only an explicitly
    # no-lazy-fetch read may fail locally without triggering a download.
    commands = tmp_path / "bin"
    commands.mkdir()
    sentinel = tmp_path / "automatic-download-attempt"
    fake = commands / "git"
    fake.write_text(
        f"#!{sys.executable}\nimport pathlib, sys\n"
        f"if '--no-lazy-fetch' not in sys.argv: pathlib.Path({str(sentinel)!r}).write_text('fetch')\n"
        "sys.exit(1)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ.get("PATH", ""))
    result = verify(repo_root, source, sha, install)
    assert result.returncode == 2
    assert not sentinel.exists(), "the readonly verifier allowed Git to download a missing object"
