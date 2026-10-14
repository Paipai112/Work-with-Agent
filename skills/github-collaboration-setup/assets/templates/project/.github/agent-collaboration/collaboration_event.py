"""Construct and schema-validate collaboration event candidates; no implicit authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


class EventError(ValueError):
    """The candidate or observed envelope is unsafe or incompatible."""


class DependencyError(EventError):
    """Event-only runtime dependencies are unavailable."""


class ReadError(EventError):
    """An external GET cannot establish a complete, current observation."""


def dependencies():
    try:
        import yaml
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as error:
        raise DependencyError("event helper dependencies missing; install reviewed requirements-helpers.txt or this project's [helpers] extra; no automatic installation") from error
    return yaml, Draft202012Validator, FormatChecker


def resource_path(kind):
    script_directory = Path(__file__).resolve().parent
    directory = script_directory.parent
    choices = ([directory / "references/schemas/collaboration-event.schema.json",
                directory / "assets/schemas/collaboration-event.schema.json"] if kind == "schema" else
               [directory / "templates/events"])
    if directory.name == "shared":
        choices.insert(0, directory.parent / ("schemas/collaboration-event.schema.json" if kind == "schema" else "skills/github-collaboration/templates/events"))
    if kind == "schema":
        choices.insert(0, script_directory / "collaboration-event.schema.json")
    if script_directory.name != "scripts":
        choices = [script_directory / "collaboration-event.schema.json"] if kind == "schema" else []
    for path in choices:
        if path.exists():
            return path
    raise EventError(f"bundled event {kind} unavailable")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EventError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def parse_event_body(body: str) -> dict:
    """Parse pure YAML or one explicit YAML fence; outside text is explanatory only."""
    yaml, _, _ = dependencies()
    if not isinstance(body, str) or len(body.encode("utf-8")) > 262144:
        raise EventError("event body unavailable or too large")
    candidates, outside, current, lines = [], [], None, []
    for line in body.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)[\r\n]*$", line)
        if current is None and match:
            current = (match[1], match[2].strip().lower())
            lines = []
        elif current is not None and match and match[1][0] == current[0][0] and len(match[1]) >= len(current[0]) and not match[2].strip():
            if current[1] in {"yaml", "yml"}:
                candidates.append("".join(lines))
            current = None
        elif current is None:
            outside.append(line)
        else:
            lines.append(line)
    if current is not None:
        raise EventError("unterminated Markdown fence")
    if len(candidates) > 1:
        raise EventError("ambiguous event YAML fences")
    if candidates and re.search(r"(?m)^\s*event(?:_id)?:", "".join(outside)):
        raise EventError("unfenced event candidate outside YAML fence")
    source = candidates[0] if candidates else body

    class StrictLoader(yaml.SafeLoader):
        def construct_object(self, node, deep=False):
            allowed = {"str", "null", "bool", "int", "seq", "map"}
            kind = node.tag.removeprefix("tag:yaml.org,2002:")
            if kind not in allowed:
                raise EventError("unsupported YAML data type")
            if kind == "bool" and node.value not in {"true", "false"}:
                raise EventError("ambiguous YAML boolean; use true/false or quote a string")
            if kind == "int" and not re.fullmatch(r"0|[1-9][0-9]*", node.value):
                raise EventError("ambiguous YAML integer; use a decimal integer or quote a string")
            if kind == "null" and node.value != "null":
                raise EventError("ambiguous YAML null; use null")
            return super().construct_object(node, deep=deep)

        def construct_mapping(self, node, deep=False):
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key == "<<":
                    raise EventError("YAML mapping keys must be plain strings; merge keys are forbidden")
                if key in result:
                    raise EventError(f"duplicate YAML key at line {key_node.start_mark.line + 1}")
                result[key] = self.construct_object(value_node, deep=deep)
            return result

    try:
        for token in yaml.scan(source):
            if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken, yaml.tokens.TagToken, yaml.tokens.DirectiveToken)):
                raise EventError(f"YAML aliases/anchors/tags/directives forbidden at line {token.start_mark.line + 1}")
        documents = list(yaml.load_all(source, Loader=StrictLoader))
        if len(documents) != 1:
            raise EventError("exactly one YAML document is required")
        data = documents[0]
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise EventError("invalid event YAML" + location) from error
    except RecursionError as error:
        raise EventError("event YAML nesting is too deep") from error
    if not isinstance(data, dict):
        raise EventError("event YAML must be an object")
    return data


def validate_event(event: dict, schema_path: Path | None = None) -> dict:
    """One schema authority; success proves structure, never authorship or ownership."""
    _, Validator, FormatChecker = dependencies()
    try:
        schema = read_json(schema_path or resource_path("schema"))
        if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or schema.get("$id") != "https://schemas.github-agent-collaboration.dev/v1/collaboration-event.schema.json":
            raise EventError("event schema identity/version invalid or incompatible")
        Validator.check_schema(schema)
        errors = sorted(Validator(schema, format_checker=FormatChecker()).iter_errors(event), key=lambda e: str(list(e.path)))
    except Exception as error:
        raise EventError("event schema invalid or incompatible") from error
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.path) or "<event>"
        raise EventError(f"event schema validation failed at {location}: {error.validator}")
    return event


def digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("operation") not in {"publish", "append-correction", "edit"}:
        raise EventError("plan requires publish, append-correction, or edit operation")
    repository, author = plan.get("repository"), plan.get("expected_author")
    if not isinstance(repository, dict) or not isinstance(author, dict):
        raise EventError("plan requires exact repository and expected_author")
    if set(repository) != {"hostname", "id", "owner", "name"} or set(author) != {"user_id", "login"}:
        raise EventError("repository/author bindings accept identity fields only; exclude credentials")
    for field in ("hostname", "owner", "name"):
        value = repository.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", value) or value in {".", ".."}:
            raise EventError("invalid repository binding")
    for value in (repository.get("id"), plan.get("issue_number"), author.get("user_id")):
        if type(value) is not int or value < 1:
            raise EventError("repository, Issue and author IDs must be positive integers")
    if not isinstance(author.get("login"), str) or not author["login"]:
        raise EventError("expected_author requires login")
    event = validate_event(parse_event_body(plan.get("body")))
    if event["controlled_by_id"] != author["user_id"] or event["controlled_by"] != author["login"]:
        raise EventError("event controller must match expected real author")
    if event.get("previous_event_id") is not None and event.get("github_comment_url") != comment_url(plan, event["github_comment_id"]):
        raise EventError("predecessor URL must bind the exact repository, Issue and comment ID")
    if event["event"] == "reassign" and event["target"]["claim_comment_url"] != comment_url(plan, event["target"]["claim_comment_id"]):
        raise EventError("reassign target must bind the exact repository, Issue and comment ID")
    if plan["operation"] != "publish":
        if type(plan.get("comment_id")) is not int or plan["comment_id"] < 1:
            raise EventError("correction/edit requires exact comment_id")
        expected_url = comment_url(plan, plan["comment_id"])
        if plan.get("comment_url") != expected_url or not isinstance(plan.get("old_body_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", plan["old_body_sha256"]):
            raise EventError("correction/edit requires canonical comment_url and old_body_sha256")
    if plan["operation"] == "append-correction":
        revision = event.get("revision")
        if not isinstance(revision, dict) or revision.get("kind") != "correction" or not isinstance(revision.get("reason"), str) or not revision["reason"].strip():
            raise EventError("append-correction requires a linked correction revision with reason")
        for key, value in (("github_comment_id", plan["comment_id"]), ("github_comment_url", plan["comment_url"]), ("old_body_sha256", plan["old_body_sha256"])):
            if revision.get(key) != value:
                raise EventError("correction revision does not bind the exact original comment")
        if not isinstance(revision.get("original_event_id"), str) or revision["original_event_id"] == event["event_id"]:
            raise EventError("correction requires a new event_id and the original event_id")
    return event


def comment_url(plan, comment_id):
    repository = plan["repository"]
    return f"https://{repository['hostname']}/{repository['owner']}/{repository['name']}/issues/{plan['issue_number']}#issuecomment-{comment_id}"


def expected_approval(plan):
    return {"confirmed": True, "operation": plan["operation"], "repository_id": plan["repository"]["id"],
            "issue_number": plan["issue_number"], "comment_id": plan.get("comment_id"),
            "body_sha256": digest(plan["body"]), "old_body_sha256": plan.get("old_body_sha256")}


def github(plan, method, endpoint, body=None):
    args = ["gh", "api", endpoint, "--hostname", plan["repository"]["hostname"], "--method", method]
    if body is not None:
        args.extend(["--input", "-"])
    try:
        response = subprocess.run(args, input=json.dumps({"body": body}) if body is not None else None,
                                  capture_output=True, text=True, check=False, timeout=60)
        if response.returncode:
            raise ReadError("GitHub response unavailable; preserve receipt and read back before another write")
        return json.loads(response.stdout, object_pairs_hook=unique_object)
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        raise ReadError("GitHub response unknown; preserve receipt and read back before another write") from error


def repository_endpoint(plan):
    repository = plan["repository"]
    return f"repos/{repository['owner']}/{repository['name']}"


def verify_target(plan, event):
    endpoint = repository_endpoint(plan)
    repository = github(plan, "GET", endpoint)
    if not isinstance(repository, dict) or type(repository.get("id")) is not int or repository["id"] != plan["repository"]["id"] or repository.get("full_name") != f"{plan['repository']['owner']}/{plan['repository']['name']}":
        raise EventError("GitHub repository binding mismatch")
    user = github(plan, "GET", "user")
    if not isinstance(user, dict) or type(user.get("id")) is not int or user["id"] != plan["expected_author"]["user_id"] or user.get("login") != plan["expected_author"]["login"]:
        raise EventError("authenticated author binding mismatch")
    issue = github(plan, "GET", f"{endpoint}/issues/{plan['issue_number']}")
    allowed_states = ("open", "closed") if event["event"] == "release" and event.get("release_mode") == "self" else ("open",)
    if not isinstance(issue, dict) or type(issue.get("number")) is not int or issue["number"] != plan["issue_number"] or "pull_request" in issue or issue.get("state") not in allowed_states:
        raise EventError("target must be the exact open Issue, or a closed Issue for self-release")


def normalize_comment(plan, comment, expected_id=None, expected_body=None):
    if not isinstance(comment, dict) or type(comment.get("id")) is not int or comment["id"] < 1:
        raise EventError("comment ID unavailable")
    if expected_id is not None and comment["id"] != expected_id:
        raise EventError("exact comment ID mismatch")
    if comment.get("html_url") != comment_url(plan, comment["id"]):
        raise EventError("comment repository/Issue/URL mismatch")
    author = comment.get("user")
    if not isinstance(author, dict) or type(author.get("id")) is not int or author["id"] != plan["expected_author"]["user_id"] or author.get("login") != plan["expected_author"]["login"]:
        raise EventError("comment author mismatch")
    body = comment.get("body")
    if not isinstance(body, str) or expected_body is not None and body != expected_body:
        raise EventError("comment body mismatch")
    if not isinstance(comment.get("updated_at"), str) or not comment["updated_at"]:
        raise EventError("comment update evidence unavailable")
    return {"id": comment["id"], "url": comment["html_url"], "user_id": author["id"], "login": author["login"],
            "issue_number": plan["issue_number"], "body": body, "updated_at": comment["updated_at"]}


def get_comment(plan, comment_id, expected_body=None):
    return normalize_comment(plan, github(plan, "GET", f"{repository_endpoint(plan)}/issues/comments/{comment_id}"), comment_id, expected_body)


def verify_predecessors(plan, event):
    def linked_event(comment_id, event_id):
        raw = github(plan, "GET", f"{repository_endpoint(plan)}/issues/comments/{comment_id}")
        if not isinstance(raw, dict):
            raise EventError("predecessor comment unavailable")
        predecessor = validate_event(parse_event_body(raw.get("body")))
        if predecessor["event_id"] != event_id:
            raise EventError("predecessor event_id mismatch")
        observed_plan = dict(plan, expected_author={"user_id": predecessor["controlled_by_id"], "login": predecessor["controlled_by"]})
        normalize_comment(observed_plan, raw, comment_id)
        return predecessor
    if event.get("previous_event_id") is not None:
        if event["github_comment_url"] != comment_url(plan, event["github_comment_id"]):
            raise EventError("predecessor URL must bind the exact repository, Issue and comment ID")
        predecessor = linked_event(event["github_comment_id"], event["previous_event_id"])
        if event["event"] in {"handoff", "release", "resume"}:
            for field in ("controlled_by", "controlled_by_id", "actor_id"):
                if predecessor[field] != event[field]:
                    raise EventError("transfer predecessor owner mismatch")
        if event["event"] == "resume" and event["handoff_event_id"] != predecessor["event_id"]:
            raise EventError("resume must reference the exact terminal handoff/release event")
    if event["event"] == "reassign":
        target = event["target"]
        claim = linked_event(target["claim_comment_id"], target["claim_event_id"])
        identity_fields = ("controlled_by", "controlled_by_id", "actor_id")
        if (claim["event"] != "claim" or target["claim_comment_url"] != comment_url(plan, target["claim_comment_id"])
                or any(claim[field] != target[field] for field in identity_fields)):
            raise EventError("reassign target claim identity mismatch")
        if any(predecessor[field] != target[field] for field in (*identity_fields, "session_id")):
            raise EventError("reassign target current owner/session mismatch")
        # The root anchors the allocation; a verified resume may change only its current session.
        ancestor, comment_id, seen = predecessor, event["github_comment_id"], set()
        root = (target["claim_comment_id"], target["claim_event_id"])
        while (comment_id, ancestor["event_id"]) != root:
            link = (comment_id, ancestor["event_id"])
            if (link in seen or len(seen) >= 3100 or any(ancestor[field] != target[field] for field in identity_fields)
                    or ancestor["event"] not in {"claim", "handoff", "release", "resume"}
                    or ancestor["event"] == "claim" and ancestor.get("revision") is None
                    or ancestor.get("previous_event_id") is None
                    or ancestor.get("github_comment_url") != comment_url(plan, ancestor["github_comment_id"])):
                raise EventError("reassign predecessor does not belong to the target original claim")
            seen.add(link)
            comment_id = ancestor["github_comment_id"]
            ancestor = linked_event(comment_id, ancestor["previous_event_id"])


def published_candidate(plan, event):
    matches = []
    for page in range(1, 1001):
        comments = github(plan, "GET", f"{repository_endpoint(plan)}/issues/{plan['issue_number']}/comments?per_page=100&page={page}")
        if not isinstance(comments, list) or len(comments) > 100:
            raise ReadError("comment pagination is incomplete or malformed")
        for comment in comments:
            body = comment.get("body") if isinstance(comment, dict) else None
            if not isinstance(body, str):
                raise ReadError("comment body unavailable in Issue inventory")
            try:
                candidate = parse_event_body(body)
            except EventError:
                if event["event_id"] in body:
                    raise EventError("ambiguous existing candidate; resolve before publication")
                continue
            if candidate.get("event_id") == event["event_id"]:
                matches.append(comment)
        if len(comments) < 100:
            break
    else:
        raise ReadError("comment pagination reached safety limit; no write allowed")
    if len(matches) > 1:
        raise EventError("duplicate event_id comments; resolve before publication")
    return normalize_comment(plan, matches[0], expected_body=plan["body"]) if matches else None


def receipt_binding(plan, event):
    return {"receipt_version": 1, "repository": plan["repository"], "issue_number": plan["issue_number"],
            "expected_author": plan["expected_author"], "operation": plan["operation"], "event_id": event["event_id"],
            "comment_id": plan.get("comment_id"), "body_sha256": digest(plan["body"]), "old_body_sha256": plan.get("old_body_sha256")}


def read_receipt(path, binding):
    for parent in path.absolute().parents:
        if parent.is_symlink():
            raise EventError("receipt path must not traverse a directory symbolic link")
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise EventError("receipt must be a regular file, never a symbolic link")
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None
    except OSError as error:
        raise EventError("receipt must be a readable regular file, never a symbolic link") from error
    with os.fdopen(descriptor, "r", encoding="utf-8") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise EventError("receipt must be a regular file, never a symbolic link")
        record = json.loads(source.read(65537), object_pairs_hook=unique_object)
    if not isinstance(record, dict) or record.get("binding") != binding or record.get("state") not in {"write-sent-result-unknown", "read-back-verified"}:
        raise EventError("existing receipt target/digests/state mismatch; preserve it")
    return record


def start_receipt(path, binding):
    record = {"binding": binding, "state": "write-sent-result-unknown"}
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(record, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    return True


def finish_receipt(path, binding, comment):
    read_receipt(path, binding)
    record = {"binding": binding, "state": "read-back-verified", "result_comment_id": comment["id"],
              "result_comment_url": comment["url"], "result_body_sha256": digest(comment["body"])}
    descriptor, temporary = tempfile.mkstemp(prefix=".event-receipt-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(record, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_plan(plan, write=False, receipt=None):
    event = validate_plan(plan)
    expected = expected_approval(plan)
    if not write:
        return {"status": "pass", "mode": "preview", "event": event, "body": plan["body"],
                "body_sha256": digest(plan["body"]), "required_approval": expected,
                "remote_write_performed": False, "authorization_verified": False}
    if json.dumps(plan.get("approval"), sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise EventError("--write requires explicit approval bound to exact operation, target and body digests")
    if receipt is None:
        raise EventError("--write requires --receipt to preserve unknown results across sessions")
    binding = receipt_binding(plan, event)
    prior = read_receipt(receipt, binding)
    verify_target(plan, event)
    verify_predecessors(plan, event)
    old = None
    if plan["operation"] == "edit":
        old = get_comment(plan, plan["comment_id"])
        existing = old if old["body"] == plan["body"] else None
        if existing is None:
            if digest(old["body"]) != plan["old_body_sha256"]:
                raise EventError("original comment digest changed; preserve current content and approval")
            original_event = validate_event(parse_event_body(old["body"]))
            for field in ("event", "event_id", "controlled_by", "controlled_by_id", "actor_id", "session_id"):
                if event[field] != original_event[field]:
                    raise EventError("editing must preserve original event and author/session identity; append a related correction")
    else:
        if plan["operation"] == "append-correction":
            old = get_comment(plan, plan["comment_id"])
            if digest(old["body"]) != plan["old_body_sha256"]:
                raise EventError("original comment digest changed; preserve current content")
            original_event = validate_event(parse_event_body(old["body"]))
            if event["revision"]["original_event_id"] != original_event["event_id"]:
                raise EventError("correction original_event_id mismatch")
        existing = published_candidate(plan, event)
    if existing is not None:
        comment = get_comment(plan, existing["id"], plan["body"])
        if prior is None:
            start_receipt(receipt, binding)
        finish_receipt(receipt, binding, comment)
        return {"status": "pass", "state": "read-back-verified", "comment": comment, "remote_write_performed": False, "authorization_verified": False}
    if prior is not None:
        return {"status": "unknown", "state": "write-sent-result-unknown", "remote_write_performed": False,
                "next_safe_action": "preserve receipt and resolve the prior request by read-back; no repeated POST", "authorization_verified": False}
    if not start_receipt(receipt, binding):
        read_receipt(receipt, binding)
        return {"status": "unknown", "state": "write-sent-result-unknown", "remote_write_performed": False,
                "next_safe_action": "another process owns this receipt; read back before any further write", "authorization_verified": False}
    write_sent = False
    try:
        if plan["operation"] == "edit":
            before = get_comment(plan, plan["comment_id"])
            if digest(before["body"]) != plan["old_body_sha256"]:
                raise EventError("comment changed immediately before editing; no write sent")
            write_sent = True
            response = github(plan, "PATCH", f"{repository_endpoint(plan)}/issues/comments/{plan['comment_id']}", plan["body"])
        else:
            if plan["operation"] == "append-correction" and digest(get_comment(plan, plan["comment_id"])["body"]) != plan["old_body_sha256"]:
                raise EventError("original comment changed immediately before correction; no write sent")
            write_sent = True
            response = github(plan, "POST", f"{repository_endpoint(plan)}/issues/{plan['issue_number']}/comments", plan["body"])
        comment = normalize_comment(plan, response, expected_body=plan["body"])
        if plan["operation"] == "edit" and comment["id"] != plan["comment_id"]:
            raise EventError("edit response returned another comment ID")
        comment = get_comment(plan, comment["id"], plan["body"])
    except (ReadError, EventError):
        try:
            comment = get_comment(plan, plan["comment_id"], plan["body"]) if plan["operation"] == "edit" else published_candidate(plan, event)
            if comment:
                comment = get_comment(plan, comment["id"], plan["body"])
        except (ReadError, EventError):
            comment = None
        if comment is None:
            return {"status": "unknown", "state": "write-sent-result-unknown", "remote_write_performed": None if write_sent else False, "remote_write_attempted": write_sent,
                    "next_safe_action": "preserve receipt and resolve exact event by GET; do not resend", "authorization_verified": False}
    finish_receipt(receipt, binding, comment)
    return {"status": "pass", "state": "read-back-verified", "comment": comment, "remote_write_performed": True, "authorization_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    construct = subcommands.add_parser("construct", help="render a real bundled template with explicit JSON field overrides")
    construct.add_argument("--template", choices=["claim", "research-claim", "handoff", "reassign", "release", "resume"], required=True)
    construct.add_argument("--fields", type=Path, required=True)
    validation = subcommands.add_parser("validate", help="schema validation only")
    validation.add_argument("--body", type=Path, required=True)
    application = subcommands.add_parser("apply", help="preview by default; --write requires exact explicit approval input")
    application.add_argument("--plan", type=Path, required=True)
    application.add_argument("--write", action="store_true")
    application.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "construct":
            yaml, _, _ = dependencies()
            event = parse_event_body((resource_path("templates") / (args.template + ".yml")).read_text(encoding="utf-8"))
            fields = read_json(args.fields)
            if not isinstance(fields, dict):
                raise EventError("field overrides must be a JSON object")
            event.update(fields)
            validate_event(event)
            body = yaml.safe_dump(event, allow_unicode=True, sort_keys=False)
        elif args.command == "validate":
            body = args.body.read_text(encoding="utf-8")
            event = validate_event(parse_event_body(body))
        else:
            result = apply_plan(read_json(args.plan), args.write, args.receipt)
        if args.command != "apply":
            result = {"status": "pass", "event": event, "body": body, "body_sha256": digest(body), "authorization_verified": False}
    except (OSError, ValueError) as error:
        unknown = isinstance(error, (DependencyError, ReadError, OSError))
        print(json.dumps({"status": "unknown" if unknown else "fail", "error": str(error), "authorization_verified": False}))
        return 2 if unknown else 1
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] == "unknown" else 0


if __name__ == "__main__":
    raise SystemExit(main())
