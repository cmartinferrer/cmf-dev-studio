"""Conservative Docker test adapters selected by build manifest.

Execution has no network access and never mounts the original repository.
Dependencies must be available in the prebuilt image/cache. Unsupported projects
are never reported as tested.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunnerSpec:
    name: str
    image: str
    command: tuple[str, ...]
    timeout: int = 180


class UnsupportedRunner(ValueError):
    pass


def select_runner(workspace: Path) -> RunnerSpec:
    paths = {p.relative_to(workspace).as_posix() for p in workspace.rglob('*') if p.is_file()}
    if 'pom.xml' in paths:
        if not any(p.startswith('src/test/') and p.endswith(('.java', '.kt')) for p in paths):
            raise UnsupportedRunner('Maven project has no test sources; generate tests before verification')
        return RunnerSpec('maven', 'multi-agent-studio-maven-tests:4', ('mvn', '-o', '-B', 'test', '-DfailIfNoTests=true', '-Dstyle.color=never'), 240)
    if 'build.gradle.kts' in paths or 'build.gradle' in paths:
        if not any(p.startswith('src/test/') and p.endswith(('.java', '.kt')) for p in paths):
            raise UnsupportedRunner('Gradle project has no test sources; generate tests before verification')
        # Never execute a repository-provided gradlew shell script.
        return RunnerSpec('gradle', 'multi-agent-studio-gradle-tests:4', ('gradle', '--offline', '--no-daemon', 'test', '--console=plain'), 240)
    if any(p.endswith('.py') for p in paths):
        return RunnerSpec('pytest', 'multi-agent-studio-project-tests:2.2', ('python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider'), 120)
    raise UnsupportedRunner('No supported test runner (Python/pytest, Java/Maven or Java/Kotlin/Gradle)')


def execute_runner(workspace: Path, spec: RunnerSpec) -> tuple[bool, str]:
    command = [
        'docker', 'run', '--rm',
        '--network', 'none',
        '--read-only',
        '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges',
        '--pids-limit', '128',
        '--memory', '1g',
        '--cpus', '1',
        '--user', '10001:10001',
        '--tmpfs', '/tmp:rw,nosuid,mode=1777,size=128m',
        '--mount',
        f'type=bind,src={workspace.resolve()},dst=/workspace,readonly',
        '-w', '/tmp',
        spec.image,
        'sh', '-c',
        'workdir=$(mktemp -d /tmp/studio-XXXXXX) || exit 125; '
        'cp -R /workspace/. "$workdir/" || exit 125; '
        'cd "$workdir" || exit 125; '
        'exec "$@"',
        'studio-runner',
        *spec.command,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=spec.timeout,
            check=False,
        )

        output = (result.stdout + '\n' + result.stderr)[-16000:]

        classification = (
            'infrastructure_error'
            if result.returncode in (125, 126, 127)
            or (spec.name == 'pytest' and result.returncode in (3, 4))
            or any(marker in output for marker in ('Could not resolve dependencies for project', 'No cached version', 'Cannot access central', 'Could not resolve all files for configuration'))
            else 'test_result'
        )

        return (
            result.returncode == 0,
            f'Runner: {spec.name} '
            f'(exit {result.returncode}; {classification})\n{output}',
        )

    except FileNotFoundError:
        return False, 'Docker is not installed or not on PATH'

    except subprocess.TimeoutExpired:
        return False, f'{spec.name} timed out after {spec.timeout} seconds'
