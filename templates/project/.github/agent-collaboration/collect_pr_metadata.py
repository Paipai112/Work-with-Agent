"""Collect data for the deployed checker; do not interpret event authorization."""

from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


INPUT_VERSION = 2


class CollectionUnavailable(ValueError):
    """Safe collection diagnostics without API response or credential contents."""


def pages(api, endpoint):
    output = []
    for page in range(1, 32):
        batch = api.get(f"{endpoint}?per_page=100&page={page}")
        if not isinstance(batch, list) or len(batch) > 100:
            raise CollectionUnavailable("GitHub metadata page invalid")
        output.extend(batch)
        if len(batch) < 100:
            return output
    raise CollectionUnavailable("GitHub pagination exceeds collection limit")


def comment_record(comment, repository, issue_number):
    if not isinstance(comment, dict):
        raise CollectionUnavailable("comment unavailable")
    identifier = comment.get("id")
    user = comment.get("user")
    url = f"https://github.com/{repository}/issues/{issue_number}#issuecomment-{identifier}"
    if (type(identifier) is not int or identifier < 1 or not isinstance(user, dict)
            or type(user.get("id")) is not int or user["id"] < 1
            or not isinstance(user.get("login"), str) or not user["login"]
            or comment.get("html_url") != url
            or comment.get("issue_url") != f"https://api.github.com/repos/{repository}/issues/{issue_number}"
            or not isinstance(comment.get("body"), str)
            or not isinstance(comment.get("updated_at"), str) or not comment["updated_at"]):
        raise CollectionUnavailable("comment envelope unverified")
    return {"id": identifier, "url": url, "user_id": user["id"], "login": user["login"],
            "issue_number": issue_number, "body": comment["body"], "updated_at": comment["updated_at"]}


def collect(api, checker, args, repository, sha, config_text, authorization, sources):
    started = datetime.now(timezone.utc).isoformat()
    prefix = f"repos/{args.repository}"
    pull = api.get(f"{prefix}/pulls/{args.pull_number}")
    if (not isinstance(pull, dict) or pull.get("number") != args.pull_number
            or pull.get("base", {}).get("repo", {}).get("id") != repository["id"]
            or not checker.SHA.fullmatch(str(pull.get("head", {}).get("sha", "")))
            or (args.expected_head is not None and args.expected_head != pull["head"]["sha"])
            or (args.default_target_only and pull.get("base", {}).get("ref") != repository["default_branch"])):
        raise CollectionUnavailable("PR identity, target or HEAD changed; refresh collection")
    metadata = checker.metadata_from_body(pull.get("body") or "")
    numbers = checker.linked_issue_numbers(pull.get("body") or "")
    files = pages(api, f"{prefix}/pulls/{args.pull_number}/files")
    if len(files) >= 3000 or ("changed_files" in pull and pull["changed_files"] != len(files)):
        raise CollectionUnavailable("PR files may be truncated")
    if len({item["filename"] for item in files}) != len(files):
        raise CollectionUnavailable("duplicate PR file paths; pagination unverified")
    reviews = pages(api, f"{prefix}/pulls/{args.pull_number}/reviews")
    if len({item["id"] for item in reviews}) != len(reviews):
        raise CollectionUnavailable("duplicate review IDs; pagination unverified")
    issues = [api.get(f"{prefix}/issues/{number}") for number in numbers]
    comments = {}
    for number in numbers:
        records = [comment_record(item, args.repository, number)
                   for item in pages(api, f"{prefix}/issues/{number}/comments")]
        if len({item["id"] for item in records}) != len(records):
            raise CollectionUnavailable("duplicate comment IDs; refresh collection")
        comments[str(number)] = records
    claims = {}
    for url in metadata["claim_urls"]:
        match = checker.CLAIM_URL.fullmatch(url)
        if match.group(1) != args.repository:
            raise CollectionUnavailable("claim URL repository mismatch")
        number, identifier = int(match.group(2)), int(match.group(3))
        raw = api.get(f"{prefix}/issues/comments/{identifier}", missing_ok=True)
        record = None if raw is None else comment_record(raw, args.repository, number)
        if record is not None and (record["id"] != identifier or record["url"] != url):
            raise CollectionUnavailable("claim comment identity mismatch")
        matching = [item for item in comments[str(number)] if item["id"] == identifier]
        if matching != ([] if record is None else [record]):
            raise CollectionUnavailable("claim changed during collection; refresh collection")
        claims[url] = record
    if pages(api, f"{prefix}/pulls/{args.pull_number}/reviews") != reviews:
        raise CollectionUnavailable("reviews changed during collection; refresh collection")
    for number, issue in zip(numbers, issues):
        if api.get(f"{prefix}/issues/{number}") != issue:
            raise CollectionUnavailable("Issue changed during collection; refresh collection")
        final_comments = [comment_record(item, args.repository, number)
                          for item in pages(api, f"{prefix}/issues/{number}/comments")]
        if final_comments != comments[str(number)]:
            raise CollectionUnavailable("Issue comments/events changed during collection; refresh collection")
    for url, record in claims.items():
        match = checker.CLAIM_URL.fullmatch(url)
        raw = api.get(f"{prefix}/issues/comments/{match.group(3)}", missing_ok=True)
        final_record = None if raw is None else comment_record(raw, args.repository, int(match.group(2)))
        if final_record != record:
            raise CollectionUnavailable("claim comment changed during collection; refresh collection")
    final_repository = api.get(prefix)
    if any(final_repository.get(key) != repository[key] for key in ("id", "full_name", "default_branch")):
        raise CollectionUnavailable("repository identity/default branch changed; refresh collection")
    final_pull = api.get(f"{prefix}/pulls/{args.pull_number}")
    if any(final_pull.get(key) != pull.get(key)
           for key in ("number", "head", "base", "body", "state", "user", "updated_at", "changed_files")):
        raise CollectionUnavailable("PR HEAD/base/body changed during collection; refresh collection")
    final_ref = api.get(f"{prefix}/git/ref/heads/{quote(repository['default_branch'], safe='')}")
    if final_ref.get("object", {}).get("sha") != sha:
        raise CollectionUnavailable("default branch changed during collection; refresh collection")
    snapshot = {
        "version": INPUT_VERSION, "source": "github-get", "collected_at": started,
        "verified_at": datetime.now(timezone.utc).isoformat(), "repository_id": repository["id"],
        "default_branch": repository["default_branch"], "trusted_sha": sha,
        "pull_number": args.pull_number, "head_sha": pull["head"]["sha"],
        "base_ref": pull["base"]["ref"],
        "trusted_resources": {path: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                              for path, raw in sources.items()},
        "unverified": ["human_approval", "effective_account_permissions", "native_branch_protection", "actual_skill_loading"],
    }
    return {"trusted_ref_verified": True, "trusted_sha": sha,
            "repository": {"id": repository["id"], "full_name": repository["full_name"],
                           "default_branch": repository["default_branch"]},
            "pull": pull, "files": files, "reviews": reviews, "issues": issues,
            "config": config_text, "authorization": authorization,
            "claim_comments": claims, "issue_comments": comments, "snapshot": snapshot}


if __name__ == "__main__":
    # The direct CLI is a locator too: formal collection uses the verified deployed copy.
    launcher = Path(__file__).with_name("run_pr_metadata_check.py")
    if not launcher.is_file() or launcher.is_symlink():
        print(json.dumps({"result": "unknown", "errors": ["local launcher missing or symlink; repair installation"], "snapshot": None}))
        raise SystemExit(2)
    raise SystemExit(subprocess.call([sys.executable, str(launcher), "--collect-only", *sys.argv[1:]]))
