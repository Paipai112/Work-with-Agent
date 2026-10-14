"""Copy canonical Skill resources into an explicit, reviewable package target."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Final

from skill_resource_profiles import PROFILES, resolve_profile


MANIFEST_NAME: Final = "RESOURCE_MANIFEST.json"


class SyncError(ValueError):
    """The requested synchronization cannot be performed safely."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_source_path(repo_root: Path, source: Path) -> None:
    try:
        relative = source.relative_to(repo_root)
    except ValueError as error:
        raise SyncError(f"canonical source escapes repository: {source}") from error
    component = repo_root
    for part in relative.parts:
        component = component / part
        if component.is_symlink():
            raise SyncError(f"canonical source must not contain a symbolic link: {component}")
    try:
        source.resolve().relative_to(repo_root)
    except ValueError as error:
        raise SyncError(f"canonical source escapes repository: {source}") from error


def _relative_files(repo_root: Path, root: Path) -> list[Path]:
    _validate_source_path(repo_root, root)
    if not root.is_dir():
        raise SyncError(f"canonical resource directory is missing: {root}")
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        _validate_source_path(repo_root, path)
        if path.is_file():
            files.append(path.relative_to(root))
    return files


def _resource_map(repo_root: Path, destination: Path, profile: str) -> list[tuple[Path, Path]]:
    resources: list[tuple[Path, Path]] = []
    selected = PROFILES[profile]
    schema_root = selected["schema_root"]
    for relative in _relative_files(repo_root, repo_root / "schemas"):
        resources.append((repo_root / "schemas" / relative, destination / schema_root / relative))
    if selected["templates"]:
        for relative in _relative_files(repo_root, repo_root / "templates"):
            resources.append((repo_root / "templates" / relative, destination / "assets" / "templates" / relative))
    for source, target in selected["helpers"]:
        helper = repo_root / source
        _validate_source_path(repo_root, helper)
        if not helper.is_file():
            raise SyncError(f"canonical resource is missing: {helper}")
        resources.append((helper, destination / target))
    return resources


def _manifest(repo_root: Path, destination: Path, profile: str) -> bytes:
    resources = []
    for source, copied in _resource_map(repo_root, destination, profile):
        if not source.is_file():
            raise SyncError(f"canonical resource is missing: {source}")
        source_relative = source.relative_to(repo_root).as_posix()
        copied_relative = copied.relative_to(destination).as_posix()
        source_hash = sha256(source)
        resources.append(
            {
                "copied_sha256": source_hash,
                "destination": copied_relative,
                "source": source_relative,
                "source_sha256": source_hash,
            }
        )
    payload = {"manifest_version": 1, "profile": profile, "resources": resources}
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _planned_files(repo_root: Path, destination: Path, profile: str) -> list[tuple[Path, bytes]]:
    planned = [(copied, source.read_bytes()) for source, copied in _resource_map(repo_root, destination, profile)]
    planned.append((destination / MANIFEST_NAME, _manifest(repo_root, destination, profile)))
    return planned


def _find_drift(planned: list[tuple[Path, bytes]]) -> list[Path]:
    return [path for path, expected in planned if path.exists() and path.read_bytes() != expected]


def _validate_planned_paths(destination: Path, planned: list[tuple[Path, bytes]]) -> None:
    for path, _ in planned:
        try:
            path.resolve().relative_to(destination)
        except ValueError as error:
            relative = path.relative_to(destination).as_posix()
            raise SyncError(f"planned output escapes destination: {relative}") from error


def sync(repo_root: Path, destination: Path, accept_reviewed_diff: bool, profile: str | None = None) -> None:
    try:
        profile = resolve_profile(destination.name, profile)
    except ValueError as error:
        raise SyncError(str(error)) from error
    repo_root = repo_root.resolve()
    destination = destination.absolute()
    if destination.is_symlink():
        raise SyncError(f"destination must not be a symbolic link: {destination}")
    destination = destination.resolve()
    repository_skill_root = repo_root / "skills"
    if destination == repo_root or (
        repo_root in destination.parents and destination.parent != repository_skill_root
    ):
        raise SyncError("destination inside the repository must be a direct child of skills/")
    planned = _planned_files(repo_root, destination, profile)
    _validate_planned_paths(destination, planned)
    drift = _find_drift(planned)
    if drift and not accept_reviewed_diff:
        paths = ", ".join(path.relative_to(destination).as_posix() for path in drift)
        raise SyncError(f"local drift requires --accept-reviewed-diff: {paths}")

    for path, content in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise SyncError(f"refusing to write through symbolic link: {path}")
        path.write_bytes(content)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--destination", type=Path, help="explicit Skill package directory")
    target.add_argument("--skill", help="explicit Skill directory name below <repo-root>/skills")
    parser.add_argument("--profile", choices=sorted(PROFILES), help="required for an arbitrarily named output directory")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository containing canonical resources",
    )
    parser.add_argument(
        "--accept-reviewed-diff",
        action="store_true",
        help="permit replacement of changed managed resource copies",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repo_root = arguments.repo_root.resolve()
    destination = arguments.destination
    if destination is None:
        skill = arguments.skill
        if not skill or Path(skill).name != skill or skill in {".", ".."}:
            print("--skill must be a single Skill directory name", file=sys.stderr)
            return 2
        destination = repo_root / "skills" / skill
    try:
        sync(repo_root, destination, arguments.accept_reviewed_diff, arguments.profile)
    except (OSError, SyncError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(f"synchronized resources to {destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
