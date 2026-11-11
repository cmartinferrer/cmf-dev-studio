"""Conservative local IDE edits with optimistic concurrency and atomic replacement."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .explorer import ExplorerError, MAX_BYTES, _target


class EditConflict(ExplorerError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(root: Path, relative: str, *, allow_missing: bool = False) -> Path:
    if not relative or relative.startswith(('/', '\\')) or '\\' in relative:
        raise ExplorerError('Invalid file path')
    parts = relative.split('/')
    if any(p in ('', '.', '..') or p.startswith('.') for p in parts):
        raise ExplorerError('Hidden or unsafe path')
    base = root.resolve(strict=True)
    target = base
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise ExplorerError('Symbolic links are not supported')
    if not target.resolve(strict=False).is_relative_to(base):
        raise ExplorerError('Path outside project')
    if not allow_missing and not target.is_file():
        raise ExplorerError('File not found')
    return target


def read_editable(root: Path, relative: str) -> dict:
    target = safe_path(root, relative)
    if target.stat().st_size > MAX_BYTES:
        raise ExplorerError('File too large to edit')
    data = target.read_bytes()
    if b'\0' in data:
        raise ExplorerError('Binary files are not editable')
    try:
        content = data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ExplorerError('Only UTF-8 files can be edited') from exc
    return {'path': relative, 'content': content, 'sha256': digest(data), 'size': len(data)}


def write_editable(root: Path, relative: str, content: str, expected_sha256: str | None, *, create: bool = False) -> dict:
    data = content.encode('utf-8')
    if len(data) > MAX_BYTES or '\0' in content:
        raise ExplorerError('Invalid content or file too large (256 KiB limit)')
    target = safe_path(root, relative, allow_missing=True)
    if create:
        if target.exists():
            raise EditConflict('File already exists')
        if expected_sha256 is not None:
            raise ExplorerError('New files must not have a previous hash')
    else:
        if not expected_sha256 or not target.is_file():
            raise EditConflict('File missing or no revision supplied')
        if digest(target.read_bytes()) != expected_sha256:
            raise EditConflict('File changed on disk. Reload before saving.')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after creating parents; refuse any links in the path.
    safe_path(root, relative, allow_missing=True)
    fd, temporary = tempfile.mkstemp(prefix='.studio-write-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if create and target.exists():
            raise EditConflict('File already exists')
        if not create and (not target.is_file() or digest(target.read_bytes()) != expected_sha256):
            raise EditConflict('File changed on disk. Reload before saving.')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {'path': relative, 'content': content, 'sha256': digest(data), 'size': len(data)}


def delete_editable(root: Path, relative: str, expected_sha256: str) -> dict:
    target = safe_path(root, relative)
    if not expected_sha256 or digest(target.read_bytes()) != expected_sha256:
        raise EditConflict('File changed on disk. Reload before deleting.')
    target.unlink()
    return {'path': relative, 'deleted': True}
