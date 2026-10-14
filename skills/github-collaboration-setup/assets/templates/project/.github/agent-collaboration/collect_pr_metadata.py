"""Collect data for the deployed checker; do not interpret event authorization."""

from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


INPUT_VERSION = 2
CHECK_CONTRACT_VERSION = 2


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


def pull_files(api, prefix, number, pull):
    files = pages(api, f"{prefix}/pulls/{number}/files")
    if (len(files) >= 3000 or pull.get("changed_files", len(files)) != len(files)
            or any(not isinstance(item, dict) or not isinstance(item.get("filename"), str) for item in files)
            or len({item["filename"] for item in files}) != len(files)):
        raise CollectionUnavailable("PR files may be truncated or duplicated; refresh collection")
    return files


def comparison(api, checker, prefix, base, head):
    commits, first = [], None
    for page in range(1, 32):
        batch = api.get(f"{prefix}/compare/{base}...{head}?per_page=100&page={page}")
        if (not isinstance(batch, dict) or not isinstance(batch.get("commits"), list)
                or len(batch["commits"]) > 100 or type(batch.get("total_commits")) is not int
                or batch["total_commits"] < 0 or batch["total_commits"] > 3100
                or batch.get("base_commit", {}).get("sha") != base
                or not checker.SHA.fullmatch(str(batch.get("merge_base_commit", {}).get("sha", "")))
                or batch.get("status") not in {"ahead", "behind", "diverged", "identical"}):
            raise CollectionUnavailable("fixed comparison envelope/pagination unverified")
        if first is None:
            first = batch
            if (not isinstance(first.get("files"), list) or len(first["files"]) >= 300
                    or any(not isinstance(item, dict) or not isinstance(item.get("filename"), str) for item in first["files"])
                    or len({item["filename"] for item in first["files"]}) != len(first["files"])):
                raise CollectionUnavailable("GitHub comparison files may be truncated at the 300-file limit")
        elif any(batch[key] != first[key] for key in ("status", "base_commit", "merge_base_commit", "total_commits")):
            raise CollectionUnavailable("comparison changed between pages; refresh collection")
        commits.extend(item.get("sha") for item in batch["commits"] if isinstance(item, dict))
        if len(batch["commits"]) < 100 or len(commits) == first["total_commits"]:
            break
    if (len(commits) != first["total_commits"] or len(set(commits)) != len(commits)
            or any(not isinstance(sha, str) or not checker.SHA.fullmatch(sha) for sha in commits)
            or first["status"] != "identical" and (not commits or commits[-1] != head)
            or first["status"] == "identical" and (base != head or commits)):
        raise CollectionUnavailable("comparison commits truncated, duplicated or not bound to fixed HEAD")
    return {"base_sha": base, "head_sha": head, "merge_base_sha": first["merge_base_commit"]["sha"],
            "status": first["status"], "commits": commits, "files": first["files"], "complete": True}


