"""Real PTY interruption regression tests."""

import asyncio
import sys

from cmf_dev_studio.api.terminal import terminal_socket
from cmf_dev_studio.projects.manager import ProjectManager


class InterruptSocket:
    """Minimal socket that sends Ctrl+C once the child is ready."""

    def __init__(self, project_id):
        self.headers = {
            "origin": "http://localhost:8000",
            "host": "localhost:8000",
        }
        self.query_params = {"run": "main.py"}
        self.path_params = {"project_id": project_id}
        self.ready = asyncio.Event()
        self.output = ""
        self.interrupted = False

    async def accept(self):
        pass

    async def close(self, code=1000):
        pass

    async def send_text(self, data):
        self.output += data

    async def send_bytes(self, data):
        self.output += data.decode(errors="replace")
        if not self.interrupted and "child-ready" in self.output:
            self.ready.set()

    async def receive(self):
        await self.ready.wait()
        self.ready.clear()
        self.interrupted = True
        return {
            "type": "websocket.receive",
            "text": '{"type":"input","data":"\\u0003"}',
        }


def test_ctrl_c_interrupts_run_process_group(tmp_path, monkeypatch):
    """Ctrl+C reaches a real child even without a controlling terminal."""
    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language="python")
    monkeypatch.setattr(
        "cmf_dev_studio.api.terminal.python_run_command",
        lambda *_: [
            sys.executable,
            "-u",
            "-c",
            "import time; print('child-ready'); time.sleep(60)",
        ],
    )

    async def exercise():
        ws = InterruptSocket(project.id)
        await asyncio.wait_for(terminal_socket(ws, manager), timeout=8)
        return ws.output

    output = asyncio.run(exercise())
    assert "KeyboardInterrupt" in output
    assert "Process exited with code" in output
