"""Data update coordinator for Muller Intuis."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import (
    MullerIntuisData,
    MullerIntuisDevice,
    MullerIntuisRoom,
    MullerIntuisEnergyData,
)
from .muller_intuisAPI import muller_intuisAPI

_LOGGER = logging.getLogger(__name__)

# Minimum 5 seconds for local network polling per HA guidelines
UPDATE_INTERVAL = timedelta(seconds=30)


class MullerIntuisConfigCoordinator:
    """Class to manage one-time configuration data from the Muller Intuis API."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry | None, api: muller_intuisAPI
    ) -> None:
        """Initialize the config coordinator."""
        self.hass = hass
        self.entry = entry
        self.api = api
        self._config_data: MullerIntuisData | None = None

    @property
    def data(self) -> MullerIntuisData | None:
        """Return the configuration data."""
        return self._config_data

    async def async_get_config_data(self) -> MullerIntuisData:
        """Fetch configuration data from homesdata API endpoint (called once)."""
        _LOGGER.info("Fetching configuration data from homesdata API")
        try:
            raw_homesdata = await self.api.get_homesdata()
            if not raw_homesdata:
                raise UpdateFailed("No homes data received from API")

            # Create config data with empty homestatus for now
            self._config_data = MullerIntuisData.from_api_response(raw_homesdata, {})
            _LOGGER.info(
                "Successfully loaded configuration with %d devices",
                len(self._config_data.devices),
            )

            return self._config_data

        except Exception as err:
            raise UpdateFailed(f"Error fetching configuration data: {err}") from err


class MullerIntuisDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, MullerIntuisRoom]]
):
    """Class to manage polling homestatus data from the Muller Intuis API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry | None,
        api: muller_intuisAPI,
        config_coordinator: MullerIntuisConfigCoordinator,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_status",
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.entry = entry
        self.config_coordinator = config_coordinator

    async def async_config_entry_first_refresh(self) -> None:
        """Handle first data refresh after config entry setup."""
        await self.async_refresh()

    async def _async_update_data(self) -> dict[str, MullerIntuisRoom]:
        """Fetch status data from homestatus API endpoint."""
        _LOGGER.debug("Starting data update from homestatus API")
        try:
            raw_homestatus = await self.api.get_homestatus(
                self.config_coordinator.data.home_id
            )
            if not raw_homestatus:
                _LOGGER.error("No homestatus data received from API")
                raise UpdateFailed("No homestatus received from API")

            _LOGGER.debug(
                "Received homestatus data: %s keys",
                list(raw_homestatus.keys())
                if isinstance(raw_homestatus, dict)
                else "not a dict",
            )

            # Check for error keys in the response
            if isinstance(raw_homestatus, dict) and "error" in raw_homestatus:
                error_info = raw_homestatus["error"]
                _LOGGER.error(
                    "API returned error in homestatus response: %s", error_info
                )
                raise UpdateFailed(f"API error: {error_info}")

            # Get the base device structure from config coordinator
            if not self.config_coordinator.data:
                _LOGGER.error("No configuration data available from config coordinator")
                raise UpdateFailed("No configuration data available")

            config_rooms = self.config_coordinator.data.rooms
            _LOGGER.debug(
                "Processing status updates for %d configured rooms",
                len(config_rooms),
            )

            # Parse the homestatus structure once to create a room status lookup
            rooms_status_data = {}
            rooms_list = raw_homestatus.get("body", {}).get("home", {}).get("rooms", [])
            if rooms_list:
                rooms_status_data = {
                    room.get("id"): room for room in rooms_list if room.get("id")
                }
                _LOGGER.debug(
                    "Found %d rooms in homestatus data", len(rooms_status_data)
                )
            else:
                _LOGGER.debug("No rooms found in homestatus data structure")

            # Update room data with homestatus information
            updated_rooms = {}
            processed_count = 0
            for room_id, room in config_rooms.items():
                _LOGGER.debug(
                    "Processing status update for room %s (%s)",
                    room_id,
                    room.name or "Unknown",
                )

                # Get room status data from our lookup dictionary
                room_status = rooms_status_data.get(room_id, {})

                # Create a copy of the room and update with homestatus data
                updated_room = MullerIntuisRoom(
                    room_id=room.room_id,
                    home_id=room.home_id,
                    name=room.name,
                    muller_type=room.muller_type,
                    modules=room.modules,
                    # Update these fields from homestatus
                    current_temperature=room_status.get("therm_measured_temperature"),
                    target_temperature=room_status.get("therm_setpoint_temperature"),
                    mode=room_status.get("therm_setpoint_mode"),
                    open_window=room_status.get("open_window"),
                    boost_status=room_status.get("boost_status"),
                    presence=room_status.get("presence"),
                )

                # Log status values for debugging
                _LOGGER.debug(
                    "Room %s status: temp=%.1f°C, target=%.1f°C, mode=%s",
                    room.room_id,
                    updated_room.current_temperature or 0.0,
                    updated_room.target_temperature or 0.0,
                    updated_room.mode or "unknown",
                )

                updated_rooms[room.room_id] = updated_room
                processed_count += 1

            _LOGGER.info(
                "Successfully updated status for %d/%d rooms",
                processed_count,
                len(config_rooms),
            )
            return updated_rooms

        except Exception as err:
            _LOGGER.error("Error during data update: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class MullerIntuisEnergyCoordinator(DataUpdateCoordinator[MullerIntuisEnergyData]):
    """Coordinator for historic energy measurement data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: muller_intuisAPI,
        config_coordinator: MullerIntuisConfigCoordinator,
    ) -> None:
        """Initialize energy coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_energy_{config_coordinator.data.home_id}",
            update_interval=timedelta(
                hours=1
            ),  # Update every 6 hours for historic data
        )
        self.api = api
        self.config_coordinator = config_coordinator

    async def _async_update_data(self) -> MullerIntuisEnergyData:
        """Fetch historic energy measurement data."""
        # Calculate fresh timestamp range on each call (last 24 hours)
        from datetime import datetime

        # Set end_date to start of current hour
        now = datetime.now()
        end_time = now.replace(minute=0, second=0, microsecond=0)
        end_date = round(end_time.timestamp())
        # Set start_date to 24 hours before end_date
        start_date = round((end_time - timedelta(hours=12)).timestamp())

        home_id = self.config_coordinator.data.home_id
        _LOGGER.debug(
            "Starting energy data update for home %s from %s to %s",
            home_id,
            start_date,
            end_date,
        )
        try:
            # Extract room IDs and bridge IDs in the same order
            roomlist = []
            bridgelist = []
            for room in self.config_coordinator.data.rooms.values():
                if room.modules is not None and room.bridge_id is not None:
                    roomlist.append(room.room_id)
                    bridgelist.append(room.bridge_id)

            raw_measurements = await self.api.get_measure(
                home_id, roomlist, bridgelist, start_date, end_date
            )
            if not raw_measurements:
                _LOGGER.error("No energy measurement data received from API")
                raise UpdateFailed("No measurement data received from API")

            _LOGGER.debug(
                "Received energy measurement data: %s keys",
                list(raw_measurements.keys())
                if isinstance(raw_measurements, dict)
                else "not a dict",
            )

            # Check for error keys in the response
            if isinstance(raw_measurements, dict) and "error" in raw_measurements:
                error_info = raw_measurements["error"]
                _LOGGER.error(
                    "API returned error in measurement response: %s", error_info
                )
                raise UpdateFailed(f"API error: {error_info}")

            # Parse energy data
            energy_data = MullerIntuisEnergyData.from_api_response(
                raw_measurements, start_date, end_date, home_id
            )

            _LOGGER.info(
                "Successfully updated energy data: %d measurements",
                len(energy_data.measurements),
            )
            return energy_data

        except Exception as err:
            _LOGGER.error("Error during energy data update: %s", err)
            raise UpdateFailed(
                f"Error communicating with measurement API: {err}"
            ) from err
