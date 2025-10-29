"""Models for Muller Intuis integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class MullerIntuisDevice:
    """Model for a Muller Intuis device."""

    device_id: str
    room_id: str | None = None
    name: str | None = None
    muller_type: str | None = None
    current_temperature: float | None = None
    target_temperature: float | None = None
    mode: str | None = None
    open_window: bool | None = None
    boost_status: bool | None = None
    presence: bool | None = None

    @classmethod
    def from_api_data(cls, device_id: str, data: dict[str, Any]) -> MullerIntuisDevice:
        """Create device model from API data."""
        _LOGGER.debug(
            "Creating MullerIntuisDevice from API data for device %s", device_id
        )
        return cls(
            device_id=device_id,
            name=data.get("name"),
            current_temperature=data.get("current_temperature"),
            target_temperature=data.get("target_temperature"),
            mode=data.get("mode"),
            open_window=data.get("open_window"),
            boost_status=data.get("boost_status"),
            presence=data.get("presence"),
            muller_type=data.get("type"),
        )

    def is_climate_device(self) -> bool:
        """Check if this device represents a climate control device."""
        # Device is climate-capable if it has temperature control
        is_climate = self.muller_type == "NMH"
        _LOGGER.debug(
            "Device %s (%s) climate check: type=%s, is_climate=%s",
            self.device_id,
            self.name or "Unknown",
            self.muller_type,
            is_climate,
        )
        return is_climate


@dataclass
class MullerIntuisHome:
    """Model for a Muller Intuis home."""

    name: str
    rooms: dict[str, MullerIntuisRoom]

    @classmethod
    def from_api_data(cls, device_id: str, data: dict[str, Any]) -> MullerIntuisHome:
        """Create device model from API data."""
        return cls()


@dataclass
class MullerIntuisRoom:
    """Model for a Muller Intuis room."""

    name: str
    room_id: str
    home_id: str
    modules: list[str]
    muller_type: str | None = None
    room_type: str | None = None
    current_temperature: float | None = None
    target_temperature: float | None = None
    mode: str | None = None
    open_window: bool | None = None
    boost_status: bool | None = None
    presence: bool | None = None

    @classmethod
    def from_api_data(
        cls, room_id: str, home_id: str, data: dict[str, Any]
    ) -> MullerIntuisRoom:
        """Create device model from API data."""
        return cls(
            name=data.get("name"),
            room_id=room_id,
            home_id=home_id,
            room_type=data.get("type"),
            modules=data.get("modules", []),
        )


@dataclass
class MullerIntuisData:
    """Model for Muller Intuis API response data."""

    homes: dict[str, MullerIntuisHome]
    rooms: dict[str, MullerIntuisRoom]
    devices: dict[str, MullerIntuisDevice]
    home_id: str

    @classmethod
    def from_api_response(
        cls, response_homesdata: dict[str, Any], response_homestatus: dict[str, Any]
    ) -> MullerIntuisData:
        """Create data model from API response."""
        _LOGGER.debug("Processing API response data to create MullerIntuisData model")
        devices = {}

        # Process the homesdata response to build homes and rooms
        homes = {}
        rooms = {}
        home_id = ""
        device_count = 0

        for home in response_homesdata.get("body", {}).get("homes", []) or []:
            _LOGGER.debug(
                "Processing home %s: %s", home["id"], home.get("name", "Unknown")
            )
            for room in home.get("rooms", []) or []:
                _LOGGER.debug(
                    "Processing room %s: %s", room["id"], room.get("name", "Unknown")
                )
                room = MullerIntuisRoom.from_api_data(
                    room_id=room["id"], home_id=home["id"], data=room
                )
                rooms[room.room_id] = room

            for module in home.get("modules", []) or []:
                _LOGGER.debug(
                    "Processing module %s (%s): %s",
                    module["id"],
                    module["type"],
                    module.get("name", "Unknown"),
                )
                device = MullerIntuisDevice.from_api_data(module.get("id"), module)
                devices[module["id"]] = device
                device_count += 1

            homes[home["id"]] = MullerIntuisHome(
                name=home.get("name", ""),
                rooms=rooms,
            )
            home_id = home["id"]

        _LOGGER.info(
            "Successfully created MullerIntuisData model with %d devices across %d homes and %d rooms",
            device_count,
            len(homes),
            len(rooms),
        )
        return cls(devices=devices, homes=homes, rooms=rooms, home_id=home_id)

    def get_device(self, device_id: str | None = None) -> MullerIntuisDevice | None:
        """Get device by ID or default device."""
        if device_id and device_id in self.devices:
            _LOGGER.debug("Found device with ID: %s", device_id)
            return self.devices[device_id]
        if "default" in self.devices:
            _LOGGER.debug("Using default device")
            return self.devices["default"]
        if self.devices:
            device = next(iter(self.devices.values()))
            _LOGGER.debug("Using first available device: %s", device.device_id)
            return device
        _LOGGER.warning("No devices found in data model")
        return None

    def get_room(self, room_id: str | None = None) -> MullerIntuisRoom | None:
        """Get room by ID or default room."""
        if room_id and room_id in self.rooms:
            _LOGGER.debug("Found room with ID: %s", room_id)
            return self.rooms[room_id]
        if "default" in self.rooms:
            _LOGGER.debug("Using default room")
            return self.rooms["default"]
        if self.rooms:
            room = next(iter(self.rooms.values()))
            _LOGGER.debug("Using first available room: %s", room.room_id)
            return room
        _LOGGER.warning("No rooms found in data model")
        return None
