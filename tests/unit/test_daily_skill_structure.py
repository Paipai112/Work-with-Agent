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
    assert metadata["metadata"]["version"] == "0.2.0"
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


def _preflight_sources(repo_root, skill_text):
    router = skill_text(f"{SKILL_NAME}/references/preflight.md")
    # Canonical shared sources are generated into each package by profiles.
    # These checks cover instruction structure, not actual Agent compliance.
    core = (repo_root / "shared/references/session-core.md").read_text()
    package = (repo_root / "shared/references/package-verification.md").read_text()
    assert "](session-core.md)" in router
    assert "](package-verification.md)" in router
    return router, core, package


def test_preflight_routes_independent_risk_gates(repo_root, skill_text):
    router, core, _ = _preflight_sources(repo_root, skill_text)
    for term in (
        "repository_id", "default branch", "same SHA", "actual discovered Skill",
        "account", "actor_id", "permission_ceiling", "claim", "index",
    ):
        assert term in core, term
    assert "references/schemas/config.schema.json" in router
    assert "references/schemas/authorization.schema.json" in router
    assert "FormatChecker" in router


def test_preflight_stops_dependent_writes_without_blocking_diagnosis(repo_root, skill_text):
    router, core, _ = _preflight_sources(repo_root, skill_text)
    assert "read-only diagnosis" in core.lower()
    assert "Unknown stops its dependent write/conclusion" in core
    assert "read-only" in core
    assert "member" in core
    assert "leader:<ceiling>" in core
    assert "default branch" in core
    assert "PR/integration branch or working-copy authority" in core
    assert "no redownload" in router


def test_preflight_resolves_governance_paths_from_pinned_config(repo_root, skill_text):
    _, core, _ = _preflight_sources(repo_root, skill_text)
    for term in ("managed_paths.protocol", "managed_paths.authorization", "INSTALL_SKILL.md", "same SHA"):
        assert term in core
    assert "hardcoded fallback" in core
    assert "ambiguous" in core and "symlink" in core


def test_package_verification_is_conditional_and_release_binding_remains_external(repo_root, skill_text):
    _, core, package = _preflight_sources(repo_root, skill_text)
    for field in (
        "source_repository_url", "release_tag", "resolved_commit_sha",
        "installation_page_permalink", "RESOURCE_MANIFEST.json",
    ):
        assert field in package
    assert "metadata.version" in core
    assert "40-character" in package
    assert "reuse unchanged verification" in core.lower()
    assert "release_binding_verified=false" in package
    assert "does **not** authenticate" in package


def test_elevation_is_conditionally_routed_without_blocking_read_only_diagnosis(repo_root, skill_text):
    _, core, _ = _preflight_sources(repo_root, skill_text)
    authority = (repo_root / "shared/references/elevated-authority.md").read_text()
    assert "](elevated-authority.md)" in core
    for trigger in ("matching active grant", "requested Leader operation", "ambiguous identity/authority"):
        assert trigger in core
    for boundary in (
        "exactly one", "permission_ceiling", "uri", "date-time",
        "default_branch_source_sha", "specific-action approval", "delegated responsibility/**scope**",
        "below Maintain", "current-session", "same-SHA", "Read-only checks need no Leader calculation",
    ):
        assert boundary in authority, boundary
    assert "](elevated-authority.md)" in skill_text(f"{SKILL_NAME}/references/identity-and-permissions.md")


def test_entrypoint_forbids_only_unscoped_stage_all(skill_text):
    text = skill_text(f"{SKILL_NAME}/SKILL.md")

    assert "git add -A" in text
    assert "git add ." in text
    assert "显式 pathspec" in text
