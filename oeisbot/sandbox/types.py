from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..config import DEFAULT_BUDGETS, MiB


class Status(str, Enum):
    EXITED = "exited"              # ran to completion on its own; check exit_code
    TIMEOUT = "timeout"            # wall clock
    CPU_CAP = "cpu_cap"
    MEMORY_CAP = "memory_cap"      # job commit cap hit, or system RAM ran low
    DISK_CAP = "disk_cap"
    OUTPUT_CAP = "output_cap"
    STOPPED = "stopped"            # the caller asked for a stop (enough terms, wrong term, over prediction...)
    LAUNCH_ERROR = "launch_error"


@dataclass
class Limits:
    wall_s: float
    mem_bytes: int = DEFAULT_BUDGETS.mem_bytes
    cpu_s: float | None = None
    disk_bytes: int = DEFAULT_BUDGETS.disk_bytes
    output_bytes: int = 256 * MiB
    reserve_phys_bytes: int = DEFAULT_BUDGETS.reserve_phys_bytes
    reserve_disk_bytes: int = DEFAULT_BUDGETS.reserve_disk_bytes
    isolate: bool = True           # no network, filesystem allow-list
    low_priority: bool = True      # keep the desktop responsive


@dataclass
class RunResult:
    status: Status
    exit_code: int | None
    wall_s: float
    cpu_s: float
    peak_mem_bytes: int
    mem_cap_bytes: int
    stop_reason: str | None = None
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is Status.EXITED and self.exit_code == 0


# on_line(line, seconds_since_start) and on_tick(seconds_since_start) return a stop reason, or None to continue.
# The sandbox serializes calls to both, so callers need no locking of their own.
LineCallback = Callable[[str, float], "str | None"]
TickCallback = Callable[[float], "str | None"]
