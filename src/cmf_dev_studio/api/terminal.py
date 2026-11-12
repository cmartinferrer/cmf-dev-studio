"""Local interactive PTY, available only to an explicitly connected browser."""
import asyncio
import fcntl
import json
import os
import pty
import select
import signal
import struct
import subprocess
import termios
from urllib.parse import urlparse

from fastapi import WebSocket


def allowed_local_origin(ws: WebSocket) -> bool:
    origin = urlparse(ws.headers.get("origin", ""))
    host = ws.headers.get("host", "").split(":")[0]
    return (origin.scheme in ("http", "https") and origin.hostname in ("127.0.0.1", "localhost")
            and origin.port in (5173, 8000) and host in ("127.0.0.1", "localhost"))


async def terminal_socket(ws: WebSocket, manager) -> None:
    if not allowed_local_origin(ws) or os.name != "posix":
        await ws.close(code=1008)
        return
    project = manager.get(ws.path_params["project_id"])
    if project is None or not project.path.is_dir():
        await ws.close(code=1008)
        return
    await ws.accept()
    master, slave = pty.openpty()
    process = None
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            shell = "/bin/sh"
        process = subprocess.Popen([shell], cwd=str(project.path), stdin=slave, stdout=slave,
                                   stderr=slave, env={**os.environ, "TERM": "xterm-256color"},
                                   start_new_session=True, close_fds=True)
        os.close(slave)
        slave = -1

        async def output_loop():
            while process.poll() is None:
                ready, _, _ = await asyncio.to_thread(select.select, [master], [], [], 0.15)
                if ready:
                    try:
                        data = os.read(master, 8192)
                    except OSError:
                        break
                    if not data:
                        break
                    await ws.send_bytes(data)

        reader = asyncio.create_task(output_loop())
        try:
            while process.poll() is None:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    os.write(master, message["bytes"])
                elif message.get("text"):
                    event = json.loads(message["text"])
                    if event.get("type") == "input" and isinstance(event.get("data"), str):
                        os.write(master, event["data"].encode())
                    elif event.get("type") == "resize":
                        cols = max(20, min(300, int(event.get("cols", 80))))
                        rows = max(5, min(100, int(event.get("rows", 24))))
                        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except (OSError, ValueError, KeyError, RuntimeError):
            pass
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=2)
            except (ProcessLookupError, asyncio.TimeoutError):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.wait)
        os.close(master)
        if slave >= 0:
            os.close(slave)