def collect(api, checker, args, repository, sha, config_text, authorization, sources):
    started = datetime.now(timezone.utc).isoformat()
    prefix = f"repos/{args.repository}"
    pull = api.get(f"{prefix}/pulls/{args.pull_number}")
    if (not isinstance(pull, dict) or pull.get("number") != args.pull_number
            or pull.get("base", {}).get("repo", {}).get("id") != repository["id"]
            or not checker.SHA.fullmatch(str(pull.get("head", {}).get("sha", "")))
            or not checker.SHA.fullmatch(str(pull.get("base", {}).get("sha", "")))
            or pull.get("base", {}).get("ref") == repository["default_branch"] and pull["base"]["sha"] != sha
            or (args.expected_head is not None and args.expected_head != pull["head"]["sha"])
            or (args.default_target_only and pull.get("base", {}).get("ref") != repository["default_branch"])):
        raise CollectionUnavailable("PR identity, target or HEAD changed; refresh collection")
    metadata = checker.metadata_from_body(pull.get("body") or "")
    if metadata["schema_version"] != 2:
        raise CollectionUnavailable("schema_version 2 delivery metadata required; old payload is legacy diagnostic only")
    numbers = checker.linked_issue_numbers(pull.get("body") or "")
    files = pull_files(api, prefix, args.pull_number, pull)
    delivery = metadata["delivery"]
    predecessor_pulls, predecessor_files = [], {}
    for declaration in delivery["predecessors"]:
        number = declaration["pull_number"]
        predecessor = api.get(f"{prefix}/pulls/{number}")
        if (not isinstance(predecessor, dict) or predecessor.get("number") != number
                or predecessor.get("head", {}).get("sha") != declaration["head_sha"]
                or predecessor.get("base", {}).get("repo", {}).get("id") != repository["id"]):
            raise CollectionUnavailable("predecessor identity/fixed HEAD changed; refresh collection")
        predecessor_pulls.append(predecessor)
        predecessor_files[str(number)] = pull_files(api, prefix, number, predecessor)
    pairs = [(delivery["development_base_sha"], pull["head"]["sha"]),
             (delivery["net_diff_base_sha"], pull["head"]["sha"])]
    pairs += [(left["head_sha"], right["head_sha"])
              for left, right in zip(delivery["predecessors"], delivery["predecessors"][1:])]
    comparisons = {pair: comparison(api, checker, prefix, *pair) for pair in dict.fromkeys(pairs)}
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
    if pull_files(api, prefix, args.pull_number, pull) != files:
        raise CollectionUnavailable("PR files changed during collection; refresh collection")
    for predecessor in predecessor_pulls:
        number = predecessor["number"]
        if (api.get(f"{prefix}/pulls/{number}") != predecessor
                or pull_files(api, prefix, number, predecessor) != predecessor_files[str(number)]):
            raise CollectionUnavailable("predecessor state/HEAD/files changed during collection; refresh collection")
    for pair, before in comparisons.items():
        if comparison(api, checker, prefix, *pair) != before:
            raise CollectionUnavailable("fixed comparison changed during collection; refresh collection")
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
        "version": INPUT_VERSION, "check_contract": CHECK_CONTRACT_VERSION, "source": "github-get", "collected_at": started,
        "verified_at": datetime.now(timezone.utc).isoformat(), "repository_id": repository["id"],
        "default_branch": repository["default_branch"], "trusted_sha": sha,
        "pull_number": args.pull_number, "head_sha": pull["head"]["sha"],
        "base_ref": pull["base"]["ref"],
        "trusted_resources": {path: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                              for path, raw in sources.items()},
        "unverified": ["human_approval", "effective_account_permissions", "native_branch_protection", "actual_skill_loading",
                       "unlisted_issue_claim_conflicts", "historical_write_authorization", "old_process_termination",
                       "protocol_current_head_review", "native_required_reviews"],
    }
    return {"trusted_ref_verified": True, "trusted_sha": sha,
            "repository": {"id": repository["id"], "full_name": repository["full_name"],
                           "default_branch": repository["default_branch"]},
            "pull": pull, "files": files, "reviews": reviews, "issues": issues,
            "config": config_text, "authorization": authorization,
            "claim_comments": claims, "issue_comments": comments, "snapshot": snapshot,
            "predecessor_pulls": predecessor_pulls, "predecessor_files": predecessor_files,
            "development_compare": comparisons[pairs[0]], "net_diff": comparisons[pairs[1]],
            "predecessor_compares": [comparisons[pair] for pair in pairs[2:]]}


if __name__ == "__main__":
    # The direct CLI is a locator too: formal collection uses the verified deployed copy.
    launcher = Path(__file__).with_name("run_pr_metadata_check.py")
    if not launcher.is_file() or launcher.is_symlink():
        print(json.dumps({"result": "unknown", "errors": ["local launcher missing or symlink; repair installation"], "snapshot": None}))
        raise SystemExit(2)
    raise SystemExit(subprocess.call([sys.executable, str(launcher), "--collect-only", *sys.argv[1:]]))
