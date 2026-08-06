"""The Lambda ships its own dependency list; it must not drift from the project's."""

import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _pinned(requirement):
    return re.split(r"[<>=!~]", requirement, maxsplit=1)[0].strip().lower()


def test_lambda_requirements_match_the_project_runtime_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = {
        _pinned(item): item for item in project["dependencies"] if _pinned(item) != "boto3"
    }
    shipped = {
        _pinned(line): line.strip()
        for line in (ROOT / "src" / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    # boto3 is provided by the Lambda runtime, so it is deliberately not shipped.
    assert declared == shipped


def test_tests_need_no_environment_wrapper_to_run():
    """`uv run pytest` has to work on its own — see conftest and pyproject."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["pytest"]["ini_options"]
    assert "src" in config["pythonpath"]
    assert "dev" in tomllib.loads((ROOT / "pyproject.toml").read_text())["dependency-groups"]
