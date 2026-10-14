"""Exercise installed loaders without model prompts/turns or GitHub writes.

Run from the repository root. The script's fixture installations/configuration
go to a TemporaryDirectory, and evidence is printed to stdout. Dedicated Claude/
Pi directories isolate supported roots. HOME and CODEX_HOME are never overridden;
Codex may read default user config and create its own runtime cache/PATH aliases.
The probe never installs global Skills or edits global rules/settings, disables
hooks/MCP for discovery, and sends only initialize/list/read requests. Credential
environment variables are not inherited; that is not a claim that Codex cannot
read its default credential store. The probe sends no model or authentication
request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlsplit


SKILL_NAMES = ("github-collaboration-setup", "github-collaboration", "github-collaboration-check")
REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
SCENARIOS = {
    "codex": (
        ("project-root", "project/.agents/skills", ".", True),
        ("project-from-nested", "project/.agents/skills", "nested/child", True),
        ("project-from-spaces", "project/.agents/skills", "nested with spaces/child", True),
    ),
    "claude": (
        ("configured-user-root", "config/claude/skills", ".", True),
        ("project-root", "project/.claude/skills", ".", True),
        ("project-from-nested", "project/.claude/skills", "nested/child", True),
        ("project-from-spaces", "project/.claude/skills", "nested with spaces/child", True),
    ),
    "pi": (
        ("configured-user-root", "config/pi/skills", ".", True),
        ("project-native-root", "project/.pi/skills", ".", True),
        ("project-native-from-nested", "project/.pi/skills", "nested/child", False),
        ("project-shared-root", "project/.agents/skills", ".", True),
        ("project-shared-from-nested", "project/.agents/skills", "nested/child", True),
        ("project-shared-from-spaces", "project/.agents/skills", "nested with spaces/child", True),
        ("project-native-untrusted", "project/.pi/skills", ".", False),
        ("project-shared-untrusted", "project/.agents/skills", ".", False),
        ("project-shared-disabled", "project/.agents/skills", ".", False),
        ("project-user-collision", "project/.agents/skills", ".", True),
    ),
}


def package_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in directory.rglob("*") if item.is_file()),
                       key=lambda item: item.relative_to(directory).as_posix()):
        digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def declared_metadata(directory: Path) -> dict:
    text = (directory / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    def field(name: str):
        match = re.search(rf"^\s*{name}:\s*(.+)$", frontmatter, re.MULTILINE)
        return match.group(1).strip().strip('\"\'') if match else None
    return {"name": field("name"), "description": field("description"), "declared_version": field("version"),
            "file_count": sum(path.is_file() for path in directory.rglob("*")),
            "relative_link_target_count": len(relative_resource_paths(directory))}


def relative_resource_paths(directory: Path) -> list[Path]:
    """Audit every Markdown local link, including links between references."""
    resources: set[Path] = {directory / "SKILL.md"}
    for markdown in directory.rglob("*.md"):
        for raw_target in RESOURCE_LINK.findall(markdown.read_text(encoding="utf-8")):
            parsed = urlsplit(raw_target.strip("<>"))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            path = (markdown.parent / unquote(parsed.path)).resolve()
            path.relative_to(directory.resolve())
            if not path.is_file():
                raise ValueError(f"missing resource: {markdown.relative_to(directory)} -> {raw_target}")
            resources.add(path)
    return sorted(resources)


def child_environment(task_root: Path) -> dict[str, str]:
    # Intentionally do not inherit credentials, proxy settings, hooks or config.
    # PATH only resolves already-installed executables; no install/update runs.
    return {
        "PATH": os.environ.get("PATH", ""),
        "CLAUDE_CONFIG_DIR": str(task_root / "config/claude"),
        "PI_CODING_AGENT_DIR": str(task_root / "config/pi"),
        "PI_OFFLINE": "1",
        "PI_TELEMETRY": "0",
        "DISABLE_AUTOUPDATER": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "LANG": "en_US.UTF-8",
    }


class JsonLinesClient:
    def __init__(self, arguments: list[str], cwd: Path, environment: dict[str, str]):
        self.process = subprocess.Popen(arguments, cwd=cwd, env=environment,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
        self.messages: list[dict] = []
        self.stderr: list[str] = []

    def request(self, message: dict, matches, timeout: int = 25) -> dict:
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for key, _ in self.selector.select(timeout=0.1):
                line = key.fileobj.readline()
                if not line:
                    self.selector.unregister(key.fileobj)
                    continue
                if key.data == "stderr":
                    self.stderr.append(line.strip())
                    continue
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self.messages.append(response)
                if matches(response):
                    return response
            if self.process.poll() is not None:
                break
        raise RuntimeError(f"no discovery response; exit={self.process.poll()}, stderr={self.stderr[-5:]}")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.selector.close()
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()


def codex_discover(executable: str, cwd: Path, environment: dict[str, str], resources: list[Path]) -> dict:
    task_root = Path(environment["CLAUDE_CONFIG_DIR"]).parents[1]
    arguments = [executable, "app-server", "--stdio", "-c", "analytics.enabled=false",
                 "-c", "mcp_servers={}", "-c", "features.hooks=false",
                 "-c", f'log_dir="{task_root / "codex-runtime/logs"}"',
                 "-c", f'sqlite_home="{task_root / "codex-runtime/sqlite"}"']
    client = JsonLinesClient(arguments, cwd, environment)
    try:
        initialized = client.request({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "skill-discovery-test", "title": None, "version": "0.1"},
            "capabilities": None,
        }}, lambda response: response.get("id") == 1)
        listing = client.request({"id": 2, "method": "skills/list", "params": {
            "cwds": [str(cwd)], "forceReload": True,
        }}, lambda response: response.get("id") == 2)
        if "error" in listing:
            raise RuntimeError(listing["error"])
        entry = listing["result"]["data"][0]
        selected = [skill for skill in entry["skills"] if skill["name"] in SKILL_NAMES and Path(skill["path"]) in resources]
        outside_count = sum(skill["name"] in SKILL_NAMES and Path(skill["path"]) not in resources for skill in entry["skills"])
        reads = []
        for request_id, path in enumerate(resources, start=3):
            response = client.request({"id": request_id, "method": "fs/readFile", "params": {"path": str(path)}},
                                      lambda value, request_id=request_id: value.get("id") == request_id)
            reads.append({"path": str(path), "ok": "result" in response,
                          "response_keys": sorted(response.get("result", {})),
                          **({"error": response["error"]} if "error" in response else {})})
        return {"interface": "app-server initialize + skills/list + fs/readFile",
                "initialized_platform": {key: initialized["result"].get(key) for key in ("platformFamily", "platformOs")},
                "skills": selected, "outside_fixture_same_name_count": outside_count,
                "fixture_errors": [error for error in entry["errors"] if str(task_root) in str(error)],
                "resource_reads": {"attempted": len(reads), "successful": sum(read["ok"] for read in reads),
                                   "failures": [read for read in reads if not read["ok"]]}, "model_turns_sent": 0}
    finally:
        client.close()


def claude_discover(executable: str, cwd: Path, environment: dict[str, str], resources: list[Path], *, mode: str = "isolated-default") -> dict:
    arguments = [executable, "--print", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose", "--no-session-persistence",
                 "--setting-sources", "user,project", "--settings", '{"disableAllHooks":true}',
                 "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
    if mode == "bare":
        arguments.append("--bare")
    client = JsonLinesClient(arguments, cwd, environment)
    try:
        response = client.request({"type": "control_request", "request_id": "skill-discovery-init",
                                   "request": {"subtype": "initialize", "hooks": {}}},
                                  lambda value: value.get("type") == "control_response")
        result = response["response"]["response"]
        selected = [command for command in result["commands"] if command["name"] in SKILL_NAMES]
        return {"interface": "stream-json control_request.initialize (no user message)",
                "initialization_mode": mode, "hooks_explicitly_disabled": True,
                "commands": selected, "account_token_source": result["account"].get("tokenSource"),
                "session_state": result.get("session_state"), "analytics_disabled": result.get("analytics_disabled"),
                "actual_skill_path_returned": False,
                "resource_loading": "unverified: initialize lists metadata but exposes no package read operation",
                "model_turns_sent": 0}
    finally:
        client.close()


def pi_discover(executable: str, cwd: Path, environment: dict[str, str], resources: list[Path],
                *, trusted: bool = True, disabled: bool = False) -> dict:
    cli = Path(executable).resolve()
    package_root = cli.parents[2] if cli.parent.name == "bundle" else cli.parents[1]
    sdk = package_root / "dist/index.js"
    probe = REPO_ROOT / "tests/platform/probe_pi_loader.mjs"
    arguments = [shutil.which("node"), str(probe), str(sdk), str(cwd), environment["PI_CODING_AGENT_DIR"],
                 json.dumps([str(path) for path in resources]), json.dumps({"trusted": trusted, "disabled": disabled})]
    response = subprocess.run(arguments, cwd=cwd, env=environment, text=True, capture_output=True, timeout=25)
    if response.returncode:
        raise RuntimeError(response.stderr.strip())
    return json.loads(response.stdout)


def prepare_fixture(task_root: Path, installation: str, cwd_relative: str) -> tuple[Path, list[Path]]:
    project = task_root / "project"
    cwd = project / cwd_relative
    cwd.mkdir(parents=True)
    for config in ("config/claude", "config/pi"):
        (task_root / config).mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", str(project)], check=True,
                   env=child_environment(task_root), capture_output=True)
    # Disposable entry files let Pi's context loader show ancestor behavior.
    (project / "AGENTS.md").write_text("# Disposable test entry\nplatform-entry: agents\n", encoding="utf-8")
    (project / "CLAUDE.md").write_text("# Disposable test entry\nplatform-entry: claude\n", encoding="utf-8")
    resources = []
    for name in SKILL_NAMES:
        source = REPO_ROOT / "skills" / name
        target = task_root / installation / name
        shutil.copytree(source, target)
        if package_digest(source) != package_digest(target):
            raise ValueError(f"copy digest mismatch: {name}")
        relative_resource_paths(target)
        resources.extend(sorted(path for path in target.rglob("*") if path.is_file()))
    return cwd, resources


def probe_agent(agent: str, executable: str, *, claude_mode: str = "isolated-default") -> list[dict]:
    observations = []
    discovery = {"codex": codex_discover, "claude": claude_discover, "pi": pi_discover}[agent]
    for scenario, installation, cwd_relative, expected in SCENARIOS[agent]:
        with tempfile.TemporaryDirectory(prefix="github-skill-discovery-", dir="/private/tmp") as temporary:
            task_root = Path(temporary)
            cwd, resources = prepare_fixture(task_root, installation, cwd_relative)
            if scenario == "project-user-collision":
                for name in SKILL_NAMES:
                    target = task_root / "config/pi/skills" / name
                    shutil.copytree(REPO_ROOT / "skills" / name, target)
                    relative_resource_paths(target)
                    resources.extend(sorted(path for path in target.rglob("*") if path.is_file()))
            try:
                if agent == "pi":
                    result = discovery(executable, cwd, child_environment(task_root), resources,
                                       trusted="untrusted" not in scenario, disabled="disabled" in scenario)
                elif agent == "claude":
                    result = discovery(executable, cwd, child_environment(task_root), resources, mode=claude_mode)
                else:
                    result = discovery(executable, cwd, child_environment(task_root), resources)
            except RuntimeError as error:
                observations.append({"scenario": scenario, "installation": installation, "cwd": cwd_relative,
                                     "status": "UNVERIFIED", "reason": str(error), "model_turns_sent": 0,
                                     "package_files_copied_and_audited": len(resources)})
                # A startup permission failure is shared by the remaining scenarios;
                # retain the reason and avoid repeating the same blocked process.
                break
            names = {entry["name"] for entry in result.get("skills", result.get("commands", []))}
            found = set(SKILL_NAMES) <= names
            status = "PASS" if found == expected else "FAIL"
            if agent == "claude" and not found:
                status = "UNVERIFIED"
                result["discovery_boundary"] = f"{claude_mode} initialize omitted target commands; on-demand resolution was not exercised"
            observations.append({"scenario": scenario, "installation": installation, "cwd": cwd_relative,
                                 "expected_discovery": expected, "observed_discovery": found,
                                 "status": status,
                                 "package_files_copied_and_audited": len(resources), **result})
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("all", "codex", "claude", "pi"), default="all")
    parser.add_argument("--claude-mode", choices=("bare", "isolated-default"), default="isolated-default")
    arguments = parser.parse_args()
    requested = list(SCENARIOS) if arguments.agent == "all" else [arguments.agent]
    result = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "os": platform.system(), "os_release": platform.release(), "architecture": platform.machine(),
              "source_base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
              "source_state": "uncommitted working tree; no release tag or release commit verified",
              "package_sha256": {name: package_digest(REPO_ROOT / "skills" / name) for name in SKILL_NAMES},
              "package_metadata": {name: declared_metadata(REPO_ROOT / "skills" / name) for name in SKILL_NAMES},
              "not_exercised": [
                  "default user HOME paths: no global installation or HOME/CODEX_HOME override",
                  "model explicit invocation and compliance, hooks, MCP, GitHub writes",
                  "release installation, upgrade, missing-skill stop-write, Linux, Windows native, WSL",
              ], "agents": {}}
    for agent in requested:
        executable = shutil.which(agent)
        if executable is None:
            result["agents"][agent] = {"status": "UNVERIFIED", "reason": "CLI not installed"}
            continue
        with tempfile.TemporaryDirectory(prefix="github-skill-version-", dir="/private/tmp") as temporary:
            task_root = Path(temporary)
            for directory in ("config/claude", "config/pi"):
                (task_root / directory).mkdir(parents=True)
            version = subprocess.check_output([executable, "--version"], env=child_environment(task_root),
                                              text=True, stderr=subprocess.DEVNULL).strip()
        result["agents"][agent] = {"client_version": version, "executable": str(Path(executable).resolve()),
                                    "observations": probe_agent(agent, executable, claude_mode=arguments.claude_mode)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
