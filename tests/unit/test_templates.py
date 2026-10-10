import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


SENTINEL = "__SETUP_REQUIRED__"
PROJECT_FILES = (
    "README.md",
    "PROTOCOL.md",
    "ROLES.md",
    "config.yml",
    "authorization.yml",
    "managed-resources.yml",
    "INSTALL_SKILL.md",
)


def validation_errors(repo_root: Path, schema_name: str, value: object):
    schema = json.loads((repo_root / "schemas" / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validator.iter_errors(value))


def markdown_relative_targets(text: str) -> list[str]:
    return [
        target
        for target in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", text)
        if not target.startswith(("#", "http://", "https://", "mailto:"))
    ]


def test_project_templates_parse_and_reference_only_repository_facts(repo_root):
    project = repo_root / "templates/project/.github/agent-collaboration"
    config = yaml.safe_load((project / "config.yml").read_text(encoding="utf-8"))

    assert config["protocol_version"] == "0.1.1"
    assert config["minimum_runtime_skill_version"] == "0.1.1"
    assert config["managed_paths"]["pull_request_template"] == (
        ".github/PULL_REQUEST_TEMPLATE/agent-change.md"
    )
    assert (repo_root / "templates/project" / config["managed_paths"]["pull_request_template"]).is_file()
    assert not validation_errors(repo_root, "config.schema.json", config)

    for entry in ("AGENTS.md.block", "CLAUDE.md.block"):
        text = (repo_root / "templates/managed-blocks" / entry).read_text(encoding="utf-8")
        assert ".github/agent-collaboration/README.md" in text
        assert "github-collaboration" in text
        assert "github-collaboration-setup" not in text or "Leader" in text


def test_candidate_metadata_requires_setup_substitution_before_schema_validation(repo_root):
    project = repo_root / "templates/project/.github/agent-collaboration"
    authorization = yaml.safe_load((project / "authorization.yml").read_text(encoding="utf-8"))
    managed_resources = yaml.safe_load((project / "managed-resources.yml").read_text(encoding="utf-8"))

    assert SENTINEL in (project / "authorization.yml").read_text(encoding="utf-8")
    assert SENTINEL in (project / "managed-resources.yml").read_text(encoding="utf-8")
    assert validation_errors(repo_root, "authorization.schema.json", authorization)
    assert validation_errors(repo_root, "managed-resources.schema.json", managed_resources)

    valid_authorization = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-authorization.yml").read_text(encoding="utf-8")
    )
    valid_managed_resources = yaml.safe_load(
        (repo_root / "tests/fixtures/config/valid-managed-resources.yml").read_text(encoding="utf-8")
    )

    configured_authorization = deepcopy(authorization)
    configured_authorization["repository"] = valid_authorization["repository"]
    configured_managed_resources = deepcopy(managed_resources)
    configured_managed_resources["installation_id"] = valid_managed_resources["installation_id"]
    configured_managed_resources["resources"] = valid_managed_resources["resources"]

    assert not validation_errors(
        repo_root, "authorization.schema.json", configured_authorization
    )
    assert not validation_errors(
        repo_root, "managed-resources.schema.json", configured_managed_resources
    )

    malformed = deepcopy(valid_authorization)
    malformed["leader_delegations"] = [{
        **malformed["leader_delegations"][0],
        "approval_evidence": {
            **malformed["leader_delegations"][0]["approval_evidence"],
            "github_pr_url": "not a URL",
            "approved_at": "not a timestamp",
        },
    }]
    messages = " ".join(
        error.message
        for error in validation_errors(repo_root, "authorization.schema.json", malformed)
    )
    assert "uri" in messages and "date-time" in messages


def test_template_documents_link_within_the_project_template_tree(repo_root):
    project = repo_root / "templates/project"
    blocks = repo_root / "templates/managed-blocks"

    for relative_path in PROJECT_FILES:
        assert (project / ".github/agent-collaboration" / relative_path).is_file()

    documents = list((project / ".github/agent-collaboration").glob("*.md"))
    documents.extend(
        blocks / entry
        for entry in ("AGENTS.md.block", "CLAUDE.md.block", "CONTRIBUTING.md.block")
    )
    for document in documents:
        for target in markdown_relative_targets(document.read_text(encoding="utf-8")):
            target_path = target.split("#", 1)[0]
            assert target_path
            base = project if document.parent == blocks else document.parent
            resolved = (base / target_path).resolve()
            assert resolved.is_relative_to(project.resolve())
            assert resolved.is_file()


