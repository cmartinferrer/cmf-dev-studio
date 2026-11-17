"""Local interactive PTY, available only to an explicitly connected browser."""

import asyncio
import fcntl
import json
import os
import pty
import select
import shlex
import signal
import struct
import subprocess
import termios
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from fastapi import WebSocket

from cmf_dev_studio.projects.editor import safe_path
from cmf_dev_studio.projects.jdk_environment import environment_info as jdk_info
from cmf_dev_studio.projects.models import Project
from cmf_dev_studio.projects.python_environment import environment_info


def allowed_local_origin(ws: WebSocket) -> bool:
    origin = urlparse(ws.headers.get("origin", ""))
    host = ws.headers.get("host", "").split(":")[0]
    return (
        origin.scheme in ("http", "https")
        and origin.hostname in ("127.0.0.1", "localhost")
        and origin.port in (5173, 8000)
        and host in ("127.0.0.1", "localhost")
    )


def terminal_environment(project: Project) -> dict[str, str]:
    """Prepare a shell environment without changing the backend process."""
    env = {**os.environ, "TERM": "xterm-256color"}
    previous = env.pop("VIRTUAL_ENV", None)
    env.pop("VIRTUAL_ENV_PROMPT", None)
    env.pop("PYTHONHOME", None)
    paths = env.get("PATH", os.defpath).split(os.pathsep)
    if previous:
        paths = [path for path in paths if path != str(Path(previous) / "bin")]
    env["PATH"] = os.pathsep.join(paths)
    jdk = jdk_info(project)
    if jdk["supported"]:
        if current := jdk["current"]:
            home = Path(current["path"])
            bin_dir = str(home / "bin")
            env["JAVA_HOME"] = str(home)
            env["PATH"] = os.pathsep.join(
                [bin_dir, *(path for path in paths if path != bin_dir)]
            )
        return env
    info = environment_info(project)
    if not info["supported"] or not info["available"]:
        return env

    interpreter = Path(info["path"])
    bin_dir = interpreter.parent
    env["PATH"] = os.pathsep.join(
        [str(bin_dir), *(path for path in paths if path != str(bin_dir))]
    )
    if (bin_dir.parent / "pyvenv.cfg").is_file():
        env["VIRTUAL_ENV"] = str(bin_dir.parent)
    return env


def shell_startup_command(
    shell: str, env: dict[str, str], project: Project, startup_dir: Path
) -> list[str]:
    """Load user startup files, then restore the selected project environment."""
    shell_name = Path(shell).name
    if shell_name not in ("bash", "zsh"):
        return [shell]

    if project.language.value in ("java", "kotlin"):
        current = jdk_info(project)["current"]
        if not current:
            return [shell]
        home = current["path"]
        bin_dir = str(Path(home) / "bin")
        activation = f"export JAVA_HOME={shlex.quote(home)}\n"
    else:
        info = environment_info(project)
        if not info["supported"] or not info["available"]:
            return [shell]
        bin_dir = str(Path(info["path"]).parent)
        activation = "unset PYTHONHOME VIRTUAL_ENV_PROMPT\n"
        if virtual_env := env.get("VIRTUAL_ENV"):
            activation += f"export VIRTUAL_ENV={shlex.quote(virtual_env)}\n"
        else:
            activation += "unset VIRTUAL_ENV\n"
    activation += f'export PATH={shlex.quote(bin_dir)}:"$PATH"\n'
    activation += "hash -r\n"

    if shell_name == "bash":
        rc = startup_dir / "bashrc"
        rc.write_text(
            'if [ -r "$HOME/.bashrc" ]; then . "$HOME/.bashrc"; fi\n' + activation
        )
        return [shell, "--rcfile", str(rc), "-i"]

    # Zsh reads .zshenv before .zshrc. Preserve the original ZDOTDIR,
    # including changes made by the user's .zshenv, for the real .zshrc.
    original = env.get("ZDOTDIR", env.get("HOME", str(Path.home())))
    (startup_dir / ".zshenv").write_text(
        f"export ZDOTDIR={shlex.quote(original)}\n"
        'if [ -r "$ZDOTDIR/.zshenv" ]; then . "$ZDOTDIR/.zshenv"; fi\n'
        '_cmf_user_zdotdir="$ZDOTDIR"\n'
        f"export ZDOTDIR={shlex.quote(str(startup_dir))}\n"
    )
    (startup_dir / ".zshrc").write_text(
        'export ZDOTDIR="$_cmf_user_zdotdir"\n'
        "unset _cmf_user_zdotdir\n"
        'if [ -r "$ZDOTDIR/.zshrc" ]; then . "$ZDOTDIR/.zshrc"; fi\n' + activation
    )
    env["ZDOTDIR"] = str(startup_dir)
    return [shell, "-i"]


