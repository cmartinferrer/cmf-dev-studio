"""Bounded filename-only search, with no file contents exposed."""
from pathlib import Path
from .explorer import IGNORED, ExplorerError

MAX_VISITS = 5000
MAX_RESULTS = 100


def search_files(root: Path, query: str) -> dict:
    term = query.strip().casefold()
    if not term or len(term) > 120:
        raise ExplorerError('Search must contain between 1 and 120 characters')
    base = root.resolve(strict=True)
    found = []
    visited = 0
    truncated = False
    pending = [base]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name.casefold())
        except OSError:
            continue
        for child in children:
            visited += 1
            if visited > MAX_VISITS:
                truncated = True
                break
            if child.name.startswith('.') or child.name in IGNORED or child.is_symlink():
                continue
            if child.is_dir():
                pending.append(child)
            elif child.is_file() and term in child.name.casefold():
                found.append({'name': child.name, 'path': child.relative_to(base).as_posix(), 'kind': 'file'})
                if len(found) >= MAX_RESULTS:
                    truncated = True
                    break
        if truncated:
            break
    return {'query': query, 'entries': found, 'truncated': truncated}
