from pathlib import Path
from unittest.mock import Mock
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.contracts import Plan


def test_repository_is_only_execution_entrypoint(tmp_path):
    app = create_app(tmp_path)
    paths = [route.path for route in app.routes]
    assert not any('/missions' in path for path in paths)
    assert '/api/projects/{project_id}/proposals' in paths
    root = Path(__file__).resolve().parents[1] / 'src/cmf_dev_studio'
    assert not (root / 'unified_engine.py').exists()
    assert not (root / 'missions.py').exists()


def test_prepare_calls_actual_roles_in_order():
    llm = Mock()
    llm.generate.side_effect = ['{"requirements":["feature"],"acceptance":["result"]}', '{"operations":[{"action":"create","path":"App.java","content":"class App {}"}]}', '{"issues":[]}']
    stages = []
    plans = []
    validate = Mock()
    ops = Orchestrator(llm).prepare('feature', '', '', ['Java'], {}, set(), validate, stages.append, plans.append)
    assert stages == ['analyst', 'developer', 'tester']
    assert plans == [Plan(('feature',), ('result',))]
    assert ops[0]['path'] == 'App.java'
    validate.assert_called_once_with(ops)
    assert [role in call.args[0] for role, call in zip(['ROLE: ANALYST','ROLE: DEVELOPER','ROLE: TESTER'], llm.generate.call_args_list)] == [True, True, True]
