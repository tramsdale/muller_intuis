"""Integration for Muller Intuis climate systems."""

from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform


from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, DOMAIN
from .coordinator import (
    MullerIntuisConfigCoordinator,
    MullerIntuisDataUpdateCoordinator,
    MullerIntuisEnergyCoordinator,
)
from .muller_intuisAPI import muller_intuisAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]

# YAML configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Muller Intuis integration from YAML configuration."""
    if DOMAIN not in config:
        return True

    _LOGGER.info("Setting up Muller Intuis integration from YAML configuration")

    conf = config[DOMAIN]

    # Create aiohttp session
    session = aiohttp.ClientSession()

    # Initialize API with YAML config parameters
    api = muller_intuisAPI(
        session=session,
        username=conf[CONF_USERNAME],
        password=conf[CONF_PASSWORD],
        client_id=conf[CONF_CLIENT_ID],
        client_secret=conf[CONF_CLIENT_SECRET],
    )

    try:
        await api.authenticate()
        _LOGGER.info("Successfully authenticated with Muller Intuis API")
    except (aiohttp.ClientError, TimeoutError) as err:
        await session.close()
        _LOGGER.error("Unable to authenticate with Muller Intuis API: %s", err)
        return False

    # Create config coordinator and fetch initial configuration
    config_coordinator = MullerIntuisConfigCoordinator(hass, None, api)
    _LOGGER.info("Created config coordinator for muller_intuis setup")

    try:
        await config_coordinator.async_get_config_data()
        _LOGGER.info("Successfully fetched configuration data from API")
    except (aiohttp.ClientError, TimeoutError) as err:
        await session.close()
        _LOGGER.error("Failed to fetch configuration data: %s", err)
        return False

    # Create data update coordinator for regular polling
    data_coordinator = MullerIntuisDataUpdateCoordinator(
        hass, None, api, config_coordinator
    )
    _LOGGER.info("Created data update coordinator for muller_intuis setup")

    # Fetch initial status data
    try:
        await data_coordinator._async_update_data()
        _LOGGER.info("Successfully fetched initial status data from API")
    except (aiohttp.ClientError, TimeoutError) as err:
        await session.close()
        _LOGGER.error("Failed to fetch initial status data: %s", err)
        return False

    # Create energy coordinator for historic power data
    energy_coordinator = MullerIntuisEnergyCoordinator(hass, api, config_coordinator)
    _LOGGER.info("Created energy coordinator for muller_intuis setup")

    # Store coordinators in hass.data first
    hass.data.setdefault(DOMAIN, {})["yaml_setup"] = {
        "config_coordinator": config_coordinator,
        "data_coordinator": data_coordinator,
        "energy_coordinator": energy_coordinator,
    }

    # Fetch initial energy data (optional, can fail if API doesn't support it yet)
    try:
        await energy_coordinator.async_config_entry_first_refresh()
        _LOGGER.info(
            "Successfully fetched initial energy measurement data from YAML setup"
        )
    except Exception as err:
        _LOGGER.warning(
            "Failed to fetch initial energy data from YAML setup, will retry later: %s",
            err,
        )

    # Load platforms using modern approach
    hass.async_create_task(async_load_platform(hass, "climate", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    hass.async_create_task(async_load_platform(hass, "water_heater", DOMAIN, {}, config))
    _LOGGER.info("Muller Intuis integration setup completed successfully")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Muller Intuis from a config entry."""
    # Create aiohttp session
    session = aiohttp.ClientSession()

    # Initialize API with config parameters
    api = muller_intuisAPI(
        session=session,
        username=entry.data["username"],
        password=entry.data["password"],
        client_id=entry.data["client_id"],
        client_secret=entry.data["client_secret"],
    )

    try:
        await api.authenticate()
    except Exception as err:
        await session.close()
        raise ConfigEntryNotReady(f"Unable to authenticate: {err}") from err

    # Create config coordinator and fetch configuration
    config_coordinator = MullerIntuisConfigCoordinator(hass, entry, api)
    try:
        await config_coordinator.async_get_config_data()
    except Exception as err:
        await session.close()
        raise ConfigEntryNotReady(f"Unable to fetch configuration: {err}") from err

    # Create data update coordinator
    data_coordinator = MullerIntuisDataUpdateCoordinator(
        hass, entry, api, config_coordinator
    )

    # Fetch initial status data
    await data_coordinator.async_config_entry_first_refresh()

    # Create energy coordinator for historic power data
    energy_coordinator = MullerIntuisEnergyCoordinator(hass, api, config_coordinator)

    # Store coordinators in hass.data first (before attempting first refresh)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "config_coordinator": config_coordinator,
        "data_coordinator": data_coordinator,
        "energy_coordinator": energy_coordinator,
    }

    # Fetch initial energy data (optional, can fail if API doesn't support it yet)
    try:
        await energy_coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Successfully fetched initial energy measurement data")
    except Exception as err:
        _LOGGER.warning(
            "Failed to fetch initial energy data, will retry later: %s", err
        )

    # Forward setup to platforms
    _LOGGER.info("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Platform setup completed successfully")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinators = hass.data[DOMAIN].pop(entry.entry_id)
        # Close the aiohttp session
        await coordinators["data_coordinator"].api.close()

    return unload_ok
