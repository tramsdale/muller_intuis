"""Sensor platform for Muller Intuis integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MullerIntuisEnergyCoordinator, MullerIntuisConfigCoordinator
from .models import MullerIntuisEnergyData, MullerIntuisDevice, MullerIntuisRoom

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Muller Intuis energy sensors from a config entry."""
    _LOGGER.info(
        "Starting sensor platform setup for entry %s",
        entry.entry_id if entry else "YAML",
    )

    # Handle both YAML and config entry setups
    if entry:
        coordinators = hass.data[DOMAIN][entry.entry_id]
    else:
        coordinators = hass.data[DOMAIN].get("yaml_setup", {})

    _LOGGER.debug("Available coordinators: %s", list(coordinators.keys()))

    config_coordinator: MullerIntuisConfigCoordinator = coordinators.get(
        "config_coordinator"
    )
    energy_coordinator: MullerIntuisEnergyCoordinator = coordinators.get(
        "energy_coordinator"
    )

    if not energy_coordinator:
        _LOGGER.warning("No energy coordinator available, skipping energy sensor setup")
        return

    _LOGGER.info("Energy coordinator found, proceeding with sensor setup")

    # Create room-based energy entities based on configuration data
    entities = []
    if config_coordinator and config_coordinator.data:
        _LOGGER.debug("Config coordinator data available, checking rooms")
        for room in config_coordinator.data.rooms.values():
            # Check if room has any energy-measuring modules (assuming climate devices can measure energy)
            has_energy_modules = True
            if has_energy_modules:
                _LOGGER.debug(
                    "Creating energy sensor for room %s (%s)", room.room_id, room.name
                )
                entities.append(MullerIntuisEnergySensor(energy_coordinator, room))

    # Create default home-level energy sensor if no room-specific sensors found
    if not entities:
        _LOGGER.info(
            "No energy-capable rooms found, creating default home-level energy sensor"
        )
        entities.append(MullerIntuisEnergySensor(energy_coordinator, None))

    _LOGGER.info("Adding %d energy sensor entities", len(entities))
    async_add_entities(entities)

    # Trigger an immediate energy coordinator refresh now that sensors are set up
    # This ensures sensors receive data and can backfill statistics
    if entities:
        _LOGGER.info(
            "Triggering immediate energy coordinator refresh after sensor setup"
        )
        await energy_coordinator.async_request_refresh()


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up Muller Intuis energy sensors from YAML platform discovery."""
    _LOGGER.info("Starting sensor platform setup from YAML discovery")

    # Call the main setup function with entry=None to indicate YAML setup
    await async_setup_entry(hass, None, async_add_entities)


class MullerIntuisEnergySensor(
    CoordinatorEntity[MullerIntuisEnergyCoordinator], SensorEntity
):
    """Muller Intuis energy consumption sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MullerIntuisEnergyCoordinator,
        room: MullerIntuisRoom | None = None,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator)
        self.room = room

        # Set proper entity naming following HA guidelines
        if room:
            home_id = coordinator.config_coordinator.data.home_id
            self._attr_name = f"Muller Intuis Energy {room.name or room.room_id}"
            self._attr_unique_id = f"muller_intuis_energy_{home_id}_{room.room_id}"

            # Set device info for proper device registry integration
            self._attr_device_info = {
                "identifiers": {(DOMAIN, f"energy_{home_id}_{room.room_id}")},
                "name": f"Muller Intuis Energy {room.name or room.room_id}",
                "manufacturer": "Muller Intuis",
                "model": "Room Energy Monitor",
            }
        else:
            # Home-level sensor
            home_id = coordinator.config_coordinator.data.home_id
            self._attr_name = f"Muller Intuis Energy {home_id}"
            self._attr_unique_id = f"muller_intuis_energy_{home_id}"

            # Set device info for proper device registry integration
            self._attr_device_info = {
                "identifiers": {(DOMAIN, f"energy_{home_id}")},
                "name": f"Muller Intuis Energy {home_id}",
                "manufacturer": "Muller Intuis",
                "model": "Home Energy Monitor",
            }

        # Check if coordinator already has data and backfill if so
        if self.coordinator.data and self.coordinator.data.measurements:
            _LOGGER.debug(
                "Sensor %s found existing coordinator data, scheduling backfill",
                self.unique_id,
            )
            # Schedule backfill after entity is fully initialized
            self.coordinator.hass.async_create_task(self._async_initial_backfill())

    @property
    def native_value(self) -> float | None:
        """Return the energy consumption value."""
        if not self.coordinator.data or not self.coordinator.data.measurements:
            return None

        # Return the total cumulative energy consumption
        return sum(
            measurement.energy_kwh for measurement in self.coordinator.data.measurements
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        attributes = {
            "measurement_count": len(self.coordinator.data.measurements),
            "start_date": self.coordinator.data.start_date,
            "end_date": self.coordinator.data.end_date,
            "home_id": self.coordinator.data.home_id,
        }

        # Add room-specific attributes if this is a room-based sensor
        if self.room:
            attributes.update(
                {
                    "room_id": self.room.room_id,
                    "room_name": self.room.name,
                    "room_modules": self.room.modules,
                }
            )

        return attributes

    async def _async_initial_backfill(self) -> None:
        """Perform initial update when coordinator already has data."""
        _LOGGER.debug("Sensor %s performing initial update with existing data", self.unique_id)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Energy sensor %s received coordinator update", self.unique_id)
        super()._handle_coordinator_update()

        if self.coordinator.data and self.coordinator.data.measurements:
            _LOGGER.debug("Energy sensor %s has %d measurements, updating state",
                         self.unique_id, len(self.coordinator.data.measurements))
        else:
            _LOGGER.debug("Energy sensor %s has no data yet", self.unique_id)

    def _backfill_energy_statistics(self) -> None:
        """Backfill historic energy data into Home Assistant statistics."""
        if not self.coordinator.data or not self.coordinator.data.measurements:
            _LOGGER.debug("No energy data available for statistics backfill")
            return

        _LOGGER.info(
            "Backfilling energy statistics for %s with %d measurements",
            self.unique_id,
            len(self.coordinator.data.measurements),
        )

        # Prepare metadata for external statistics
        # For external statistics, use a custom statistic_id format
        statistic_id = f"muller_intuis:{self.unique_id}"
        metadata = {
            "has_mean": True,
            "has_sum": False,
            "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
            "statistic_id": statistic_id,
            "name": self.name,
            "source": DOMAIN,
        }

        _LOGGER.debug("Statistics metadata: %s", metadata)

        # Convert measurements to statistics format
        statistics = []
        for measurement in self.coordinator.data.measurements:
            try:
                # Convert local timestamp integer to datetime object
                _LOGGER.debug(
                    "Processing measurement: timestamp=%s, energy=%s",
                    measurement.timestamp,
                    measurement.energy_kwh,
                )
                timestamp = datetime.fromtimestamp(measurement.timestamp)
                # Make it timezone-aware using Home Assistant's default timezone
                timestamp = dt_util.as_local(timestamp)
                statistics.append(
                    {
                        "start": timestamp,
                        "mean": measurement.energy_kwh,
                    }
                )
            except (ValueError, AttributeError) as err:
                _LOGGER.warning(
                    "Failed to parse measurement timestamp %s: %s",
                    measurement.timestamp,
                    err,
                )
                continue

        if statistics:
            _LOGGER.info(
                "Adding external statistics for %s with %d data points",
                self.unique_id,
                len(statistics),
            )
            async_add_external_statistics(self.hass, metadata, statistics)
        else:
            _LOGGER.warning("No valid statistics to add for %s", self.unique_id)


async def backfill_energy(hass, name, energy_kwh: float, hours_ago: int):
    """Legacy utility function for backfilling energy data."""
    timestamp = dt_util.utcnow() - timedelta(hours=hours_ago)

    metadata = {
        "has_mean": False,
        "has_sum": True,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "statistic_id": f"sensor.{name.lower().replace(' ', '_')}",
    }

    statistics = [
        {
            "start": timestamp,
            "sum": energy_kwh,
        }
    ]

    async_add_external_statistics(hass, metadata, statistics)
