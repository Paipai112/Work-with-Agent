from collections.abc import Callable
from pathlib import Path

import pytest
import subprocess
import sys


def _repository_path(repo_root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path must stay beneath the repository: {relative_path}")

    resolved_root = repo_root.resolve()
    resolved_path = (resolved_root / path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"path must stay beneath the repository: {relative_path}") from error
    return resolved_path


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def fixtures_dir(repo_root: Path) -> Path:
    return _repository_path(repo_root, "tests/fixtures")


@pytest.fixture
def fixture_bytes(fixtures_dir: Path) -> Callable[[str], bytes]:
    def load_fixture(name: str) -> bytes:
        path = _repository_path(fixtures_dir, name)
        return path.read_bytes()

    return load_fixture


@pytest.fixture
def fixture_path(fixtures_dir: Path) -> Callable[[str], Path]:
    def resolve_fixture(name: str) -> Path:
        return _repository_path(fixtures_dir, name)

    return resolve_fixture


@pytest.fixture
def load_yaml(repo_root: Path) -> Callable[[str], object]:
    def load(path: str) -> object:
        import yaml

        return yaml.safe_load(_repository_path(repo_root, path).read_text(encoding="utf-8"))

    return load


@pytest.fixture
def load_eval(repo_root: Path, load_yaml: Callable[[str], object]) -> Callable[[str], object]:
    def load(path: str) -> object:
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError(f"path must stay beneath skill evaluations: {path}")
        return load_yaml(str(Path("tests/skill_eval") / path))

    return load


@pytest.fixture
def skill_text(repo_root: Path) -> Callable[[str], str]:
    def load(path: str) -> str:
        return _repository_path(repo_root, str(Path("skills") / path)).read_text(encoding="utf-8")

    return load


@pytest.fixture
def run_metadata_check(repo_root: Path, tmp_path: Path):
    def run(input_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(repo_root / "templates/project/.github/agent-collaboration/check_pr_metadata.py"), str(input_path), str(tmp_path)],
            text=True,
            capture_output=True,
            check=False,
        )

    return run
