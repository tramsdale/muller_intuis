"""Climate platform for Muller Intuis."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
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
    """Set up Muller Intuis climate entities from config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    config_coordinator: MullerIntuisConfigCoordinator = coordinators[
        "config_coordinator"
    ]
    data_coordinator: MullerIntuisDataUpdateCoordinator = coordinators[
        "data_coordinator"
    ]

    # Create initial entities based on configuration data (rooms, not devices)
    entities = []
    if config_coordinator.data:
        for room in config_coordinator.data.rooms.values():
            # Check if room has any climate-capable modules
            has_climate_modules = any(
                config_coordinator.data.devices.get(
                    module_id, MullerIntuisDevice(device_id=module_id)
                ).is_climate_device()
                for module_id in room.modules
            )
            if has_climate_modules:
                _LOGGER.debug(
                    "Creating climate entity for room %s (%s)", room.room_id, room.name
                )
                entities.append(
                    MullerIntuisClimate(config_coordinator, data_coordinator, room)
                )

    # Create default climate entity if no rooms found
    if not entities:
        _LOGGER.info("No climate-capable rooms found, creating default climate entity")
        entities.append(MullerIntuisClimate(config_coordinator, data_coordinator, None))

    async_add_entities(entities)

    # Set up listener for dynamic entity creation
    async def _async_add_new_entities():
        """Add new entities when new rooms are discovered."""
        if not config_coordinator.data:
            return

        existing_entity_ids = {entity.unique_id for entity in entities}
        new_entities = []

        for room in config_coordinator.data.rooms.values():
            # Check if room has any climate-capable modules
            has_climate_modules = any(
                config_coordinator.data.devices.get(
                    module_id, MullerIntuisDevice(device_id=module_id)
                ).is_climate_device()
                for module_id in room.modules
            )
            if has_climate_modules:
                unique_id = f"{entry.entry_id}_climate_room_{room.room_id}"
                if unique_id not in existing_entity_ids:
                    _LOGGER.debug(
                        "Adding new climate entity for room %s (%s)",
                        room.room_id,
                        room.name,
                    )
                    new_entity = MullerIntuisClimate(
                        config_coordinator, data_coordinator, room
                    )
                    new_entities.append(new_entity)
                    entities.append(new_entity)

        if new_entities:
            async_add_entities(new_entities)

    # Add listener for status updates (not config changes)
    data_coordinator.async_add_listener(_async_add_new_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict | None = None,
) -> None:
    """Set up Muller Intuis climate entities from YAML configuration."""
    coordinators = hass.data[DOMAIN]["yaml_setup"]
    config_coordinator: MullerIntuisConfigCoordinator = coordinators[
        "config_coordinator"
    ]
    data_coordinator: MullerIntuisDataUpdateCoordinator = coordinators[
        "data_coordinator"
    ]

    # Create initial entities based on configuration data (rooms, not devices)
    entities = []
    if config_coordinator.data:
        for room in config_coordinator.data.rooms.values():
            # Check if room has any climate-capable modules
            has_climate_modules = any(
                config_coordinator.data.devices.get(
                    module_id, MullerIntuisDevice(device_id=module_id)
                ).is_climate_device()
                for module_id in room.modules
            )
            if has_climate_modules:
                _LOGGER.debug(
                    "Creating climate entity for room %s (%s)", room.room_id, room.name
                )
                entities.append(
                    MullerIntuisClimate(config_coordinator, data_coordinator, room)
                )

    # Create default climate entity if no rooms found
    if not entities:
        _LOGGER.info("No climate-capable rooms found, creating default climate entity")
        entities.append(MullerIntuisClimate(config_coordinator, data_coordinator, None))

    async_add_entities(entities)


