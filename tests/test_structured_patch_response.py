import json
from unittest.mock import Mock
import pytest
from multi_agent_software_team.orchestrator import Orchestrator, Plan
from multi_agent_software_team.contracts import PATCH_SCHEMA
from multi_agent_software_team.workspaces import validate_operations

class StructuredProvider:
    def __init__(self):
        self.generate_json = Mock(side_effect=['[]', '{"operations": [{"action":"create","path":"app.py","content":"def broken name(): pass"}]}', '{"operations": [{"action":"create","path":"app.py","content":"def fixed(): pass"}]}'])
    def generate_json(self, prompt, schema): ...
    def generate(self, prompt): raise AssertionError('Unstructured call')

def test_repair_retries_array_and_syntax_error_using_schema():
    provider = StructuredProvider()
    result = Orchestrator(provider).generate_patch('task', Plan(('task',), ('criterion',)), feedback='SyntaxError', validate=lambda ops: validate_operations(ops, {}, set()))
    assert result[0]['content'] == 'def fixed(): pass'
    assert provider.generate_json.call_count == 3
    assert all(c.args[1] == PATCH_SCHEMA for c in provider.generate_json.call_args_list)
    assert 'Expected a JSON object' in provider.generate_json.call_args_list[1].args[0]
    assert 'Syntax error' in provider.generate_json.call_args_list[2].args[0]