def python_run_command(project: Project, path: str) -> list[str]:
    """Resolve a saved Python file and its configured interpreter without a shell."""
    target = safe_path(project.path, path)
    if target.suffix.lower() != ".py":
        raise ValueError("Select a Python file to run")
    info = environment_info(project)
    if not info["supported"] or not info["available"]:
        raise ValueError("Set up Python in the status bar before running this file.")
    return [info["path"], "-u", str(target)]


async def terminal_socket(ws: WebSocket, manager) -> None:
    if not allowed_local_origin(ws) or os.name != "posix":
        await ws.close(code=1008)
        return
    project = manager.get(ws.path_params["project_id"])
    if project is None or not project.path.is_dir():
        await ws.close(code=1008)
        return
    await ws.accept()
    run_path = ws.query_params.get("run")
    command = None
    if run_path is not None:
        try:
            command = python_run_command(project, run_path)
        except (ValueError, OSError) as exc:
            await ws.send_text(f"\r\n{exc}\r\n")
            await ws.close()
            return
    master, slave = pty.openpty()
    process = None
    startup = None
    try:
        shell = os.environ.get("SHELL", "/bin/sh")
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            shell = "/bin/sh"
        env = terminal_environment(project)
        if command is None:
            startup = TemporaryDirectory(prefix="cmf-shell-")
            args = shell_startup_command(shell, env, project, Path(startup.name))
        else:
            args = command
        process = subprocess.Popen(  # noqa: ASYNC220
            args,
            cwd=str(project.path),
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave)
        slave = -1
        if command is not None:
            await ws.send_text(f"Running Python file: {run_path!r}\r\n\r\n")

        async def output_loop():
            while True:
                ready, _, _ = await asyncio.to_thread(
                    select.select, [master], [], [], 0.15
                )
                if not ready and process.poll() is not None:
                    break
                if ready:
                    try:
                        data = os.read(master, 8192)
                    except OSError:
                        break
                    if not data:
                        break
                    await ws.send_bytes(data)
            while process.poll() is None:
                await asyncio.sleep(0.05)

        async def receive_loop():
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes"):
                    os.write(master, message["bytes"])
                elif message.get("text"):
                    event = json.loads(message["text"])
                    if event.get("type") == "input" and isinstance(
                        event.get("data"), str
                    ):
                        os.write(master, event["data"].encode())
                    elif event.get("type") == "resize":
                        cols = max(20, min(300, int(event.get("cols", 80))))
                        rows = max(5, min(100, int(event.get("rows", 24))))
                        fcntl.ioctl(
                            master,
                            termios.TIOCSWINSZ,
                            struct.pack("HHHH", rows, cols, 0, 0),
                        )

        reader = asyncio.create_task(output_loop())
        receiver = asyncio.create_task(receive_loop())
        try:
            done, _ = await asyncio.wait(
                (reader, receiver), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
            if reader in done and receiver not in done:
                if command is not None and process.poll() is not None:
                    await ws.send_text(
                        f"\r\nProcess exited with code {process.returncode}\r\n"
                    )
                await ws.close()
        except (OSError, ValueError, KeyError, RuntimeError):
            pass
        finally:
            for task in (reader, receiver):
                task.cancel()
            await asyncio.gather(reader, receiver, return_exceptions=True)
    except OSError as exc:
        await ws.send_text(f"\r\nCould not start terminal: {exc}\r\n")
        await ws.close()
    finally:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=2)
            except (ProcessLookupError, asyncio.TimeoutError):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await asyncio.to_thread(process.wait)
        if startup is not None:
            startup.cleanup()
        os.close(master)
        if slave >= 0:
            os.close(slave)
