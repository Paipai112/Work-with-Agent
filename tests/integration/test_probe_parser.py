"""Offline contract tests for the read-only GitHub evidence probe."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def probe_module():
    path = Path(__file__).with_name("probe_repository.py")
    spec = importlib.util.spec_from_file_location("probe_repository", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def api_fixture(tmp_path):
    def write(name: str) -> Path:
        sample = {
            "repository": {"status": "observed", "data": {
                "id": 99123, "name": "sample", "full_name": "team/sample",
                "default_branch": "main", "permissions": {"admin": False, "maintain": True},
                "clone_url": "https://user:secret@github.com/team/sample.git",
                "owner": {"email": "person@example.org"},
            }},
            "default_branch": {"status": "observed", "data": {"name": "main", "commit": {"sha": "a" * 40}}},
            "snapshot": {"status": "observed", "data": {"repository_id": 99123,
                "repository_full_name": "team/sample", "default_branch": "main", "commit_sha": "a" * 40}},
            "labels": {"status": "observed", "data": [{"name": "agent-collaboration/task"}]},
            "rulesets": {"status": "observed", "data": [{"id": 42, "name": "team", "rules": [
                {"type": "required_status_checks", "parameters": {"required_status_checks": [
                    {"context": "agent-collaboration"}]}},
                {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
            ]}]},
            "branch_protection": {"status": "unverified", "http_status": 403, "reason": "forbidden"},
            "workflow": {"status": "observed", "data": {"id": 91, "state": "active", "name": "agent-collaboration"}},
            "workflow_runs": {"status": "observed", "data": {"workflow_runs": [{"id": 7, "status": "completed", "conclusion": "success", "head_sha": "b" * 40}]}},
            "issue_template": {"status": "observed", "data": {"path": ".github/ISSUE_TEMPLATE/agent-task.yml", "sha": "c" * 40, "ref": "a" * 40}},
            "pr_template": {"status": "observed", "data": {"path": ".github/PULL_REQUEST_TEMPLATE/agent-change.md", "sha": "d" * 40, "ref": "a" * 40}},
            "codeowners": {"status": "unverified", "http_status": 404, "reason": "not found or inaccessible"},
            "managed_resources": {"status": "observed", "data": {"installation_id": "install-expected",
                "path": ".github/agent-collaboration/managed-resources.yml", "sha": "e" * 40, "ref": "a" * 40}},
            "pull_requests": {"status": "observed", "data": [{"number": 5, "mergeable": True, "mergeable_state": "clean"}]},
        }
        path = tmp_path / name
        path.write_text(json.dumps(sample), encoding="utf-8")
        return path
    return write


@pytest.fixture
def run_probe_parser(probe_module):
    def parse(path: Path):
        return probe_module.normalize_repository_state(
            json.loads(path.read_text(encoding="utf-8")),
            repo="github.com/team/sample", installation_id="install-expected",
        )
    return parse


def test_probe_normalizes_remote_ids_without_credentials(api_fixture, run_probe_parser):
    result = run_probe_parser(api_fixture("repository-state.json"))
    assert result["repository"]["id"] == 99123
    assert result["rulesets"][0]["managed_fields"]["required_status_checks"] == ["agent-collaboration"]
    assert result["installation"]["matches_expected"] is True
    assert result["branch_protection"]["status"] == "unverified"
    assert result["codeowners"]["status"] == "unverified"
    rendered = json.dumps(result).lower()
    assert "secret" not in rendered
    assert "person@example.org" not in rendered
    assert "clone_url" not in rendered


def test_failed_endpoint_is_unverified_not_absent(probe_module):
    source = {"repository": {"status": "unverified", "http_status": 404, "reason": "not found or inaccessible"}}
    result = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert result["repository"]["status"] == "unverified"
    assert result["labels"]["status"] == "unverified"
    assert "absent" not in json.dumps(result).lower()


def test_repository_target_rejects_unsafe_shape(probe_module):
    for target in ("team/sample", "github.com/team/sample/extra", "https://github.com/team/sample", "github.com/te am/sample"):
        with pytest.raises(ValueError):
            probe_module.parse_repo(target)


def test_endpoint_error_does_not_copy_sensitive_stderr_or_reason(probe_module, monkeypatch):
    seen = []
    def fake_run(command, **kwargs):
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, "", "HTTP 403 https://user:secret@github.com; person@example.org")
    monkeypatch.setattr(probe_module.subprocess, "run", fake_run)
    endpoint = probe_module._gh_api("github.com", "repos/team/sample")
    assert endpoint == {"status": "unverified", "reason": "endpoint unavailable or inaccessible", "http_status": 403}
    assert seen[0][0] == ["gh", "api", "--hostname", "github.com", "--method", "GET", "repos/team/sample"]
    assert seen[0][1].get("shell") is not True
    result = probe_module.normalize_repository_state(
        {"repository": {"status": "unverified", "http_status": 403,
                        "reason": "https://user:secret@github.com person@example.org"}},
        repo="github.com/team/sample", installation_id="install-expected",
    )
    assert "secret" not in json.dumps(result)
    assert "person@example.org" not in json.dumps(result)


def test_evidence_conforms_to_local_schema(api_fixture, run_probe_parser):
    import jsonschema
    schema = json.loads(Path(__file__).with_name("evidence.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(run_probe_parser(api_fixture("repository-state.json")), schema)


def test_probe_reads_ruleset_and_pull_details_before_claiming_fields(probe_module, monkeypatch):
    endpoints = []
    def fake_api(host, endpoint, *, paginate=False):
        endpoints.append(endpoint)
        if endpoint == "repos/team/sample":
            return {"status": "observed", "data": {"id": 99123, "name": "sample", "full_name": "team/sample", "default_branch": "main"}}
        if endpoint == "repos/team/sample/branches/main":
            return {"status": "observed", "data": {"name": "main", "commit": {"sha": "a" * 40}}}
        if endpoint.endswith("/rulesets?includes_parents=true&per_page=100"):
            return {"status": "observed", "data": [{"id": 42, "name": "team"}]}
        if endpoint.endswith("/rulesets/42"):
            return {"status": "observed", "data": {"id": 42, "name": "team", "rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "agent-collaboration"}]}}]}}
        if endpoint.endswith("/pulls?state=open&per_page=100"):
            return {"status": "observed", "data": [{"number": 5}]}
        if endpoint.endswith("/pulls/5"):
            return {"status": "observed", "data": {"number": 5, "mergeable": True, "mergeable_state": "clean"}}
        return {"status": "unverified", "reason": "fixture endpoint unavailable"}
    monkeypatch.setattr(probe_module, "_gh_api", fake_api)
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert "repos/team/sample/rulesets/42" in endpoints
    assert "repos/team/sample/pulls/5" in endpoints
    assert result["rulesets"][0]["managed_fields"]["required_status_checks"] == ["agent-collaboration"]
    assert result["pull_requests"]["open_prs"][0]["mergeability"]["mergeable"] is True


def test_missing_detail_stays_unverified_and_legacy_contexts_are_preserved(probe_module):
    source = {
        "branch_protection": {"status": "observed", "data": {
            "required_status_checks": {"contexts": ["build"]},
            "required_pull_request_reviews": {"required_approving_review_count": 2},
        }},
        "rulesets": {"status": "observed", "data": [{"id": 42, "name": "team"}]},
        "pull_requests": {"status": "observed", "data": [{"number": 5}]},
    }
    result = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert result["branch_protection"]["required_status_checks"] == ["build"]
    assert result["branch_protection"]["required_approving_review_count"] == 2
    assert result["rulesets"][0]["managed_fields"]["status"] == "unverified"
    assert result["pull_requests"]["open_prs"][0]["mergeability"]["status"] == "unverified"


def test_codeowners_falls_back_to_root_or_docs(probe_module, monkeypatch):
    paths = []
    def fake_content(host, root, path, *, ref):
        paths.append(path)
        assert ref == "b" * 40
        if path == "CODEOWNERS":
            return {"status": "observed", "data": {"path": path, "sha": "a" * 40}}
        return {"status": "unverified", "reason": "endpoint unavailable"}
    monkeypatch.setattr(probe_module, "_content", fake_content)
    result = probe_module._codeowners("github.com", "repos/team/sample", ref="b" * 40)
    assert paths == [".github/CODEOWNERS", "CODEOWNERS"]
    assert result["data"]["path"] == "CODEOWNERS"


def test_pending_github_mergeability_is_unverified(probe_module):
    source = {"pull_requests": {"status": "observed", "data": [
        {"number": 5, "mergeable": None, "mergeable_state": "unknown"}]}}
    result = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert result["pull_requests"]["open_prs"][0]["mergeability"]["status"] == "unverified"


def test_evidence_validation_rejects_unmodelled_absence(probe_module, api_fixture, run_probe_parser):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence["codeowners"] = {"status": "absent"}
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


def test_metadata_names_redact_email_and_token_shapes(probe_module):
    source = {"labels": {"status": "observed", "data": [
        {"name": "contact-person@example.org"},
        {"name": "github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"},
    ]}}
    result = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    rendered = json.dumps(result)
    assert "person@example.org" not in rendered
    assert "github_pat_" not in rendered


def test_evidence_file_is_private_and_never_overwritten(probe_module, monkeypatch, tmp_path, api_fixture, run_probe_parser):
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    monkeypatch.setattr(probe_module, "probe_repository", lambda repo, installation_id: evidence)
    output = tmp_path / "evidence.json"
    assert probe_module.main(["--repo", "github.com/team/sample", "--installation-id", "install-expected", "--output", str(output)]) == 0
    assert os.stat(output).st_mode & 0o777 == 0o600
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        probe_module.main(["--repo", "github.com/team/sample", "--installation-id", "install-expected", "--output", str(output)])
    assert output.read_bytes() == original


@pytest.fixture
def gh_transport(probe_module, monkeypatch):
    """Replace only the external process; all parsing/probing/writing stays real."""
    class Transport:
        def __init__(self):
            self.commands = []
            self.repository = {"id": 99123, "name": "sample", "full_name": "team/sample",
                               "default_branch": "main", "permissions": {
                                   "admin": False, "maintain": True, "push": True}}
            self.final_repository = None
            self.final_sha = "a" * 40
            self.branch_name = "main"
            self.repository_reads = 0
            self.branch_reads = 0
            self.denied = {}
            self.content_path = None
            self.content_sha = "c" * 40

        def run(self, command, **kwargs):
            self.commands.append((command, kwargs))
            endpoint = command[command.index("--method") + 2]
            if endpoint in self.denied:
                return subprocess.CompletedProcess(command, 1, "", self.denied[endpoint])
            if endpoint == "repos/team/sample":
                self.repository_reads += 1
                data = self.final_repository if self.repository_reads > 1 and self.final_repository else self.repository
            elif endpoint == "repos/team/sample/branches/main":
                self.branch_reads += 1
                data = {"name": self.branch_name, "commit": {
                    "sha": "a" * 40 if self.branch_reads == 1 else self.final_sha}}
            elif "/contents/" in endpoint:
                path = endpoint.split("/contents/", 1)[1].split("?", 1)[0]
                data = {"type": "file", "path": self.content_path or path,
                        "sha": self.content_sha, "encoding": "base64",
                        "content": "aW5zdGFsbGF0aW9uX2lkOiBpbnN0YWxsLWV4cGVjdGVkCg=="}
            elif endpoint.endswith("/labels?per_page=100"):
                data = [[{"name": "agent-collaboration/task"}]]
            elif endpoint.endswith("/rulesets?includes_parents=true&per_page=100"):
                data = [[{"id": 42, "name": "team"}]]
            elif endpoint.endswith("/rulesets/42"):
                data = {"id": 42, "name": "team", "rules": []}
            elif endpoint.endswith("/pulls?state=open&per_page=100"):
                data = [[{"number": 5}]]
            elif endpoint.endswith("/pulls/5"):
                data = {"number": 5, "mergeable": True, "mergeable_state": "clean"}
            elif endpoint.endswith("/protection"):
                data = {"required_status_checks": {"contexts": ["build"]}}
            elif endpoint.endswith("/runs?per_page=20"):
                data = {"workflow_runs": []}
            elif endpoint.endswith("/actions/workflows/agent-collaboration-check.yml"):
                data = {"id": 91, "state": "active"}
            else:
                return subprocess.CompletedProcess(command, 1, "", "HTTP 404")
            return subprocess.CompletedProcess(command, 0, json.dumps(data), "")

    transport = Transport()
    monkeypatch.setattr(probe_module.subprocess, "run", transport.run)
    return transport


@pytest.mark.parametrize("field,value", [
    ("full_name", "other/sample"), ("full_name", None), ("id", None),
    ("id", True), ("id", 0), ("name", "other"),
])
def test_probe_rejects_wrong_or_unidentified_repository(probe_module, gh_transport, field, value):
    gh_transport.repository[field] = value
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert result["repository"]["status"] == "unverified"
    assert result["installation"]["status"] == "unverified"
    assert len(gh_transport.commands) == 1


def test_contents_are_pinned_to_verified_default_branch_commit(probe_module, gh_transport):
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    content_endpoints = [command[command.index("--method") + 2]
                         for command, _ in gh_transport.commands if "/contents/" in command[command.index("--method") + 2]]
    assert content_endpoints
    assert all(endpoint.endswith("?ref=" + "a" * 40) for endpoint in content_endpoints)
    assert result["repository"].get("full_name") == "team/sample"
    assert result["issue_template"].get("ref") == "a" * 40
    assert result["snapshot"] == {"status": "observed", "repository_id": 99123,
                                  "repository_full_name": "team/sample", "default_branch": "main",
                                  "commit_sha": "a" * 40}
    probe_module.validate_evidence(result)


def test_branch_movement_invalidates_snapshot_and_content_evidence(probe_module, gh_transport):
    gh_transport.final_sha = "b" * 40
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert result.get("snapshot", {}).get("status") == "unverified"
    assert result["issue_template"]["status"] == "unverified"
    assert result["installation"]["status"] == "unverified"
    assert gh_transport.branch_reads == 2


@pytest.mark.parametrize("field,value", [("id", 88234), ("default_branch", "develop"),
                                         ("full_name", "other/sample")])
def test_repository_change_invalidates_snapshot(probe_module, gh_transport, field, value):
    gh_transport.final_repository = {**gh_transport.repository, field: value}
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert result.get("snapshot", {}).get("status") == "unverified"
    assert result["pr_template"]["status"] == "unverified"


def test_wrong_branch_response_cannot_bind_contents(probe_module, gh_transport):
    gh_transport.branch_name = "other"
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert result["default_branch"]["status"] == "unverified"
    assert not any("/contents/" in command[command.index("--method") + 2]
                   for command, _ in gh_transport.commands)


@pytest.mark.parametrize("field,value", [("content_path", "wrong/path"), ("content_sha", "invalid")])
def test_wrong_content_path_or_invalid_blob_sha_stays_unverified(probe_module, gh_transport, field, value):
    setattr(gh_transport, field, value)
    result = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert result["issue_template"]["status"] == "unverified"
    assert result["installation"]["status"] == "unverified"


def test_fixture_parser_never_claims_live_api_evidence(api_fixture, run_probe_parser):
    result = run_probe_parser(api_fixture("repository-state.json"))
    assert result["evidence_kind"] == "offline-fixture"
    assert "observed_at" not in result


def test_fixture_cli_writes_valid_private_evidence_without_gh(tmp_path, api_fixture):
    output = tmp_path / "offline-evidence.json"
    completed = subprocess.run([
        sys.executable, str(Path(__file__).with_name("probe_repository.py")),
        "--repo", "github.com/team/sample", "--installation-id", "install-expected",
        "--fixture", str(api_fixture("repository-state.json")), "--output", str(output),
    ], capture_output=True, text=True, check=False, env={**os.environ, "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"})
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["evidence_kind"] == "offline-fixture"
    assert os.stat(output).st_mode & 0o777 == 0o600


def test_all_probe_processes_are_explicit_read_only_get(probe_module, gh_transport):
    probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert len(gh_transport.commands) >= 12
    for command, kwargs in gh_transport.commands:
        assert command[:6] == ["gh", "api", "--hostname", "github.com", "--method", "GET"]
        assert command[6].startswith("repos/team/sample")
        assert command[7:] in ([], ["--paginate", "--slurp"])
        assert kwargs.get("shell") is not True
        assert kwargs["capture_output"] is True


@pytest.mark.parametrize("endpoint,key,code", [
    ("repos/team/sample", "repository", 401),
    ("repos/team/sample/branches/main/protection", "branch_protection", 403),
    ("repos/team/sample/contents/.github/ISSUE_TEMPLATE/agent-task.yml?ref=" + "a" * 40,
     "issue_template", 404),
])
def test_permission_or_not_found_errors_stay_unverified_without_error_prose(
        probe_module, gh_transport, endpoint, key, code):
    # Entirely synthetic credentials exercise redaction; no real token is used.
    gh_transport.denied[endpoint] = f"HTTP {code} https://fixture:secret@github.com person@example.org ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
    evidence = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert evidence[key]["status"] == "unverified"
    assert evidence[key]["http_status"] == code
    rendered = json.dumps(evidence)
    assert all(secret not in rendered for secret in ("secret", "person@example.org", "ghp_", "absent"))
    probe_module.validate_evidence(evidence)


@pytest.mark.parametrize("key,field,value", [
    ("snapshot", "repository_id", 88234), ("snapshot", "commit_sha", "b" * 40),
    ("issue_template", "ref", "b" * 40), ("installation", "ref", "b" * 40),
])
def test_validation_rejects_cross_field_binding_tampering(probe_module, api_fixture, run_probe_parser, key, field, value):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence[key][field] = value
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


def test_validation_rejects_repository_and_snapshot_rebound_to_another_target(probe_module, api_fixture, run_probe_parser):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence["repository"]["full_name"] = "other/sample"
    evidence["snapshot"]["repository_full_name"] = "other/sample"
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


def test_fixture_cannot_upgrade_its_own_provenance(probe_module, api_fixture):
    source = json.loads(api_fixture("repository-state.json").read_text(encoding="utf-8"))
    source["evidence_kind"] = "read-only-gh-api"
    source["observed_at"] = "2026-10-01T00:00:00+00:00"
    evidence = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert evidence["evidence_kind"] == "offline-fixture"
    assert "observed_at" not in evidence


def test_repository_names_allow_case_only_differences(probe_module, gh_transport):
    gh_transport.repository.update(name="SAMPLE", full_name="Team/SAMPLE")
    evidence = probe_module.probe_repository("github.com/team/sample", "install-expected")
    assert evidence["snapshot"]["status"] == "observed"
    probe_module.validate_evidence(evidence)


@pytest.mark.parametrize("key,data", [
    ("workflow", {"id": {"password": "SYNTHETIC_PRIVATE_MARKER"}, "state": "active"}),
    ("workflow", {"id": 91, "state": {"password": "SYNTHETIC_PRIVATE_MARKER"}}),
    ("workflow_runs", {"workflow_runs": [{"id": {"password": "SYNTHETIC_PRIVATE_MARKER"},
        "status": "completed", "conclusion": "success", "head_sha": "a" * 40}]}),
    ("rulesets", [{"id": {"password": "SYNTHETIC_PRIVATE_MARKER"}, "name": "team", "rules": []}]),
    ("rulesets", [{"id": 42, "name": {"password": "SYNTHETIC_PRIVATE_MARKER"}, "rules": []}]),
    ("branch_protection", {"required_status_checks": {}, "required_pull_request_reviews": {
        "required_approving_review_count": {"password": "SYNTHETIC_PRIVATE_MARKER"}}}),
    ("pull_requests", [{"number": {"password": "SYNTHETIC_PRIVATE_MARKER"},
        "mergeable": True, "mergeable_state": "clean"}]),
])
def test_non_scalar_remote_metadata_is_unverified_and_never_copied(
        probe_module, api_fixture, key, data):
    source = json.loads(api_fixture("repository-state.json").read_text(encoding="utf-8"))
    source[key] = {"status": "observed", "data": data}
    evidence = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(evidence)
    assert evidence[key]["status"] == "unverified"
    probe_module.validate_evidence(evidence)


@pytest.mark.parametrize("parameters", ["malformed", ["malformed"], 7, True])
def test_malformed_ruleset_parameters_keep_managed_fields_unverified(probe_module, parameters):
    source = {"rulesets": {"status": "observed", "data": [
        {"id": 42, "name": "team", "rules": [{"type": "required_status_checks", "parameters": parameters}]}]}}
    evidence = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert evidence["rulesets"][0]["managed_fields"]["status"] == "unverified"
    probe_module.validate_evidence(evidence)


def test_ruleset_nested_review_count_is_not_copied(probe_module):
    source = {"rulesets": {"status": "observed", "data": [
        {"id": 42, "name": "team", "rules": [{"type": "pull_request", "parameters": {
            "required_approving_review_count": {"password": "SYNTHETIC_PRIVATE_MARKER"}}}]}]}}
    evidence = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(evidence)
    assert evidence["rulesets"][0]["managed_fields"]["status"] == "unverified"


def test_pull_request_nested_mergeability_state_is_unverified(probe_module):
    source = {"pull_requests": {"status": "observed", "data": [
        {"number": 5, "mergeable": True, "mergeable_state": {"password": "SYNTHETIC_PRIVATE_MARKER"}}]}}
    evidence = probe_module.normalize_repository_state(source, repo="github.com/team/sample", installation_id="install-expected")
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(evidence)
    assert evidence["pull_requests"]["open_prs"][0]["mergeability"]["status"] == "unverified"


def test_live_observation_timestamp_is_actually_validated(probe_module, api_fixture, run_probe_parser):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence.update(evidence_kind="read-only-gh-api", observed_at="not-a-date-time")
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


@pytest.mark.parametrize("key,data", [
    ("workflow", {"status": "observed", "id": {"private": "SYNTHETIC_PRIVATE_MARKER"}, "state": "active"}),
    ("workflow_runs", {"status": "observed", "runs": [{"id": {"private": "SYNTHETIC_PRIVATE_MARKER"},
        "status": "completed", "conclusion": "success", "head_sha": "a" * 40}]}),
    ("rulesets", [{"id": {"private": "SYNTHETIC_PRIVATE_MARKER"}, "name": "team", "managed_fields": {
        "required_status_checks": [], "required_approving_review_count": 1}}]),
    ("branch_protection", {"status": "observed", "required_status_checks": [],
        "required_approving_review_count": {"private": "SYNTHETIC_PRIVATE_MARKER"}}),
    ("pull_requests", {"status": "observed", "open_prs": [{"number": {"private": "SYNTHETIC_PRIVATE_MARKER"},
        "mergeability": {"status": "observed", "mergeable": True, "mergeable_state": "clean"}}]}),
    ("labels", {"status": "observed", "names": [{"private": "SYNTHETIC_PRIVATE_MARKER"}]}),
])
def test_evidence_schema_rejects_nested_data_in_scalar_metadata(probe_module, api_fixture, run_probe_parser, key, data):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence[key] = data
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


def test_evidence_schema_rejects_unknown_permission_fields(probe_module, api_fixture, run_probe_parser):
    import jsonschema
    evidence = run_probe_parser(api_fixture("repository-state.json"))
    evidence["repository"]["permission"] = {"status": "observed", "admin": False, "maintain": True,
        "push": True, "private": {"password": "SYNTHETIC_PRIVATE_MARKER"}}
    with pytest.raises(jsonschema.ValidationError):
        probe_module.validate_evidence(evidence)


@pytest.mark.parametrize("content", [{"private": "SYNTHETIC_PRIVATE_MARKER"}, None, [], True])
def test_managed_manifest_non_string_content_stays_unverified(probe_module, content):
    result = probe_module._managed_id({"status": "observed", "data": {
        "encoding": "base64", "content": content}})
    assert result["status"] == "unverified"
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(result)
