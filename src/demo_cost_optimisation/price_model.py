"""Energy price model.

PricePath is the interface the model relies on for retrieving price development information. 
DeterministicPricePath covers a fixed scenario table (e.g. from a CSV/list of Ct/kWh values). 
A future stochastic model can be easily implemented.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class PriceModel(ABC):
    @abstractmethod
    def electricity_price(self, year: int) -> float:
        """EUR/kWh in simulation year `year` (0-indexed)."""

    @abstractmethod
    def gas_price(self, year: int) -> float:
        """EUR/kWh in simulation year `year` (0-indexed)."""


class DeterministicPriceModel(PriceModel):
    """Fixed per-year price scenario. If the simulation runs longer than the
    given data, the last known value is held constant."""

    def __init__(self, electricity_prices: Sequence[float], gas_prices: Sequence[float]):
        self._electricity = list(electricity_prices)
        self._gas = list(gas_prices)

    def electricity_price(self, year: int) -> float:
        return self._electricity[min(year, len(self._electricity) - 1)]

    def gas_price(self, year: int) -> float:
        return self._gas[min(year, len(self._gas) - 1)]
