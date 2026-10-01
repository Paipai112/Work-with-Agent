import re
from pathlib import Path


AGENTS = {"codex", "claude-code", "pi-agent"}
SYSTEMS = {"macos", "linux", "windows-native"}
CHECKS = {
    "install",
    "explicit_invocation",
    "project_entry_discovery",
    "resource_loading",
    "upgrade",
    "conflict",
    "disablement",
    "missing_skill_stop_write",
}


def test_release_matrix_has_every_native_combination_and_honest_status(load_yaml):
    rows = load_yaml("tests/platform/skill-matrix.yml")["rows"]
    assert len(rows) == 9
    assert {(row["agent"], row["os"]) for row in rows} == {
        (agent, os_name) for agent in AGENTS for os_name in SYSTEMS
    }
    assert all(row["status"] in {"verified", "failed", "unverified"} for row in rows)
    assert all(set(row["checks"]) == CHECKS for row in rows)
    assert all(row["os"] != "wsl" for row in rows)


def test_verified_rows_require_pinned_source_runtime_and_real_evidence(load_yaml, repo_root: Path):
    rows = load_yaml("tests/platform/skill-matrix.yml")["rows"]
    for row in rows:
        if row["status"] != "verified":
            continue
        assert row["client_version"]
        assert row["skill_release_tag"]
        assert re.fullmatch(r"[0-9a-f]{40}", row["skill_commit_sha"])
        assert row["evidence"]
        for relative in row["evidence"]:
            path = (repo_root / relative).resolve()
            path.relative_to(repo_root.resolve())
            assert path.is_file() and path.stat().st_size > 0
        assert all(row["checks"][name] == "verified" for name in CHECKS)


def test_unverified_rows_cannot_carry_success_claims(load_yaml):
    rows = load_yaml("tests/platform/skill-matrix.yml")["rows"]
    for row in rows:
        assert all(value in {"verified", "failed", "unverified"} for value in row["checks"].values())
        if row["status"] == "unverified":
            assert any(value != "verified" for value in row["checks"].values())
        if any(value != "unverified" for value in row["checks"].values()):
            assert row["evidence"]
