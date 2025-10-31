"""Muller Intuis API client."""

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

AUTH_URL = "https://app.muller-intuitiv.net/oauth2/token"
DATA_URL = "https://app.muller-intuitiv.net/api/homesdata"
STATUS_URL = "https://app.muller-intuitiv.net/syncapi/v1/homestatus"
CONTROL_URL = "https://app.muller-intuitiv.net/syncapi/v1/getconfigs"
SETSTATE_URL = "https://app.muller-intuitiv.net/syncapi/v1/setstate"
MEASURE_URL = "https://app.muller-intuitiv.net/api/gethomemeasure"

# Cache expiry time in seconds (300 seconds)
CACHE_EXPIRY = 300
# Token expiry time in seconds (1 hour)
TOKEN_EXPIRY = 3600


class muller_intuisAPI:
    """API client for Muller Intuitiv heating system."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp session for HTTP requests
            username: Username for authentication
            password: Password for authentication
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret

        """
        self._session = session
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = None
        self._token_timestamp = 0
        self._homestatus_cached_data: dict[str, Any] = {}
        self._homestatus_cache_timestamp = 0

    async def authenticate(self) -> None:
        """Authenticate with the API and get access token."""
        _LOGGER.info("Starting authentication with Muller Intuis API")
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "password",
            "user_prefix": "muller",
            "scope": "read_muller write_muller",
            "username": self._username,
            "password": self._password,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with (
                asyncio.timeout(10),
                self._session.post(AUTH_URL, data=payload, headers=headers) as resp,
            ):
                data = await resp.json()
                self._access_token = data.get("access_token")
                if not self._access_token:
                    _LOGGER.error("Failed to get access token: %s", data)
                else:
                    self._token_timestamp = time.time()
                    _LOGGER.info("Successfully authenticated with Muller Intuis API")
        except Exception:
            _LOGGER.exception("Authentication error")

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid token, re-authenticating if expired."""
        current_time = time.time()

        # Check if we don't have a token or it's expired (1 hour = 3600 seconds)
        if (
            not self._access_token
            or current_time - self._token_timestamp >= TOKEN_EXPIRY
        ):
            if self._access_token:
                _LOGGER.info(
                    "Access token expired (age: %.1f seconds), re-authenticating",
                    current_time - self._token_timestamp,
                )
            await self.authenticate()

    async def get_homesdata(self) -> dict[str, Any]:
        """Get homesdata from API (no caching - called once during setup).

        Returns:
            Dictionary containing homes configuration data

        """
        _LOGGER.debug("Fetching fresh homesdata from API")
        await self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            async with self._session.get(f"{DATA_URL}", headers=headers) as resp:
                data = await resp.json()
                _LOGGER.debug("Successfully fetched homesdata")
                return data
        except Exception:
            _LOGGER.exception("Error fetching homesdata")
            raise

    async def get_homestatus(self, home_id: str) -> dict[str, Any]:
        """Get data for entity, using cached response if available.

        Args:
            home_id: The ID of the home to get status for

        Returns:
            Dictionary containing entity data

        """
        current_time = time.time()

        # Check if we have cached data and it's still valid
        if (
            self._homestatus_cached_data
            and current_time - self._homestatus_cache_timestamp < CACHE_EXPIRY
        ):
            _LOGGER.debug(
                "Using cached homestatus (age: %.1f seconds)",
                current_time - self._homestatus_cache_timestamp,
            )
            return self._homestatus_cached_data

        # Cache expired or empty, fetch fresh data
        _LOGGER.debug("Fetching fresh homestatus from API")
        await self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {"home_id": home_id}
        _LOGGER.debug("Homestatus homeid: %s", home_id)

        try:
            async with self._session.get(
                f"{STATUS_URL}", headers=headers, params=payload
            ) as resp:
                data = await resp.json()
                # Cache the response
                self._homestatus_cached_data = data
                self._homestatus_cache_timestamp = current_time
                _LOGGER.debug("Successfully fetched and cached fresh homestatus")
                return data
        except Exception:
            _LOGGER.exception("Error fetching data for homestatus")
            # Return cached data if available, even if expired
            if self._homestatus_cached_data:
                _LOGGER.debug("Returning expired cached data for homestatus")
                return self._homestatus_cached_data
            raise

    def clear_cache(self) -> None:
        """Clear the cached homestatus data."""
        self._homestatus_cached_data = {}
        self._homestatus_cache_timestamp = 0
        _LOGGER.debug("Homestatus cache cleared")

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            _LOGGER.debug("Closing API session")
            await self._session.close()

    async def set_temperature(
        self, home_id: str, room_id: str, temperature: float
    ) -> dict[str, Any]:
        """Set temperature for entity.

        Args:
            home_id: The ID of the home
            room_id: The ID of the room
            temperature: Target temperature

        Returns:
            API response

        """
        _LOGGER.info("Setting temperature for %s to %.1f°C", room_id, temperature)
        await self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "home": {
                "id": home_id,
                "rooms": [
                    {
                        "id": room_id,
                        "therm_setpoint_mode": "manual",
                        "therm_setpoint_temperature": temperature,
                    }
                ],
            }
        }
        _LOGGER.info("Data structure is %s", data)

        async with self._session.post(
            SETSTATE_URL, headers=headers, data=json.dumps(data)
        ) as resp:
            # Clear cache after making changes
            self.clear_cache()
            _LOGGER.debug("Temperature set successfully, cache cleared")
            resp = await resp.json()
            _LOGGER.debug("Response from set_temperature: %s", resp)
            return resp

    async def set_mode(self, home_id: str, room_id: str, mode: str) -> dict[str, Any]:
        """Set mode for entity.

        Args:
            home_id: ID of the home
            room_id: ID of the room
            mode: HVAC mode

        Returns:
            API response

        """
        _LOGGER.info("Setting HVAC mode for room %s to %s", room_id, mode)
        await self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "home": {
                "id": home_id,
                "rooms": [
                    {
                        "id": room_id,
                        "therm_setpoint_mode": mode,
                    }
                ],
            }
        }
        async with self._session.post(
            SETSTATE_URL, headers=headers, data=json.dumps(data)
        ) as resp:
            # Clear cache after making changes
            self.clear_cache()
            _LOGGER.debug("HVAC mode set successfully, cache cleared")
            resp = await resp.json()
            _LOGGER.debug("Response from set_mode: %s", resp)
            return resp

    async def get_measure(
        self,
        home_id: str,
        roomlist: list[str],
        bridgelist: list[str],
        start_date: int,
        end_date: int,
    ) -> dict[str, Any]:
        """Get historic power/energy measurement data.

        Args:
            home_id: The home ID to get measurements for
            roomlist: List of room IDs to get measurements for
            bridgelist: List of bridge IDs corresponding to rooms
            start_date: Start timestamp as integer (Unix timestamp)
            end_date: End timestamp as integer (Unix timestamp)

        Returns:
            API response containing historic energy measurements

        """
        _LOGGER.debug(
            "Getting measurement data for home %s from %s to %s",
            home_id,
            start_date,
            end_date,
        )
        _LOGGER.debug("roomlist: %s", roomlist)
        _LOGGER.debug("bridgelist: %s", bridgelist)

        await self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        data = {
            "date_begin": int(start_date),
            "date_end": int(end_date),
            "scale": "1hour",
            "step_time": 60,
            "app_identifier": "app_muller",
            "real_time": True,
            "home": {"id": home_id, "rooms": []},
        }
        types = [
            "sum_energy_elec_hot_water",
            "sum_energy_elec_heating",
            "sum_energy_elec",
            "sum_energy_elec$0",
            "sum_energy_elec$1",
            "sum_energy_elec$2",
        ]
        # Iterate through roomlist and bridgelist in parallel
        for room_id, bridge_id in zip(roomlist, bridgelist, strict=True):
            data["home"]["rooms"].append(
                {"id": str(room_id), "bridge": str(bridge_id), "type": types}
            )

        _LOGGER.debug("Final API data structure: %s", data)

        try:
            async with self._session.post(
                MEASURE_URL, headers=headers, data=json.dumps(data)
            ) as resp:
                # Clear cache after making changes
                response_data = await resp.json()
                _LOGGER.debug(
                    "Received measurement data: %s keys and full response %s",
                    list(response_data.keys())
                    if isinstance(response_data, dict)
                    else "not a dict",
                    response_data,
                )
                return response_data

        except Exception as err:
            _LOGGER.error("Error fetching measurement data: %s", err)
            raise
