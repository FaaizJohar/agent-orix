"""
Agent S Multimodal GUI Interaction Adapter (simular-ai/Agent-S).
Provides hierarchical GUI action planning: decomposes high-level user tasks
into sub-goals, UI landmark grounding, and atomic coordinate actions.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UIElementBoundingBox(BaseModel):
    label: str
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    confidence: float = 1.0

    @property
    def center_point(self) -> tuple[int, int]:
        return ((self.x_min + self.x_max) // 2, (self.y_min + self.y_max) // 2)


class HierarchicalPlanStep(BaseModel):
    step_id: int
    sub_goal: str
    target_element: str
    action_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentSPlanner:
    """
    Hierarchical GUI interaction planner implementing the Agent S architecture.
    """

    def __init__(self):
        self.elements_cache: Dict[str, UIElementBoundingBox] = {}

    def register_element(self, element: UIElementBoundingBox):
        self.elements_cache[element.label.lower()] = element

    def resolve_element_coordinates(self, label: str) -> Optional[tuple[int, int]]:
        lbl = label.lower()
        if lbl in self.elements_cache:
            return self.elements_cache[lbl].center_point
        # Fallback partial match
        for k, v in self.elements_cache.items():
            if lbl in k:
                return v.center_point
        return None

    def plan_gui_task(self, goal: str) -> List[HierarchicalPlanStep]:
        """
        Decomposes a user task into hierarchical GUI steps.
        """
        # Deterministic decomposition for standard tasks
        steps = [
            HierarchicalPlanStep(
                step_id=1,
                sub_goal=f"Locate UI anchor for '{goal}'",
                target_element="active_window",
                action_type="focus_window",
            ),
            HierarchicalPlanStep(
                step_id=2,
                sub_goal=f"Execute interaction for '{goal}'",
                target_element="primary_target",
                action_type="click_or_type",
            ),
        ]
        return steps
