from importlib.metadata import version

import copout


def test_package_version_matches_distribution_metadata() -> None:
    assert copout.__version__ == version("copout")
