"""Local discovery behavior, separate from the nine-platform release contract."""

import importlib.util
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def platform_probe(repo_root):
    path = repo_root / "tests/platform/probe_skill_discovery.py"
    spec = importlib.util.spec_from_file_location("platform_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovery_contract_includes_the_optional_check_skill(platform_probe):
    assert set(platform_probe.SKILL_NAMES) == {
        "github-collaboration-setup", "github-collaboration", "github-collaboration-check",
    }


@pytest.mark.parametrize("traversal", [
    ("a.txt", "nested/a.txt", "Z.bin", "nested/B.bin"),
    ("nested/B.bin", "Z.bin", "nested/a.txt", "a.txt"),
])
def test_package_digest_uses_ordinal_relative_posix_order(platform_probe, tmp_path, traversal):
    (tmp_path / "nested").mkdir()
    (tmp_path / "Z.bin").write_bytes(b"\xffZ")
    (tmp_path / "a.txt").write_bytes(b"a\n")
    (tmp_path / "nested/B.bin").write_bytes(b"\x00B")
    (tmp_path / "nested/a.txt").write_bytes(b"a\r\n")

    class CaseInsensitivePath(type(tmp_path)):
        """Control native path ordering while retaining real filesystem I/O."""

        def __lt__(self, other):
            return self.as_posix().casefold() < other.as_posix().casefold()

        def rglob(self, pattern):
            return iter(type(self)(self / name) for name in traversal)

    # Hand-derived stream: b"Z.bin\0\xffZ\0a.txt\0a\n\0nested/B.bin\0\x00B\0nested/a.txt\0a\r\n\0".
    expected = "29d99da49118bf19daa7664d3b2c9133d8aba02f8a48ce48d2c26f6fb83d6111"
    assert platform_probe.package_digest(CaseInsensitivePath(tmp_path)) == expected


def test_probe_never_redefines_home_or_inherits_credentials(platform_probe, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-inherited")
    monkeypatch.setenv("CODEX_HOME", "must-not-be-redefined")
    environment = platform_probe.child_environment(tmp_path)
    assert {"HOME", "home", "CODEX_HOME", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"}.isdisjoint(environment)
    assert environment["PI_OFFLINE"] == "1"
    assert environment["CLAUDE_CONFIG_DIR"].startswith(str(tmp_path))


def test_resource_audit_checks_nested_reference_links(platform_probe, tmp_path):
    (tmp_path / "references").mkdir()
    (tmp_path / "SKILL.md").write_text("[start](references/start.md)\n", encoding="utf-8")
    (tmp_path / "references/start.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing resource"):
        platform_probe.relative_resource_paths(tmp_path)


def test_resource_audit_rejects_escape_outside_package(platform_probe, tmp_path):
    package = tmp_path / "skill"
    package.mkdir()
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")
    (package / "SKILL.md").write_text("[escape](../outside.md)\n", encoding="utf-8")
    with pytest.raises(ValueError):
        platform_probe.relative_resource_paths(package)


@pytest.mark.parametrize("installation,cwd_relative,trusted,disabled,expected", [
    ("project/.pi/skills", ".", True, False, True),
    ("project/.pi/skills", "nested/child", True, False, False),
    ("project/.agents/skills", "nested with spaces/child", True, False, True),
    ("project/.agents/skills", ".", False, False, False),
    ("project/.agents/skills", ".", True, True, False),
])
def test_installed_pi_loader_discovers_and_expands_real_packages(
    platform_probe, tmp_path, installation, cwd_relative, trusted, disabled, expected,
):
    executable = shutil.which("pi")
    if executable is None or shutil.which("node") is None:
        pytest.skip("Pi/Node not installed; cannot substitute a mock for platform discovery")
    cli_path = Path(executable).resolve()
    if cli_path.parent.name != "bundle" or not (cli_path.parents[2] / "dist/index.js").is_file():
        pytest.skip("installed Pi SDK cannot be located from CLI executable")
    cwd, resources = platform_probe.prepare_fixture(tmp_path, installation, cwd_relative)
    result = platform_probe.pi_discover(executable, cwd, platform_probe.child_environment(tmp_path), resources,
                                       trusted=trusted, disabled=disabled)
    assert result["model_turns_sent"] == 0
    assert result["outside_fixture_same_name_count"] == 0
    assert result["resource_reads"]["successful"] == len(resources)
    found = {skill["name"] for skill in result["skills"]}
    assert found == (set(platform_probe.SKILL_NAMES) if expected else set())
    assert result["prompt_metadata_contains_all"] is expected
    if expected:
        assert len(result["expansions"]) == len(platform_probe.SKILL_NAMES)
        assert all(expansion["contains_full_body"] and expansion["contains_base_dir"]
                   and expansion["arguments_preserved"] for expansion in result["expansions"])
        for skill in result["skills"]:
            assert Path(skill["filePath"]).is_relative_to(tmp_path)


def test_installed_claude_safe_initialize_registers_real_packages(platform_probe, tmp_path):
    executable = shutil.which("claude")
    if executable is None:
        pytest.skip("Claude Code not installed; cannot substitute a mock for discovery")
    cwd, resources = platform_probe.prepare_fixture(tmp_path, "project/.claude/skills", "nested with spaces/child")
    result = platform_probe.claude_discover(executable, cwd, platform_probe.child_environment(tmp_path), resources)
    assert {command["name"] for command in result["commands"]} == set(platform_probe.SKILL_NAMES)
    assert result["initialization_mode"] == "isolated-default"
    assert result["hooks_explicitly_disabled"] is True
    assert result["account_token_source"] == "none"
    assert result["session_state"] == "idle"
    assert result["model_turns_sent"] == 0
    assert result["actual_skill_path_returned"] is False
    assert result["resource_loading"].startswith("unverified:")
