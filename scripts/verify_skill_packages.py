"""Verify that repository Skill packages are self-contained and reproducible."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from skill_resource_profiles import PROFILES, resolve_profile


MANIFEST_NAME = "RESOURCE_MANIFEST.json"
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
MARKDOWN_REFERENCE_LINK = re.compile(r"!?\[([^]]+)\]\[([^]]*)\]")
MARKDOWN_REFERENCE_DEFINITION = re.compile(
    r"(?m)^[ ]{0,3}\[([^]]+)\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))"
)
ABSOLUTE_DEVELOPER_PATH = re.compile(
    r"(?:^|[\s\"'`(])(?:/(?:Users|home)/|[A-Za-z]:[/\\](?:Users|home)[/\\])"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _local_target(target: str) -> str | None:
    target = target.strip()
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    return target.split("#", 1)[0].split("?", 1)[0]


def _reference_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _check_local_reference(
    document: Path, raw_target: str, root: Path, errors: list[str]
) -> None:
    target = _local_target(raw_target)
    if target is None:
        return
    candidate = (document.parent / target).resolve()
    if not _inside(candidate, root):
        errors.append(f"{document}: reference escapes skill directory: {raw_target}")
    elif not candidate.is_file():
        errors.append(f"{document}: referenced file does not exist: {raw_target}")


def _frontmatter_name(skill_file: Path, errors: list[str]) -> None:
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        errors.append(f"{skill_file}: SKILL.md must be UTF-8")
        return
    if not lines or lines[0] != "---":
        errors.append(f"{skill_file}: frontmatter is required")
        return
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"{skill_file}: frontmatter is not closed")
        return
    name_line = next((line for line in lines[1:end] if line.startswith("name:")), None)
    if name_line is None:
        errors.append(f"{skill_file}: frontmatter name is required")
        return
    name = name_line.partition(":")[2].strip().strip("'\"")
    if not name or name != name.lower() or name != skill_file.parent.name:
        errors.append(f"{skill_file}: frontmatter name must equal lowercase folder name")


def _check_references(skill: Path, errors: list[str]) -> None:
    root = skill.resolve()
    for document in sorted(path for path in skill.rglob("*.md") if path.is_file()):
        try:
            text = document.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{document}: Markdown must be UTF-8")
            continue
        for raw_target in MARKDOWN_LINK.findall(text):
            _check_local_reference(document, raw_target, root, errors)
        definitions: dict[str, str] = {}
        for label, angle_target, plain_target in MARKDOWN_REFERENCE_DEFINITION.findall(text):
            target = angle_target or plain_target
            definitions.setdefault(_reference_label(label), target)
            _check_local_reference(document, target, root, errors)
        for text_label, destination_label in MARKDOWN_REFERENCE_LINK.findall(text):
            label = _reference_label(destination_label or text_label)
            if label not in definitions:
                errors.append(f"{document}: reference definition does not exist: {label}")
                continue


def _check_absolute_paths(skill: Path, errors: list[str]) -> None:
    for path in sorted(path for path in skill.rglob("*") if path.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if ABSOLUTE_DEVELOPER_PATH.search(text):
            errors.append(f"{path}: contains an absolute developer-machine path")


def _check_script_syntax(skill: Path, errors: list[str]) -> None:
    scripts = skill / "scripts"
    if not scripts.is_dir():
        return
    for script in sorted(path for path in scripts.rglob("*.py") if path.is_file()):
        try:
            compile(script.read_bytes(), str(script), "exec")
        except (SyntaxError, UnicodeDecodeError) as error:
            errors.append(f"{script}: invalid executable-script syntax: {error}")


def _check_package_symlinks(skill: Path, errors: list[str]) -> None:
    root = skill.resolve()
    for path in sorted(skill.rglob("*")):
        if path.is_symlink():
            reason = "symlink escapes skill directory" if not _inside(path.resolve(), root) else "symlink is not a package resource"
            errors.append(f"{path}: {reason}")


def _expected_resources(skill: Path, repo_root: Path, profile: str) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    selected = PROFILES[profile]
    schema_destination = Path(selected["schema_root"])
    schemas = repo_root / "schemas"
    if schemas.is_dir():
        for source in sorted(path for path in schemas.rglob("*") if path.is_file()
                             and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}):
            relative = source.relative_to(schemas)
            expected.add(
                (
                    source.relative_to(repo_root).as_posix(),
                    (schema_destination / relative).as_posix(),
                )
            )
    templates = repo_root / "templates"
    if selected["templates"] and templates.is_dir():
        for source in sorted(path for path in templates.rglob("*") if path.is_file()
                             and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}):
            relative = source.relative_to(templates)
            expected.add(
                (
                    source.relative_to(repo_root).as_posix(),
                    (Path("assets/templates") / relative).as_posix(),
                )
            )
    expected.update(selected["helpers"])
    return expected


def _check_manifest(skill: Path, repo_root: Path, errors: list[str]) -> None:
    manifest = skill / MANIFEST_NAME
    if not manifest.is_file():
        errors.append(f"{skill}: {MANIFEST_NAME} is required")
        return
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{manifest}: invalid JSON: {error}")
        return
    if not isinstance(payload, dict):
        errors.append(f"{manifest}: manifest must be a JSON object")
        return
    try:
        profile = resolve_profile(skill.name, payload.get("profile"))
    except (ValueError, TypeError):
        errors.append(f"{manifest}: unknown or conflicting resource profile")
        return
    resources = payload.get("resources")
    if payload.get("manifest_version") != 1 or not isinstance(resources, list):
        errors.append(f"{manifest}: manifest_version=1 and resources list are required")
        return

    destinations: set[str] = set()
    declared_resources: set[tuple[str, str]] = set()
    root = skill.resolve()
    repository = repo_root.resolve()
    for entry in resources:
        if not isinstance(entry, dict):
            errors.append(f"{manifest}: every resource must be an object")
            continue
        source_name = entry.get("source")
        destination_name = entry.get("destination")
        source_hash = entry.get("source_sha256")
        copied_hash = entry.get("copied_sha256")
        if not all(isinstance(value, str) for value in (source_name, destination_name, source_hash, copied_hash)):
            errors.append(f"{manifest}: resource requires source, destination, and both SHA-256 values")
            continue
        declared_resources.add((source_name, destination_name))
        if destination_name in destinations:
            errors.append(f"{manifest}: duplicate resource destination: {destination_name}")
            continue
        destinations.add(destination_name)
        copied = (root / destination_name).resolve()
        source = (repository / source_name).resolve()
        if not _inside(copied, root):
            errors.append(f"{manifest}: destination escapes skill directory: {destination_name}")
            continue
        if not _inside(source, repository):
            errors.append(f"{manifest}: source escapes repository: {source_name}")
            continue
        if not copied.is_file():
            errors.append(f"{manifest}: copied resource does not exist: {destination_name}")
            continue
        if _sha256(copied) != copied_hash:
            errors.append(f"{manifest}: copied resource hash drift: {destination_name}")
        if copied_hash != source_hash:
            errors.append(f"{manifest}: source/copy hash mismatch: {destination_name}")
        if not source.is_file():
            errors.append(f"{manifest}: canonical resource does not exist: {source_name}")
        elif _sha256(source) != source_hash:
            errors.append(f"{manifest}: canonical resource hash drift: {source_name}")

    if declared_resources != _expected_resources(skill, repo_root, profile):
        errors.append(f"{manifest}: manifest resource set does not match canonical resources")


def verify_skill(skill: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if skill.is_symlink():
        return [f"{skill}: Skill directory must not be a symbolic link"]
    if not skill.is_dir():
        return [f"{skill}: Skill directory does not exist"]
    _check_package_symlinks(skill, errors)
    if errors:
        return errors
    skill_file = skill / "SKILL.md"
    if not skill_file.is_file():
        return [f"{skill}: SKILL.md entrypoint is required"]
    _frontmatter_name(skill_file, errors)
    _check_references(skill, errors)
    _check_manifest(skill, repo_root, errors)
    _check_script_syntax(skill, errors)
    _check_absolute_paths(skill, errors)
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path, nargs="?", help="one explicit Skill package directory")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--allow-missing-skill-entrypoints",
        action="store_true",
        help="allow only a repository with no Skill directories during foundation setup",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo_root = arguments.repo_root.resolve()
    if arguments.skill is not None:
        skills = [arguments.skill]
    else:
        skills_root = repo_root / "skills"
        skills = sorted(path for path in skills_root.iterdir() if path.is_dir()) if skills_root.is_dir() else []
        if not skills:
            if arguments.allow_missing_skill_entrypoints:
                print("deferred: Skill entrypoints are not created in this foundation stage")
                return 0
            print("no Skill entrypoints found; use --allow-missing-skill-entrypoints only during foundation setup", file=sys.stderr)
            return 2

    errors = [error for skill in skills for error in verify_skill(skill, repo_root)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    print(f"verified {len(skills)} self-contained Skill package(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