class MullerIntuisClimate(
    CoordinatorEntity[MullerIntuisDataUpdateCoordinator], ClimateEntity
):
    """Muller Intuis climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]

    def __init__(
        self,
        config_coordinator: MullerIntuisConfigCoordinator,
        data_coordinator: MullerIntuisDataUpdateCoordinator,
        room: MullerIntuisRoom | None = None,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(data_coordinator)
        self.config_coordinator = config_coordinator
        self.room = room

        # Initialize state tracking variables
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._hvac_mode: HVACMode = HVACMode.OFF
        self._hvac_action: HVACAction = HVACAction.IDLE

        # Set proper entity naming following HA guidelines
        if room:
            self._attr_name = room.name or f"Climate {room.room_id}"
            self._attr_unique_id = f"muller_intuis_climate_room_{room.room_id}"
        else:
            self._attr_name = "Muller Intuis Climate"
            self._attr_unique_id = "muller_intuis_climate_default"

        # Set device info for proper device registry integration
        room_id_for_info = self.room.room_id if self.room else "default"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, room_id_for_info)},
            "name": self._attr_name,
            "manufacturer": "Muller Intuis",
            "model": "Room Climate Controller",
        }

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        return self._hvac_action

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self.room:
            # Get updated room data from the data coordinator
            updated_room = self.coordinator.data.get(self.room.room_id)
            if updated_room:
                _LOGGER.debug(
                    "Updating climate entity for room %s with fresh data: temp=%.1f°C, target=%.1f°C, mode=%s",
                    self.room.room_id,
                    updated_room.current_temperature or 0.0,
                    updated_room.target_temperature or 0.0,
                    updated_room.mode or "unknown",
                )

                # Update entity state from coordinator data
                self._current_temperature = updated_room.current_temperature
                self._target_temperature = updated_room.target_temperature

                # Map mode string to HVACMode
                if updated_room.mode:
                    mode_mapping = {
                        "manual": HVACMode.HEAT,
                        "home": HVACMode.AUTO,
                        "off": HVACMode.OFF,
                        "hg": HVACMode.OFF,
                    }
                    self._hvac_mode = mode_mapping.get(
                        updated_room.mode.lower(), HVACMode.OFF
                    )
                else:
                    self._hvac_mode = HVACMode.OFF

                # Set action based on current state
                if self._hvac_mode == HVACMode.OFF:
                    self._hvac_action = HVACAction.OFF
                elif self._current_temperature and self._target_temperature:
                    if self._current_temperature < self._target_temperature:
                        self._hvac_action = (
                            HVACAction.HEATING
                            if self._hvac_mode in (HVACMode.HEAT, HVACMode.AUTO)
                            else HVACAction.IDLE
                        )
                    else:
                        self._hvac_action = HVACAction.IDLE
                else:
                    self._hvac_action = HVACAction.IDLE
            else:
                _LOGGER.debug("No updated data found for room %s", self.room.room_id)
        elif not self.room:
            # Handle default entity case with no specific room
            _LOGGER.debug("Default climate entity - no room data to update")
            self._current_temperature = None
            self._target_temperature = None
            self._hvac_mode = HVACMode.OFF
            self._hvac_action = HVACAction.OFF

        super()._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        try:
            if self.room:
                # Set temperature for the room using room_id
                _LOGGER.debug(
                    "Setting temperature %s for room %s (%s)",
                    temperature,
                    self.room.room_id,
                    self.room.name,
                )
                await self.coordinator.api.set_temperature(
                    self.room.home_id, self.room.room_id, temperature
                )
            else:
                # Default behavior for entities without specific room
                _LOGGER.debug(
                    "Setting temperature %s for default climate entity", temperature
                )
                await self.coordinator.api.set_temperature("default", temperature)

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set temperature to %s: %s", temperature, err)
            raise

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        try:
            # Map HVACMode to API mode string
            mode_mapping = {
                HVACMode.HEAT: "manual",
                HVACMode.AUTO: "home",
                HVACMode.OFF: "off",
            }
            mode_str = mode_mapping.get(hvac_mode, "off")

            if self.room:
                # Set mode for the room using room_id
                _LOGGER.debug(
                    "Setting HVAC mode %s for room %s (%s)",
                    mode_str,
                    self.room.room_id,
                    self.room.name,
                )
                await self.coordinator.api.set_mode(
                    self.home_id, self.room.room_id, mode_str
                )
            else:
                # Default behavior for entities without specific room
                _LOGGER.debug(
                    "Setting HVAC mode %s for default climate entity", mode_str
                )
                await self.coordinator.api.set_mode("default", mode_str)

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set HVAC mode to %s: %s", hvac_mode, err)
            raise
