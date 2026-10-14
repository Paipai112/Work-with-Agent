"""Data-only PR metadata check. No network, PR code execution, or generic YAML parsing.

Closing keywords in commit messages are outside this check; re-read Issue state after merge.
"""

import json
import re
import sys
from pathlib import Path, PurePosixPath


COLLECTOR_INPUT_VERSION = 2
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


def report(errors):
    print("::notice::metadata check does not verify human approval, effective account permissions, or real Skill loading")
    print("::notice::closing keywords in commit messages are not checked; read back Issue state after merge")
    for error in sorted(set(errors)):
        safe = error.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::{safe}")
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
    if not isinstance(metadata, dict) or set(metadata) != METADATA_FIELDS:
        raise ValueError("missing or unknown collaboration metadata fields")
    if type(metadata["schema_version"]) is not int or metadata["schema_version"] != 1:
        raise ValueError("unsupported collaboration metadata version")
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


def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError("expected INPUT_JSON OUTPUT_DIR")
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)
        return report(check(data))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return report([f"metadata check unavailable: {type(exc).__name__}"])


if __name__ == "__main__":
    raise SystemExit(main())
