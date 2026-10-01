from pathlib import Path
import re

import yaml

from tests.helpers import frontmatter


SKILL_NAME = "github-collaboration-setup"
MODES = (
    "initialize",
    "upgrade",
    "diagnose",
    "repair",
    "authorization",
    "remote-governance",
)


def test_setup_entrypoint_is_discoverable_and_routes_to_existing_preflight(skill_text, repo_root: Path):
    text = skill_text(f"{SKILL_NAME}/SKILL.md")
    metadata = frontmatter(text)

    assert len(text.splitlines()) < 500
    assert metadata["name"] == SKILL_NAME
    assert metadata["description"].startswith("Use when ")
    assert all(re.search(rf"\b{re.escape(mode)}\b", text) for mode in MODES)
    assert re.search(r"\]\(references/preflight-and-identity\.md\)", text)
    assert (repo_root / "skills" / SKILL_NAME / "references/preflight-and-identity.md").is_file()


def test_setup_openai_metadata_keeps_implicit_discovery(repo_root: Path):
    path = repo_root / "skills" / SKILL_NAME / "agents/openai.yaml"
    metadata = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert metadata.get("policy", {}).get("allow_implicit_invocation", True) is True
    assert metadata["interface"]["display_name"]
    assert metadata["interface"]["short_description"]
    if "default_prompt" in metadata["interface"]:
        assert f"${SKILL_NAME}" in metadata["interface"]["default_prompt"]
