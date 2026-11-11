"""Constrained, read-only folder picker for a local FastAPI installation."""
import os
from pathlib import Path


class FolderBrowserError(ValueError):
    pass


def allowed_root() -> Path:
    """Never expose arbitrary filesystem roots to the browser."""
    return Path(os.environ.get('STUDIO_BROWSE_ROOT', str(Path.home()))).expanduser().resolve(strict=True)


def browse_directory(path: str = '') -> dict:
    root = allowed_root()
    target = Path(path).expanduser() if path else root
    if not target.is_absolute():
        raise FolderBrowserError('An absolute directory path is required')
    # Disallow symbolic links anywhere in the traversed path, including the final folder.
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise FolderBrowserError('Directory is outside the allowed browse root') from exc
    current = root
    for part in relative.parts:
        if part.startswith('.') or part in ('..', ''):
            raise FolderBrowserError('Hidden and parent paths are not available')
        current = current / part
        if current.is_symlink():
            raise FolderBrowserError('Symbolic links are not available')
    try:
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_dir():
            raise FolderBrowserError('Not an allowed directory')
        folders = sorted((child for child in resolved.iterdir() if child.is_dir() and not child.is_symlink() and not child.name.startswith('.')), key=lambda p: p.name.casefold())
    except (OSError, PermissionError) as exc:
        raise FolderBrowserError('Directory cannot be accessed') from exc
    return {'root': str(root), 'path': str(resolved), 'parent': str(resolved.parent) if resolved != root else None,
            'directories': [{'name': p.name, 'path': str(p)} for p in folders[:200]], 'truncated': len(folders) > 200}
