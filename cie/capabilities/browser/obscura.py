"""
Obscura Stealth & Privacy Browser Profile Adapter (h4ckf0r0day/obscura).
Configures privacy-preserving browser profiles, user-agent hygiene,
fingerprint masking headers, and lightweight connection parameters.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BrowserProfileConfig(BaseModel):
    user_agent: str
    viewport_width: int = 1280
    viewport_height: int = 800
    headers: Dict[str, str] = Field(default_factory=dict)
    disable_webrtc: bool = True
    mask_canvas_noise: bool = True


class ObscuraAdapter:
    """
    Manages safe, stealth-conscious browser profiles and CDP connections.
    """

    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ]

    def create_stealth_profile(self, profile_name: str = "default") -> BrowserProfileConfig:
        ua = self.DEFAULT_USER_AGENTS[0]
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        return BrowserProfileConfig(
            user_agent=ua,
            viewport_width=1280,
            viewport_height=800,
            headers=headers,
            disable_webrtc=True,
            mask_canvas_noise=True,
        )
