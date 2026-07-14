"""Energy demand profiles for households.

The model only ever calls `annual_electricity_demand()` and `annual_heat_demand()`. 
Today these are backed by simple annual values (`AnnualValueProfile`). 
Later, a standard-load-profile implementation can back the same interface with real 15-min time series,
it would just sum its own series in these two methods, and expose extra methods (e.g. `timeseries_*()`)
for whatever needs the resolved profile (e.g. PV self-consumption). 
No other module needs to change.
"""

from abc import ABC, abstractmethod
import random

# Representative annual heat demand per energy efficiency class, kWh/(m^2*a).
# Approximate midpoints of typical German Energieausweis bands - placeholder values
EFFICIENCY_CLASS_KWH_PER_M2 = {
    "A": 40,
    "B": 65,
    "C": 85,
    "D": 115,
    "E": 145,
    "F": 180,
    "G": 220,
    "H": 260,
}

DEFAULT_ELECTRICITY_DEMAND_MEAN = 3000.0  # kWh/a, baseline household electricity use
DEFAULT_ELECTRICITY_DEMAND_STD = 300.0


def heat_demand_for_class(efficiency_class: str, area_m2: float) -> float:
    """Annual heat demand (kWh/a) for a household of `area_m2` living space
    in a building of the given efficiency class."""
    return EFFICIENCY_CLASS_KWH_PER_M2[efficiency_class] * area_m2

def electricity_demand_for_household_gauss(mean: float | None = None, std: float | None = None) -> float:
    """Annual electricity demand (kWh/a) for a household, drawn from a normal distribution."""
    mean = mean if mean is not None else DEFAULT_ELECTRICITY_DEMAND_MEAN
    std = std if std is not None else DEFAULT_ELECTRICITY_DEMAND_STD
    return round(random.gauss(mean, std), 1)  # round to 1 decimal place, e.g. 3000.0 kWh/a

class EnergyProfile(ABC):
    """Interface every household energy profile implementation must satisfy."""

    @abstractmethod
    def annual_electricity_demand(self) -> float:
        """kWh/year of household electricity demand (excludes heating)."""

    @abstractmethod
    def annual_heat_demand(self) -> float:
        """kWh/year of heat demand (space heating + hot water)."""


class AnnualValueProfile(EnergyProfile):
    """Simplest implementation: fixed annual kWh values."""

    def __init__(self, electricity_kwh: float, heat_kwh: float):
        self._electricity_kwh = electricity_kwh
        self._heat_kwh = heat_kwh

    def annual_electricity_demand(self) -> float:
        return self._electricity_kwh

    def annual_heat_demand(self) -> float:
        return self._heat_kwh
