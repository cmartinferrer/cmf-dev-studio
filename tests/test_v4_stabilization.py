import json
from unittest.mock import Mock
import pytest
from multi_agent_software_team.unified_engine import UnifiedEngine, Plan
from multi_agent_software_team.workspaces import validate_operations, WorkspaceError, _reviewed_patch


def test_invalid_python_is_rejected_before_execution():
    with pytest.raises(WorkspaceError, match='Syntax error in tests/test_main.py:1'):
        validate_operations([{'action':'create','path':'tests/test_main.py','content':'def test_ greeting_default():\n    pass'}], {}, set())


def test_review_only_receives_approved_baseline_and_diff():
    llm = Mock(); llm.generate.return_value = '{"issues": []}'
    original = {'tests/test_main.py': b'def test_version():\n    assert version == "0.1.0"\n', 'private.py': b'PRIVATE_SENTINEL'}
    operations = [{'action':'modify','path':'tests/test_main.py','content':original['tests/test_main.py'].decode()+'\ndef test_greeting():\n    assert True\n'}]
    assert UnifiedEngine(llm).review_patch('greeting', Plan(('greeting',), ('greeting',)), operations, original=original, approved_paths={'tests/test_main.py'}) == []
    prompt = llm.generate.call_args.args[0]
    assert 'PRIVATE_SENTINEL' not in prompt
    assert '0.1.0' in prompt and 'Preserve unchanged pre-existing tests' in prompt
    assert 'Proposed diffs' in prompt


def test_review_feedback_retries_and_requires_clean_review():
    engine = Mock(); operations = [{'action':'create','path':'app.py','content':'x=1'}]
    engine.generate_patch.return_value = operations
    engine.review_patch.side_effect = [['fix assertion'], []]
    assert _reviewed_patch(engine,'task','prompt',Plan(('task',),('criterion',)),{},set(),Mock(),Mock()) == operations
    assert 'fix assertion' in engine.generate_patch.call_args.kwargs['feedback']
    assert engine.review_patch.call_count == 2


def test_persistent_review_failure_never_returns_patch():
    engine = Mock(); engine.review_patch.return_value = ['missing tests']
    with pytest.raises(WorkspaceError, match='Tester review unresolved'):
        _reviewed_patch(engine,'task','prompt',Plan(('task',),('criterion',)),{},set(),Mock(),Mock())


def test_syntax_error_is_repaired_in_generation():
    llm = Mock(); llm.generate.side_effect = [json.dumps({'operations':[{'action':'create','path':'app.py','content':'def broken name(): pass'}]}),json.dumps({'operations':[{'action':'create','path':'app.py','content':'def fixed(): pass'}]})]
    result = UnifiedEngine(llm).generate_patch('prompt',Plan(('task',),('criterion',)),validate=lambda ops: validate_operations(ops,{},set()))
    assert result[0]['content'] == 'def fixed(): pass'
    assert 'Syntax error' in llm.generate.call_args.args[0]

@pytest.mark.parametrize('infra', [False, True])
def test_existing_broken_proposal_repair_or_infrastructure_stop(tmp_path, monkeypatch, infra):
    import sys, types, subprocess
    from pathlib import Path
    import multi_agent_software_team.workspaces as ws
    from multi_agent_software_team.projects.manager import ProjectManager
    manager = ProjectManager(tmp_path/'data'); project = manager.create('demo')
    service = ws.WorkspaceService(manager); pid = 'a'*32
    baseline = service.baselines/pid; baseline.mkdir()
    workspace = service.root/pid; workspace.mkdir()
    original = {'test_app.py': b'def test_old():\n    assert 1 == 1\n'}
    for root in (baseline, project.path):
        (root/'test_app.py').write_bytes(original['test_app.py'])
    broken = [{'action':'modify','path':'test_app.py','content':'def test_ greeting(): pass'}]
    changes = service._write_operations(pid, broken, original)
    with service._db() as db:
        db.execute('INSERT INTO workspace_proposals(id,project_id,status,task,created_at,changes,approved_paths,plan) VALUES (?,?,?,?,?,?,?,?)', (pid,project.id,'ready','greeting','now',json.dumps(changes),json.dumps(['test_app.py']),json.dumps({'requirements':['greeting'],'acceptance':['greeting works']})))
    calls=[]
    def runner(root,spec):
        calls.append(spec.name)
        if infra: return False, 'Runner: pytest (exit 125; infrastructure_error)\npermission denied'
        result=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider'],cwd=root,capture_output=True,text=True,env={**__import__('os').environ,'PYTHONDONTWRITEBYTECODE':'1'})
        return result.returncode==0, f'Runner: pytest (exit {result.returncode}; test_result)\n'+result.stdout
    monkeypatch.setattr(ws,'execute_runner',runner)
    llm=Mock(); llm.generate.side_effect=[json.dumps({'operations':[{'action':'modify','path':'test_app.py','content':original['test_app.py'].decode()+'\ndef test_greeting():\n    assert "Hello" == "Hello"\n'}]}),'{"issues": []}']
    module=types.ModuleType('multi_agent_software_team.llm.gemini'); module.GeminiClient=lambda:llm
    monkeypatch.setitem(sys.modules,module.__name__,module)
    result=service.test(pid)
    assert result['status']==('test_failed' if infra else 'tested'), result
    assert len(calls)==(1 if infra else 2)
    assert llm.generate.call_count==(0 if infra else 2)
    assert (project.path/'test_app.py').read_bytes()==original['test_app.py']
    if not infra:
        service.apply(pid,'demo')
        assert 'test_greeting' in (project.path/'test_app.py').read_text()
