from pathlib import Path
import re

import yaml

from tests.helpers import frontmatter


SKILL_NAME = "github-collaboration"
WRITE_OPERATIONS = (
    "issue",
    "claim",
    "branch",
    "stage",
    "commit",
    "push",
    "pull request",
    "review",
    "merge",
    "handoff",
)


def test_daily_entrypoint_is_discoverable_and_routes_writes(skill_text, repo_root: Path):
    text = skill_text(f"{SKILL_NAME}/SKILL.md")
    metadata = frontmatter(text)

    assert metadata["name"] == SKILL_NAME
    assert metadata["description"].startswith("Use when ")
    assert metadata["metadata"]["version"] == "0.1.0"
    assert len(text.splitlines()) < 500
    assert all(operation in text.lower() for operation in WRITE_OPERATIONS)
    assert re.search(r"\]\(references/preflight\.md\)", text)
    assert (repo_root / "skills" / SKILL_NAME / "references/preflight.md").is_file()


def test_daily_openai_metadata_supports_implicit_discovery(repo_root: Path):
    path = repo_root / "skills" / SKILL_NAME / "agents/openai.yaml"
    metadata = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert metadata.get("policy", {}).get("allow_implicit_invocation", True) is True
    assert metadata["interface"]["display_name"]
    assert metadata["interface"]["short_description"]
    assert f"${SKILL_NAME}" in metadata["interface"]["default_prompt"]


def test_preflight_has_ordered_independent_gates(skill_text):
    text = skill_text(f"{SKILL_NAME}/references/preflight.md")
    steps = re.findall(r"^\d+\. (.+)$", text, flags=re.MULTILINE)

    assert len(steps) >= 9
    for index, term in enumerate(
        (
            "仓库",
            "默认分支",
            "当前 SHA",
            "Skill 版本",
            "账号",
            "职责身份",
            "角色",
            "Issue",
            "Git 状态",
        )
    ):
        assert term in steps[index]


def test_preflight_fails_closed_when_source_or_authority_is_uncertain(skill_text):
    text = skill_text(f"{SKILL_NAME}/references/preflight.md")

    for condition in ("缺失", "不可发现", "不兼容", "读取失败", "身份", "授权", "过期"):
        assert condition in text
    assert "read-only" in text
    assert "member" in text
    assert "leader:<ceiling>" in text
    assert "未确认的本地文件" in text


def test_preflight_resolves_governance_paths_from_pinned_config(skill_text):
    text = skill_text(f"{SKILL_NAME}/references/preflight.md")

    assert "managed_paths.protocol" in text
    assert "managed_paths.authorization" in text
    assert "INSTALL_SKILL.md" in text
    assert "同一 SHA" in text
    assert "路径缺失" in text
    assert "歧义" in text


def test_preflight_verifies_installed_skill_against_release_source(skill_text):
    text = skill_text(f"{SKILL_NAME}/references/preflight.md")

    for field in (
        "source_repository_url",
        "release_tag",
        "resolved_commit_sha",
        "installation_page_permalink",
        "RESOURCE_MANIFEST.json",
    ):
        assert field in text
    assert "metadata.version" in text
    assert "完整 40 位" in text
    assert "本地打包完成" in text
    assert "不等于公开发布" in text


def test_entrypoint_forbids_only_unscoped_stage_all(skill_text):
    text = skill_text(f"{SKILL_NAME}/SKILL.md")

    assert "git add -A" in text
    assert "git add ." in text
    assert "显式 pathspec" in text
