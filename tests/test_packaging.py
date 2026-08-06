"""Packaging: what the Lambda needs must be what the project declares.

`src/requirements.txt` is generated from the lockfile by `make requirements`,
so the old hand-maintained-duplicate check is gone. What can still go wrong is
importing something at runtime that was never declared — green tests locally,
ImportError in Lambda.
"""

import ast
import pathlib
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Provided by the Lambda runtime, so deliberately not packaged.
RUNTIME_PROVIDED = {"boto3", "botocore"}

# Import name → distribution name, where they differ.
DISTRIBUTIONS = {"jwt": "pyjwt"}


def _imported_top_level_modules():
    found = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def _declared_distributions():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return {
        item.split("[")[0].split("=")[0].split(">")[0].split("<")[0].strip().lower()
        for item in project["dependencies"]
    }


def test_every_third_party_import_is_declared():
    declared = _declared_distributions()
    undeclared = set()
    for module in _imported_top_level_modules():
        if module in sys.stdlib_module_names or module in RUNTIME_PROVIDED:
            continue
        if module in {"dataqna", "public_handler", "admin_handler"}:
            continue
        if DISTRIBUTIONS.get(module, module) not in declared:
            undeclared.add(module)
    assert not undeclared, f"imported but not in pyproject dependencies: {sorted(undeclared)}"


def test_boto3_is_not_packaged_into_the_lambda():
    """Shipping our own would add megabytes and shadow the version AWS patches."""
    assert not (RUNTIME_PROVIDED & _declared_distributions())


def test_tests_need_no_environment_wrapper_to_run():
    """`uv run pytest` has to work on its own — see conftest and pyproject."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "src" in pyproject["tool"]["pytest"]["ini_options"]["pythonpath"]
    assert "dev" in pyproject["dependency-groups"]
