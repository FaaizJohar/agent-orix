"""
OpenHands Agent EventStream Architecture Adapter (All-Hands-AI/OpenHands).
Implements the event stream pattern: Action -> Observation loop,
state tracking, and micro-agent lifecycle control.
"""

from enum import Enum
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentState(str, Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OpenHandsAction(BaseModel):
    id: str
    action_type: str
    payload: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)


class OpenHandsObservation(BaseModel):
    action_id: str
    observation_type: str
    content: Any
    success: bool = True
    timestamp: float = Field(default_factory=time.time)


class OpenHandsAgentSession:
    """
    Manages an OpenHands-compatible EventStream and Agent Loop.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state: AgentState = AgentState.INIT
        self.events: List[Dict[str, Any]] = []

    def start(self):
        self.state = AgentState.RUNNING

    def add_action(self, action: OpenHandsAction):
        self.events.append({"type": "action", "data": action.model_dump()})

    def add_observation(self, observation: OpenHandsObservation):
        self.events.append({"type": "observation", "data": observation.model_dump()})

    def pause_for_approval(self):
        self.state = AgentState.AWAITING_APPROVAL

    def complete(self):
        self.state = AgentState.COMPLETED

    def fail(self):
        self.state = AgentState.FAILED

    def get_event_stream(self) -> List[Dict[str, Any]]:
        return list(self.events)
