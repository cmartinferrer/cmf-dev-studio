from pathlib import Path

import pytest

from multi_agent_software_team.workflow import WorkflowPolicy, identify_technology, acceptance_guidance
from multi_agent_software_team.projects.intelligence import analyze_repository, prepare_context


def test_shared_retry_policy():
    policy = WorkflowPolicy(3)
    assert policy.can_retry(1, recoverable=True)
    assert policy.can_retry(2, recoverable=True)
    assert not policy.can_retry(3, recoverable=True)
    assert not policy.can_retry(1, recoverable=False)
    with pytest.raises(ValueError):
        WorkflowPolicy(0)


def test_conservative_language_adapters():
    assert identify_technology({'app/main.py', 'pyproject.toml'}).test_adapter == 'python-pytest'
    assert identify_technology({'src/App.java', 'pom.xml'}).test_adapter is None
    assert identify_technology({'src/App.kt', 'build.gradle.kts'}).test_adapter is None
    assert identify_technology({'app/main.py', 'src/App.kt'}).test_adapter is None


def test_known_manifest_can_be_explicitly_approved(tmp_path: Path):
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')
    (tmp_path / '.env').write_text('PASSWORD=secret123')
    inventory = analyze_repository(tmp_path)
    assert 'pyproject.toml' in {x['path'] for x in inventory['candidates']}
    assert '.env' not in {x['path'] for x in inventory['candidates']}
    context = prepare_context(tmp_path, ['pyproject.toml'])
    assert context['files'][0]['path'] == 'pyproject.toml'


def test_tester_guidance_rejects_circular_assertions():
    assert 'not compare an endpoint to the same helper' in acceptance_guidance()
