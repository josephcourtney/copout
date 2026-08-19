import tomllib
from pathlib import Path

import copout


def test_package_version_matches_project_metadata() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert copout.__version__ == project["project"]["version"]
