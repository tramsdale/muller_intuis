"""Services for Muller Intuis integration."""

from __future__ import annotations

import logging

from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)


async def async_clear_statistics(hass: HomeAssistant, call: ServiceCall) -> None:
    """Clear all Muller Intuis statistics from the database."""
    _LOGGER.info("Clearing all Muller Intuis statistics")

    try:
        instance = get_instance(hass)

        # SQL to delete all muller_intuis statistics
        await instance.async_add_executor_job(
            _delete_muller_intuis_statistics,
            instance,
        )

        _LOGGER.info("Successfully cleared all Muller Intuis statistics")

    except Exception as err:
        _LOGGER.error("Failed to clear Muller Intuis statistics: %s", err)
        raise


def _delete_muller_intuis_statistics(instance) -> None:
    """Delete Muller Intuis statistics from database."""
    with instance.get_session() as session:
        # Delete statistics data
        session.execute(
            "DELETE FROM statistics WHERE metadata_id IN "
            "(SELECT id FROM statistics_meta WHERE statistic_id LIKE 'muller_intuis:%')"
        )

        # Delete short-term statistics data
        session.execute(
            "DELETE FROM statistics_short_term WHERE metadata_id IN "
            "(SELECT id FROM statistics_meta WHERE statistic_id LIKE 'muller_intuis:%')"
        )

        # Delete metadata
        session.execute(
            "DELETE FROM statistics_meta WHERE statistic_id LIKE 'muller_intuis:%'"
        )

        session.commit()
