"""Muller Intuis water heater platform."""

from __future__ import annotations

import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    MullerIntuisConfigCoordinator,
    MullerIntuisDataUpdateCoordinator,
)
from .models import MullerIntuisDevice, MullerIntuisRoom

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Muller Intuis water heater entities from config entry."""
    _LOGGER.info("Starting water heater platform setup for config entry")

    coordinators = hass.data[DOMAIN][entry.entry_id]
    config_coordinator: MullerIntuisConfigCoordinator = coordinators[
        "config_coordinator"
    ]
    data_coordinator: MullerIntuisDataUpdateCoordinator = coordinators[
        "data_coordinator"
    ]

    # Create water heater entities based on configuration data
    entities = []
    if config_coordinator.data:
        _LOGGER.info(
            "Water heater setup: Found %d rooms to check",
            len(config_coordinator.data.rooms),
        )

        for room in config_coordinator.data.rooms.values():
            _LOGGER.debug(
                "Checking room %s (%s) for water heater: room_type=%s, modules=%s",
                room.room_id,
                room.name,
                getattr(room, "room_type", "unknown"),
                room.modules,
            )

            # Log device types for each module in this room
            for module_id in room.modules:
                device = config_coordinator.data.devices.get(module_id)
                if device:
                    _LOGGER.debug(
                        "Room %s module_id=%s: device_type=%s, muller_type=%s",
                        room.name,
                        module_id,
                        getattr(device, "device_type", "unknown"),
                        getattr(device, "muller_type", "unknown"),
                    )
                else:
                    _LOGGER.debug(
                        "Room %s module_id=%s: no device data found",
                        room.name,
                        module_id,
                    )

            # Check if room has any modules that could be water heaters
            # Look for specific module types or room types that indicate water heating
            water_heater_modules = []
            for module_id in room.modules:
                device = config_coordinator.data.devices.get(
                    module_id, MullerIntuisDevice(device_id=module_id)
                )
                muller_type = device.muller_type
                _LOGGER.debug(
                    "Checking module_id=%s for water heater: muller_type=%s",
                    module_id,
                    muller_type,
                )
                if muller_type in ["NWH", "NMW", "WH", "WATER_HEATER"]:
                    water_heater_modules.append(module_id)
                    _LOGGER.info(
                        "Found water heater module_id=%s with muller_type=%s in room %s",
                        module_id,
                        muller_type,
                        room.name,
                    )

            has_water_heater_modules = bool(water_heater_modules)

            _LOGGER.debug(
                "Room %s water heater check result: has_water_heater_modules=%s",
                room.name,
                has_water_heater_modules,
            )

            if has_water_heater_modules:
                _LOGGER.debug(
                    "Creating water heater entity for room %s (%s)",
                    room.room_id,
                    room.name,
                )
                entities.append(
                    MullerIntuisWaterHeater(config_coordinator, data_coordinator, room)
                )

    # Create a single home-wide water heater entity if no room-specific ones found
    if not entities:
        _LOGGER.info(
            "No room-specific water heaters found, creating home water heater entity"
        )
        entities.append(
            MullerIntuisWaterHeater(config_coordinator, data_coordinator, None)
        )

    _LOGGER.info(
        "Water heater setup complete: created %d water heater entities", len(entities)
    )
    async_add_entities(entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up Muller Intuis water heater entities from YAML configuration."""
    coordinators = hass.data[DOMAIN]["yaml_setup"]
    config_coordinator: MullerIntuisConfigCoordinator = coordinators[
        "config_coordinator"
    ]
    data_coordinator: MullerIntuisDataUpdateCoordinator = coordinators[
        "data_coordinator"
    ]

    # Create water heater entities based on configuration data
    entities = []
    if config_coordinator.data:
        for room in config_coordinator.data.rooms.values():
            # Check if room has any modules that could be water heaters
            water_heater_modules = []
            for module_id in room.modules:
                device = config_coordinator.data.devices.get(
                    module_id, MullerIntuisDevice(device_id=module_id)
                )
                muller_type = device.muller_type
                _LOGGER.debug(
                    "YAML setup - Checking module_id=%s for water heater: muller_type=%s",
                    module_id,
                    muller_type,
                )
                if muller_type in ["NWH", "NMW", "WH", "WATER_HEATER"]:
                    water_heater_modules.append(module_id)
                    _LOGGER.info(
                        "YAML setup - Found water heater module_id=%s with muller_type=%s in room %s",
                        module_id,
                        muller_type,
                        room.name,
                    )

            has_water_heater_modules = bool(water_heater_modules)

            if has_water_heater_modules:
                _LOGGER.debug(
                    "Creating water heater entity for room %s (%s)",
                    room.room_id,
                    room.name,
                )
                entities.append(
                    MullerIntuisWaterHeater(config_coordinator, data_coordinator, room)
                )

    # Create a single home-wide water heater entity if no room-specific ones found
    if not entities:
        _LOGGER.info(
            "No room-specific water heaters found, creating home water heater entity"
        )
        entities.append(
            MullerIntuisWaterHeater(config_coordinator, data_coordinator, None)
        )

    async_add_entities(entities)


