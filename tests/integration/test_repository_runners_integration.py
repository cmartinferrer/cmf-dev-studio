"""Integration tests for real Docker-based project runners."""

from pathlib import Path

import pytest

from cmf_dev_studio.project_runners import (
    execute_runner,
    select_runner,
)


@pytest.mark.integration
@pytest.mark.parametrize(
    "example, expected_runner",
    [
        ("python-pytest", "pytest"),
        ("java-maven", "maven"),
        ("kotlin-gradle", "gradle"),
    ],
)
def test_project_runner_real(example, expected_runner):
    root = Path(__file__).resolve().parents[2] / "examples" / example

    assert root.is_dir()

    runner = select_runner(root)

    assert runner.name == expected_runner

    passed, output = execute_runner(root, runner)

    assert passed, output