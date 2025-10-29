"""API client for Muller Intuitiv heating system."""

import asyncio
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

AUTH_URL = "https://app.muller-intuitiv.net/oauth2/token"
DATA_URL = "https://app.muller-intuitiv.net/api/homesdata"
STATUS_URL = "https://app.muller-intuitiv.net/syncapi/v1/homestatus"
CONTROL_URL = "https://app.muller-intuitiv.net/syncapi/v1/getconfigs"

# Cache expiry time in seconds (20 seconds)
CACHE_EXPIRY = 20


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
                    _LOGGER.info("Successfully authenticated with Muller Intuis API")
        except Exception:
            _LOGGER.exception("Authentication error")

    async def get_homesdata(self) -> dict[str, Any]:
        """Get homesdata from API (no caching - called once during setup).

        Returns:
            Dictionary containing homes configuration data

        """
        _LOGGER.debug("Fetching fresh homesdata from API")
        if not self._access_token:
            await self.authenticate()

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
            None

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
        if not self._access_token:
            await self.authenticate()

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
        self, entity_name: str, temperature: float
    ) -> dict[str, Any]:
        """Set temperature for entity.

        Args:
            entity_name: Name of the entity
            temperature: Target temperature

        Returns:
            API response

        """
        _LOGGER.info("Setting temperature for %s to %.1f°C", entity_name, temperature)
        headers = {"Authorization": f"Bearer {self._access_token}"}
        payload = {"device": entity_name, "target_temperature": temperature}
        async with self._session.post(
            CONTROL_URL, headers=headers, json=payload
        ) as resp:
            # Clear cache after making changes
            self.clear_cache()
            _LOGGER.debug("Temperature set successfully, cache cleared")
            return await resp.json()

    async def set_mode(self, entity_name: str, mode: str) -> dict[str, Any]:
        """Set mode for entity.

        Args:
            entity_name: Name of the entity
            mode: HVAC mode

        Returns:
            API response

        """
        _LOGGER.info("Setting HVAC mode for %s to %s", entity_name, mode)
        headers = {"Authorization": f"Bearer {self._access_token}"}
        payload = {"device": entity_name, "hvac_mode": mode}
        async with self._session.post(
            CONTROL_URL, headers=headers, json=payload
        ) as resp:
            # Clear cache after making changes
            self.clear_cache()
            _LOGGER.debug("HVAC mode set successfully, cache cleared")
            return await resp.json()
