"""
Safe OS-level desktop automation and window management for Windows.
Utilizes pure ctypes and Windows user32 APIs with strict security barriers.
Handles headless and detached sessions gracefully with diagnostic fallback boundaries.
"""

import asyncio
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil
from PIL import Image, ImageDraw, ImageFont

from cie.desktop.schemas import (
    DesktopClickInput,
    DesktopClickOutput,
    DesktopKeypressInput,
    DesktopKeypressOutput,
    DesktopListWindowsInput,
    DesktopListWindowsOutput,
    DesktopScreenshotInput,
    DesktopScreenshotOutput,
    DesktopStateOutput,
    DesktopTypeTextInput,
    DesktopTypeTextOutput,
    DesktopWaitForStateInput,
    DesktopWaitForStateOutput,
    DesktopWindowInfo,
)
from cie.desktop.security import DesktopSecurityError, DesktopSecurityManager
from cie.safety import redact_secrets

logger = logging.getLogger("cie.desktop.manager")

# Windows Virtual Key Codes Mapping
VK_CODES: Dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
}

# Mouse Event Flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class DesktopManager:
    """
    Manages safe local desktop interactions on Windows with application allowlisting
    and action-bound cryptographic approval enforcement.
    """

    def __init__(self, screenshot_dir: Optional[str] = None):
        self._user32 = ctypes.windll.user32
        self.screenshot_dir = Path(screenshot_dir or r"E:\cavrix_cie\.storage\desktop_screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def get_screen_resolution(self) -> Dict[str, int]:
        """Queries primary monitor resolution via GetSystemMetrics."""
        w = self._user32.GetSystemMetrics(0)
        h = self._user32.GetSystemMetrics(1)
        return {
            "width": max(800, int(w) if w > 0 else 1920),
            "height": max(600, int(h) if h > 0 else 1080),
        }

    def _get_window_info(self, hwnd: int) -> Optional[DesktopWindowInfo]:
        """Constructs a DesktopWindowInfo model for a given window handle."""
        if not hwnd or not self._user32.IsWindow(hwnd):
            return None

        # 1. Window Title
        length = self._user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

        # 2. Process Info
        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = "unknown"
        if pid.value > 0:
            try:
                process_name = psutil.Process(pid.value).name().lower()
            except Exception:
                process_name = "unknown"

        # 3. Visibility and Minimized State
        is_visible = bool(self._user32.IsWindowVisible(hwnd))
        is_minimized = bool(self._user32.IsIconic(hwnd))

        # 4. Rect Bounds
        rect = RECT()
        self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
        bounds = {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": max(0, int(rect.right - rect.left)),
            "height": max(0, int(rect.bottom - rect.top)),
        }

        # 5. Security Validation
        is_permitted, _ = DesktopSecurityManager.is_window_permitted(title, process_name)

        return DesktopWindowInfo(
            hwnd=int(hwnd),
            title=redact_secrets(title or "Untitled"),
            process_name=process_name,
            pid=int(pid.value),
            is_visible=is_visible,
            is_minimized=is_minimized,
            is_permitted=is_permitted,
            bounds=bounds,
        )

    def get_state(self) -> DesktopStateOutput:
        """
        Retrieves current screen resolution, active foreground window,
        and allowlist security compliance.
        """
        res = self.get_screen_resolution()
        fg_hwnd = self._user32.GetForegroundWindow()
        active_win = self._get_window_info(fg_hwnd) if fg_hwnd else None

        # Check if desktop DC is interactive
        is_interactive = (fg_hwnd != 0)
        diagnostic = None
        if not is_interactive:
            diagnostic = "OS desktop session is non-interactive or running in background service mode."

        is_permitted = active_win.is_permitted if active_win else True

        # Count visible windows
        visible_count = len(self.list_windows(include_prohibited=False).windows)

        return DesktopStateOutput(
            screen_resolution=res,
            active_window=active_win,
            is_permitted=is_permitted,
            total_visible_windows=visible_count,
            os_interactive_session=is_interactive,
            diagnostic_note=diagnostic,
        )

    def list_windows(self, include_prohibited: bool = False) -> DesktopListWindowsOutput:
        """
        Enumerates all visible top-level windows, annotating whether they are
        permitted by the application security allowlist.
        """
        windows: List[DesktopWindowInfo] = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_cb(hwnd, lparam):
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    info = self._get_window_info(hwnd)
                    if info:
                        if info.is_permitted or include_prohibited:
                            windows.append(info)
            return True

        self._user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        permitted_count = sum(1 for w in windows if w.is_permitted)

        return DesktopListWindowsOutput(
            windows=windows,
            total_windows=len(windows),
            permitted_windows=permitted_count,
        )

    def take_screenshot(
        self,
        target_window_only: bool = False,
        filename_prefix: str = "desktop_snap",
    ) -> DesktopScreenshotOutput:
        """
        Captures the screen or active window rectangle.
        If running in a non-interactive/headless Windows session where BitBlt fails,
        safely generates a diagnostic visual frame rather than crashing.
        """
        res = self.get_screen_resolution()
        width = res["width"]
        height = res["height"]
        target_win = None
        is_synthetic = False

        if target_window_only:
            state = self.get_state()
            if state.active_window and state.active_window.bounds["width"] > 0:
                b = state.active_window.bounds
                width = b["width"]
                height = b["height"]
                target_win = state.active_window.title

        img = None

        # 1. Attempt GDI capture via mss
        try:
            import mss
            with mss.MSS() as sct:
                mon = sct.monitors[1]
                sct_img = sct.grab(mon)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                if target_window_only and state.active_window:
                    b = state.active_window.bounds
                    img = img.crop((b["left"], b["top"], b["right"], b["bottom"]))
        except Exception as e:
            logger.debug(f"Direct BitBlt screen capture unavailable ({e}); generating safe diagnostic visual frame.")

        # 2. Safe Fallback Boundary for headless/service execution
        if img is None:
            is_synthetic = True
            img = Image.new("RGB", (width, height), color=(24, 24, 30))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(60, 60, 75), width=2)
            draw.text((20, 20), "CAVRIXCODE DESKTOP DIAGNOSTIC FRAME", fill=(200, 200, 220))
            draw.text((20, 45), f"Resolution: {width}x{height}", fill=(150, 150, 170))
            draw.text((20, 70), f"Active Window: {target_win or 'None (Headless/Detached)'}", fill=(150, 150, 170))
            draw.text((20, 95), "Status: OS Display DC detached. Operating in safe diagnostic mode.", fill=(100, 180, 255))

        # 3. Save PNG artifact
        timestamp = int(time.time() * 1000)
        safe_prefix = re.sub(r"[^a-zA-Z0-9_\-]", "", filename_prefix)[:30] or "snap"
        filename = f"{safe_prefix}_{timestamp}.png"
        file_path = str(self.screenshot_dir / filename)
        img.save(file_path, "PNG")

        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        return DesktopScreenshotOutput(
            file_path=file_path,
            width=img.width,
            height=img.height,
            size_bytes=size_bytes,
            window_captured=target_win,
            is_synthetic=is_synthetic,
        )

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        double_click: bool = False,
        consequential: bool = False,
        approval_token: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> DesktopClickOutput:
        """
        Moves cursor and simulates a mouse click at (x, y).
        Requires action-bound cryptographic approval for consequential actions.
        """
        btn_lower = (button or "left").lower()
        if btn_lower not in ("left", "right", "middle"):
            return DesktopClickOutput(
                action="click", x=x, y=y, button=btn_lower, success=False, error=f"Invalid mouse button '{button}'."
            )

        # 1. Verify active window security
        fg_hwnd = self._user32.GetForegroundWindow()
        active_win = self._get_window_info(fg_hwnd)
        target_desc = f"{active_win.title} ({active_win.process_name})" if active_win else f"Coord ({x}, {y})"

        if active_win and not active_win.is_permitted:
            return DesktopClickOutput(
                action="click",
                x=x,
                y=y,
                button=btn_lower,
                success=False,
                error=f"Desktop security violation: Interaction with prohibited window '{active_win.title}' is blocked.",
            )

        # 2. Consequential Action & Approval Token Verification
        is_consequential, reason = DesktopSecurityManager.is_consequential_desktop_action(
            action_type="click",
            window_title=active_win.title if active_win else None,
            explicit_flag=consequential,
        )

        if is_consequential:
            action_args = {
                "button": btn_lower,
                "consequential": consequential,
                "double_click": double_click,
                "x": x,
                "y": y,
            }
            valid, token_reason = DesktopSecurityManager.verify_action_token(
                tool_name="desktop_click",
                arguments=action_args,
                provided_token=approval_token,
                session_id=session_id,
            )
            if not valid:
                return DesktopClickOutput(
                    action="click",
                    x=x,
                    y=y,
                    button=btn_lower,
                    success=False,
                    error=token_reason,
                )

        # 3. Simulate Mouse Click via user32
        res = self.get_screen_resolution()
        if x > res["width"] or y > res["height"]:
            return DesktopClickOutput(
                action="click",
                x=x,
                y=y,
                button=btn_lower,
                success=False,
                error=f"Coordinates ({x}, {y}) exceed screen resolution {res['width']}x{res['height']}.",
            )

        try:
            self._user32.SetCursorPos(int(x), int(y))
            time.sleep(0.05)

            if btn_lower == "left":
                down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP
            elif btn_lower == "right":
                down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
            else:
                down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP

            self._user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            self._user32.mouse_event(up_flag, 0, 0, 0, 0)

            if double_click:
                time.sleep(0.08)
                self._user32.mouse_event(down_flag, 0, 0, 0, 0)
                time.sleep(0.02)
                self._user32.mouse_event(up_flag, 0, 0, 0, 0)

            return DesktopClickOutput(
                action="click",
                x=x,
                y=y,
                button=btn_lower,
                success=True,
                verified_target=target_desc,
            )
        except Exception as e:
            return DesktopClickOutput(
                action="click",
                x=x,
                y=y,
                button=btn_lower,
                success=False,
                error=f"Mouse event execution failed: {e}",
            )

    def type_text(
        self,
        text: str,
        press_enter: bool = False,
        consequential: bool = False,
        approval_token: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> DesktopTypeTextOutput:
        """
        Types a text string into the active window.
        Redacts credentials from traces and requires approval tokens for consequential content.
        """
        if not text:
            return DesktopTypeTextOutput(
                action="type_text", characters_typed=0, success=False, error="Text parameter cannot be empty."
            )

        fg_hwnd = self._user32.GetForegroundWindow()
        active_win = self._get_window_info(fg_hwnd)
        target_desc = f"{active_win.title} ({active_win.process_name})" if active_win else "Active Window"

        if active_win and not active_win.is_permitted:
            return DesktopTypeTextOutput(
                action="type_text",
                characters_typed=0,
                success=False,
                error=f"Desktop security violation: Interaction with prohibited window '{active_win.title}' is blocked.",
            )

        # Consequential check
        is_consequential, reason = DesktopSecurityManager.is_consequential_desktop_action(
            action_type="type_text",
            window_title=active_win.title if active_win else None,
            text=text,
            explicit_flag=consequential,
        )

        if is_consequential:
            action_args = {
                "consequential": consequential,
                "press_enter": press_enter,
                "text": text,
            }
            valid, token_reason = DesktopSecurityManager.verify_action_token(
                tool_name="desktop_type_text",
                arguments=action_args,
                provided_token=approval_token,
                session_id=session_id,
            )
            if not valid:
                return DesktopTypeTextOutput(
                    action="type_text",
                    characters_typed=0,
                    success=False,
                    error=token_reason,
                )

        try:
            # Send keystrokes via SendInput or keybd_event
            for ch in text:
                vk = self._user32.VkKeyScanW(ord(ch))
                if vk != -1:
                    vk_code = vk & 0xFF
                    shift_needed = bool((vk >> 8) & 1)
                    if shift_needed:
                        self._user32.keybd_event(0x10, 0, 0, 0)
                    self._user32.keybd_event(vk_code, 0, 0, 0)
                    time.sleep(0.005)
                    self._user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
                    if shift_needed:
                        self._user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)

            if press_enter:
                time.sleep(0.02)
                self._user32.keybd_event(0x0D, 0, 0, 0)
                time.sleep(0.01)
                self._user32.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)

            return DesktopTypeTextOutput(
                action="type_text",
                characters_typed=len(text),
                success=True,
                target_window=redact_secrets(target_desc),
            )
        except Exception as e:
            return DesktopTypeTextOutput(
                action="type_text",
                characters_typed=0,
                success=False,
                error=f"Key input simulation failed: {e}",
            )

    def keypress(
        self,
        key: str,
        modifiers: Optional[List[str]] = None,
        consequential: bool = False,
        approval_token: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> DesktopKeypressOutput:
        """
        Sends a single key or modifier combo (e.g. Enter, Esc, Ctrl+S).
        Requires approval tokens for consequential keys.
        """
        key_clean = (key or "").strip().lower()
        if key_clean not in VK_CODES and len(key_clean) != 1:
            return DesktopKeypressOutput(
                action="keypress", key_sent=key, success=False, error=f"Unsupported key identifier '{key}'."
            )

        fg_hwnd = self._user32.GetForegroundWindow()
        active_win = self._get_window_info(fg_hwnd)
        target_desc = f"{active_win.title} ({active_win.process_name})" if active_win else "Active Window"

        if active_win and not active_win.is_permitted:
            return DesktopKeypressOutput(
                action="keypress",
                key_sent=key,
                success=False,
                error=f"Desktop security violation: Interaction with prohibited window '{active_win.title}' is blocked.",
            )

        mods_list = [m.lower().strip() for m in (modifiers or []) if m.lower().strip() in VK_CODES]

        is_consequential, reason = DesktopSecurityManager.is_consequential_desktop_action(
            action_type="keypress",
            window_title=active_win.title if active_win else None,
            key=key_clean,
            explicit_flag=consequential,
        )

        if is_consequential:
            action_args = {
                "consequential": consequential,
                "key": key,
                "modifiers": modifiers or [],
            }
            valid, token_reason = DesktopSecurityManager.verify_action_token(
                tool_name="desktop_keypress",
                arguments=action_args,
                provided_token=approval_token,
                session_id=session_id,
            )
            if not valid:
                return DesktopKeypressOutput(
                    action="keypress",
                    key_sent=key,
                    modifiers_sent=mods_list,
                    success=False,
                    error=token_reason,
                )

        try:
            # Press modifiers down
            for mod in mods_list:
                self._user32.keybd_event(VK_CODES[mod], 0, 0, 0)
                time.sleep(0.01)

            # Press main key
            vk_code = VK_CODES.get(key_clean) or self._user32.VkKeyScanW(ord(key[0])) & 0xFF
            self._user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.02)
            self._user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

            # Release modifiers in reverse order
            for mod in reversed(mods_list):
                self._user32.keybd_event(VK_CODES[mod], 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.005)

            return DesktopKeypressOutput(
                action="keypress",
                key_sent=key,
                modifiers_sent=mods_list,
                success=True,
                target_window=redact_secrets(target_desc),
            )
        except Exception as e:
            return DesktopKeypressOutput(
                action="keypress",
                key_sent=key,
                modifiers_sent=mods_list,
                success=False,
                error=f"Keypress execution failed: {e}",
            )

    async def wait_for_state(
        self,
        window_title: Optional[str] = None,
        process_name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> DesktopWaitForStateOutput:
        """
        Polls until a window with matching title or process name appears.
        """
        if not window_title and not process_name:
            return DesktopWaitForStateOutput(
                matched=False, error="Must specify at least one search criterion: window_title or process_name."
            )

        start = time.perf_counter()
        deadline = start + max(0.5, float(timeout_seconds))

        while time.perf_counter() < deadline:
            windows = self.list_windows(include_prohibited=False).windows
            for w in windows:
                title_match = (
                    window_title.lower() in w.title.lower() if window_title else True
                )
                proc_match = (
                    process_name.lower() in w.process_name.lower() if process_name else True
                )
                if title_match and proc_match:
                    return DesktopWaitForStateOutput(
                        matched=True,
                        window_found=w,
                        elapsed_seconds=round(time.perf_counter() - start, 2),
                    )
            await asyncio.sleep(0.25)

        return DesktopWaitForStateOutput(
            matched=False,
            elapsed_seconds=round(time.perf_counter() - start, 2),
            error=f"Timed out after {timeout_seconds}s waiting for matching desktop state.",
        )


_DEFAULT_DESKTOP_MANAGER: Optional[DesktopManager] = None


def get_desktop_manager() -> DesktopManager:
    global _DEFAULT_DESKTOP_MANAGER
    if _DEFAULT_DESKTOP_MANAGER is None:
        _DEFAULT_DESKTOP_MANAGER = DesktopManager()
    return _DEFAULT_DESKTOP_MANAGER
