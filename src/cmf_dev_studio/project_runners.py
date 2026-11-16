"""Native test commands, executed only after proposal approval by the caller."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class RunnerSpec:
    name: str
    command: tuple[str, ...]
    timeout: int = 300


class UnsupportedRunner(ValueError):
    pass


def select_runner(workspace: Path) -> RunnerSpec:
    paths = {p.relative_to(workspace).as_posix() for p in workspace.rglob('*') if p.is_file()}
    if 'pom.xml' in paths:
        if not any(p.startswith('src/test/') and p.endswith(('.java', '.kt')) for p in paths):
            raise UnsupportedRunner('Maven project has no test sources')
        return RunnerSpec('maven', ('mvn', '-B', 'test', '-DfailIfNoTests=true'))
    if {'build.gradle.kts', 'build.gradle'} & paths:
        if not any(p.startswith('src/test/') and p.endswith(('.java', '.kt')) for p in paths):
            raise UnsupportedRunner('Gradle project has no test sources')
        return RunnerSpec('gradle', ('gradle', 'test', '--console=plain', '--no-daemon'))
    if any(p.endswith('.py') for p in paths):
        command = ('uv', 'run', '--with', 'pytest', 'pytest', '-q') if 'pyproject.toml' in paths else (sys.executable, '-m', 'pytest', '-q')
        return RunnerSpec('pytest', command)
    raise UnsupportedRunner('No supported test runner (Python/pytest, Java/Maven or Java/Kotlin/Gradle)')


def execute_runner(workspace: Path, spec: RunnerSpec) -> tuple[bool, str]:
    # A disposable copy protects against ordinary build artifacts, not hostile code.
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'JAVA_HOME', 'GRADLE_USER_HOME', 'SYSTEMROOT', 'TMPDIR', 'XDG_CACHE_HOME'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        with TemporaryDirectory(prefix='cmf-test-') as directory:
            root = Path(directory) / 'project'
            shutil.copytree(workspace, root)
            with subprocess.Popen(spec.command, cwd=root, env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, errors='replace',
                                  stdin=subprocess.DEVNULL, start_new_session=True) as process:
                try:
                    output, _ = process.communicate(timeout=spec.timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
                    return False, f'Runner: {spec.name} (infrastructure_error) timed out after {spec.timeout} seconds'
                code = process.returncode
        classification = 'infrastructure_error' if code in (125, 126, 127) or (spec.name == 'pytest' and code in (3, 4)) else 'test_result'
        return code == 0, f'Runner: {spec.name} (exit {code}; {classification})\n{output[-16000:]}'
    except OSError as exc:
        return False, f'Runner: {spec.name} (infrastructure_error): {exc}'
