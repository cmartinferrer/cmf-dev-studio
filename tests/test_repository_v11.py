from pathlib import Path
import pytest
from multi_agent_software_team.projects.intelligence import prepare_context, credential_findings
from multi_agent_software_team.projects.explorer import ExplorerError


def test_documentation_mention_does_not_trigger(tmp_path: Path):
    (tmp_path / 'README.md').write_text('Set your API_KEY in the environment.\npassword: your_password_here\n')
    assert prepare_context(tmp_path, ['README.md'])['files'][0]['path'] == 'README.md'


def test_real_secret_reports_line_without_value(tmp_path: Path):
    (tmp_path / 'main.py').write_text('print(1)\napi_key = "actualSensitiveValue123"\n')
    with pytest.raises(ExplorerError, match=r'line 2') as exc:
        prepare_context(tmp_path, ['main.py'])
    assert 'actualSensitiveValue123' not in str(exc.value)


def test_reference_data_not_mounted_instruction():
    from multi_agent_software_team.agents.developer import DeveloperAgent
    from multi_agent_software_team.models import Mission
    from unittest.mock import Mock
    llm = Mock()
    llm.generate.return_value = 'def f(): return 1'
    mission = Mission(description='Summarize approved repository context')
    mission.requirements = ['summarize']
    DeveloperAgent(llm).execute(mission)
    assert 'NOT mounted' in llm.generate.call_args.args[0]


def test_gemini_retries_transient_errors(monkeypatch):
    import sys
    import types
    from unittest.mock import Mock
    google = sys.modules.get('google')
    if google is None:
        google = types.ModuleType('google')
        monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setattr(google, 'genai', types.SimpleNamespace(Client=object), raising=False)
    sys.modules.pop('multi_agent_software_team.llm.gemini', None)
    from multi_agent_software_team.llm.gemini import GeminiClient
    sdk = Mock()
    sdk.models.generate_content.side_effect = [RuntimeError('503 UNAVAILABLE'), Mock(text='ok')]
    client = GeminiClient(sdk_client=sdk, retry_base_seconds=0)
    assert client.generate('prompt') == 'ok'
    assert sdk.models.generate_content.call_count == 2


def test_gemini_does_not_retry_bad_request(monkeypatch):
    import sys
    import types
    from unittest.mock import Mock
    google = sys.modules.get('google')
    if google is None:
        google = types.ModuleType('google')
        monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setattr(google, 'genai', types.SimpleNamespace(Client=object), raising=False)
    sys.modules.pop('multi_agent_software_team.llm.gemini', None)
    from multi_agent_software_team.llm.gemini import GeminiClient
    sdk = Mock()
    sdk.models.generate_content.side_effect = RuntimeError('400 INVALID_ARGUMENT')
    with pytest.raises(RuntimeError):
        GeminiClient(sdk_client=sdk, retry_base_seconds=0).generate('prompt')
    assert sdk.models.generate_content.call_count == 1
