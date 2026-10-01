import hashlib
import json
import os
import subprocess
import sys

import pytest

from shared.scripts.managed_block import ManagedBlockError, plan_managed_block


def test_replaces_only_existing_managed_block(fixture_bytes):
    before = fixture_bytes("managed-block/existing-valid.md")

    result = plan_managed_block(before, "New instructions\n", "0.1.0")

    start = b"<!-- github-agent-collaboration:start"
    end = b"<!-- github-agent-collaboration:end -->"
    before_prefix, before_suffix = before.split(start, 1)[0], before.split(end, 1)[1]
    after_prefix, after_suffix = result.candidate.split(start, 1)[0], result.candidate.split(end, 1)[1]
    assert (after_prefix, after_suffix) == (before_prefix, before_suffix)
    assert b"New instructions\n" in result.candidate
    assert result.original_sha256 == hashlib.sha256(before).hexdigest()
    assert result.candidate_sha256 == hashlib.sha256(result.candidate).hexdigest()


def test_preserves_crlf_bom_and_no_final_newline(fixture_bytes):
    for name in ("plain-crlf.md", "utf8-bom.md", "no-final-newline.md"):
        before = fixture_bytes(f"managed-block/{name}")

        result = plan_managed_block(before, "Protocol entry", "0.1.0")

        assert result.candidate.startswith(b"\xef\xbb\xbf") == before.startswith(b"\xef\xbb\xbf")
        assert result.candidate.startswith(before)
        if b"\r\n" in before:
            assert b"\n" not in result.candidate.replace(b"\r\n", b"")


def test_stops_on_duplicate_broken_or_similar_unmanaged(fixture_bytes):
    for name in ("duplicate.md", "broken-start.md", "similar-unmanaged.md"):
        with pytest.raises(ManagedBlockError):
            plan_managed_block(
                fixture_bytes(f"managed-block/{name}"), "Protocol entry", "0.1.0"
            )


def test_rejects_body_that_injects_a_managed_marker():
    with pytest.raises(ManagedBlockError, match="managed marker"):
        plan_managed_block(
            b"# Existing instructions\n",
            "<!-- github-agent-collaboration:end -->",
            "0.1.0",
        )


def test_rejects_version_that_can_close_an_html_comment():
    with pytest.raises(ManagedBlockError, match="safe token"):
        plan_managed_block(
            b"# Existing instructions\n",
            "Protocol entry",
            "0.1.0 --> <!-- github-agent-collaboration:end",
        )


@pytest.mark.parametrize("extra_marker", [
    b"<!-- github-agent-collaboration:start version=0.1.0 -->",
    b"<!-- github-agent-collaboration:start broken -->",
    b"<!-- github-agent-collaboration:end broken -->",
])
def test_rejects_same_line_duplicate_markers(extra_marker):
    before = (
        b"<!-- github-agent-collaboration:start version=0.1.0 --> "
        + extra_marker + b"\nold body\n<!-- github-agent-collaboration:end -->"
    )

    with pytest.raises(ManagedBlockError):
        plan_managed_block(before, "Replacement", "0.1.0")


@pytest.mark.parametrize("version", [b"", b"0.1.0 extra", b"0.1.0\t"])
def test_rejects_malformed_existing_start_marker_version(version):
    before = (
        b"<!-- github-agent-collaboration:start version=" + version
        + b" -->\nold body\n<!-- github-agent-collaboration:end -->"
    )

    with pytest.raises(ManagedBlockError):
        plan_managed_block(before, "Replacement", "0.1.0")


def test_plan_cli_writes_a_new_candidate_without_changing_source(tmp_path, fixture_bytes):
    source = tmp_path / "AGENTS.md"
    body = tmp_path / "block.md"
    candidate = tmp_path / "candidate.md"
    before = fixture_bytes("managed-block/plain-crlf.md")
    source.write_bytes(before)
    body.write_text("Protocol entry\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "shared/scripts/managed_block.py",
            "plan",
            "--path",
            os.fspath(source),
            "--body-file",
            os.fspath(body),
            "--version",
            "0.1.0",
            "--candidate",
            os.fspath(candidate),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert source.read_bytes() == before
    assert candidate.exists()
    assert payload["status"] == "planned"
    assert payload["original_sha256"] == hashlib.sha256(before).hexdigest()
    assert payload["candidate_sha256"] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert payload["reason"] == "candidate rendered"


def test_plan_cli_refuses_symlink_source_and_existing_candidate(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("source\n", encoding="utf-8")
    source_link = tmp_path / "source-link.md"
    source_link.symlink_to(source)
    body = tmp_path / "block.md"
    body.write_text("Protocol entry", encoding="utf-8")
    candidate = tmp_path / "candidate.md"
    candidate.write_text("already here", encoding="utf-8")

    symlink_run = subprocess.run(
        [
            sys.executable,
            "shared/scripts/managed_block.py",
            "plan",
            "--path",
            os.fspath(source_link),
            "--body-file",
            os.fspath(body),
            "--version",
            "0.1.0",
            "--candidate",
            os.fspath(tmp_path / "new-candidate.md"),
        ],
        capture_output=True,
        text=True,
    )
    existing_run = subprocess.run(
        [
            sys.executable,
            "shared/scripts/managed_block.py",
            "plan",
            "--path",
            os.fspath(source),
            "--body-file",
            os.fspath(body),
            "--version",
            "0.1.0",
            "--candidate",
            os.fspath(candidate),
        ],
        capture_output=True,
        text=True,
    )

    assert symlink_run.returncode != 0
    assert "symbolic link" in symlink_run.stderr
    assert existing_run.returncode != 0
    assert "already exists" in existing_run.stderr
    assert candidate.read_text(encoding="utf-8") == "already here"


def test_verify_cli_compares_current_bytes_to_approved_digest(tmp_path):
    source = tmp_path / "AGENTS.md"
    before = b"# Existing instructions\n"
    source.write_bytes(before)
    digest = hashlib.sha256(before).hexdigest()

    matching = subprocess.run(
        [
            sys.executable,
            "shared/scripts/managed_block.py",
            "verify",
            "--path",
            os.fspath(source),
            "--approved-digest",
            digest,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    source.write_bytes(before + b"Changed\n")
    changed = subprocess.run(
        [
            sys.executable,
            "shared/scripts/managed_block.py",
            "verify",
            "--path",
            os.fspath(source),
            "--approved-digest",
            digest,
        ],
        capture_output=True,
        text=True,
    )

    assert json.loads(matching.stdout)["status"] == "verified"
    assert changed.returncode != 0
    payload = json.loads(changed.stdout)
    assert payload["status"] == "stale"
    assert payload["original_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
