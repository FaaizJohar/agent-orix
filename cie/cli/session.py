"""
Session Continuity and Conversation Memory for Agent Orix.
Persists multi-turn conversations safely with bounded context and secret redaction.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from cie.safety import redact_secrets

logger = logging.getLogger("cie.cli.session")

DEFAULT_SESSION_DIR = Path.home() / ".cavrix" / "sessions"
MAX_HISTORY_ENTRIES = 50


class MessageTurn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionState(BaseModel):
    session_id: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    workspace: Optional[str] = None
    messages: List[MessageTurn] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionManager:
    """
    Manages persistent sessions on disk with safety bounds and encryption/redaction hygiene.
    """

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = session_dir or DEFAULT_SESSION_DIR
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create default session dir {self.session_dir}: {e}. Falling back to local .cavrix_sessions")
            self.session_dir = Path.cwd() / ".cavrix_sessions"
            self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return self.session_dir / f"{safe_id}.json"

    def create_session(
        self,
        session_id: Optional[str] = None,
        workspace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionState:
        sid = session_id or f"session_{int(time.time())}_{str(uuid.uuid4())[:6]}"
        state = SessionState(
            session_id=sid,
            created_at=time.time(),
            updated_at=time.time(),
            workspace=workspace or os.getcwd(),
            messages=[],
            metadata=metadata or {},
        )
        self.save_session(state)
        return state

    def load_session(self, session_id: str) -> Optional[SessionState]:
        path = self._get_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionState.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def save_session(self, state: SessionState) -> None:
        path = self._get_path(state.session_id)
        state.updated_at = time.time()
        # Bound history to MAX_HISTORY_ENTRIES to prevent unbounded file growth
        if len(state.messages) > MAX_HISTORY_ENTRIES:
            state.messages = state.messages[-MAX_HISTORY_ENTRIES:]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state.model_dump(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save session {state.session_id}: {e}")

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MessageTurn]:
        state = self.load_session(session_id)
        if not state:
            state = self.create_session(session_id=session_id)

        # Redact secrets from persisted message content
        safe_content = redact_secrets(content)
        turn = MessageTurn(
            role=role,
            content=safe_content,
            timestamp=time.time(),
            metadata=metadata or {},
        )
        state.messages.append(turn)
        self.save_session(state)
        return turn

    def get_history(self, session_id: str, limit: int = 20) -> List[MessageTurn]:
        state = self.load_session(session_id)
        if not state:
            return []
        return state.messages[-limit:]

    def clear_session(self, session_id: str) -> bool:
        path = self._get_path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
                return False
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        results = []
        if not self.session_dir.exists():
            return results
        for item in self.session_dir.glob("*.json"):
            try:
                with open(item, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "session_id": data.get("session_id", item.stem),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", 0),
                    "workspace": data.get("workspace", ""),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                continue
        results.sort(key=lambda x: x["updated_at"], reverse=True)
        return results
