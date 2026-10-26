"""
Frigate NVR Video Analytics & Event Adapter (blakeblackshear/frigate).
Safe, strictly opt-in integration for receiving external NVR camera events,
parsing object detection webhooks, and analyzing snapshot alerts.
Disabled by default to prevent unauthorized camera access and excessive resource usage.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FrigateEvent(BaseModel):
    id: str
    camera: str
    label: str  # e.g., 'person', 'car', 'dog'
    score: float
    start_time: float
    end_time: Optional[float] = None
    has_snapshot: bool = False
    has_clip: bool = False


class FrigateAdapter:
    """
    Passive, secure NVR event receiver.
    Requires explicit opt-in enablement in configuration.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.events_cache: List[FrigateEvent] = []

    def handle_webhook_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "success": False,
                "error": "Frigate NVR integration is currently disabled by security policy.",
                "enabled": False,
            }

        event = FrigateEvent(
            id=str(payload.get("id", "evt_unknown")),
            camera=str(payload.get("camera", "camera_1")),
            label=str(payload.get("label", "unknown")),
            score=float(payload.get("score", 0.0)),
            start_time=float(payload.get("start_time", 0.0)),
            has_snapshot=bool(payload.get("has_snapshot", False)),
        )
        self.events_cache.append(event)
        return {"success": True, "event_id": event.id, "label": event.label}

    def list_recent_events(self, camera: Optional[str] = None) -> List[FrigateEvent]:
        if not self.enabled:
            return []
        if camera:
            return [e for e in self.events_cache if e.camera == camera]
        return list(self.events_cache)
