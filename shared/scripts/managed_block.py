"""Render managed Markdown blocks as reviewable candidate files.

This module deliberately does not apply a candidate to its source.  The
command-line interface only reads source/body files and creates a new candidate
with exclusive creation semantics.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


DEFAULT_MARKER_NAME = "github-agent-collaboration"
_SAFE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class ManagedBlockError(ValueError):
    """The source cannot be rendered safely as a managed block candidate."""


@dataclass(frozen=True)
class PlanResult:
    status: str
    original_sha256: str
    candidate_sha256: str
    candidate: bytes
    reason: str


def _marker_bytes(marker_name: str) -> bytes:
    if not marker_name or any(character in marker_name for character in "\r\n"):
        raise ManagedBlockError("marker name must be a non-empty single line")
    try:
        return marker_name.encode("ascii")
    except UnicodeEncodeError as error:
        raise ManagedBlockError("marker name must be ASCII") from error


def _newline_for(source: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in source else b"\n"


def _managed_markers(source: bytes, marker: bytes) -> tuple[list[re.Match[bytes]], list[int]]:
    start_prefix = b"<!-- " + marker + b":start"
    end_prefix = b"<!-- " + marker + b":end"
    start_pattern = re.compile(
        re.escape(start_prefix) + rb" version=[A-Za-z0-9][A-Za-z0-9._-]* -->"
    )
    end = end_prefix + b" -->"
    starts = list(start_pattern.finditer(source))
    ends = [
        match.start() for match in re.finditer(re.escape(end), source)
    ]
    if source.count(start_prefix) != len(starts) or source.count(end_prefix) != len(ends):
        raise ManagedBlockError("malformed managed marker is ambiguous")
    return starts, ends


def _validate_rendered_candidate(candidate: bytes, marker: bytes) -> None:
    starts, ends = _managed_markers(candidate, marker)
    end = b"<!-- " + marker + b":end -->"
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0].end():
        raise ManagedBlockError("rendered candidate must contain one complete managed block")
    before = candidate[:starts[0].start()]
    after = candidate[ends[0] + len(end):]
    if marker in before or marker in after:
        raise ManagedBlockError("rendered candidate contains an unmanaged marker phrase")


def _render_block(body: str, marker_name: str, version: str, newline: bytes) -> bytes:
    if not isinstance(body, str):
        raise ManagedBlockError("block body must be text")
    if not _SAFE_VERSION.fullmatch(version):
        raise ManagedBlockError("version must be a safe token")

    marker = _marker_bytes(marker_name)
    try:
        body_bytes = body.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ManagedBlockError("block body must be valid UTF-8") from error
    if b"<!-- " + marker + b":" in body_bytes:
        raise ManagedBlockError("block body must not contain a managed marker")

    normalized_body = body_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    normalized_body = normalized_body.replace(b"\n", newline)
    start = b"<!-- " + marker + b":start version=" + version.encode("utf-8") + b" -->"
    end = b"<!-- " + marker + b":end -->"
    if normalized_body and not normalized_body.endswith(newline):
        normalized_body += newline
    return start + newline + normalized_body + end


def plan_managed_block(
    source: bytes,
    body: str,
    version: str,
    marker_name: str = DEFAULT_MARKER_NAME,
) -> PlanResult:
    """Return a candidate that replaces one exact block or appends a new one.

    Any marker-name occurrence outside exactly one complete managed block is
    treated as ambiguous so a human must decide how to handle it.
    """

    if not isinstance(source, bytes):
        raise ManagedBlockError("source must be bytes")

    marker = _marker_bytes(marker_name)
    newline = _newline_for(source)
    end = b"<!-- " + marker + b":end -->"
    starts, ends = _managed_markers(source, marker)

    if starts or ends:
        if len(starts) != 1 or len(ends) != 1:
            raise ManagedBlockError("expected exactly one complete managed block")
        start = starts[0]
        end_start = ends[0]
        if end_start < start.end():
            raise ManagedBlockError("managed block end marker precedes its start marker")
        before = source[:start.start()]
        after = source[end_start + len(end):]
        if marker in before or marker in after:
            raise ManagedBlockError("similar unmanaged marker phrase is ambiguous")
        candidate = before + _render_block(body, marker_name, version, newline) + after
        reason = "existing managed block replaced"
    else:
        if marker in source:
            raise ManagedBlockError("similar unmanaged marker phrase is ambiguous")
        rendered = _render_block(body, marker_name, version, newline)
        if source:
            candidate = source + newline + rendered
            if source.endswith(newline):
                candidate += newline
        else:
            candidate = rendered
        reason = "managed block appended"

    _validate_rendered_candidate(candidate, marker)
    return PlanResult(
        status="planned",
        original_sha256=hashlib.sha256(source).hexdigest(),
        candidate_sha256=hashlib.sha256(candidate).hexdigest(),
        candidate=candidate,
        reason=reason,
    )


def _read_regular_file(path: Path) -> bytes:
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError as error:
        raise ManagedBlockError(f"file does not exist: {path}") from error
    if stat.S_ISLNK(path_stat.st_mode):
        raise ManagedBlockError(f"symbolic link is not allowed: {path}")
    if not stat.S_ISREG(path_stat.st_mode):
        raise ManagedBlockError(f"not a regular file: {path}")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ManagedBlockError(f"cannot safely read file: {path}") from error
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise ManagedBlockError(f"not a regular file: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65536):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_new_candidate(path: Path, content: bytes) -> None:
    try:
        existing = os.lstat(path)
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if stat.S_ISLNK(existing.st_mode):
            raise ManagedBlockError(f"symbolic link is not allowed: {path}")
        raise ManagedBlockError(f"candidate already exists: {path}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise ManagedBlockError(f"candidate already exists: {path}") from error
    except OSError as error:
        raise ManagedBlockError(f"cannot create candidate: {path}") from error
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
    finally:
        os.close(descriptor)


def _json_result(result: PlanResult) -> str:
    payload = asdict(result)
    payload.pop("candidate")
    return json.dumps(payload, sort_keys=True)


def _plan_command(arguments: argparse.Namespace) -> int:
    source = _read_regular_file(Path(arguments.path))
    try:
        body = _read_regular_file(Path(arguments.body_file)).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ManagedBlockError("block body file must be valid UTF-8") from error
    result = plan_managed_block(source, body, arguments.version)
    _write_new_candidate(Path(arguments.candidate), result.candidate)
    print(_json_result(PlanResult(
        status=result.status,
        original_sha256=result.original_sha256,
        candidate_sha256=result.candidate_sha256,
        candidate=result.candidate,
        reason="candidate rendered",
    )))
    return 0


def _verify_command(arguments: argparse.Namespace) -> int:
    approved_digest = arguments.approved_digest.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approved_digest):
        raise ManagedBlockError("approved digest must be a SHA-256 hex digest")
    current_digest = hashlib.sha256(_read_regular_file(Path(arguments.path))).hexdigest()
    if current_digest == approved_digest:
        payload = {
            "status": "verified",
            "original_sha256": current_digest,
            "candidate_sha256": approved_digest,
            "reason": "current file matches approved digest",
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    payload = {
        "status": "stale",
        "original_sha256": current_digest,
        "candidate_sha256": approved_digest,
        "reason": "current file differs from approved digest",
    }
    print(json.dumps(payload, sort_keys=True))
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="render a new candidate without changing the source")
    plan.add_argument("--path", required=True)
    plan.add_argument("--body-file", required=True)
    plan.add_argument("--version", required=True)
    plan.add_argument("--candidate", required=True)
    plan.set_defaults(handler=_plan_command)

    verify = commands.add_parser("verify", help="compare the current source to an approved digest")
    verify.add_argument("--path", required=True)
    verify.add_argument("--approved-digest", required=True)
    verify.set_defaults(handler=_verify_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return arguments.handler(arguments)
    except ManagedBlockError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
