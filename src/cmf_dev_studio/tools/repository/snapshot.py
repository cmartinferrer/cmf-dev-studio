"""Read-only repository snapshot and existing exclusion policy."""

from pathlib import PurePosixPath
from types import MappingProxyType

from cmf_dev_studio.projects.intelligence import (
    _eligible,
    _sensitive_name,
    credential_findings,
)


class RepositorySnapshot:
    def __init__(self, files):
        self.files = MappingProxyType(dict(files))

    def eligible(self, path):
        p = PurePosixPath(path)
        return (
            path in self.files
            and (
                _eligible(p)
                or (
                    p.suffix.lower()
                    in {
                        ".xml",
                        ".yaml",
                        ".yml",
                        ".json",
                        ".sql",
                        ".html",
                        ".css",
                        ".properties",
                        ".toml",
                        ".kts",
                        ".sh",
                    }
                    and not _sensitive_name(p.name)
                )
            )
            and not any(
                _sensitive_name(x)
                or x.startswith(".")
                or x in {"target", "build", "dist", "venv"}
                for x in p.parts[:-1]
            )
        )

    def text(self, path):
        if not self.eligible(path):
            return None
        raw = self.files[path]
        if len(raw) > 24000 or b"\x00" in raw:
            return None
        try:
            value = raw.decode("utf-8")
        except UnicodeError:
            return None
        return None if credential_findings(value) else value
