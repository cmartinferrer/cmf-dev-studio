"""Conservative local IDE edits with optimistic concurrency and atomic replacement."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .explorer import ExplorerError, MAX_BYTES, IGNORED, _target


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


def entry_path(root: Path, relative: str) -> Path:
    """Resolve a visible file or directory without following symbolic links."""
    if any(part in IGNORED for part in relative.split('/')):
        raise ExplorerError('Protected path')
    target = safe_path(root, relative, allow_missing=True)
    if not (target.is_file() or target.is_dir()):
        raise ExplorerError('Entry not found')
    return target


def rename_entry(root: Path, relative: str, name: str) -> dict:
    target = entry_path(root, relative)
    if not name or name != name.strip() or name.startswith('.') or name in IGNORED or any(c in name for c in ('/', '\\', '\x00')):
        raise ExplorerError('Invalid entry name')
    destination = target.with_name(name)
    if destination == target:
        return {'path': relative}
    if destination.exists() or destination.is_symlink():
        raise EditConflict('Destination already exists')
    target.rename(destination)
    return {'path': destination.relative_to(root.resolve()).as_posix()}


def delete_entry(root: Path, relative: str) -> dict:
    target = entry_path(root, relative)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {'path': relative, 'deleted': True}


def directory_path(root: Path, relative: str) -> Path:
    target = root.resolve(strict=True) if relative == '' else entry_path(root, relative)
    if not target.is_dir():
        raise ExplorerError('Destination must be a directory')
    return target


def create_directory(root: Path, relative: str) -> dict:
    if any(part in IGNORED for part in relative.split('/')) or '\x00' in relative:
        raise ExplorerError('Protected or invalid path')
    target = safe_path(root, relative, allow_missing=True)
    if not target.parent.is_dir():
        raise ExplorerError('Parent directory not found')
    try:
        target.mkdir()
    except FileExistsError as exc:
        raise EditConflict('Destination already exists') from exc
    return {'path': relative}


def move_entry(root: Path, relative: str, parent: str) -> dict:
    source = entry_path(root, relative)
    folder = directory_path(root, parent)
    destination = folder / source.name
    if destination == source:
        return {'path': relative}
    if source.is_dir() and (folder == source or source in folder.parents):
        raise ExplorerError('Cannot move a folder into itself')
    if destination.exists() or destination.is_symlink():
        raise EditConflict('Destination already exists')
    source.rename(destination)
    return {'path': destination.relative_to(root.resolve()).as_posix()}


def batch_entries(root: Path, paths: list[str], parent: str | None, protect=lambda target: None) -> dict:
    """Preflight the entire selection; report completed operations on I/O failure."""
    unique = sorted(set(paths))
    sources = [(p, entry_path(root, p)) for p in unique]
    sources = [(p, s) for p, s in sources if not any(p.startswith(q + '/') for q in unique)]
    folder = directory_path(root, parent) if parent is not None else None
    destinations = set()
    for p, source in sources:
        protect(source)
        if folder is not None:
            destination = folder / source.name
            protect(destination)
            if folder == source or source in folder.parents:
                raise ExplorerError('Cannot move a folder into itself')
            if destination in destinations or (destination != source and (destination.exists() or destination.is_symlink())):
                raise EditConflict('Destination already exists')
            destinations.add(destination)
    completed = []
    for p, source in sources:
        try:
            result = delete_entry(root, p) if parent is None else move_entry(root, p, parent)
            completed.append({'source': p, 'path': result['path']})
        except (OSError, ExplorerError, ValueError) as exc:
            return {'completed': completed, 'error': str(exc)}
    return {'completed': completed, 'error': None}


def copy_entries(root: Path, paths: list[str], parent: str, protect=lambda target: None) -> dict:
    """Copy saved resources without overwriting or following symbolic links."""
    unique = sorted(set(paths))
    sources = [(p, entry_path(root, p)) for p in unique]
    sources = [(p, s) for p, s in sources if not any(p.startswith(q + '/') for q in unique)]
    folder = directory_path(root, parent)
    planned = []
    destinations = set()
    for p, source in sources:
        protect(source)
        if folder == source or source in folder.parents:
            raise ExplorerError('Cannot copy a folder into itself')
        destination = folder / source.name
        if destination.exists() or destination.is_symlink() or destination in destinations:
            stem, suffix = (source.stem, source.suffix) if source.is_file() else (source.name, '')
            n = 1
            while destination.exists() or destination.is_symlink() or destination in destinations:
                destination = folder / f'{stem} ({n}){suffix}'
                n += 1
        protect(destination)
        if destination in destinations or destination.exists() or destination.is_symlink():
            raise EditConflict('Destination already exists')
        destinations.add(destination)
        if source.is_dir():
            for child in source.rglob('*'):
                protect(child)
                if child.is_symlink() or not (child.is_file() or child.is_dir()):
                    raise ExplorerError('Unsupported entry inside folder')
                if child.name.startswith('.') or child.name in IGNORED:
                    raise ExplorerError('Protected entry inside folder')
        planned.append((p, source, destination))
    completed = []
    for p, source, destination in planned:
        try:
            if source.is_dir():
                shutil.copytree(source, destination, symlinks=True)
            else:
                with source.open('rb') as src, destination.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
            completed.append({'source': p, 'path': destination.relative_to(root.resolve()).as_posix()})
        except (OSError, ExplorerError, ValueError) as exc:
            return {'completed': completed, 'error': str(exc)}
    return {'completed': completed, 'error': None}
