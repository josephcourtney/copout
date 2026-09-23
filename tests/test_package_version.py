import tomllib
from importlib.metadata import version
from pathlib import Path


def test_package_version_matches_project_metadata() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert version("copout") == project["project"]["version"]