class MullerIntuisWaterHeater(
    CoordinatorEntity[MullerIntuisDataUpdateCoordinator], WaterHeaterEntity
):
    """Muller Intuis water heater entity."""

    _attr_supported_features = WaterHeaterEntityFeature.OPERATION_MODE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS  # Required by base class

    # Water heater supports three modes: Off, Auto and Force-on
    MODE_OFF = "Off"
    MODE_AUTO = "Auto"
    MODE_FORCE_ON = "Force On"

    _attr_operation_list = [MODE_OFF, MODE_AUTO, MODE_FORCE_ON]

    def __init__(
        self,
        config_coordinator: MullerIntuisConfigCoordinator,
        data_coordinator: MullerIntuisDataUpdateCoordinator,
        room: MullerIntuisRoom | None = None,
    ) -> None:
        """Initialize the water heater entity."""
        super().__init__(data_coordinator)
        self.config_coordinator = config_coordinator
        self.room = room

        # Find the water heater module ID and bridge ID for this room
        self.water_heater_module_id = None
        self.water_heater_bridge_id = None
        if room and room.modules:
            for module_id in room.modules:
                device = config_coordinator.data.devices.get(module_id)
                if device and device.muller_type == "NMW":
                    self.water_heater_module_id = module_id
                    self.water_heater_bridge_id = device.bridge_id
                    _LOGGER.debug(
                        "Found water heater module %s with bridge %s for room %s",
                        module_id,
                        device.bridge_id,
                        room.name,
                    )
                    break

        # Initialize state tracking variables
        self._operation_mode: str = self.MODE_OFF

        # Set proper entity naming following HA guidelines
        if room:
            self._attr_name = (
                f"{room.name} Water Heater"
                if room.name
                else f"Water Heater {room.room_id}"
            )
            self._attr_unique_id = f"muller_intuis_water_heater_room_{room.room_id}"
        else:
            self._attr_name = "Muller Intuis Water Heater"
            self._attr_unique_id = "muller_intuis_water_heater_home"

        # Set device info for proper device registry integration
        room_id_for_info = self.room.room_id if self.room else "home"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"water_heater_{room_id_for_info}")},
            "name": self._attr_name,
            "manufacturer": "Muller Intuis",
            "model": "Water Heater Controller",
        }

    @property
    def current_operation(self) -> str:
        """Return current operation mode."""
        return self._operation_mode

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature - disabled for this water heater."""
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature - disabled for this water heater."""
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature - disabled for this water heater."""
        return 0

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature - disabled for this water heater."""
        return 0

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self.room:
            # Get updated room data from the data coordinator
            updated_room = self.coordinator.data.get(self.room.room_id)
            if updated_room:
                _LOGGER.debug(
                    "Updating water heater entity for room %s with fresh data: mode=%s",
                    self.room.room_id,
                    updated_room.mode or "unknown",
                )

                # Map upstream mode to our simplified water heater modes
                if updated_room.mode:
                    m = updated_room.mode.lower()
                    # force-on corresponds to manual/forced/on modes
                    if m in ("manual", "on", "forced", "force", "override"):
                        self._operation_mode = self.MODE_FORCE_ON
                    # auto corresponds to home/auto/schedule modes
                    elif m in ("home", "auto", "schedule"):
                        self._operation_mode = self.MODE_AUTO
                    # anything else treat as off
                    else:
                        self._operation_mode = self.MODE_OFF
                else:
                    self._operation_mode = self.MODE_OFF
            else:
                _LOGGER.debug("No updated data found for room %s", self.room.room_id)
        elif not self.room:
            # Handle home-wide water heater entity case
            _LOGGER.debug("Home water heater entity - aggregating room data")
            # For a home-wide water heater, we might use data from a specific room that has the main water heater
            self._operation_mode = self.MODE_OFF

            if self.coordinator.data:
                # Find the first room with water heater data or use aggregated data
                for room_data in self.coordinator.data.values():
                    if room_data.mode:
                        m = room_data.mode.lower()
                        if m in ("manual", "on", "forced", "force", "override"):
                            self._operation_mode = self.MODE_FORCE_ON
                        elif m in ("home", "auto", "schedule"):
                            self._operation_mode = self.MODE_AUTO
                        else:
                            self._operation_mode = self.MODE_OFF
                        break

        super()._handle_coordinator_update()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        try:
            # Map water heater operation mode to API mode string
            mode_mapping = {
                self.MODE_FORCE_ON: "temporary_on",
                self.MODE_AUTO: "auto",
                self.MODE_OFF: "off",
            }
            mode_str = mode_mapping.get(operation_mode, "off")

            if (
                self.room
                and self.water_heater_module_id
                and self.water_heater_bridge_id
            ):
                # Set mode for the specific water heater module
                _LOGGER.debug(
                    "Setting water heater operation mode %s for module %s (bridge %s) in room %s (%s)",
                    mode_str,
                    self.water_heater_module_id,
                    self.water_heater_bridge_id,
                    self.room.room_id,
                    self.room.name,
                )
                await self.coordinator.api.set_water_heater_mode(
                    self.room.home_id,
                    self.water_heater_module_id,
                    self.water_heater_bridge_id,
                    mode_str,
                )
            elif not self.room:
                # Set mode for home-wide water heater - find all water heater modules
                _LOGGER.debug(
                    "Setting water heater operation mode %s for home system", mode_str
                )
                if (
                    self.config_coordinator.data
                    and self.config_coordinator.data.devices
                ):
                    # Find all water heater modules and set their mode
                    for (
                        device_id,
                        device,
                    ) in self.config_coordinator.data.devices.items():
                        if device.muller_type == "NMW" and device.bridge_id:
                            # Find the home_id for this device
                            home_id = self.config_coordinator.data.home_id
                            _LOGGER.debug(
                                "Setting mode %s for water heater module %s (bridge %s)",
                                mode_str,
                                device_id,
                                device.bridge_id,
                            )
                            await self.coordinator.api.set_water_heater_mode(
                                home_id, device_id, device.bridge_id, mode_str
                            )
            else:
                if self.room:
                    if not self.water_heater_module_id:
                        _LOGGER.warning(
                            "Cannot set water heater mode: room %s has no water heater module",
                            self.room.room_id,
                        )
                    elif not self.water_heater_bridge_id:
                        _LOGGER.warning(
                            "Cannot set water heater mode: module %s in room %s has no bridge ID",
                            self.water_heater_module_id,
                            self.room.room_id,
                        )
                else:
                    _LOGGER.warning(
                        "Cannot set water heater mode: no room or home configuration available"
                    )
                return

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to set water heater operation mode to %s: %s",
                operation_mode,
                err,
            )
            raise
