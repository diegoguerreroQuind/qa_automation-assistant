"""
Execution state machine — valid transitions for ExecutionStatus.

Diagram:
                         ┌─────────────────────────────────────┐
                         │  re-extract allowed                 │
                         ▼                                     │
  pending ──► extracting ──► generating ──► complete (terminal)
                  ▲              │
                  │              ├──► partial  (terminal → re-generate)
                  │              │
                  │              └──► failed   (terminal → re-extract / re-generate)
                  │
                  └── failed (recovery: re-upload and re-extract)

Terminal rules:
  - complete / partial → only re-generation is allowed (fix a bad run)
  - failed             → full recovery: re-extract or re-generate

Raises InvalidStatusTransitionError (a ValueError subclass) on illegal moves,
so callers can let it bubble as HTTP 422 or log it as an unexpected task error.
"""
from backend.models.db import ExecutionStatus

# Map: current status → set of allowed next statuses
VALID_TRANSITIONS: dict[ExecutionStatus, frozenset] = {
    ExecutionStatus.pending: frozenset({
        ExecutionStatus.extracting,
    }),
    ExecutionStatus.extracting: frozenset({
        ExecutionStatus.extracting,   # re-extract is idempotent → allowed
        ExecutionStatus.generating,
    }),
    ExecutionStatus.generating: frozenset({
        ExecutionStatus.complete,
        ExecutionStatus.partial,
        ExecutionStatus.failed,
    }),
    ExecutionStatus.complete: frozenset({
        ExecutionStatus.generating,   # re-run generation (e.g. after manual edit)
    }),
    ExecutionStatus.partial: frozenset({
        ExecutionStatus.generating,   # re-run to fix failed endpoints
    }),
    ExecutionStatus.failed: frozenset({
        ExecutionStatus.extracting,   # full recovery: re-upload + re-extract
        ExecutionStatus.generating,   # partial recovery: re-try generation
    }),
}


class InvalidStatusTransitionError(ValueError):
    """Raised when an Execution is moved to a state that is not reachable from its current one."""

    def __init__(self, current: ExecutionStatus, target: ExecutionStatus) -> None:
        allowed = sorted(
            s.value for s in VALID_TRANSITIONS.get(current, frozenset())
        )
        super().__init__(
            f"Transición de estado inválida: '{current.value}' → '{target.value}'. "
            f"Transiciones permitidas desde '{current.value}': {allowed or ['ninguna (estado terminal)']}"
        )
        self.current = current
        self.target = target


def assert_valid_transition(
    current: "ExecutionStatus | str",
    target: ExecutionStatus,
) -> None:
    """
    Validates that moving an Execution from *current* to *target* is allowed.

    Args:
        current: The execution's present status (accepts raw string from DB).
        target:  The desired next status.

    Raises:
        InvalidStatusTransitionError: if the transition is not in VALID_TRANSITIONS.
    """
    if isinstance(current, str):
        try:
            current = ExecutionStatus(current)
        except ValueError:
            # Unknown status in DB — treat as non-blocking to avoid stuck executions
            return

    allowed = VALID_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStatusTransitionError(current, target)
