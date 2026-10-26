"""
Task Storage, Lifecycle Management, and Isolation for CIE Plans.
Enforces size constraints, safe retention limits, and secret scrubbing.
"""

from collections import OrderedDict
import threading
from typing import Any, Dict, Optional

from cie.planning.schemas import TaskPlan
from cie.safety import redact_secrets


class TaskManager:
    """
    Thread-safe, bounded in-memory store for TaskPlans.
    Limits memory footprint to the last 100 tasks and scrubs stored traces.
    """

    def __init__(self, max_tasks: int = 100):
        self.max_tasks = max_tasks
        self._tasks: OrderedDict[str, TaskPlan] = OrderedDict()
        self._lock = threading.Lock()

    def store_task(self, plan: TaskPlan) -> None:
        """Stores or updates a task plan, pruning oldest if capacity exceeded."""
        with self._lock:
            # Redact secrets from execution trace and summary
            plan.final_summary = redact_secrets(plan.final_summary or "")
            for entry in plan.execution_trace:
                if "detail" in entry and isinstance(entry["detail"], str):
                    entry["detail"] = redact_secrets(entry["detail"])

            if plan.task_id in self._tasks:
                self._tasks.move_to_end(plan.task_id)
            self._tasks[plan.task_id] = plan

            # Evict oldest tasks if limit reached
            while len(self._tasks) > self.max_tasks:
                self._tasks.popitem(last=False)

    def get_task(self, task_id: str) -> Optional[TaskPlan]:
        """Retrieves task by ID if present."""
        with self._lock:
            plan = self._tasks.get(task_id)
            return plan.model_copy() if plan else None

    def clear(self) -> None:
        """Clears all stored tasks."""
        with self._lock:
            self._tasks.clear()
