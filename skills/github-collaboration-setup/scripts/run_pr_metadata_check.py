"""Locate and run the deployed default-branch metadata chain. GitHub GET only."""

import argparse
import base64
import binascii
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote


DEPLOYED = ".github/agent-collaboration/"
INPUT_VERSION = 2
CHECK_CONTRACT_VERSION = 2
SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
TRUSTED_PROGRAM_FILES = ("run_pr_metadata_check.py", "collect_pr_metadata.py", "check_pr_metadata.py")
TRUSTED_EXTRA_FILES = ("collaboration_event.py", "collaboration_scope.py", "collaboration-event.schema.json", "requirements-helpers.txt")


class EvidenceUnavailable(Exception):
    """No complete, current snapshot can be asserted."""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise EvidenceUnavailable("invalid command arguments; run --help")


class GitHub:
    def __init__(self):
        self.trees = {}

    def get(self, endpoint, missing_ok=False):
        try:
            result = subprocess.run(
                ["gh", "api", "--method", "GET", "--hostname", "github.com", endpoint],
                capture_output=True, text=True, check=False, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise EvidenceUnavailable("GitHub GET unavailable; retry collection") from error
        if result.returncode:
            if missing_ok and re.search(r"HTTP (404|410)\b", result.stderr or ""):
                return None
            raise EvidenceUnavailable("GitHub GET failed or rate limited; retry collection")
        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError) as error:
            raise EvidenceUnavailable("GitHub returned invalid JSON") from error

    def content(self, repository, path, sha):
        key = (repository, sha)
        if key not in self.trees:
            tree = self.get(f"repos/{repository}/git/trees/{sha}?recursive=1")
            if (not isinstance(tree, dict) or tree.get("truncated") is not False
                    or not isinstance(tree.get("tree"), list)):
                raise EvidenceUnavailable("trusted Git tree unavailable or truncated")
            self.trees[key] = tree["tree"]
        entries = [entry for entry in self.trees[key] if isinstance(entry, dict) and entry.get("path") == path]
        if (len(entries) != 1 or entries[0].get("type") != "blob"
                or entries[0].get("mode") not in {"100644", "100755"}):
            raise EvidenceUnavailable("trusted path is missing, ambiguous, symlink or gitlink")
        item = self.get(f"repos/{repository}/contents/{quote(path, safe='/')}?ref={sha}")
        if (not isinstance(item, dict) or item.get("type") != "file"
                or item.get("encoding") != "base64" or item.get("path") != path):
            raise EvidenceUnavailable("trusted deployment file missing, ambiguous or not a regular file")
        try:
            raw = base64.b64decode("".join(item["content"].split()), validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as error:
            raise EvidenceUnavailable("trusted deployment file encoding invalid") from error
        if len(raw) > 262144:
            raise EvidenceUnavailable("trusted deployment file exceeds size limit")
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if item.get("sha") != blob or entries[0].get("sha") != blob or item.get("size") != len(raw):
            raise EvidenceUnavailable("trusted deployment file bytes do not match GitHub blob")
        return raw


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def default_sha(api, repository, default_branch):
    value = api.get(f"repos/{repository}/git/ref/heads/{quote(default_branch, safe='')}")
    sha = value.get("object", {}).get("sha") if isinstance(value, dict) else None
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise EvidenceUnavailable("current default-branch SHA unavailable")
    return sha


def arguments(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub owner/name")
    parser.add_argument("--pull-number", type=int, required=True)
    parser.add_argument("--repository-id", type=int, help="optional externally bound stable ID")
    parser.add_argument("--expected-head", help="reject a PR event or caller whose HEAD is stale")
    parser.add_argument("--expected-trusted-sha", help="expected current default SHA; always independently queried")
    parser.add_argument("--default-target-only", action="store_true", help="Actions default-target restriction")
    parser.add_argument("--collect-only", action="store_true", help="print input snapshot without claiming check pass")
    parser.add_argument("--output-dir", help="save metadata.json and the formal check report")
    args = parser.parse_args(argv)
    if (not REPOSITORY.fullmatch(args.repository) or args.pull_number < 1
            or (args.repository_id is not None and args.repository_id < 1)
            or any(value is not None and not SHA.fullmatch(value)
                   for value in (args.expected_head, args.expected_trusted_sha))):
        raise EvidenceUnavailable("invalid repository, PR number, stable ID or expected SHA")
    return args


@contextmanager
def output_directory(path, create=False):
    """Walk directory descriptors without following symlinks in any component."""
    if (not all(hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW"))
            or any(operation not in getattr(os, "supports_dir_fd", set()) for operation in (os.open, os.mkdir))
            or os.listdir not in getattr(os, "supports_fd", set())):
        raise EvidenceUnavailable("safe output directory capabilities unavailable; omit --output-dir or use a supported platform")
    absolute = Path(path).absolute()
    if ".." in absolute.parts:
        raise EvidenceUnavailable("output directory must not contain parent traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                try:
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    except (OSError, NotImplementedError) as error:
        raise EvidenceUnavailable("output directory unavailable, non-regular or contains a symlink") from error
    finally:
        os.close(descriptor)


def require_empty_output(descriptor):
    if descriptor is not None and os.listdir(descriptor):
        raise EvidenceUnavailable("output directory is occupied; choose a new or empty regular directory")


def save_outputs(path, payload, report=None):
    with output_directory(path, create=True) as descriptor:
        require_empty_output(descriptor)
        outputs = {"metadata.json": payload}
        if report is not None:
            outputs["check-report.json"] = report
        for name, value in outputs.items():
            handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=descriptor)
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(args, api):
    if args.output_dir:
        with output_directory(args.output_dir) as descriptor:
            require_empty_output(descriptor)
    repository = api.get(f"repos/{args.repository}")
    if (not isinstance(repository, dict) or repository.get("full_name") != args.repository
            or type(repository.get("id")) is not int or repository["id"] < 1
            or not isinstance(repository.get("default_branch"), str) or not repository["default_branch"]
            or (args.repository_id is not None and args.repository_id != repository["id"])):
        raise EvidenceUnavailable("repository identity mismatch or unavailable")
    sha = default_sha(api, args.repository, repository["default_branch"])
    if args.expected_trusted_sha is not None and sha != args.expected_trusted_sha:
        raise EvidenceUnavailable("default branch changed since caller/event; refresh collection")
    sources = {}
    for name in (*TRUSTED_PROGRAM_FILES, *TRUSTED_EXTRA_FILES, "config.yml"):
        path = DEPLOYED + name
        sources[path] = api.content(args.repository, path, sha)
    # Installed copies locate the chain. Only byte-identical deployed launchers run it.
    if Path(__file__).read_bytes() != sources[DEPLOYED + "run_pr_metadata_check.py"]:
        raise EvidenceUnavailable("local launcher differs from deployed version; update the launcher from this default SHA")
    if default_sha(api, args.repository, repository["default_branch"]) != sha:
        raise EvidenceUnavailable("default branch changed before trusted code load; refresh collection")
    with tempfile.TemporaryDirectory(prefix="agent-metadata-") as directory:
        root = Path(directory)
        for name in (*TRUSTED_PROGRAM_FILES, *TRUSTED_EXTRA_FILES):
            (root / name).write_bytes(sources[DEPLOYED + name])
        checker = load_module("trusted_checker", root / "check_pr_metadata.py")
        collector = load_module("trusted_collector", root / "collect_pr_metadata.py")
        if (getattr(checker, "COLLECTOR_INPUT_VERSION", None) != INPUT_VERSION
                or getattr(collector, "INPUT_VERSION", None) != INPUT_VERSION
                or getattr(checker, "FORMAL_CHECK_VERSION", None) != CHECK_CONTRACT_VERSION
                or getattr(collector, "CHECK_CONTRACT_VERSION", None) != CHECK_CONTRACT_VERSION):
            raise EvidenceUnavailable("deployed collector/checker input version incompatible; upgrade the complete chain")
        config_text = sources[DEPLOYED + "config.yml"].decode("utf-8")
        config = checker.restricted_yaml(config_text)
        auth_path = checker.managed_paths(config)["authorization"]
        sources[auth_path] = api.content(args.repository, auth_path, sha)
        payload = collector.collect(api, checker, args, repository, sha, config_text,
                                    sources[auth_path].decode("utf-8"), sources)
        input_path = root / "metadata.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.collect_only:
            if args.output_dir:
                save_outputs(args.output_dir, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 0
        result = subprocess.run([sys.executable, str(root / "check_pr_metadata.py"),
                                 str(input_path), str(root)], capture_output=True,
                                text=True, check=False, timeout=30)
        declared = re.findall(r"(?m)^RESULT=(pass|fail|unknown)$", result.stdout)
        if ((result.returncode, declared) not in ((0, ["pass"]), (1, ["fail"]))):
            raise EvidenceUnavailable("checker did not complete with a compatible result; refresh/repair deployed chain")
        report = {"result": "pass" if result.returncode == 0 else "fail", "snapshot": payload["snapshot"],
                  "check_report": result.stdout, "unverified": payload["snapshot"]["unverified"]}
        if args.output_dir:
            save_outputs(args.output_dir, payload, report)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if result.returncode == 0 else 1


def main(argv=None):
    try:
        return run(arguments(argv), GitHub())
    except (EvidenceUnavailable, OSError, ValueError, TypeError, KeyError, SyntaxError, ImportError, NotImplementedError,
            AttributeError, subprocess.TimeoutExpired) as error:
        message = str(error) if isinstance(error, EvidenceUnavailable) or type(error).__name__ == "CollectionUnavailable" else "trusted metadata chain invalid or unavailable"
        print(json.dumps({"result": "unknown", "errors": [message], "snapshot": None}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