def test_managed_block_templates_are_body_only_and_point_to_installation(repo_root):
    blocks = repo_root / "templates/managed-blocks"

    for entry in ("AGENTS.md.block", "CLAUDE.md.block", "CONTRIBUTING.md.block"):
        text = (blocks / entry).read_text(encoding="utf-8")
        assert "<!-- github-agent-collaboration:" not in text
        assert ".github/agent-collaboration/README.md" in text
        assert "[安装说明](.github/agent-collaboration/INSTALL_SKILL.md)" in text
        assert "github-collaboration" in text
        assert "0.1.1" in text


def test_github_templates_offer_structured_agent_workflows(repo_root):
    project = repo_root / "templates/project/.github"
    issue = yaml.safe_load((project / "ISSUE_TEMPLATE/agent-task.yml").read_text(encoding="utf-8"))
    pull_request = (project / "PULL_REQUEST_TEMPLATE/agent-change.md").read_text(encoding="utf-8")

    assert issue["name"] == "Agent task"
    assert issue["body"]
    assert "Issue" in pull_request
    assert "验证" in pull_request


@pytest.mark.parametrize("closes_issues", [[], [7], [7, 8]])
def test_pr_template_can_be_completed_for_partial_or_multi_issue_delivery(
    repo_root, fixture_path, run_metadata_check, tmp_path, closes_issues
):
    template = (
        repo_root / "templates/project/.github/PULL_REQUEST_TEMPLATE/agent-change.md"
    ).read_text(encoding="utf-8")
    blocks = list(re.finditer(r"<!-- agent-collaboration:metadata\s*([\s\S]*?)-->", template))
    assert len(blocks) == 1

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, f"duplicate template metadata key: {key}"
            result[key] = value
        return result

    metadata = json.loads(blocks[0].group(1), object_pairs_hook=unique_keys)
    data = json.loads(fixture_path("github/pr-valid.json").read_text(encoding="utf-8"))
    data["pull"]["body"] = template
    candidate = tmp_path / "template-candidate.json"
    candidate.write_text(json.dumps(data), encoding="utf-8")
    result = run_metadata_check(candidate)
    assert result.returncode == 1, "an unfilled template must not pass"

    metadata.update(
        primary_issue=7,
        closes_issues=closes_issues,
        actor_id="backend-api",
        controlled_by=data["pull"]["user"]["login"],
        controlled_by_id=data["pull"]["user"]["id"],
        runtime="codex",
        session_id="template-validation",
        head_sha=data["pull"]["head"]["sha"],
        base_branch=data["pull"]["base"]["ref"],
        claim_urls=["https://github.com/sample/repo/issues/7#issuecomment-1"],
    )
    block = blocks[0]
    data["pull"]["body"] = (
        template[: block.start(1)]
        + json.dumps(metadata, ensure_ascii=False)
        + "\n"
        + template[block.end(1) :]
        + "\n"
        + "\n".join(f"Closes #{issue}" for issue in closes_issues)
    )
    if 8 in closes_issues:
        data["issues"].append({"number": 8, "state": "open", "pull_request": None})
    candidate.write_text(json.dumps(data), encoding="utf-8")
    result = run_metadata_check(candidate)
    assert result.returncode == 0, result.stdout + result.stderr


def test_roles_template_defines_permission_intersection_and_account_changes(repo_root):
    roles = (repo_root / "templates/project/.github/agent-collaboration/ROLES.md").read_text(
        encoding="utf-8"
    )

    assert "有效权限 = 授权上限 ∩ GitHub 账号当前权限 ∩ 项目协议允许范围 ∩ Rulesets / 分支保护" in roles
    assert "账号从 Maintain 升到 Admin 时，既有 Leader 仍保持 Maintain 上限" in roles
    assert "账号降权时，有效权限立即下降" in roles
    assert "账号仍处于冻结的权限上限内" not in roles
