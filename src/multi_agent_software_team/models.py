from dataclasses import dataclass, field
from enum import Enum


class MissionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Mission:
    description: str
    status: MissionStatus = MissionStatus.PENDING
    requirements: list[str] = field(default_factory=list)
    code: str = ""
    tests: str = ""
    feedback: str = ""
    attempts: int = 0