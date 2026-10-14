from pathlib import Path
from urllib.parse import urlparse

import yaml


SKILL_NAME = "github-collaboration-setup"
AGENTS = ("codex", "claude-code", "pi-agent")
SYSTEMS = ("macos", "linux", "windows-native")
USER_ROOTS = {
    "codex": ("~/.agents/skills", r"$env:USERPROFILE\.agents\skills"),
    "claude-code": ("~/.claude/skills", r"$env:USERPROFILE\.claude\skills"),
    "pi-agent": ("~/.pi/agent/skills", r"$env:USERPROFILE\.pi\agent\skills"),
}
PROJECT_ROOTS = {
    "codex": ".agents/skills",
    "claude-code": ".claude/skills",
    "pi-agent": ".agents/skills",
}
COMMANDS = {
    "codex": "$github-collaboration-setup",
    "claude-code": "/github-collaboration-setup",
    "pi-agent": "/skill:github-collaboration-setup",
}
DAILY_COMMANDS = {
    "codex": "$github-collaboration",
    "claude-code": "/github-collaboration",
    "pi-agent": "/skill:github-collaboration",
}
OFFICIAL_HOSTS = {
    "codex": "learn.chatgpt.com",
    "claude-code": "code.claude.com",
    "pi-agent": "github.com",
}


def test_install_contract_names_all_nine_native_combinations(load_yaml):
    matrix = load_yaml("tests/platform/install-contract.yml")["matrix"]

    assert len(matrix) == 9
    assert {(row["agent"], row["os"]) for row in matrix} == {
        (agent, os_name) for agent in AGENTS for os_name in SYSTEMS
    }
    assert all(row["explicit_invocation"] and row["new_session_required"] for row in matrix)
    assert all(row["wsl_is_separate"] for row in matrix if row["os"] == "windows-native")


def test_three_packages_declare_a_version_for_installation_readback(repo_root: Path):
    for name in ("github-collaboration-setup", "github-collaboration", "github-collaboration-check"):
        text = (repo_root / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])
        assert frontmatter.get("metadata", {}).get("version") == "0.2.0"


def test_paths_and_commands_point_to_discoverable_skill_folders(load_yaml):
    matrix = load_yaml("tests/platform/install-contract.yml")["matrix"]

    for row in matrix:
        agent, os_name = row["agent"], row["os"]
        user_root = USER_ROOTS[agent][1 if os_name == "windows-native" else 0]
        separator = "\\" if os_name == "windows-native" else "/"
        assert row["user_skill_path"] == f"{user_root}{separator}github-collaboration-setup"
        assert row["project_skill_path"] == f"{PROJECT_ROOTS[agent]}/github-collaboration-setup"
        assert row["explicit_invocation"] == COMMANDS[agent]
        assert row["daily_explicit_invocation"] == DAILY_COMMANDS[agent]
        assert "SKILL.md" == row["entrypoint"]


def test_each_platform_contract_has_official_source_and_package_discovery(load_yaml, repo_root: Path):
    matrix = load_yaml("tests/platform/install-contract.yml")["matrix"]
    official_repositories = {
        "pi-agent": "earendil-works/pi",
    }

    for row in matrix:
        url = urlparse(row["official_skill_documentation"])
        assert url.scheme == "https" and url.hostname == OFFICIAL_HOSTS[row["agent"]]
        if row["agent"] in official_repositories:
            assert url.path.startswith(f"/{official_repositories[row['agent']]}/")
        assert row["check_actual_discovery_path"] is True
        assert row["check_same_name_collision"] is True
        assert row["check_disabled_or_override"] is True

    package = repo_root / "skills" / SKILL_NAME
    assert (package / "SKILL.md").is_file()
    assert (package / "references/platform-installation.md").is_file()
    assert (package / "references/upgrade-and-diagnosis.md").is_file()


def test_documented_install_table_matches_both_skill_commands_and_contract(load_yaml, repo_root: Path):
    matrix = load_yaml("tests/platform/install-contract.yml")["matrix"]
    text = (repo_root / "skills/github-collaboration-setup/references/platform-installation.md").read_text(
        encoding="utf-8"
    )
    display_names = {"codex": "Codex", "claude-code": "Claude Code", "pi-agent": "Pi Agent"}

    for agent in AGENTS:
        table_line = next(line for line in text.splitlines() if line.startswith(f"| {display_names[agent]} |"))
        cells = [cell.strip().strip("`") for cell in table_line.strip("|").split("|")]
        assert len(cells) == 5
        for os_name in SYSTEMS:
            row = next(row for row in matrix if row["agent"] == agent and row["os"] == os_name)
            user_root = USER_ROOTS[agent][1 if os_name == "windows-native" else 0]
            if os_name == "windows-native":
                relative_root = user_root.removeprefix("$env:USERPROFILE\\")
                assert cells[2] == f"Join-Path $env:USERPROFILE '{relative_root}\\<skill>'"
            else:
                assert cells[1] == f"{user_root}/<skill>/"
            assert cells[3] == f"{PROJECT_ROOTS[agent]}/<skill>/"
            assert row["explicit_invocation"] in cells[4].replace("<skill>", "github-collaboration-setup")
            assert row["daily_explicit_invocation"] in cells[4].replace("<skill>", "github-collaboration")


def test_unpublished_project_install_template_cannot_look_ready(repo_root: Path):
    canonical = repo_root / "templates/project/.github/agent-collaboration/INSTALL_SKILL.md"
    bundled = repo_root / "skills/github-collaboration-setup/assets/templates/project/.github/agent-collaboration/INSTALL_SKILL.md"

    for path in (canonical, bundled):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        _, frontmatter, body = text.split("---\n", 2)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["installation_status"] == "unpublished"
        assert all(metadata[key] is None for key in (
            "source_repository_url", "release_tag", "resolved_commit_sha", "installation_page_permalink"
        ))
        assert "不可执行安装" in body
        assert "不可宣称配置完成" in body
