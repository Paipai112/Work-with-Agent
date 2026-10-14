"""Read-only delivery scope comparison. JSON output never grants ownership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def repository_path(path, pattern=False):
    if (not isinstance(path, str) or not path or path.startswith("/")
            or "\\" in path or ":" in path or any(ord(c) < 32 for c in path)
            or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise ValueError("scope paths must be repository-relative POSIX paths")
    if not pattern and any(c in path for c in "*?["):
        raise ValueError("changed paths cannot be patterns")
    if pattern and ("[" in path or "]" in path or any("**" in p and p != "**" for p in path.split("/"))):
        raise ValueError("scope supports literal paths, segment * and ?, and whole-segment **")
    return path


def scope_patterns(values):
    if not isinstance(values, list) or not values:
        raise ValueError("scope must be a nonempty list")
    patterns = []
    for value in values:
        value = repository_path(value, pattern=True)
        parts = value.split("/")
        expression = ""
        for index, part in enumerate(parts):
            if part == "**":
                expression += ".*" if index == len(parts) - 1 else "(?:[^/]+/)*"
            else:
                expression += "".join("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c) for c in part)
                if index != len(parts) - 1:
                    expression += "/"
        patterns.append(re.compile("^" + expression + "$"))
    return patterns


def compare(payload):
    if not isinstance(payload, dict):
        raise ValueError("scope input must be an object")
    patterns = scope_patterns(payload.get("scope"))
    changes = payload.get("changes")
    if not isinstance(changes, list):
        raise ValueError("changes must be a list")
    paths = set()
    for change in changes:
        if not isinstance(change, dict) or change.get("status") not in {"added", "modified", "deleted", "renamed", "untracked"}:
            raise ValueError("unsupported change status")
        paths.add(repository_path(change.get("path")))
        if change["status"] == "renamed":
            paths.add(repository_path(change.get("previous_path")))
    claims = payload.get("other_claims", [])
    if not isinstance(claims, list):
        raise ValueError("other_claims must be a list")
    conflicts = []
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("claim_url"), str) or not claim["claim_url"]:
            raise ValueError("other claim requires claim_url")
        other = scope_patterns(claim.get("scope"))
        conflicts.extend({"path": path, "claim_url": claim["claim_url"]} for path in sorted(paths)
                         if any(pattern.fullmatch(path) for pattern in other))
    outside = sorted(path for path in paths if not any(pattern.fullmatch(path) for pattern in patterns))
    return {"status": "fail" if outside or conflicts else "pass", "paths": sorted(paths),
            "out_of_scope": outside, "conflicts": conflicts, "authorization_verified": False}


def git_output(repo, *arguments):
    result = subprocess.run(["git", "--no-replace-objects", "--no-lazy-fetch", "-C", str(repo), *arguments],
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError("local Git inventory unavailable; check Git support and fixed local objects; no automatic fetch")
    return result.stdout.decode("utf-8", errors="strict")


def git_changes(repo, base):
    if not isinstance(base, str) or not re.fullmatch(r"[0-9a-f]{40,64}", base):
        raise ValueError("--base must be a fixed full commit SHA")
    git_output(repo, "rev-parse", "--verify", base + "^{commit}")
    changes = []
    for revisions in ([base, "HEAD"], ["--cached", "HEAD"], []):
        args = ["diff", "--no-ext-diff", "--no-textconv", "--name-status", "-z", "-M", *revisions]
        args.append("--")
        fields = git_output(repo, *args).split("\0")
        index = 0
        while index < len(fields) - 1:
            status = fields[index]
            index += 1
            kind = status[0] if status else ""
            if kind not in {"A", "M", "D", "T", "R", "C"} or index >= len(fields) - 1:
                raise ValueError("unsupported or incomplete Git change record")
            path = fields[index]
            index += 1
            if kind in {"R", "C"}:
                if index >= len(fields) - 1:
                    raise ValueError("incomplete Git rename record")
                changes.append({"status": "renamed", "previous_path": path, "path": fields[index]})
                index += 1
            else:
                changes.append({"status": {"A": "added", "D": "deleted", "M": "modified", "T": "modified"}[kind], "path": path})
    changes.extend({"status": "untracked", "path": path} for path in
                   git_output(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if path)
    return changes


def checkpoint_record(payload):
    """Validate progress observations without promoting them into current authority."""
    required = {"repository", "issue_number", "actor_id", "session_id", "claim_url", "completed", "tests", "uncommitted_changes", "remaining_steps"}
    optional = {"branch", "head_sha", "process_observation", "artifact_urls"}
    if not isinstance(payload, dict) or not required.issubset(payload) or set(payload) - required - optional:
        raise ValueError("checkpoint requires progress/identity fields; permission or claim-state fields are not accepted")
    for field in ("repository", "actor_id", "session_id", "claim_url"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError("checkpoint identity references must be nonempty strings")
    if type(payload["issue_number"]) is not int or payload["issue_number"] < 1:
        raise ValueError("checkpoint Issue number must be positive")
    for field in ("completed", "remaining_steps"):
        if not isinstance(payload[field], list) or any(not isinstance(item, str) or not item.strip() for item in payload[field]):
            raise ValueError("checkpoint progress must be string lists")
    tests = payload["tests"]
    if not isinstance(tests, list) or any(not isinstance(test, dict) or not isinstance(test.get("command"), str) or not test["command"].strip() or test.get("status") not in {"pass", "fail", "unknown"} for test in tests):
        raise ValueError("checkpoint tests require command and pass/fail/unknown status")
    # Reuse the actual change inventory contract; ** only permits recording, never allocation.
    compare({"scope": ["**"], "changes": payload["uncommitted_changes"]})
    if "head_sha" in payload and (not isinstance(payload["head_sha"], str) or not re.fullmatch(r"[0-9a-f]{40,64}", payload["head_sha"])):
        raise ValueError("checkpoint HEAD must be a full SHA")
    if "branch" in payload and (not isinstance(payload["branch"], str) or not payload["branch"].strip()):
        raise ValueError("checkpoint branch must be nonempty")
    observation = payload.get("process_observation")
    if observation is not None and not isinstance(observation, dict):
        raise ValueError("process observation must be an object")
    return {"status": "pass", "checkpoint_version": 1, "checkpoint": payload, "old_process_status": "unknown",
            "claim_released": False, "push_authorized": False, "authorization_verified": False,
            "next_safe_action": "refresh current repository, claim lineage, account and session facts before the remaining operation"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--repo", type=Path)
    source.add_argument("--checkpoint", type=Path)
    parser.add_argument("--base")
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--other-claims", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.checkpoint:
            if args.base or args.scope or args.other_claims:
                raise ValueError("--checkpoint cannot be combined with scope inventory arguments")
            result = checkpoint_record(read_json(args.checkpoint))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.input:
            if args.base or args.scope or args.other_claims:
                raise ValueError("--input cannot be combined with Git inventory arguments")
            payload = read_json(args.input)
        else:
            if not args.base or not args.scope:
                raise ValueError("--repo requires --base and --scope JSON list")
            payload = {"scope": read_json(args.scope), "changes": git_changes(args.repo, args.base),
                       "other_claims": read_json(args.other_claims) if args.other_claims else []}
        result = compare(payload)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "unknown", "error": str(error), "authorization_verified": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
