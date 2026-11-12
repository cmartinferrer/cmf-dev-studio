from types import SimpleNamespace
from cmf_dev_studio.api.terminal import allowed_local_origin


def test_terminal_requires_local_browser_origin():
    def ws(origin, host='127.0.0.1:8000'):
        return SimpleNamespace(headers={'origin': origin, 'host': host})
    assert allowed_local_origin(ws('http://127.0.0.1:5173'))
    assert allowed_local_origin(ws('http://localhost:5173'))
    assert not allowed_local_origin(ws('https://evil.example'))
    assert not allowed_local_origin(ws('http://127.0.0.1:5174'))
    assert not allowed_local_origin(ws('http://127.0.0.1:5173', 'example.com'))
    assert not allowed_local_origin(ws(''))
