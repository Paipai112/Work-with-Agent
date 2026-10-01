#!/usr/bin/env python3
"""Read-only GitHub repository probe. Never stores raw API responses in evidence."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote


_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_HOST = re.compile(r"^[A-Za-z0-9.-]+$")
_HTTP = re.compile(r"\b(?:HTTP\s+)?(401|403|404|422|429|500|502|503)\b")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TOKEN = re.compile(r"\b(?:github_pat_[A-Za-z0-9_]{10,}|gh[pousr]_[A-Za-z0-9]{10,})\b")
_CREDENTIAL_URL = re.compile(r"(https?://)[^\s/@]+:[^\s/@]+@", re.IGNORECASE)
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_CONTENT_PATHS = {
    "issue_template": {".github/ISSUE_TEMPLATE/agent-task.yml"},
    "pr_template": {".github/PULL_REQUEST_TEMPLATE/agent-change.md"},
    "codeowners": {".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"},
}


def _redact(value):
    if isinstance(value, str):
        value = _CREDENTIAL_URL.sub(r"\1[redacted]@", value)
        value = _EMAIL.sub("[redacted-email]", value)
        return _TOKEN.sub("[redacted-token]", value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def parse_repo(value: str) -> tuple[str, str, str]:
    parts = value.split("/")
    if len(parts) != 3 or not _HOST.fullmatch(parts[0]) or "." not in parts[0] or not all(_PART.fullmatch(part) for part in parts[1:]):
        raise ValueError("--repo must be HOST/OWNER/NAME with no URL, spaces, or extra path")
    if any(part in {".", ".."} for part in parts):
        raise ValueError("--repo contains an invalid path component")
    return parts[0], parts[1], parts[2]


def _unverified(reason: str, http_status: int | None = None) -> dict:
    item = {"status": "unverified", "reason": reason}
    if http_status is not None:
        item["http_status"] = http_status
    return item


def _value(source: dict, key: str):
    item = source.get(key)
    if not isinstance(item, dict) or item.get("status") != "observed":
        return None
    return item.get("data")


def _status(source: dict, key: str):
    item = source.get(key)
    if isinstance(item, dict) and item.get("status") == "unverified":
        # Raw API/CLI error prose can contain credential-bearing URLs or emails.
        code = item.get("http_status")
        return _unverified("endpoint unavailable or inaccessible", code if isinstance(code, int) else None)
    return _unverified("endpoint not probed")


def _list(data):
    if isinstance(data, list):
        return data
    return []


def _positive_integer(value):
    return type(value) is int and value > 0


def _nonempty_string(value):
    return isinstance(value, str) and bool(value)


def _optional_review_count(value):
    return value is None or (type(value) is int and value >= 0)


def _repository_identity(data, owner: str, name: str):
    if not isinstance(data, dict):
        return None
    repository_id, full_name = data.get("id"), data.get("full_name")
    returned_name, branch = data.get("name"), data.get("default_branch")
    if (not _positive_integer(repository_id) or
            not isinstance(full_name, str) or full_name.casefold() != f"{owner}/{name}".casefold() or
            not isinstance(returned_name, str) or returned_name.casefold() != name.casefold() or
            not isinstance(branch, str) or not branch):
        return None
    return repository_id, full_name, branch


def _branch_sha(data, branch: str):
    if not isinstance(data, dict) or data.get("name") != branch:
        return None
    commit = data.get("commit")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    return sha if isinstance(sha, str) and _SHA.fullmatch(sha) else None


def _content_metadata(source: dict, key: str, ref: str | None):
    data = _value(source, key)
    if not isinstance(data, dict):
        return _status(source, key)
    if (ref is None or data.get("ref") != ref or not isinstance(data.get("path"), str) or
            data["path"] not in _CONTENT_PATHS[key] or
            not isinstance(data.get("sha"), str) or not _SHA.fullmatch(data["sha"])):
        return _unverified("content is not bound to the verified repository snapshot")
    return {"status": "observed", "path": data["path"], "sha": data["sha"], "ref": ref}


def normalize_repository_state(source: dict, *, repo: str, installation_id: str,
                               evidence_kind: str = "offline-fixture") -> dict:
    """Allowlist remote metadata; never copy unknown fields, URLs, bodies, or people."""
    host, owner, name = parse_repo(repo)
    result = {
        "schema_version": 1,
        "evidence_kind": evidence_kind,
        "target": {"host": host, "owner": owner, "name": name},
        "expected_installation_id": installation_id,
    }
    repository = _value(source, "repository")
    identity = _repository_identity(repository, owner, name)
    if identity is not None:
        permissions = repository.get("permissions")
        result["repository"] = {
            "status": "observed", "id": identity[0], "name": repository["name"],
            "full_name": identity[1], "default_branch": identity[2],
            "permission": ({"status": "observed", **{key: permissions[key] for key in ("admin", "maintain", "push")}}
                           if isinstance(permissions, dict) and all(
                               isinstance(permissions.get(key), bool) for key in ("admin", "maintain", "push"))
                           else _unverified("complete permission fields not returned")),
        }
    elif isinstance(repository, dict):
        result["repository"] = _unverified("repository identity does not match the requested target")
        # A redirect or malformed identity must not lend the requested name to other observations.
        source = {}
    else:
        result["repository"] = _status(source, "repository")
    branch = _value(source, "default_branch")
    branch_name = identity[2] if identity is not None else None
    sha = _branch_sha(branch, branch_name)
    result["default_branch"] = ({"status": "observed", "name": branch_name, "sha": sha}
                                if sha else _status(source, "default_branch"))
    snapshot = _value(source, "snapshot")
    expected_snapshot = ({"repository_id": identity[0], "repository_full_name": identity[1],
                          "default_branch": identity[2], "commit_sha": sha}
                         if identity is not None and sha else None)
    if expected_snapshot is not None and snapshot == expected_snapshot:
        result["snapshot"] = {"status": "observed", **expected_snapshot}
    else:
        result["snapshot"] = _unverified("repository/default-branch snapshot not confirmed")
    content_ref = sha if result["snapshot"]["status"] == "observed" else None
    labels = _value(source, "labels")
    result["labels"] = ({"status": "observed", "names": sorted(
        str(row["name"]) for row in _list(labels) if isinstance(row, dict) and isinstance(row.get("name"), str))}
        if isinstance(labels, list) else _status(source, "labels"))
    rulesets = _value(source, "rulesets")
    if isinstance(rulesets, list) and all(
            isinstance(item, dict) and _positive_integer(item.get("id")) and
            _nonempty_string(item.get("name")) for item in rulesets):
        result["rulesets"] = []
        for item in rulesets:
            if not isinstance(item, dict):
                continue
            if not isinstance(item.get("rules"), list):
                result["rulesets"].append({"id": item.get("id"), "name": item.get("name"),
                                           "managed_fields": _unverified("ruleset detail unavailable")})
                continue
            checks = []
            reviews = None
            detail_verified = True
            for rule in _list(item.get("rules")):
                if not isinstance(rule, dict) or not _nonempty_string(rule.get("type")):
                    detail_verified = False
                    break
                params = rule.get("parameters", {})
                if not isinstance(params, dict):
                    detail_verified = False
                    break
                if rule.get("type") == "required_status_checks":
                    rows = params.get("required_status_checks")
                    if not isinstance(rows, list) or not all(
                            isinstance(row, dict) and _nonempty_string(row.get("context")) for row in rows):
                        detail_verified = False
                        break
                    checks.extend(row["context"] for row in rows)
                if rule.get("type") == "pull_request":
                    reviews = params.get("required_approving_review_count")
                    if type(reviews) is not int or reviews < 0:
                        detail_verified = False
                        break
            result["rulesets"].append({"id": item.get("id"), "name": item.get("name"),
                                       "managed_fields": ({"required_status_checks": sorted(set(checks)),
                                                           "required_approving_review_count": reviews}
                                                          if detail_verified else _unverified("ruleset detail malformed"))})
    else:
        result["rulesets"] = _status(source, "rulesets")
    protection = _value(source, "branch_protection")
    checks = protection.get("required_status_checks") if isinstance(protection, dict) else None
    reviews = protection.get("required_pull_request_reviews") if isinstance(protection, dict) else None
    checks = {} if checks is None else checks
    reviews = {} if reviews is None else reviews
    check_rows = checks.get("checks", []) if isinstance(checks, dict) else None
    contexts = checks.get("contexts", []) if isinstance(checks, dict) else None
    if (isinstance(protection, dict) and isinstance(checks, dict) and isinstance(reviews, dict) and
            isinstance(check_rows, list) and all(isinstance(row, dict) and _nonempty_string(row.get("context")) for row in check_rows) and
            isinstance(contexts, list) and all(_nonempty_string(context) for context in contexts) and
            _optional_review_count(reviews.get("required_approving_review_count"))):
        result["branch_protection"] = {"status": "observed",
            "required_status_checks": sorted(set(
                [row["context"] for row in check_rows] + contexts)),
            "required_approving_review_count": reviews.get("required_approving_review_count")}
    else:
        result["branch_protection"] = _status(source, "branch_protection")
    for key in ("issue_template", "pr_template", "codeowners"):
        result[key] = _content_metadata(source, key, content_ref)
    workflow = _value(source, "workflow")
    result["workflow"] = ({"status": "observed", "id": workflow["id"], "state": workflow["state"]}
                          if isinstance(workflow, dict) and _positive_integer(workflow.get("id")) and
                          _nonempty_string(workflow.get("state")) else _status(source, "workflow"))
    runs = _value(source, "workflow_runs")
    result["workflow_runs"] = ({"status": "observed", "runs": [
        {"id": row.get("id"), "status": row.get("status"), "conclusion": row.get("conclusion"),
         "head_sha": row.get("head_sha")}
        for row in _list(runs.get("workflow_runs")) if isinstance(row, dict)]}
        if isinstance(runs, dict) and isinstance(runs.get("workflow_runs"), list) and all(
            isinstance(row, dict) and _positive_integer(row.get("id")) and
            _nonempty_string(row.get("status")) and (row.get("conclusion") is None or _nonempty_string(row.get("conclusion"))) and
            isinstance(row.get("head_sha"), str) and _SHA.fullmatch(row["head_sha"])
            for row in runs["workflow_runs"]) else _status(source, "workflow_runs"))
    managed = _value(source, "managed_resources")
    if (isinstance(managed, dict) and isinstance(managed.get("installation_id"), str) and
            content_ref is not None and managed.get("ref") == content_ref and
            managed.get("path") == ".github/agent-collaboration/managed-resources.yml" and
            isinstance(managed.get("sha"), str) and _SHA.fullmatch(managed["sha"])):
        result["installation"] = {"status": "observed", "actual_id": managed["installation_id"],
                                  "matches_expected": managed["installation_id"] == installation_id,
                                  "path": managed["path"], "sha": managed["sha"], "ref": content_ref}
    else:
        result["installation"] = _status(source, "managed_resources")
    prs = _value(source, "pull_requests")
    result["pull_requests"] = ({"status": "observed", "open_prs": [
        {"number": row.get("number"),
         "mergeability": ({"status": "observed", "mergeable": row.get("mergeable"),
                           "mergeable_state": row.get("mergeable_state")}
                          if isinstance(row.get("mergeable"), bool) and _nonempty_string(row.get("mergeable_state"))
                          else _unverified("mergeability not yet computed or detail unavailable"))}
        for row in _list(prs) if isinstance(row, dict)]}
        if isinstance(prs, list) and all(isinstance(row, dict) and _positive_integer(row.get("number"))
                                        for row in prs) else _status(source, "pull_requests"))
    return _redact(result)


def _gh_api(host: str, endpoint: str, *, paginate: bool = False) -> dict:
    command = ["gh", "api", "--hostname", host, "--method", "GET", endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return _unverified("gh unavailable or timed out")
    if completed.returncode != 0:
        match = _HTTP.search(completed.stderr)
        code = int(match.group(1)) if match else None
        return _unverified("endpoint unavailable or inaccessible", code)
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return _unverified("invalid JSON from gh api")
    if paginate:
        if not isinstance(data, list) or not all(isinstance(page, list) for page in data):
            return _unverified("invalid paginated response")
        data = [item for page in data for item in page]
    return {"status": "observed", "data": data}


def _content(host: str, root: str, path: str, *, ref: str) -> dict:
    item = _gh_api(host, f"{root}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}")
    data = _value({"item": item}, "item")
    if not isinstance(data, dict):
        return item
    if (data.get("type") != "file" or data.get("path") != path or
            not isinstance(data.get("sha"), str) or not _SHA.fullmatch(data["sha"])):
        return _unverified("content path, type, or blob SHA could not be verified")
    return {"status": "observed", "data": {"path": data.get("path"), "sha": data.get("sha"),
            "content": data.get("content"), "encoding": data.get("encoding"), "ref": ref}}


def _managed_id(item: dict) -> dict:
    data = _value({"item": item}, "item")
    if (not isinstance(data, dict) or data.get("encoding") != "base64" or
            not isinstance(data.get("content"), str)):
        return _unverified("managed manifest content unavailable")
    try:
        decoded = base64.b64decode(data.get("content", ""), validate=False).decode("utf-8")
    except (ValueError, UnicodeError):
        return _unverified("managed manifest is not decodable")
    match = re.search(r"^installation_id:\s*['\"]?([^'\"\s#]+)", decoded, re.MULTILINE)
    if not match:
        return _unverified("managed manifest installation_id unavailable")
    return {"status": "observed", "data": {"installation_id": match.group(1),
            **{key: data.get(key) for key in ("path", "sha", "ref")}}}


def _codeowners(host: str, root: str, *, ref: str) -> dict:
    for path in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        item = _content(host, root, path, ref=ref)
        if isinstance(_value({"item": item}, "item"), dict):
            return item
    return _unverified("CODEOWNERS not confirmed; paths may be absent or inaccessible")


def probe_repository(repo: str, installation_id: str) -> dict:
    host, owner, name = parse_repo(repo)
    root = f"repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    raw = {"repository": _gh_api(host, root)}
    repository = _value(raw, "repository")
    identity = _repository_identity(repository, owner, name)
    branch = identity[2] if identity is not None else None
    def finish():
        evidence = normalize_repository_state(raw, repo=repo, installation_id=installation_id,
                                              evidence_kind="read-only-gh-api")
        evidence["observed_at"] = datetime.now(timezone.utc).isoformat()
        return evidence
    if identity is None:
        return finish()
    raw["default_branch"] = (_gh_api(host, f"{root}/branches/{quote(branch, safe='')}")
                             if isinstance(branch, str) and branch else _unverified("default branch unknown"))
    sha = _branch_sha(_value(raw, "default_branch"), branch)
    if sha is None:
        raw["default_branch"] = _unverified("default branch name or commit SHA could not be verified")
        return finish()
    raw["labels"] = _gh_api(host, f"{root}/labels?per_page=100", paginate=True)
    raw["rulesets"] = _gh_api(host, f"{root}/rulesets?includes_parents=true&per_page=100", paginate=True)
    listed_rulesets = _value(raw, "rulesets")
    if isinstance(listed_rulesets, list):
        detailed_rulesets = []
        for entry in listed_rulesets:
            if not isinstance(entry, dict) or not _positive_integer(entry.get("id")):
                detailed_rulesets.append(entry)
                continue
            detail = _gh_api(host, f"{root}/rulesets/{entry['id']}")
            data = _value({"detail": detail}, "detail")
            detailed_rulesets.append(data if isinstance(data, dict) else {"id": entry["id"], "name": entry.get("name")})
        raw["rulesets"] = {"status": "observed", "data": detailed_rulesets}
    raw["branch_protection"] = (_gh_api(host, f"{root}/branches/{quote(branch, safe='')}/protection")
                                if isinstance(branch, str) and branch else _unverified("default branch unknown"))
    raw["issue_template"] = _content(host, root, ".github/ISSUE_TEMPLATE/agent-task.yml", ref=sha)
    raw["pr_template"] = _content(host, root, ".github/PULL_REQUEST_TEMPLATE/agent-change.md", ref=sha)
    raw["codeowners"] = _codeowners(host, root, ref=sha)
    raw["managed_resources"] = _managed_id(_content(host, root, ".github/agent-collaboration/managed-resources.yml", ref=sha))
    raw["workflow"] = _gh_api(host, f"{root}/actions/workflows/agent-collaboration-check.yml")
    raw["workflow_runs"] = _gh_api(host, f"{root}/actions/workflows/agent-collaboration-check.yml/runs?per_page=20")
    raw["pull_requests"] = _gh_api(host, f"{root}/pulls?state=open&per_page=100", paginate=True)
    listed_prs = _value(raw, "pull_requests")
    if isinstance(listed_prs, list):
        detailed_prs = []
        for entry in listed_prs:
            if not isinstance(entry, dict) or not _positive_integer(entry.get("number")):
                detailed_prs.append(entry)
                continue
            detail = _gh_api(host, f"{root}/pulls/{entry['number']}")
            data = _value({"detail": detail}, "detail")
            detailed_prs.append(data if isinstance(data, dict) else {"number": entry["number"]})
        raw["pull_requests"] = {"status": "observed", "data": detailed_prs}
    final_repository = _gh_api(host, root)
    final_branch = _gh_api(host, f"{root}/branches/{quote(branch, safe='')}")
    if (_repository_identity(_value({"item": final_repository}, "item"), owner, name) == identity and
            _branch_sha(_value({"item": final_branch}, "item"), branch) == sha):
        raw["snapshot"] = {"status": "observed", "data": {
            "repository_id": identity[0], "repository_full_name": identity[1],
            "default_branch": branch, "commit_sha": sha}}
    else:
        raw["snapshot"] = _unverified("repository or default branch changed or became inaccessible during probe")
    return finish()


def validate_evidence(evidence: dict) -> None:
    import jsonschema

    schema = json.loads(Path(__file__).with_name("evidence.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(evidence, schema, format_checker=jsonschema.FormatChecker())
    target, repository = evidence["target"], evidence["repository"]
    if repository["status"] == "observed" and _repository_identity(
            repository, target["owner"], target["name"]) is None:
        raise jsonschema.ValidationError("repository identity does not match the evidence target")
    snapshot = evidence["snapshot"]
    if snapshot["status"] == "observed":
        repository, branch = evidence["repository"], evidence["default_branch"]
        if (repository["status"] != "observed" or branch["status"] != "observed" or
                snapshot["repository_id"] != repository["id"] or
                snapshot["repository_full_name"] != repository["full_name"] or
                snapshot["default_branch"] != repository["default_branch"] or
                snapshot["default_branch"] != branch["name"] or snapshot["commit_sha"] != branch["sha"]):
            raise jsonschema.ValidationError("snapshot binding is inconsistent")
    for key in (*_CONTENT_PATHS, "installation"):
        item = evidence[key]
        if item["status"] == "observed" and (
                snapshot["status"] != "observed" or item["ref"] != snapshot["commit_sha"]):
            raise jsonschema.ValidationError("content binding is inconsistent")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="HOST/OWNER/NAME")
    parser.add_argument("--installation-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, help="normalize an offline raw fixture without calling gh")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; refusing overwrite")
    try:
        if args.fixture is not None:
            try:
                source = json.loads(args.fixture.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                parser.error("offline fixture could not be read as JSON")
            if not isinstance(source, dict):
                parser.error("offline fixture must be a JSON object")
            evidence = normalize_repository_state(source, repo=args.repo, installation_id=args.installation_id)
        else:
            evidence = probe_repository(args.repo, args.installation_id)
    except ValueError as error:
        parser.error(str(error))
    validate_evidence(evidence)
    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error("output already exists; refusing overwrite")
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote redacted read-only evidence: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
