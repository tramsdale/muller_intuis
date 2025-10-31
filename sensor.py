"""Support for Muller Intuis sensors."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MullerIntuisEnergyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Muller Intuis sensors from a config entry."""
    _LOGGER.debug("Setting up Muller Intuis sensor platform")

    coordinators = entry.runtime_data
    _LOGGER.debug("Available coordinators: %s", list(coordinators.keys()))

    await _setup_energy_statistics_handlers(hass, coordinators, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up Muller Intuis energy sensors from YAML platform discovery."""
    from .const import DOMAIN

    _LOGGER.info("Starting sensor platform setup from YAML discovery")

    # For YAML setup, coordinators are stored in hass.data
    if DOMAIN not in hass.data or "yaml_setup" not in hass.data[DOMAIN]:
        _LOGGER.error("YAML setup coordinators not found in hass.data")
        return

    coordinators = hass.data[DOMAIN]["yaml_setup"]
    _LOGGER.debug("Found YAML coordinators: %s", list(coordinators.keys()))

    await _setup_energy_statistics_handlers(hass, coordinators, async_add_entities)


async def _setup_energy_statistics_handlers(
    hass: HomeAssistant,
    coordinators: dict,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up energy statistics handlers."""

    # Check if energy coordinator is available
    if "energy_coordinator" in coordinators:
        _LOGGER.info("Energy coordinator found, setting up energy statistics handlers")
        energy_coordinator = coordinators["energy_coordinator"]

        # Setup statistics handlers directly (no entities)
        if "config_coordinator" in coordinators:
            config_coordinator = coordinators["config_coordinator"]
            if config_coordinator.data and config_coordinator.data.rooms:
                _LOGGER.debug(
                    "Config coordinator data available, creating room energy statistics handlers"
                )

                # Create statistics handlers for each room, but don't add them as entities
                for room_id, room in config_coordinator.data.rooms.items():
                    _LOGGER.debug(
                        "Creating energy statistics handler for room %s (%s)",
                        room_id,
                        room.name,
                    )

                    # Create the handler
                    handler = MullerIntuisEnergyStatisticsHandler(
                        hass=hass,
                        coordinator=energy_coordinator,
                        room_id=room_id,
                        room_name=room.name,
                        home_id=config_coordinator.data.home_id,
                    )

                    _LOGGER.debug(
                        "Created energy statistics handler: %s", handler.unique_id
                    )

                    # Add coordinator listener for automatic updates
                    energy_coordinator.async_add_listener(
                        handler.handle_coordinator_update
                    )

                _LOGGER.info(
                    "Setup %d energy statistics handlers",
                    len(config_coordinator.data.rooms),
                )

                # Trigger immediate refresh if coordinator has data
                if energy_coordinator.data:
                    _LOGGER.info(
                        "Energy coordinator has data, triggering statistics processing"
                    )
                    # Process statistics for all handlers
                    for room_id, room in config_coordinator.data.rooms.items():
                        handler = MullerIntuisEnergyStatisticsHandler(
                            hass=hass,
                            coordinator=energy_coordinator,
                            room_id=room_id,
                            room_name=room.name,
                            home_id=config_coordinator.data.home_id,
                        )
                        handler.handle_coordinator_update()
                else:
                    _LOGGER.info(
                        "Triggering immediate energy coordinator refresh for statistics"
                    )
                    await energy_coordinator.async_refresh()
            else:
                _LOGGER.warning(
                    "Config coordinator has no room data for energy sensors"
                )
        else:
            _LOGGER.warning("Config coordinator not available for energy sensors")
    else:
        _LOGGER.debug("Energy coordinator not available, skipping energy sensors")

    # No regular sensor entities to add for now
    async_add_entities([])


class MullerIntuisEnergyStatisticsHandler:
    """Handler for Muller Intuis energy statistics (no sensor entity, only energy dashboard integration)."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MullerIntuisEnergyCoordinator,
        room_id: str,
        room_name: str,
        home_id: str,
    ) -> None:
        """Initialize the energy statistics handler."""
        self.hass = hass
        self.coordinator = coordinator
        self.room_id = room_id
        self.room_name = room_name
        self.home_id = home_id
        self.unique_id = f"muller_intuis_energy_{home_id}_{room_id}"
        self.name = f"Muller Intuis Energy {room_name}"

        _LOGGER.debug("Created energy statistics handler: %s", self.unique_id)

    async def _download_existing_statistics(
        self, start_time: datetime, end_time: datetime
    ) -> dict[str, list]:
        """Download existing energy statistics from Home Assistant for the last 12 values.

        Args:
            start_time: Start time for statistics query
            end_time: End time for statistics query

        Returns:
            Dictionary with 'mean' and 'sum' statistics from HA database

        """
        statistic_id = f"muller_intuis:{self.unique_id}"

        _LOGGER.debug(
            "Downloading existing statistics for %s from %s to %s",
            statistic_id,
            start_time,
            end_time,
        )

        try:
            # Download statistics from Home Assistant database
            instance = get_instance(self.hass)
            existing_stats = await instance.async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_time,
                end_time,
                {statistic_id},  # Set of statistic IDs
                "hour",  # Period
                None,  # Units (use default)
                {"mean", "sum"},  # Types we want both mean and sum
            )

            if statistic_id in existing_stats:
                stats_data = existing_stats[statistic_id]
                _LOGGER.debug(
                    "Found %d existing statistics for %s",
                    len(stats_data),
                    statistic_id,
                )
                return {
                    "mean": [s for s in stats_data if "mean" in s],
                    "sum": [s for s in stats_data if "sum" in s],
                }

        except (OSError, ValueError) as err:
            _LOGGER.warning(
                "Failed to download existing statistics for %s: %s",
                statistic_id,
                err,
            )

        _LOGGER.debug("No existing statistics found for %s", statistic_id)
        return {"mean": [], "sum": []}

    @callback
    def handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and backfill statistics."""
        _LOGGER.debug(
            "Energy statistics handler %s received coordinator update", self.unique_id
        )

        if self.coordinator.data and self.coordinator.data.measurements:
            _LOGGER.debug(
                "Energy statistics handler %s has data, calling backfill",
                self.unique_id,
            )
            # Backfill energy statistics to Home Assistant's energy dashboard
            self._backfill_energy_statistics()
        else:
            _LOGGER.debug(
                "Energy statistics handler %s has no data yet", self.unique_id
            )

    def _backfill_energy_statistics(self) -> None:
        """Backfill historic energy data into Home Assistant statistics with cumulative handling."""
        if not self.coordinator.data or not self.coordinator.data.measurements:
            _LOGGER.debug("No energy data available for statistics backfill")
            return

        _LOGGER.info(
            "Backfilling energy statistics for %s with %d measurements",
            self.unique_id,
            len(self.coordinator.data.measurements),
        )

        # Filter measurements for this specific room and sort by timestamp
        room_measurements = [
            m for m in self.coordinator.data.measurements if m.room_id == self.room_id
        ]
        room_measurements.sort(key=lambda x: x.timestamp)

        if not room_measurements:
            _LOGGER.debug("No measurements found for room %s", self.room_id)
            return

        # Calculate time range for downloading existing statistics (last 12 hours + buffer)
        start_time = datetime.fromtimestamp(room_measurements[0].timestamp)
        end_time = datetime.fromtimestamp(room_measurements[-1].timestamp)

        # Extend range to get more context for comparison
        extended_start = start_time - timedelta(hours=12)
        extended_end = end_time + timedelta(hours=1)

        # Make timezone-aware
        extended_start = dt_util.as_local(extended_start)
        extended_end = dt_util.as_local(extended_end)

        _LOGGER.debug(
            "Downloading existing statistics from %s to %s for comparison",
            extended_start,
            extended_end,
        )

        # Download existing statistics from HA (async operation)
        self.hass.async_create_task(
            self._process_energy_with_comparison(
                room_measurements, extended_start, extended_end
            )
        )

    async def _process_energy_with_comparison(
        self,
        room_measurements: list,
        extended_start: datetime,
        extended_end: datetime,
    ) -> None:
        """Process energy measurements with comparison to existing HA statistics."""
        existing_stats = await self._download_existing_statistics(
            extended_start, extended_end
        )

        _LOGGER.debug(
            "Downloaded %d existing mean stats and %d sum stats",
            len(existing_stats["mean"]),
            len(existing_stats["sum"]),
        )

        # Calculate cumulative sums from the per-hour API data
        cumulative_sum = 0.0
        api_statistics = []

        # If we have existing sum statistics, start from the last known value
        if existing_stats["sum"]:
            # Find the latest sum statistic that's before our new data
            latest_sum_stat = max(existing_stats["sum"], key=lambda x: x["start"])
            latest_sum_time = latest_sum_stat["start"]
            latest_sum_value = latest_sum_stat.get("sum", 0.0)

            # Only use this as starting point if it's before our first measurement
            first_measurement_time = datetime.fromtimestamp(
                room_measurements[0].timestamp
            )
            first_measurement_time = dt_util.as_local(first_measurement_time)

            # Ensure both times are datetime objects for comparison
            if isinstance(latest_sum_time, (int, float)):
                latest_sum_time = datetime.fromtimestamp(latest_sum_time)
                latest_sum_time = dt_util.as_local(latest_sum_time)

            if latest_sum_time < first_measurement_time:
                cumulative_sum = latest_sum_value
                _LOGGER.debug(
                    "Starting cumulative sum from existing value: %f Wh at %s",
                    cumulative_sum,
                    latest_sum_time,
                )

        # Process each measurement to create both mean and cumulative sum statistics
        for measurement in room_measurements:
            try:
                # Convert timestamp to datetime object
                timestamp = datetime.fromtimestamp(measurement.timestamp)
                timestamp = dt_util.as_local(timestamp)

                # Add this hour's energy to cumulative sum
                cumulative_sum += measurement.energy_wh

                api_statistics.append(
                    {
                        "start": timestamp,
                        "mean": measurement.energy_wh,  # Per-hour consumption
                        "sum": cumulative_sum,  # Cumulative consumption
                    }
                )

                _LOGGER.debug(
                    "Processed measurement: timestamp=%s, mean=%f Wh, cumulative_sum=%f Wh",
                    timestamp,
                    measurement.energy_wh,
                    cumulative_sum,
                )

            except (ValueError, AttributeError) as err:
                _LOGGER.warning(
                    "Failed to parse measurement timestamp %s: %s",
                    measurement.timestamp,
                    err,
                )
                continue

        # Compare overlapping ranges and flag changes
        changes_detected = self._compare_overlapping_statistics(
            existing_stats, api_statistics
        )

        if changes_detected:
            _LOGGER.info(
                "Detected changes in overlapping statistics, updating all statistics"
            )

        # Upload both mean and sum statistics to Home Assistant
        if api_statistics:
            await self._upload_dual_statistics(api_statistics)

    def _compare_overlapping_statistics(
        self, existing_stats: dict, api_statistics: list
    ) -> bool:
        """Compare overlapping statistics to detect changes.

        Args:
            existing_stats: Statistics from HA database
            api_statistics: New statistics from API

        Returns:
            True if changes detected in overlapping ranges

        """
        changes_found = False

        # Create lookup for existing statistics by timestamp
        existing_mean_lookup = {stat["start"]: stat for stat in existing_stats["mean"]}
        existing_sum_lookup = {stat["start"]: stat for stat in existing_stats["sum"]}

        for api_stat in api_statistics:
            timestamp = api_stat["start"]

            # Check mean values
            if timestamp in existing_mean_lookup:
                existing_mean = existing_mean_lookup[timestamp].get("mean", 0.0)
                api_mean = api_stat["mean"]

                # Allow small floating point differences (1 Wh tolerance)
                if abs(existing_mean - api_mean) > 1.0:
                    _LOGGER.warning(
                        "Mean value change detected at %s: existing=%f, api=%f",
                        timestamp,
                        existing_mean,
                        api_mean,
                    )
                    changes_found = True

            # Check sum values
            if timestamp in existing_sum_lookup:
                existing_sum = existing_sum_lookup[timestamp].get("sum", 0.0)
                api_sum = api_stat["sum"]

                # Allow small floating point differences (1 Wh tolerance)
                if abs(existing_sum - api_sum) > 1.0:
                    _LOGGER.warning(
                        "Sum value change detected at %s: existing=%f, api=%f",
                        timestamp,
                        existing_sum,
                        api_sum,
                    )
                    changes_found = True

        return changes_found

    async def _upload_dual_statistics(self, statistics: list) -> None:
        """Upload both mean and sum statistics to Home Assistant.

        Args:
            statistics: List of statistics with both mean and sum values

        """
        statistic_id = f"muller_intuis:{self.unique_id}"

        # Prepare metadata for external statistics (with both mean and sum)
        metadata = {
            "has_mean": True,
            "has_sum": True,
            "unit_of_measurement": UnitOfEnergy.WATT_HOUR,
            "statistic_id": statistic_id,
            "name": self.name,
            "source": "muller_intuis",
        }

        _LOGGER.debug("Dual statistics metadata: %s", metadata)

        _LOGGER.info(
            "Adding external statistics for %s with %d data points (mean and sum)",
            self.unique_id,
            len(statistics),
        )

        # Upload statistics with both mean and sum
        async_add_external_statistics(self.hass, metadata, statistics)


async def backfill_energy(
    hass: HomeAssistant, name: str, energy_wh: float, hours_ago: int
) -> None:
    """Legacy utility function for backfilling energy data."""
    timestamp = dt_util.utcnow() - timedelta(hours=hours_ago)

    metadata = {
        "has_mean": False,
        "has_sum": True,
        "unit_of_measurement": UnitOfEnergy.WATT_HOUR,
        "statistic_id": f"sensor.{name.lower().replace(' ', '_')}",
    }

    statistics = [
        {
            "start": timestamp,
            "sum": energy_wh,
        }
    ]

    async_add_external_statistics(hass, metadata, statistics)
