"""Bounded, read-only inspection of a registered local project."""
from pathlib import Path

IGNORED = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', '.ruff_cache', '.studio-data', '.runner-workspaces', 'dist', 'build', '.next'}
MAX_ENTRIES = 250
MAX_BYTES = 256 * 1024


class ExplorerError(ValueError):
    pass


def _target(root: Path, relative: str) -> Path:
    base = root.resolve(strict=True)
    candidate = base / relative
    # Reject symlinks (including intermediate components), not just escapes.
    current = base
    for part in Path(relative).parts:
        if part in ('', '.'):
            continue
        if part == '..' or part == '/' or part.startswith('.') or part in IGNORED or part.startswith('\\'):
            raise ExplorerError('Invalid path')
        current = current / part
        if current.is_symlink():
            raise ExplorerError('Symbolic links cannot be opened')
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(base):
        raise ExplorerError('Path outside project')
    return resolved


def list_directory(root: Path, relative: str = '') -> dict:
    target = _target(root, relative)
    if not target.is_dir():
        raise ExplorerError('Not a directory')
    entries = []
    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))
        for child in children:
            if child.name in IGNORED or child.name.startswith('.') or child.is_symlink():
                continue
            if len(entries) >= MAX_ENTRIES:
                break
            if not (child.is_dir() or child.is_file()):
                continue
            entries.append({'name': child.name, 'path': child.relative_to(root.resolve()).as_posix(), 'kind': 'directory' if child.is_dir() else 'file'})
    except OSError as exc:
        raise ExplorerError('Cannot list directory') from exc
    return {'path': relative, 'entries': entries, 'truncated': len(children) > MAX_ENTRIES}


def read_file(root: Path, relative: str) -> dict:
    if not relative or any(part in IGNORED or part.startswith('.') for part in Path(relative).parts):
        raise ExplorerError('File is not available for preview')
    target = _target(root, relative)
    if not target.is_file():
        raise ExplorerError('Not a file')
    if target.stat().st_size > MAX_BYTES:
        raise ExplorerError('File exceeds 256 KiB preview limit')
    try:
        content = target.read_bytes()
    except OSError as exc:
        raise ExplorerError('Cannot read file') from exc
    if b'\x00' in content:
        raise ExplorerError('Binary files cannot be previewed')
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ExplorerError('Only UTF-8 text files can be previewed') from exc
    return {'path': relative, 'content': decoded, 'size': len(content)}
