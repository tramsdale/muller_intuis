"""Sensor utilities for Muller Intuis integration."""

from datetime import timedelta

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.util import dt as dt_util


async def backfill_energy(hass, name, energy_kwh: float, hours_ago: int):
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
