import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def run_sync(repo_root: Path, destination: Path) -> Path:
    profile = destination.name if destination.name in {
        "github-collaboration", "github-collaboration-setup", "github-collaboration-check"
    } else "github-collaboration-setup"
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(repo_root),
            "--profile", profile,
            "--destination",
            str(destination),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return destination


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run_verifier(skill: Path, repo_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str((repo_root or skill.parent) / "scripts" / "verify_skill_packages.py"),
    ]
    if repo_root is not None:
        command.extend(["--repo-root", str(repo_root)])
    command.append(str(skill))
    return subprocess.run(command, text=True, capture_output=True, check=False)


@pytest.fixture
def tmp_skill(tmp_path: Path) -> Path:
    skill = tmp_path / "github-collaboration"
    skill.mkdir()
    return skill


def test_sync_is_reproducible(repo_root: Path, tmp_path: Path):
    first = run_sync(repo_root, tmp_path / "one")
    second = run_sync(repo_root, tmp_path / "two")
    assert tree_digest(first) == tree_digest(second)


def test_generated_python_cache_is_not_a_distributed_resource(repo_root: Path, tmp_path: Path):
    isolated = tmp_path / "source"
    for name in ("schemas", "templates", "shared", "skills/github-collaboration/templates/events"):
        shutil.copytree(repo_root / name, isolated / name)
    cache = isolated / "templates/project/.github/agent-collaboration/__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "checker.cpython-313.pyc").write_bytes(b"machine-specific-cache")
    package = tmp_path / "package"
    result = subprocess.run([
        sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
        "--repo-root", str(isolated), "--profile", "github-collaboration-setup", "--destination", str(package),
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((package / "RESOURCE_MANIFEST.json").read_text())
    assert all("__pycache__" not in resource["source"] for resource in manifest["resources"])
    assert not list(package.rglob("*.pyc"))
    # Run the independent verifier against that same noisy canonical source tree.
    (package / "SKILL.md").write_text("---\nname: package\ndescription: Test\n---\n")
    checked = subprocess.run([
        sys.executable, str(repo_root / "scripts/verify_skill_packages.py"),
        "--repo-root", str(isolated), str(package),
    ], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_sync_skill_writes_to_the_named_repository_skill(repo_root: Path, tmp_path: Path):
    isolated_repo = tmp_path / "repo"
    for name in ("schemas", "templates", "shared", "skills/github-collaboration/templates/events"):
        shutil.copytree(repo_root / name, isolated_repo / name)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(isolated_repo),
            "--skill",
            "github-collaboration",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    skill = isolated_repo / "skills" / "github-collaboration"
    assert result.returncode == 0, result.stderr
    assert (skill / "references" / "schemas" / "config.schema.json").is_file()
    assert (skill / "RESOURCE_MANIFEST.json").is_file()


def test_sync_refuses_to_overwrite_local_drift(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    copied_schema = skill / "assets" / "schemas" / "config.schema.json"
    copied_schema.write_text("local edit\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(repo_root),
            "--profile", "github-collaboration-setup",
            "--destination",
            str(skill),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "local drift" in result.stderr
    assert copied_schema.read_text(encoding="utf-8") == "local edit\n"


def test_sync_accepts_an_explicitly_reviewed_diff(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    copied_schema = skill / "assets" / "schemas" / "config.schema.json"
    copied_schema.write_text("reviewed local edit\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(repo_root),
            "--profile", "github-collaboration-setup",
            "--destination",
            str(skill),
            "--accept-reviewed-diff",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert copied_schema.read_bytes() == (repo_root / "schemas/config.schema.json").read_bytes()


def test_sync_refuses_a_symbolic_link_destination(repo_root: Path, tmp_path: Path):
    external = tmp_path / "external"
    external.mkdir()
    destination = tmp_path / "package"
    destination.symlink_to(external, target_is_directory=True)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(repo_root),
            "--profile", "github-collaboration-setup",
            "--destination",
            str(destination),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "symbolic link" in result.stderr
    assert not (external / "RESOURCE_MANIFEST.json").exists()


def test_sync_refuses_a_nested_link_that_escapes_destination(repo_root: Path, tmp_path: Path):
    external = tmp_path / "external"
    external.mkdir()
    destination = tmp_path / "package"
    destination.mkdir()
    (destination / "assets").symlink_to(external, target_is_directory=True)

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "sync_skill_resources.py"),
            "--repo-root",
            str(repo_root),
            "--profile", "github-collaboration-setup",
            "--destination",
            str(destination),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "escapes destination" in result.stderr
    assert not (external / "schemas").exists()


@pytest.mark.parametrize("source_path", [
    "schemas/z-linked.json", "templates/z-linked.md", "shared/scripts/managed_block.py",
    "schemas", "templates/project", "shared/scripts",
])
@pytest.mark.parametrize("existing_destination", [False, True])
def test_sync_rejects_canonical_symlinks_before_any_output(
    repo_root: Path, tmp_path: Path, source_path: str, existing_destination: bool
):
    isolated_repo = tmp_path / "repo"
    for directory in ("schemas", "templates", "shared", "skills/github-collaboration/templates/events"):
        shutil.copytree(repo_root / directory, isolated_repo / directory)
    source = isolated_repo / source_path
    external = tmp_path / "external-resource"
    if source.exists():
        source.rename(external)
    else:
        external.write_text("external bytes must not be copied\n", encoding="utf-8")
    source.symlink_to(external, target_is_directory=external.is_dir())
    destination = tmp_path / "package"
    if existing_destination:
        destination.mkdir()
        (destination / "user-note.md").write_text("preserve this\n", encoding="utf-8")
        before = tree_digest(destination)

    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts/sync_skill_resources.py"),
         "--repo-root", str(isolated_repo), "--profile", "github-collaboration-setup", "--destination", str(destination)],
        text=True, capture_output=True, check=False,
    )

    assert result.returncode != 0
    assert "canonical" in result.stderr and "symbolic link" in result.stderr
    if existing_destination:
        assert tree_digest(destination) == before
        assert list(destination.iterdir()) == [destination / "user-note.md"]
    else:
        assert not destination.exists()


def test_verifier_rejects_reference_outside_skill(repo_root: Path, tmp_skill: Path):
    (tmp_skill / "SKILL.md").write_text("Read [outside](../../secret.md)\n", encoding="utf-8")
    result = run_verifier(tmp_skill, repo_root)
    assert result.returncode != 0
    assert "escapes skill directory" in result.stderr


def test_verifier_rejects_image_reference_outside_skill(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "![outside](../../secret.png)\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "escapes skill directory" in result.stderr


def test_verifier_rejects_reference_style_link_outside_skill(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Read [the procedure][procedure].\n\n"
        "[procedure]: ../../outside.md\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "escapes skill directory" in result.stderr


def test_verifier_accepts_reference_style_link_inside_skill(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Read [the config schema][config].\n\n"
        "[config]: assets/schemas/config.schema.json \"Config schema\"\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("use", ["[outside]", "![outside]", ""])
@pytest.mark.parametrize(("target", "diagnostic"), [
    ("../../outside.md", "escapes skill directory"),
    ("references/missing.md", "referenced file does not exist"),
])
def test_verifier_checks_all_local_reference_definitions(
    repo_root: Path, tmp_path: Path, use: str, target: str, diagnostic: str
):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        f"{use}\n\n[outside]: <{target}>\n", encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert diagnostic in result.stderr


@pytest.mark.parametrize("use", ["[config]", "![config]"])
def test_verifier_accepts_shortcut_reference_inside_skill(repo_root: Path, tmp_path: Path, use: str):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        f"{use}\n\n[config]: assets/schemas/config.schema.json\n", encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode == 0, result.stderr


def test_verifier_rejects_a_missing_linked_file(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Read [missing](references/missing.md).\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "referenced file does not exist" in result.stderr


def test_verifier_checks_references_from_a_linked_document(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    references = skill / "references"
    references.mkdir(exist_ok=True)
    (references / "guide.md").write_text("Read [missing](missing.md).\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Read [the guide](references/guide.md).\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "referenced file does not exist" in result.stderr


def test_allow_missing_entrypoints_only_defers_an_absent_skills_directory(repo_root: Path, tmp_path: Path):
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "verify_skill_packages.py"),
            "--repo-root",
            str(tmp_path),
            "--allow-missing-skill-entrypoints",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "deferred" in result.stdout


def test_allow_missing_entrypoints_does_not_accept_existing_bad_skill(repo_root: Path, tmp_path: Path):
    skill = tmp_path / "skills" / "github-collaboration"
    skill.mkdir(parents=True)
    (skill / "notes.md").write_text("not an entrypoint\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "verify_skill_packages.py"),
            "--repo-root",
            str(tmp_path),
            "--allow-missing-skill-entrypoints",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SKILL.md" in result.stderr


def test_verifier_accepts_a_synced_self_contained_package(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Read [the config schema](assets/schemas/config.schema.json).\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)
    assert result.returncode == 0, result.stderr


def test_verifier_rejects_skill_entrypoint_symlink_outside_package(
    repo_root: Path, tmp_path: Path
):
    skill = run_sync(repo_root, tmp_path / "package")
    external = tmp_path / "external-skill.md"
    external.write_text(
        "---\nname: package\ndescription: External package.\n---\n",
        encoding="utf-8",
    )
    (skill / "SKILL.md").symlink_to(external)

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "symlink escapes skill directory" in result.stderr


def test_verifier_rejects_non_manifest_file_symlink_outside_package(
    repo_root: Path, tmp_path: Path
):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n",
        encoding="utf-8",
    )
    external = tmp_path / "external-guide.md"
    external.write_text("External instructions.\n", encoding="utf-8")
    references = skill / "references"
    references.mkdir(exist_ok=True)
    (references / "guide.md").symlink_to(external)

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "symlink escapes skill directory" in result.stderr


def test_verifier_rejects_frontmatter_name_mismatch(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: Other-Package\ndescription: Test package.\n---\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "frontmatter name must equal lowercase folder name" in result.stderr


def test_verifier_rejects_copied_resource_hash_drift(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n",
        encoding="utf-8",
    )
    (skill / "assets/schemas/config.schema.json").write_text("drift\n", encoding="utf-8")

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "copied resource hash drift" in result.stderr


def test_verifier_rejects_invalid_python_script_syntax(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n",
        encoding="utf-8",
    )
    (skill / "scripts/managed_block.py").write_text("def broken(:\n", encoding="utf-8")

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "invalid executable-script syntax" in result.stderr


def test_verifier_rejects_absolute_developer_machine_path(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n"
        "Do not embed /Users/example/work/project paths.\n",
        encoding="utf-8",
    )

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "absolute developer-machine path" in result.stderr


def test_verifier_rejects_an_incomplete_resource_manifest(repo_root: Path, tmp_path: Path):
    skill = run_sync(repo_root, tmp_path / "package")
    (skill / "SKILL.md").write_text(
        "---\nname: package\ndescription: Test package.\n---\n",
        encoding="utf-8",
    )
    manifest = skill / "RESOURCE_MANIFEST.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["resources"] = payload["resources"][1:]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = run_verifier(skill, repo_root)

    assert result.returncode != 0
    assert "manifest resource set does not match canonical resources" in result.stderr


def test_daily_skill_profile_contains_operation_resources_but_no_project_template(
    repo_root: Path, tmp_path: Path
):
    skill = run_sync(repo_root, tmp_path / "github-collaboration")
    assert (skill / "references" / "schemas" / "config.schema.json").is_file()
    assert not (skill / "assets").exists()
    assert (skill / "scripts/collaboration_event.py").is_file()
    assert (skill / "scripts/collaboration_scope.py").is_file()
    assert not (skill / "scripts/managed_block.py").exists()
