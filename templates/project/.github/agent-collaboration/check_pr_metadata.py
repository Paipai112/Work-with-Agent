"""Data-only PR metadata check. No network, PR code execution, or generic YAML parsing.

Closing keywords in commit messages are outside this check; re-read Issue state after merge.
"""

import json
import importlib.util
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath


COLLECTOR_INPUT_VERSION = 2
FORMAL_CHECK_VERSION = 2


class EvidenceUnknown(ValueError):
    """Incomplete source or deployment evidence cannot give a formal verdict."""
SHA = re.compile(r"^[0-9a-f]{40}$")
ACTOR = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
BRANCH = re.compile(r"^agent/([a-z][a-z0-9-]*)/issue-([1-9][0-9]*)-[a-z0-9][a-z0-9-]*$")
METADATA_MARKER = "<!-- agent-collaboration:metadata"
METADATA_FIELDS = {
    "schema_version", "primary_issue", "closes_issues", "actor_id", "controlled_by",
    "controlled_by_id", "runtime", "session_id", "skill_version", "head_sha",
    "base_branch", "claim_urls", "workflow",
}
ISSUE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?[ \t]+#([1-9][0-9]*)\b", re.I)
CLAIM_URL = re.compile(r"https://github\.com/([^/#?]+/[^/#?]+)/issues/([1-9][0-9]*)#issuecomment-([1-9][0-9]*)", re.I)
GOVERNANCE_PREFIXES = (
    ".github/agent-collaboration/",
    ".github/workflows/",
    ".github/ISSUE_TEMPLATE/",
    ".github/PULL_REQUEST_TEMPLATE/",
    "PULL_REQUEST_TEMPLATE/",
    "docs/PULL_REQUEST_TEMPLATE/",
    ".claude/rules/",
    ".agents/skills/",
    ".claude/skills/",
    ".pi/agent/skills/",
    ".pi/skills/",
    ".github/actions/",
)
GOVERNANCE_EXACT = {
    "CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS",
    "pull_request_template.md", ".github/pull_request_template.md", "docs/pull_request_template.md",
    ".codex/config.toml", ".pi/settings.json", ".claude/settings.json", ".claude/settings.local.json",
    ".github/copilot-instructions.md",
}


def restricted_yaml(source):
    """Parse only setup-generated plain mapping/list YAML; reject advanced syntax."""
    def error(message, line):
        return ValueError(f"{message} at line {line}")

    if len(source) > 262144:
        raise error("YAML too large", 1)
    lines = []
    for number, raw in enumerate(source.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw or raw.rstrip() != raw or raw.lstrip().startswith(("---", "...")):
            raise error("unsupported YAML syntax", number)
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise error("unsupported YAML indentation", number)
        lines.append((indent, raw.strip(), number))

    def scalar(value, number):
        if value == "[]":
            return []
        if value in ("true", "false"):
            return value == "true"
        if re.fullmatch(r"[1-9][0-9]*|0", value):
            return int(value)
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise error("invalid quoted YAML value", number)
            if value[0] == '"':
                try:
                    return json.loads(value)
                except ValueError:
                    raise error("invalid quoted YAML value", number) from None
            if "''" in value:
                raise error("unsupported YAML escaping", number)
            return value[1:-1]
        if not re.fullmatch(r"[A-Za-z0-9_./:@+-]+", value):
            raise error("unsupported or ambiguous YAML scalar", number)
        if value.lower() in {"null", "yes", "no", "on", "off", "true", "false"}:
            raise error("ambiguous YAML scalar", number)
        return value

    def key_value(content, number):
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*):(?: (.*))?", content)
        if not match or match.group(1) == "<<":
            raise error("unsupported YAML key", number)
        return match.group(1), match.group(2)

    def block(index, indent, indentless=False):
        if index >= len(lines) or lines[index][0] != indent:
            raise error("invalid YAML block", lines[min(index, len(lines) - 1)][2])
        if lines[index][1].startswith("- "):
            result = []
            while index < len(lines) and lines[index][0] == indent:
                content = lines[index][1]
                if not content.startswith("- "):
                    if indentless:
                        break
                    raise error("mixed YAML list and map", lines[index][2])
                item = content[2:]
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*:.*", item):
                    child = [(indent + 2, item, lines[index][2])]
                    index += 1
                    while index < len(lines) and lines[index][0] > indent:
                        child.append(lines[index])
                        index += 1
                    value, consumed = parse(child, 0, indent + 2)
                    if consumed != len(child):
                        raise error("invalid YAML list item", child[consumed][2])
                    result.append(value)
                else:
                    result.append(scalar(item, lines[index][2]))
                    index += 1
            return result, index
        result = {}
        while index < len(lines) and lines[index][0] == indent:
            number = lines[index][2]
            key, raw_value = key_value(lines[index][1], number)
            if key in result:
                raise error("duplicate YAML key", number)
            index += 1
            if raw_value is None:
                if index >= len(lines):
                    raise error("missing YAML value", number)
                if lines[index][0] == indent + 2:
                    value, index = block(index, indent + 2)
                elif lines[index][0] == indent and lines[index][1].startswith("- "):
                    value, index = block(index, indent, indentless=True)
                else:
                    raise error("missing YAML value", number)
            else:
                value = scalar(raw_value, number)
            result[key] = value
        return result, index

    def parse(items, index, indent):
        nonlocal lines
        original = lines
        lines = items
        try:
            return block(index, indent)
        finally:
            lines = original

    if not lines:
        raise error("empty YAML", 1)
    data, end = block(0, 0)
    if end != len(lines) or not isinstance(data, dict):
        raise error("invalid YAML document", lines[end][2] if end < len(lines) else lines[0][2])
    return data


