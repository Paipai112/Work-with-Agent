"""Read-only byte comparison with a caller-pinned commit in a verified Git source.

No download, install, repair or release lookup is performed. Confirm the source
repository and tag-to-commit binding separately; this checks the selected objects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys


SKILLS = ("github-collaboration", "github-collaboration-setup", "github-collaboration-check")
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def relative(value: str) -> str:
    if (not isinstance(value, str) or not value or value.startswith("/") or "\\" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(ord(character) < 32 for character in value)):
        raise ValueError("unsafe package-relative path")
    return value


def git(source: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "--no-replace-objects", "--no-lazy-fetch", "-C", str(source), *args],
                            capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError("pinned Git objects unavailable; fetch the verified fixed source separately")
    return result.stdout


def source_files(source: Path, sha: str, skill: str) -> dict[str, bytes]:
    if not SHA.fullmatch(sha):
        raise ValueError("source must be a full immutable commit SHA, not a branch or tag")
    commit = git(source, "rev-parse", "--verify", sha + "^{commit}").decode().strip()
    if commit != sha:
        raise ValueError("selected source is not that exact commit")
    prefix = f"skills/{skill}/"
    result = {}
    for record in git(source, "ls-tree", "-r", "-z", sha, "--", prefix).split(b"\0"):
        if not record:
            continue
        info, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = info.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if mode not in {"100644", "100755"} or kind != "blob" or not path.startswith(prefix):
            raise ValueError("pinned package contains symlink, gitlink or non-regular content")
        name = relative(path[len(prefix):])
        if name in result or len(result) >= 20000:
            raise ValueError("duplicate or excessive pinned package files")
        result[name] = git(source, "cat-file", "blob", object_id)
    if "SKILL.md" not in result or "RESOURCE_MANIFEST.json" not in result:
        raise ValueError("pinned package lacks its entry or resource manifest")
    return result


def installed_files(root: Path) -> dict[str, bytes]:
    root = root.absolute()
    for component in [*reversed(root.parents), root]:
        if component.is_symlink():
            raise ValueError("installed path has a symlink; preserve it and resolve ownership")
    if not root.is_dir():
        raise ValueError("installed package directory is unavailable")
    result = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("installed package has a symlink or non-regular resource")
        if len(result) >= 20000 or path.stat().st_size > 16777216:
            raise ValueError("installed package exceeds verification limits")
        result[relative(path.relative_to(root).as_posix())] = path.read_bytes()
    return result


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest JSON key")
        result[key] = value
    return result


def validate_manifest(files: dict[str, bytes]) -> None:
    manifest = json.loads(files["RESOURCE_MANIFEST.json"], object_pairs_hook=unique_json)
    if (not isinstance(manifest, dict) or manifest.get("manifest_version") != 1
            or not isinstance(manifest.get("resources"), list)):
        raise ValueError("pinned resource manifest format is incompatible")
    destinations = set()
    for resource in manifest["resources"]:
        if not isinstance(resource, dict):
            raise ValueError("invalid pinned resource record")
        destination = relative(resource["destination"])
        relative(resource["source"])
        if destination in destinations or destination not in files:
            raise ValueError("duplicate or missing pinned resource")
        destinations.add(destination)
        actual = hashlib.sha256(files[destination]).hexdigest()
        if resource.get("copied_sha256") != actual or resource.get("source_sha256") != actual:
            raise ValueError("pinned package resource manifest hash mismatch")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--skill", choices=SKILLS, required=True)
    parser.add_argument("--installed", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        expected = source_files(args.source_repo, args.source_sha, args.skill)
        validate_manifest(expected)
        actual = installed_files(args.installed)
        missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
        changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
        if actual != installed_files(args.installed):
            raise ValueError("installed package changed during verification")
        status = "fail" if missing or extra or changed else "pass"
        digest = hashlib.sha256()
        for name in sorted(actual):
            digest.update(name.encode("utf-8") + b"\0" + actual[name] + b"\0")
        report = {"status": status, "source_sha": args.source_sha, "skill": args.skill,
                  "package_sha256": digest.hexdigest(), "files_verified": len(actual),
                  "missing": missing, "extra": extra, "changed": changed,
                  "authorization_verified": False, "release_binding_verified": False,
                  "scope": "point-in-time installed bytes versus pinned Git objects; release source/tag binding remains external"}
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        report = {"status": "unknown", "error": "source/package verification unavailable or unsafe; preserve files and inspect the fixed source, manifest and regular paths",
                  "authorization_verified": False, "release_binding_verified": False}
    print(json.dumps(report, ensure_ascii=False))
    return {"pass": 0, "fail": 1, "unknown": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
