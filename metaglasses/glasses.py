"""
Core connection and control layer for Ray-Ban Meta Smart Glasses (Generation 2).

The glasses communicate with the host over Bluetooth LE using the Meta View
companion-app protocol.  This module abstracts that transport behind a simple,
high-level ``Glasses`` class.

Typical usage::

    from metaglasses import Glasses

    glasses = Glasses()
    glasses.connect()

    info = glasses.device_info()
    print(f"Battery: {info['battery_pct']}%")

    glasses.take_photo()
    glasses.disconnect()
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GlassesConnectionError(Exception):
    """Raised when a connection to the glasses cannot be established."""


class GlassesNotConnectedError(Exception):
    """Raised when an operation is attempted before connecting."""


# ---------------------------------------------------------------------------
# Enums / constants
# ---------------------------------------------------------------------------

class CaptureMode(Enum):
    """Supported capture modes."""
    PHOTO = "photo"
    VIDEO = "video"
    LIVESTREAM = "livestream"


class LEDColor(Enum):
    """Privacy LED colors."""
    OFF = "off"
    WHITE = "white"
    RED = "red"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DeviceInfo:
    """Snapshot of device state returned by :meth:`Glasses.device_info`."""
    firmware_version: str
    battery_pct: int          # 0-100
    storage_used_mb: float
    storage_total_mb: float
    capture_mode: CaptureMode
    is_charging: bool
    serial_number: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Glasses
# ---------------------------------------------------------------------------

class Glasses:
    """High-level interface to a pair of Ray-Ban Meta Smart Glasses (Gen 2).

    Parameters
    ----------
    device_name:
        Bluetooth device name advertised by the glasses.  Defaults to
        ``"Ray-Ban Meta"``.
    timeout:
        Connection timeout in seconds.  Defaults to ``10``.
    auto_reconnect:
        Automatically attempt to re-connect if the connection drops.
    on_event:
        Optional callback invoked whenever the glasses emit an event (e.g.
        button press, capture complete).  Receives a ``dict`` with at least
        an ``"event"`` key.
    """

    def __init__(
        self,
        device_name: str = "Ray-Ban Meta",
        timeout: float = 10.0,
        auto_reconnect: bool = True,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.device_name = device_name
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect
        self.on_event = on_event

        self._connected: bool = False
        self._device_info: Optional[DeviceInfo] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Scan for the glasses over Bluetooth and open a connection.

        Raises
        ------
        GlassesConnectionError
            If the glasses cannot be found within :attr:`timeout` seconds.
        """
        # In a real implementation this would call into a BLE library
        # (e.g. ``bleak``) to discover and connect to the device.
        start = time.monotonic()
        while time.monotonic() - start < self.timeout:
            # Simulated discovery
            if self._discover():
                self._connected = True
                self._device_info = self._fetch_device_info()
                return
            time.sleep(0.1)
        raise GlassesConnectionError(
            f"Could not find '{self.device_name}' within {self.timeout}s. "
            "Make sure the glasses are turned on and within Bluetooth range."
        )

    def disconnect(self) -> None:
        """Close the Bluetooth connection gracefully."""
        self._connected = False
        self._device_info = None

    @property
    def is_connected(self) -> bool:
        """``True`` if the glasses are currently connected."""
        return self._connected

    # ------------------------------------------------------------------
    # Device information
    # ------------------------------------------------------------------

    def device_info(self) -> DeviceInfo:
        """Return a :class:`DeviceInfo` snapshot of the current device state.

        Raises
        ------
        GlassesNotConnectedError
            If called before :meth:`connect`.
        """
        self._require_connected()
        assert self._device_info is not None
        return self._device_info

    def status(self) -> dict:
        """Return a human-friendly status dictionary."""
        info = self.device_info()
        return {
            "connected": self._connected,
            "firmware": info.firmware_version,
            "battery_pct": info.battery_pct,
            "storage_used_mb": info.storage_used_mb,
            "storage_total_mb": info.storage_total_mb,
            "capture_mode": info.capture_mode.value,
            "is_charging": info.is_charging,
        }

    # ------------------------------------------------------------------
    # Capture controls
    # ------------------------------------------------------------------

    def take_photo(self) -> str:
        """Trigger the built-in camera shutter and return a media ID.

        The privacy LED will blink white before capture as required by
        Meta's hardware design.

        Returns
        -------
        str
            Opaque media ID that can be passed to :class:`~metaglasses.media.MediaManager`.
        """
        self._require_connected()
        self._set_led(LEDColor.WHITE)
        media_id = str(uuid.uuid4())
        self._dispatch_event({"event": "capture_complete", "type": "photo", "media_id": media_id})
        self._set_led(LEDColor.OFF)
        return media_id

    def start_video(self) -> None:
        """Begin video recording.

        Raises
        ------
        GlassesNotConnectedError
            If not connected.
        RuntimeError
            If a recording is already in progress.
        """
        self._require_connected()
        if self._device_info and self._device_info.capture_mode == CaptureMode.VIDEO:
            raise RuntimeError("A video recording is already in progress.")
        self._set_led(LEDColor.WHITE)
        self._dispatch_event({"event": "recording_started"})
        if self._device_info:
            self._device_info.capture_mode = CaptureMode.VIDEO

    def stop_video(self) -> str:
        """Stop the current video recording and return a media ID."""
        self._require_connected()
        self._set_led(LEDColor.OFF)
        media_id = str(uuid.uuid4())
        self._dispatch_event({"event": "recording_stopped", "media_id": media_id})
        if self._device_info:
            self._device_info.capture_mode = CaptureMode.PHOTO
        return media_id

    def start_livestream(self, destination_url: str) -> None:
        """Begin an RTMP livestream to *destination_url*."""
        self._require_connected()
        self._set_led(LEDColor.RED)
        self._dispatch_event({"event": "livestream_started", "destination": destination_url})

    def stop_livestream(self) -> None:
        """Stop an active livestream."""
        self._require_connected()
        self._set_led(LEDColor.OFF)
        self._dispatch_event({"event": "livestream_stopped"})

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def set_capture_mode(self, mode: CaptureMode) -> None:
        """Switch the default capture mode."""
        self._require_connected()
        assert self._device_info is not None
        self._device_info.capture_mode = mode

    def update_firmware(self) -> None:
        """Trigger an OTA firmware update check."""
        self._require_connected()
        self._dispatch_event({"event": "firmware_check_started"})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_connected(self) -> None:
        if not self._connected:
            raise GlassesNotConnectedError(
                "Not connected to any glasses. Call connect() first."
            )

    def _discover(self) -> bool:
        # Placeholder: in production this calls into bleak/BLE scanning.
        return True

    def _fetch_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            firmware_version="2.0.0",
            battery_pct=85,
            storage_used_mb=512.0,
            storage_total_mb=32768.0,
            capture_mode=CaptureMode.PHOTO,
            is_charging=False,
        )

    def _set_led(self, color: LEDColor) -> None:
        # Placeholder: writes to BLE characteristic for the privacy LED.
        pass

    def _dispatch_event(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    def __repr__(self) -> str:
        state = "connected" if self._connected else "disconnected"
        return f"Glasses(device_name={self.device_name!r}, state={state})"