def report(errors, mode="formal", unknown=False):
    print("::notice::metadata check does not verify human approval, effective account permissions, or real Skill loading")
    print("::notice::closing keywords in commit messages are not checked; read back Issue state after merge")
    for error in sorted(set(errors)):
        safe = error.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::{safe}")
    if mode == "legacy":
        print("::notice::legacy metadata diagnostic only; not a v0.2 formal check")
        print("LEGACY_RESULT=fail" if errors else "LEGACY_RESULT=pass")
        return 1 if errors else 0
    if unknown:
        print("RESULT=unknown")
        return 2
    print("::notice::offline checker result applies to this snapshot only; live provenance requires the trusted launcher")
    print("::notice::unlisted Issue claims and historical write authorization require Agent preflight; process termination is not proven")
    print("::notice::protocol current-HEAD review and native Required Reviews remain unverified; metadata pass is not merge authorization")
    print("RESULT=fail" if errors else "RESULT=pass")
    return 1 if errors else 0


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def outside_code_fences(text):
    """Ignore examples, not live closing statements or metadata."""
    output, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^[ \t]{0,3}(\x60{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            output.append("")
        else:
            output.append(line if fence is None else "")
    return "\n".join(output)


def metadata_from_body(body):
    if not isinstance(body, str) or len(body) > 262144:
        raise ValueError("PR body unavailable or too large")
    if body.count(METADATA_MARKER) != 1:
        raise ValueError("exactly one collaboration metadata block is required")
    matches = re.findall(
        r"(?ms)^<!-- agent-collaboration:metadata[ \t]*\n(.*?)\n-->[ \t]*$",
        outside_code_fences(body),
    )
    if len(matches) != 1:
        raise ValueError("invalid collaboration metadata block")
    metadata = json.loads(matches[0], object_pairs_hook=unique_object)
    if not isinstance(metadata, dict):
        raise ValueError("missing or unknown collaboration metadata fields")
    version = metadata.get("schema_version")
    expected = METADATA_FIELDS | {"delivery"} if version == 2 else METADATA_FIELDS
    if set(metadata) != expected:
        raise ValueError("missing or unknown collaboration metadata fields")
    if type(version) is not int or version not in {1, 2}:
        raise ValueError("unsupported collaboration metadata version")
    if version == 2:
        delivery = metadata["delivery"]
        if not isinstance(delivery, dict) or set(delivery) != {"development_base_sha", "net_diff_base_sha", "predecessors", "merge_order"}:
            raise ValueError("invalid delivery metadata fields")
        if any(not isinstance(delivery[key], str) or not SHA.fullmatch(delivery[key])
               for key in ("development_base_sha", "net_diff_base_sha")):
            raise ValueError("delivery requires fixed full SHA baselines")
        predecessors = delivery["predecessors"]
        if (not isinstance(predecessors, list) or len(predecessors) > 20
                or any(not isinstance(item, dict) or set(item) != {"pull_number", "head_sha"}
                       or type(item["pull_number"]) is not int or item["pull_number"] < 1
                       or not isinstance(item["head_sha"], str) or not SHA.fullmatch(item["head_sha"])
                       for item in predecessors)
                or len({item["pull_number"] for item in predecessors}) != len(predecessors)):
            raise ValueError("invalid or duplicate predecessor PR declarations")
        order = delivery["merge_order"]
        if (not isinstance(order, list) or any(type(number) is not int or number < 1 for number in order)
                or len(set(order)) != len(order) or len(order) != len(predecessors) + 1
                or order[:-1] != [item["pull_number"] for item in predecessors]):
            raise ValueError("invalid merge order")
    if type(metadata["primary_issue"]) is not int or metadata["primary_issue"] < 1:
        raise ValueError("invalid primary_issue")
    closes = metadata["closes_issues"]
    if (not isinstance(closes, list) or len(closes) > 100
            or any(type(n) is not int or n < 1 for n in closes)
            or len(set(closes)) != len(closes)):
        raise ValueError("invalid or duplicate closes_issues")
    if type(metadata["controlled_by_id"]) is not int or metadata["controlled_by_id"] < 1:
        raise ValueError("invalid controlling account ID")
    for field in ("actor_id", "controlled_by", "runtime", "session_id", "skill_version",
                  "head_sha", "base_branch", "workflow"):
        value = metadata[field]
        if not isinstance(value, str) or not value.strip() or "<" in value or "\n" in value:
            raise ValueError(f"invalid metadata field: {field}")
    if metadata["workflow"] not in {"daily", "setup"}:
        raise ValueError("invalid workflow")
    links = metadata["claim_urls"]
    if (not isinstance(links, list) or not links or len(links) > 100
            or any(not isinstance(x, str) or not CLAIM_URL.fullmatch(x) for x in links)
            or len(set(links)) != len(links)):
        raise ValueError("invalid or duplicate claim URLs")
    return metadata


def linked_issue_numbers(body):
    metadata = metadata_from_body(body)
    claim_issues = {int(CLAIM_URL.fullmatch(url).group(2)) for url in metadata["claim_urls"]}
    return sorted({metadata["primary_issue"], *metadata["closes_issues"], *claim_issues})


def claim_comment_ids(body):
    """Return the sorted comment ids referenced by the metadata claim URLs."""
    metadata = metadata_from_body(body)
    return sorted({int(CLAIM_URL.fullmatch(url).group(3)) for url in metadata["claim_urls"]})


def managed_paths(config):
    """Use the same bounded config paths as setup and the daily Skill."""
    paths = config.get("managed_paths")
    if not isinstance(paths, dict):
        raise ValueError("trusted managed paths unavailable")
    for field in ("protocol", "authorization", "managed_resources"):
        path = paths.get(field)
        if (not isinstance(path, str) or "\\" in path
                or not path.startswith(".github/agent-collaboration/")
                or any(x in {"", ".", ".."} for x in path.split("/"))
                or str(PurePosixPath(path)) != path):
            raise ValueError("trusted managed paths unsupported")
    return paths


def is_governance_path(path):
    if not isinstance(path, str):
        return False
    lower = path.lower()
    if lower in {p.lower() for p in GOVERNANCE_EXACT}:
        return True
    if any(lower.startswith(p.lower()) for p in GOVERNANCE_PREFIXES):
        return True
    name = PurePosixPath(path).name
    return name == "AGENTS.override.md" or (
        "/" in path and name in {"AGENTS.md", "CLAUDE.md"}
    )


def governance_files(files, config):
    governed, errors = [], []
    paths = managed_paths(config)
    entries = set(paths.get("entry_files", ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"]))
    exact = {paths[key] for key in ("protocol", "authorization", "managed_resources")}
    if paths.get("pull_request_template"):
        exact.add(paths["pull_request_template"])
    for file in files:
        path, prior = file["filename"], file.get("previous_filename", "")
        candidates = (path, prior) if file.get("status") == "renamed" else (path,)
        if any(p in exact or is_governance_path(p) for p in candidates):
            governed.append(path)
        elif any(p in entries for p in candidates):
            # Entry files steer agents: any edit requires the separate governance review.
            governed.append(path)
    # Path lists and entry-file handling are conservative heuristics, not a semantic proof.
    return governed, errors


def _check(data):
    errors = []
    if data.get("trusted_ref_verified") is not True or not SHA.fullmatch(str(data.get("trusted_sha", ""))):
        errors.append("trusted default-branch source unverified")
    try:
        config = data["config"]
        auth = data["authorization"]
        parsed = {}
        for field, value in (("config", config), ("authorization", auth)):
            try:
                parsed[field] = restricted_yaml(value) if isinstance(value, str) else value
            except ValueError as exc:
                return errors + [f"metadata or trusted config unverified: {field} YAML: {exc}"]
        config, auth = parsed["config"], parsed["authorization"]
        repo, pull = data["repository"], data["pull"]
        files, issues, reviews = data["files"], data["issues"], data["reviews"]
        assert isinstance(config, dict) and isinstance(auth, dict)
        assert isinstance(files, list) and isinstance(issues, list) and isinstance(reviews, list)
    except (KeyError, TypeError, ValueError, AssertionError) as exc:
        return errors + [f"metadata or trusted config unverified: {type(exc).__name__}"]
    body = pull.get("body") or ""
    try:
        metadata = metadata_from_body(body)
        managed_paths(config)
    except (ValueError, TypeError) as exc:
        return errors + [str(exc)]
    try:
        owner, name = repo["full_name"].split("/")
        ar = auth["repository"]
        if (ar["repository_id"] != repo["id"] or ar["owner"].lower() != owner.lower()
                or ar["name"].lower() != name.lower() or ar["default_branch"] != repo["default_branch"]
                or ar["hostname"] != "github.com"):
            errors.append("authorization repository mismatch")
        integrations = config.get("branch_policy", {}).get("integration_branches", [])
        if (not isinstance(integrations, list)
                or any(not isinstance(ref, str) or not BRANCH.fullmatch(ref) for ref in integrations)
                or len(set(integrations)) != len(integrations)):
            errors.append("invalid integration branch policy")
            integrations = []
        base = pull["base"]["ref"]
        if base not in [repo["default_branch"], *integrations] or metadata["base_branch"] != base:
            errors.append("unapproved or mismatched PR base")
    except (KeyError, TypeError, ValueError):
        errors.append("repository identity unverified")
    if config.get("schema_version") != 1 or auth.get("schema_version") != 1:
        errors.append("trusted schema version unverified")
    if set(auth) != {"schema_version", "repository", "leader_delegations"}:
        errors.append("unknown trusted authorization field")
    if isinstance(auth.get("repository"), dict) and set(auth["repository"]) != {
        "hostname", "repository_id", "owner", "name", "default_branch", "default_branch_source_sha"
    }:
        errors.append("unknown trusted authorization field")
    if not isinstance(auth.get("leader_delegations"), list) or any(
        not isinstance(d, dict) or not set(d).issubset({
            "actor_id", "controlled_by", "controlled_by_id", "permission_ceiling",
            "account_permission_at_grant", "approval_evidence", "status", "granted_at", "revoked_at"
        }) for d in auth.get("leader_delegations", [])
    ):
        errors.append("unknown trusted authorization field")
    actor = metadata["actor_id"]
    if not ACTOR.fullmatch(actor) or actor in {"leader", "member", "codex", "claude", "pi", "claude-code", "pi-agent"} or re.search(r"-[0-9]+$", actor):
        errors.append("invalid responsibility actor_id")
    if (metadata["controlled_by"].lower() != pull.get("user", {}).get("login", "").lower()
            or metadata["controlled_by_id"] != pull.get("user", {}).get("id")):
        errors.append("controlled_by differs from PR author account")
    version = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", metadata["skill_version"])
    minimum = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", str(config.get("minimum_runtime_skill_version", "")))
    if not version or not minimum or tuple(map(int, version.groups())) < tuple(map(int, minimum.groups())):
        errors.append("skill version declaration below minimum or unverified")
    if not SHA.fullmatch(metadata["head_sha"]) or metadata["head_sha"] != pull.get("head", {}).get("sha"):
        errors.append("declared HEAD SHA differs from current PR HEAD")
    visible = re.sub(r"<!--.*?-->", "", outside_code_fences(body), flags=re.S)
    if {int(n) for n in ISSUE.findall(visible)} != set(metadata["closes_issues"]):
        errors.append("closing statements differ from closes_issues")
    if re.search(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?[ \t]+(?:https?://|[\w.-]+/)", visible, re.I):
        errors.append("cross-repository or URL closing syntax is unsupported; use local #numbers")
    primary = metadata["primary_issue"]
    try:
        must_be_open = {primary, *metadata["closes_issues"]}
        for number in linked_issue_numbers(body):
            matches = [x for x in issues if x["number"] == number]
            if len(matches) != 1:
                raise ValueError("missing or duplicate Issue")
            if matches[0].get("pull_request") or matches[0].get("state") not in {"open", "closed"}:
                errors.append(f"linked task is not a verified Issue: {number}")
            elif number in must_be_open and matches[0]["state"] != "open":
                errors.append(f"linked Issue is not an open Issue: {number}")
        branch = BRANCH.fullmatch(pull["head"]["ref"])
        if not branch or branch.group(1) != actor or int(branch.group(2)) != primary:
            errors.append("branch mismatch")
        claims = [CLAIM_URL.fullmatch(url) for url in metadata["claim_urls"]]
        if any(match.group(1).lower() != repo["full_name"].lower() for match in claims):
            errors.append("claim URL does not reference this repository")
        if not any(int(match.group(2)) == primary for match in claims):
            errors.append("claim URLs must include the primary Issue")
        comments = data.get("claim_comments")
        if not isinstance(comments, dict):
            errors.append("claim comments unverified")
        else:
            for url in metadata["claim_urls"]:
                comment = comments.get(url)
                if not isinstance(comment, dict):
                    errors.append("claim comment does not exist or is unverifiable")
                    continue
                if comment.get("user_id") != metadata["controlled_by_id"]:
                    errors.append("claim comment author differs from controlling account")
                if comment.get("issue_number") != int(CLAIM_URL.fullmatch(url).group(2)):
                    errors.append("claim comment issue mismatch")
    except (IndexError, StopIteration, KeyError, ValueError, TypeError):
        errors.append("linked Issue metadata unverified")
    paths = [f.get("filename") for f in files if isinstance(f, dict)]
    if not paths or len(paths) != len(files) or any(not isinstance(p, str) for p in paths):
        return errors + ["PR file list unverified"]
    governance, reachability_errors = governance_files(files, config)
    errors.extend(reachability_errors)
    if governance or metadata["workflow"] == "setup":
        # A metadata check cannot authorize setup. It only rejects mixed or undeclared governance.
        if len(governance) != len(files) or metadata["workflow"] != "setup" or pull["base"]["ref"] != repo["default_branch"]:
            errors.append("governance files require a separate setup PR")
        else:
            try:
                matches = [d for d in auth["leader_delegations"] if d["status"] == "active" and d["actor_id"] == actor and d["controlled_by_id"] == pull["user"]["id"] and d["controlled_by"].lower() == pull["user"]["login"].lower() and d["permission_ceiling"] in {"maintain", "admin"}]
                if len(matches) != 1:
                    errors.append("invalid Leader claim")
            except (KeyError, TypeError):
                errors.append("invalid Leader claim")
    approved = [r for r in reviews if isinstance(r, dict) and r.get("state") == "APPROVED" and r.get("user", {}).get("id") != pull.get("user", {}).get("id")]
    if approved and not any(r.get("commit_id") == pull.get("head", {}).get("sha") for r in approved):
        errors.append("stale review SHA")
    return errors


def check(data):
    try:
        return _check(data)
    except (KeyError, ValueError, TypeError, AttributeError):
        return ["metadata or trusted config unverified: malformed input"]


def deployed_helpers():
    directory = Path(__file__).resolve().parent
    for name in ("collaboration_event.py", "collaboration_scope.py", "collaboration-event.schema.json", "requirements-helpers.txt"):
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise EvidenceUnknown("deployed event/scope/schema/requirements missing; install the complete trusted chain")
    schema_path = directory / "collaboration-event.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        if schema.get("$id") != "https://schemas.github-agent-collaboration.dev/v1/collaboration-event.schema.json":
            raise ValueError("schema identity")
        modules = []
        for name in ("collaboration_event", "collaboration_scope"):
            spec = importlib.util.spec_from_file_location(name, directory / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            modules.append(module)
    except (OSError, ValueError, ImportError, SyntaxError, AttributeError) as error:
        raise EvidenceUnknown("deployed helper/schema incompatible; repair the trusted chain") from error
    return *modules, schema_path


def comment_envelope(record, repository, issue_number):
    if (not isinstance(record, dict) or type(record.get("id")) is not int or record["id"] < 1
            or type(record.get("user_id")) is not int or record["user_id"] < 1
            or record.get("issue_number") != issue_number
            or record.get("url") != f"https://github.com/{repository}/issues/{issue_number}#issuecomment-{record['id']}"
            or not isinstance(record.get("login"), str) or not record["login"]
            or not isinstance(record.get("body"), str)
            or not isinstance(record.get("updated_at"), str) or not record["updated_at"]):
        raise ValueError("collaboration comment envelope mismatch")


def event_inventory(data, metadata, event_helper, scope_helper, schema_path):
    comments = data.get("issue_comments")
    if not isinstance(comments, dict):
        raise EvidenceUnknown("complete related Issue comments required")
    required = {str(number) for number in linked_issue_numbers(data["pull"]["body"])}
    if not required.issubset(comments):
        raise EvidenceUnknown("related Issue comment inventory missing")
    entries, records, identifiers = {}, {}, set()
    for key, items in comments.items():
        if not isinstance(key, str) or not re.fullmatch(r"[1-9][0-9]*", key) or not isinstance(items, list):
            raise EvidenceUnknown("Issue comment inventory malformed")
        if len(items) > 3100:
            raise EvidenceUnknown("Issue comment inventory exceeds collection limit")
        for index, record in enumerate(items):
            comment_envelope(record, data["repository"]["full_name"], int(key))
            if record["id"] in identifiers or record["url"] in records:
                raise ValueError("duplicate collaboration comment ID/URL")
            identifiers.add(record["id"])
            records[record["url"]] = record
            body = record["body"]
            try:
                event = event_helper.parse_event_body(body)
            except event_helper.DependencyError as error:
                raise EvidenceUnknown(str(error)) from error
            except event_helper.EventError as error:
                if re.search(r"(?mi)(?:^|[{,])\s*[\"']?(?:event|event_id)[\"']?\s*:", body):
                    raise ValueError("collaboration event body invalid") from error
                continue
            if "event" not in event:
                continue
            try:
                event_helper.validate_event(event, schema_path)
            except event_helper.DependencyError as error:
                raise EvidenceUnknown(str(error)) from error
            except event_helper.EventError as error:
                if "schema invalid or incompatible" in str(error):
                    raise EvidenceUnknown("deployed event schema incompatible") from error
                raise ValueError("collaboration event schema validation failed") from error
            if (event["controlled_by_id"] != record["user_id"]
                    or event["controlled_by"].lower() != record["login"].lower()):
                raise ValueError("event controller differs from real comment author")
            scope_helper.scope_patterns(event["scope"])
            identity = (int(key), event["event_id"])
            if identity in entries:
                raise ValueError("duplicate collaboration event_id")
            entries[identity] = {"event": event, "record": record, "index": index, "issue_number": int(key)}
    return entries, records


def file_changes(files):
    if not isinstance(files, list):
        raise EvidenceUnknown("complete changed-file inventory required")
    changes = []
    for item in files:
        if not isinstance(item, dict) or item.get("status") not in {"added", "modified", "removed", "deleted", "renamed", "changed", "copied"}:
            raise ValueError("changed-file status unsupported")
        change = {"path": item.get("filename"), "status": {"removed": "deleted", "changed": "modified", "copied": "added"}.get(item["status"], item["status"])}
        if change["status"] == "renamed":
            change["previous_path"] = item.get("previous_filename")
        changes.append(change)
    return changes


def snapshot_evidence(data):
    snapshot, repo, pull = data["snapshot"], data["repository"], data["pull"]
    if (snapshot.get("source") != "github-get" or snapshot.get("repository_id") != repo["id"]
            or snapshot.get("default_branch") != repo["default_branch"]
            or snapshot.get("trusted_sha") != data.get("trusted_sha")
            or snapshot.get("pull_number") != pull["number"]
            or snapshot.get("head_sha") != pull["head"]["sha"]
            or snapshot.get("base_ref") != pull["base"]["ref"]
            or any(not isinstance(snapshot.get(key), str) or not snapshot[key]
                   for key in ("collected_at", "verified_at"))):
        raise EvidenceUnknown("snapshot repository/default SHA/PR binding incomplete or inconsistent")
    if pull["base"]["ref"] == repo["default_branch"] and pull["base"]["sha"] != data["trusted_sha"]:
        raise EvidenceUnknown("default-target base differs from the verified current default SHA; refresh collection")
    directory = Path(__file__).resolve().parent
    config = restricted_yaml(data["config"])
    authorization_path = managed_paths(config)["authorization"]
    names = ["run_pr_metadata_check.py", "collect_pr_metadata.py", "check_pr_metadata.py",
             "collaboration_event.py", "collaboration_scope.py", "collaboration-event.schema.json",
             "requirements-helpers.txt", "config.yml"]
    expected = {".github/agent-collaboration/" + name for name in names} | {authorization_path}
    receipts = snapshot.get("trusted_resources")
    if not isinstance(receipts, dict) or set(receipts) != expected:
        raise EvidenceUnknown("trusted deployment resource receipts incomplete")
    for path in expected:
        receipt = receipts[path]
        if (not isinstance(receipt, dict) or set(receipt) != {"sha256", "bytes"}
                or not isinstance(receipt["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"])
                or type(receipt["bytes"]) is not int or receipt["bytes"] < 1):
            raise EvidenceUnknown("trusted resource receipt malformed")
        if path == authorization_path:
            source = data["authorization"].encode("utf-8")
        elif path.endswith("/config.yml"):
            source = data["config"].encode("utf-8")
        else:
            local = directory / PurePosixPath(path).name
            if local.is_symlink() or not local.is_file():
                raise EvidenceUnknown("deployed resource missing")
            source = local.read_bytes()
        if receipt != {"sha256": hashlib.sha256(source).hexdigest(), "bytes": len(source)}:
            raise EvidenceUnknown("trusted deployed resource bytes differ from snapshot")


def comparison_evidence(value, base, head):
    if (not isinstance(value, dict) or value.get("complete") is not True
            or value.get("base_sha") != base or value.get("head_sha") != head
            or not SHA.fullmatch(str(value.get("merge_base_sha", "")))
            or value.get("status") not in {"ahead", "behind", "diverged", "identical"}
            or not isinstance(value.get("commits"), list) or not isinstance(value.get("files"), list)):
        raise EvidenceUnknown("fixed comparison incomplete or bound to another SHA")
    commits = value["commits"]
    if (len(value["files"]) >= 300 or len(commits) > 3100
            or len(set(commits)) != len(commits)
            or any(not isinstance(sha, str) or not SHA.fullmatch(sha) for sha in commits)
            or (value["status"] != "identical" and (not commits or commits[-1] != head))
            or value["status"] == "identical" and (base != head or commits)):
        raise EvidenceUnknown("comparison pagination/file cap cannot prove complete fixed facts")
    changes = file_changes(value["files"])
    if len({item["path"] for item in changes}) != len(changes):
        raise EvidenceUnknown("duplicate comparison changed paths")
    return changes


def change_tuples(files):
    return {(item["path"], item["status"], item.get("previous_path")) for item in file_changes(files)}


def delivery_facts(data, metadata):
    delivery, pull = metadata["delivery"], data["pull"]
    if any(key not in data for key in ("development_compare", "net_diff", "predecessor_pulls")):
        raise EvidenceUnknown("complete v2 fixed delivery facts required")
    if not isinstance(data["predecessor_pulls"], list):
        raise EvidenceUnknown("predecessor PR inventory malformed")
    comparison_evidence(data["development_compare"], delivery["development_base_sha"], pull["head"]["sha"])
    comparison_evidence(data["net_diff"], delivery["net_diff_base_sha"], pull["head"]["sha"])
    if (data["development_compare"]["status"] not in {"ahead", "identical"}
            or data["development_compare"]["merge_base_sha"] != delivery["development_base_sha"]):
        raise ValueError("declared development baseline is not an ancestor of current HEAD")
    if delivery["merge_order"][-1] != pull["number"]:
        raise ValueError("merge order does not end with current PR")
    declarations = delivery["predecessors"]
    if not declarations:
        if data["predecessor_pulls"]:
            raise ValueError("undeclared predecessor PR facts")
        if delivery["net_diff_base_sha"] != pull["base"]["sha"]:
            raise ValueError("final net diff must use the current PR target baseline")
        if change_tuples(data["files"]) != change_tuples(data["net_diff"]["files"]):
            raise ValueError("API PR files and fixed final net diff disagree")
        return []
    pulls = data["predecessor_pulls"]
    inventory, comparisons = data.get("predecessor_files"), data.get("predecessor_compares")
    if (len(pulls) != len(declarations) or not isinstance(inventory, dict)
            or set(inventory) != {str(item["pull_number"]) for item in declarations}
            or not isinstance(comparisons, list) or len(comparisons) != len(declarations) - 1):
        raise EvidenceUnknown("complete fixed predecessor files/ancestry inventory required")
    merged_times, inherited = [], set()
    pending = False
    for declaration, predecessor in zip(declarations, pulls):
        if (not isinstance(predecessor, dict) or predecessor.get("number") != declaration["pull_number"]
                or predecessor.get("base", {}).get("repo", {}).get("id") != data["repository"]["id"]
                or predecessor.get("base", {}).get("ref") != pull["base"]["ref"]
                or predecessor.get("head", {}).get("sha") != declaration["head_sha"]):
            raise ValueError("predecessor identity/target/fixed HEAD changed")
        files = inventory[str(declaration["pull_number"])]
        changes = file_changes(files)
        if (len(files) >= 3000 or len({item["path"] for item in changes}) != len(changes)
                or predecessor.get("changed_files", len(files)) != len(files)):
            raise EvidenceUnknown("predecessor files truncated or ambiguous")
        inherited.update(item["path"] for item in changes)
        inherited.update(item["previous_path"] for item in changes if item["status"] == "renamed")
        if predecessor.get("merged") is True:
            if (pending or predecessor.get("state") != "closed"
                    or not SHA.fullmatch(str(predecessor.get("merge_commit_sha", "")))):
                raise ValueError("predecessor merge order/result unsupported or inconsistent")
            merged_times.append(timestamp(predecessor.get("merged_at")))
        elif predecessor.get("merged") is False and predecessor.get("state") == "open":
            pending = True
        else:
            raise ValueError("predecessor closed without a verified merge")
    if merged_times != sorted(merged_times):
        raise ValueError("predecessors were merged out of the declared order")
    for index, value in enumerate(comparisons):
        base, head = declarations[index]["head_sha"], declarations[index + 1]["head_sha"]
        comparison_evidence(value, base, head)
        if value["status"] not in {"ahead", "identical"} or value["merge_base_sha"] != base:
            raise ValueError("predecessor merge order lacks actual fixed-HEAD ancestry")
    if pending:
        last = declarations[-1]["head_sha"]
        if pull.get("draft") is not True:
            raise ValueError("unmerged predecessors permit Draft net-increment checks only; not Ready or merge")
        if delivery["net_diff_base_sha"] != last or delivery["development_base_sha"] != last:
            raise ValueError("Draft stacked baselines must use the last fixed predecessor HEAD")
        net_paths = {path for item in file_changes(data["net_diff"]["files"])
                     for path in (item["path"], item.get("previous_path")) if path is not None}
        api_paths = {path for item in file_changes(data["files"])
                     for path in (item["path"], item.get("previous_path")) if path is not None}
        if not api_paths.issubset(net_paths | inherited) or not net_paths.issubset(api_paths | inherited):
            raise EvidenceUnknown("Draft total diff cannot be safely explained by fixed predecessor files and current net increment")
    else:
        if delivery["net_diff_base_sha"] != pull["base"]["sha"]:
            raise ValueError("merged predecessors require a fresh net diff on the current target baseline")
        if change_tuples(data["files"]) != change_tuples(data["net_diff"]["files"]):
            raise ValueError("API PR files and fixed final net diff disagree after predecessor merge")
    return merged_times


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone missing")
        return parsed
    except (TypeError, AttributeError, ValueError) as error:
        raise EvidenceUnknown("merge/review/event timestamp unavailable or malformed") from error


def same_identity(left, right):
    return (all(left.get(field) == right.get(field) for field in ("controlled_by_id", "actor_id", "session_id"))
            and str(left.get("controlled_by", "")).lower() == str(right.get("controlled_by", "")).lower())


def delegation_evidence(delegation, entry):
    approval = delegation.get("approval_evidence")
    if (not isinstance(approval, dict) or set(approval) != {"github_pr_url", "approved_by", "approved_at", "approved_head_sha"}
            or not re.fullmatch(r"https://github\.com/[^/]+/[^/]+/pull/[1-9][0-9]*", str(approval.get("github_pr_url", "")))
            or not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip()
            or not SHA.fullmatch(str(approval.get("approved_head_sha", "")))
            or delegation.get("account_permission_at_grant") not in {"maintain", "admin"}
            or delegation.get("permission_ceiling") == "admin" and delegation["account_permission_at_grant"] != "admin"
            or delegation.get("revoked_at") is not None):
        raise EvidenceUnknown("canonical active Leader delegation evidence incomplete; human approval/live permissions are not proven")
    if not timestamp(approval["approved_at"]) <= timestamp(delegation.get("granted_at")) <= timestamp(entry["record"]["updated_at"]):
        raise EvidenceUnknown("Leader delegation evidence timestamps inconsistent")


def lineage_states(entries, authorization):
    states, roots = {}, {}
    for key, entry in entries.items():
        event = entry["event"]
        kind, prior_id = event["event"], event["previous_event_id"]
        if prior_id is None:
            if kind != "claim":
                raise ValueError("non-claim event has no predecessor")
            states[key] = {"root": entry, "current": entry, "status": "active", "review_threshold": None}
            roots[key] = key
            continue
        prior_key = (entry["issue_number"], prior_id)
        prior = entries.get(prior_key)
        if (prior is None or prior["index"] >= entry["index"]
                or event.get("github_comment_id") != prior["record"]["id"]
                or event.get("github_comment_url") != prior["record"]["url"]
                or prior_key not in roots):
            raise ValueError("event predecessor ID/URL/order unverified")
        root = roots[prior_key]
        state = states[root]
        if state["current"] is not prior:
            raise ValueError("event branches from a superseded predecessor; no latest-comment winner")
        before = prior["event"]
        if kind == "claim":
            revision = event.get("revision")
            if revision is not None:
                original = state["root"]
                if (state["status"] != "active" or revision["original_event_id"] != original["event"]["event_id"]
                        or revision["github_comment_id"] != original["record"]["id"]
                        or revision["github_comment_url"] != original["record"]["url"]
                        or revision["old_body_sha256"] != hashlib.sha256(original["record"]["body"].encode("utf-8")).hexdigest()
                        or not revision["reason"].strip()):
                    raise ValueError("revision must bind the exact original claim/comment/body and active lineage")
                for field in ("controlled_by_id", "controlled_by", "actor_id", "session_id", "scope", "branch", "task_kind"):
                    if event.get(field, "code" if field == "task_kind" else None) != before.get(field, "code" if field == "task_kind" else None):
                        raise ValueError("baseline/correction revision cannot change identity or scope")
                if revision["kind"] == "baseline":
                    if (event.get("task_kind", "code") != "code" or revision["from_base_head"] != before["base_head"]
                            or revision["to_base_head"] != event["base_head"] or revision["from_base_head"] == revision["to_base_head"]):
                        raise ValueError("baseline revision from/to does not match the recorded development baselines")
                elif event["base_head"] != before["base_head"]:
                    raise ValueError("correction cannot silently revise a development baseline")
                revised_at = timestamp(entry["record"]["updated_at"])
                state["review_threshold"] = max(state["review_threshold"] or revised_at, revised_at)
                state["current"] = entry
                roots[key] = root
                continue
            if before["event"] == "reassign":
                if (not same_identity(event, before["successor"]) or event["scope"] != before["scope"]
                        or event.get("base_head") != before.get("base_head")
                        or event.get("task_kind", "code") != before.get("task_kind", "code")
                        or before["old_process_status"] == "unknown" and event.get("branch") == before.get("branch")):
                    raise ValueError("successor claim differs from verified reassignment or reuses an uncertain writer branch")
            elif before["event"] not in {"handoff", "release"}:
                raise ValueError("successor claim requires a terminal predecessor")
            states[key] = {"root": entry, "current": entry, "status": "active", "review_threshold": state["review_threshold"]}
            roots[key] = key
            continue
        if kind == "reassign":
            original = state["root"]
            target = event["target"]
            if (state["status"] not in {"active", "handoff"} or not same_identity(target, before)
                    or target["claim_event_id"] != original["event"]["event_id"]
                    or target["claim_comment_id"] != original["record"]["id"]
                    or target["claim_comment_url"] != original["record"]["url"]
                    or any(event.get(field) != before.get(field) for field in ("scope", "branch", "base_head"))
                    or not event["reason"].strip()):
                raise ValueError("reassignment target/allocation/checkpoint mismatch")
            leaders = [delegation for delegation in authorization["leader_delegations"]
                       if delegation.get("status") == "active"
                       and delegation.get("controlled_by_id") == event["controlled_by_id"]
                       and str(delegation.get("controlled_by", "")).lower() == event["controlled_by"].lower()
                       and delegation.get("actor_id") == event["actor_id"]
                       and delegation.get("permission_ceiling") in {"maintain", "admin"}]
            if len(leaders) != 1:
                raise EvidenceUnknown("reassignment Leader delegation evidence unavailable or ambiguous; approval and live permissions remain unverified")
            delegation_evidence(leaders[0], entry)
            state.update(current=entry, status="reassigned")
            roots[key] = root
            continue
        for field in ("controlled_by_id", "controlled_by", "actor_id", "scope", "branch", "base_head"):
            if event.get(field) != before.get(field):
                raise ValueError("transfer changes owner, branch, scope or development baseline")
        if kind == "resume":
            if (state["status"] not in {"handoff", "release"}
                    or event["handoff_event_id"] != before["event_id"]
                    or event["session_id"] == before["session_id"]
                    or before.get("head_sha") is not None and event["head_sha"] != before["head_sha"]):
                raise ValueError("resume requires the exact terminal handoff/release and checkpoint")
            state["status"] = "active"
        else:
            if event["session_id"] != before["session_id"] or state["status"] not in {"active", "handoff"}:
                raise ValueError("terminal event does not belong to the active owner/session")
            state["status"] = kind
        state["current"] = entry
        roots[key] = root
    return states, roots


def formal_check(data):
    metadata = metadata_from_body(data["pull"].get("body") or "")
    if metadata["schema_version"] != 2:
        raise EvidenceUnknown("schema_version 2 delivery metadata required for formal checks")
    snapshot_evidence(data)
    merged_times = delivery_facts(data, metadata)
    # Governance of the current increment is checked independently from explained inherited files.
    errors = check({**data, "files": data["net_diff"]["files"]})
    if errors:
        return errors
    event_helper, scope_helper, schema_path = deployed_helpers()
    entries, records = event_inventory(data, metadata, event_helper, scope_helper, schema_path)
    states, roots = lineage_states(entries, restricted_yaml(data["authorization"]))
    selected, patterns, review_thresholds = set(), [], list(merged_times)
    for url in metadata["claim_urls"]:
        record = data["claim_comments"].get(url)
        if records.get(url) != record:
            raise ValueError("claim comment disagrees with complete Issue inventory")
        entry = next((entry for entry in entries.values() if entry["record"]["url"] == url), None)
        if entry is None:
            raise ValueError("claim body does not identify a validated event")
        source_event = entry["event"]
        if source_event["event"] != "claim" or source_event.get("task_kind", "code") != "code":
            raise ValueError("PR requires a code claim")
        root = roots[(entry["issue_number"], source_event["event_id"])]
        state = states[root]
        if state["status"] != "active":
            raise ValueError("linked claim has been released, handed off or reassigned")
        if root in selected:
            raise ValueError("duplicate links into the same claim allocation")
        event = state["current"]["event"]
        if any(event[field] != metadata[field] for field in ("actor_id", "session_id", "controlled_by_id")) or event["controlled_by"].lower() != metadata["controlled_by"].lower():
            raise ValueError("claim responsibility/session/controller differs from PR metadata")
        if event["branch"] != data["pull"]["head"]["ref"] or event["base_head"] != metadata["delivery"]["development_base_sha"]:
            raise ValueError("claim branch/development baseline mismatch")
        selected.add(root)
        patterns.extend(event["scope"])
        if state["review_threshold"] is not None:
            review_thresholds.append(state["review_threshold"])
        checkpoint = event.get("head_sha")
        if checkpoint is not None and checkpoint not in [metadata["delivery"]["development_base_sha"], *data["development_compare"]["commits"]]:
            raise ValueError("handoff/resume checkpoint is not in the collected development ancestry")
    others = [{"claim_url": state["root"]["record"]["url"], "scope": state["current"]["event"]["scope"]}
              for root, state in states.items() if root not in selected and state["status"] == "active"
              and state["current"]["event"].get("task_kind", "code") == "code"]
    result = scope_helper.compare({"scope": patterns, "changes": file_changes(data["net_diff"]["files"]), "other_claims": others})
    if result["status"] == "fail":
        errors.extend("changed path outside active claim scope: " + path for path in result["out_of_scope"])
        errors.extend("known competing claim covers changed path: " + item["path"] for item in result["conflicts"])
    head = data["pull"]["head"]["sha"]
    approvals = [review for review in data["reviews"] if review.get("state") == "APPROVED"]
    if approvals and not any(review.get("commit_id") == head
                             and (not review_thresholds or timestamp(review.get("submitted_at")) >= max(review_thresholds))
                             for review in approvals):
        errors.append("recorded review is stale relative to current HEAD/predecessor merges/baseline revision")
    return errors


def main():
    arguments = sys.argv[1:]
    legacy = "--legacy-diagnostic" in arguments
    arguments = [argument for argument in arguments if argument != "--legacy-diagnostic"]
    try:
        if len(arguments) != 2:
            raise ValueError("expected INPUT_JSON OUTPUT_DIR")
        data = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
        if not legacy and (not isinstance(data, dict) or not isinstance(data.get("snapshot"), dict)
                           or type(data["snapshot"].get("version")) is not int
                           or data["snapshot"]["version"] != COLLECTOR_INPUT_VERSION
                           or type(data["snapshot"].get("check_contract")) is not int
                           or data["snapshot"]["check_contract"] != FORMAL_CHECK_VERSION):
            return report(["complete v2 snapshot required; use --legacy-diagnostic explicitly for old metadata only"], unknown=True)
        Path(arguments[1]).mkdir(parents=True, exist_ok=True)
        return report(check(data) if legacy else formal_check(data), mode="legacy" if legacy else "formal")
    except EvidenceUnknown as exc:
        return report([str(exc)], unknown=True)
    except (KeyError, AttributeError) as exc:
        return report(["formal input facts incomplete or malformed"], unknown=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        message = str(exc) if not legacy and type(exc) is ValueError else f"metadata check unavailable: {type(exc).__name__}"
        return report([message], mode="legacy" if legacy else "formal")


if __name__ == "__main__":
    raise SystemExit(main())
