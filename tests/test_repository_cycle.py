from unittest.mock import Mock
import pytest
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.workflow import WorkflowPolicy
from cmf_dev_studio.project_runners import select_runner, execute_runner

@pytest.mark.parametrize('name', ['pytest','maven','gradle'])
def test_cycle_repairs_only_test_failures(name):
    run = Mock(side_effect=[(False, f'Runner: {name} (exit 1; test_result)'), (True, 'ok')])
    repair = Mock(return_value=(True, 'repaired'))
    assert Orchestrator.repository_test_cycle(WorkflowPolicy(), run, repair) == (True, 'ok')
    assert run.call_count == 2 and repair.call_count == 1

def test_cycle_stops_on_infrastructure():
    run = Mock(return_value=(False, 'Runner: gradle (exit 125; infrastructure_error)'))
    repair = Mock()
    assert not Orchestrator.repository_test_cycle(WorkflowPolicy(), run, repair)[0]
    repair.assert_not_called()

@pytest.mark.parametrize('directory,name,cache', [('java-maven','maven','/tmp/maven/repository'),('kotlin-gradle','gradle','/tmp/gradle')])
def test_jvm_example_runner(directory,name,cache,monkeypatch):
    from pathlib import Path
    from cmf_dev_studio import project_runners
    root = Path(__file__).resolve().parents[1] / 'examples' / directory
    spec = select_runner(root)
    assert spec.name == name
    run = Mock(return_value=Mock(returncode=0,stdout='ok',stderr=''))
    monkeypatch.setattr(project_runners.subprocess,'run',run)
    assert execute_runner(root,spec)[0]
    command = run.call_args.args[0]
    assert cache in ' '.join(command)
    assert '--read-only' in command and '--network' in command and 'none' in command
