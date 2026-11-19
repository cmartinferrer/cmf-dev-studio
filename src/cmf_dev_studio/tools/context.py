"""Request-scoped tool state."""

from collections.abc import Callable
from dataclasses import dataclass, field

from cmf_dev_studio.tools.repository.snapshot import RepositorySnapshot

MAX_READ_BYTES = 48000


@dataclass
class ToolContext:
    snapshot: RepositorySnapshot
    approved: dict[str, str]
    allowed: bool
    activity: Callable[[str, str], None]
    spent: int = field(init=False)
    cache: dict[tuple[str, str], str] = field(default_factory=dict)

    def __post_init__(self):
        self.approved = dict(self.approved)
        self.spent = sum(len(value.encode()) for value in self.approved.values())
