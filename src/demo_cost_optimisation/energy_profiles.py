"""Energy demand profiles for households.

Interface: `annual_electricity_demand()`, `annual_space_heat_demand()` and
`annual_dhw_demand()`. `annual_heat_demand()` is the sum of the latter two and
is provided by the base class -- agents that use a single COP can keep calling
it, agents that use separate COPs for space heating and hot water call the two
parts individually.

Two implementations:
  * `AnnualValueProfile`    -- synthetic annual kWh values (unchanged behaviour)
  * `HouseholdShareProfile` -- one household's share of a districtgenerator
                               building time series (see `BuildingTimeseries`)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import random
import pandas as pd

# Representative annual heat demand per energy efficiency class, kWh/(m^2*a).
# Approximate midpoints of typical German Energieausweis bands - placeholder values
EFFICIENCY_CLASS_KWH_PER_M2 = {
    "A+": 30,
    "A": 50,
    "B": 75,
    "C": 100,
    "D": 130,
    "E": 160,
    "F": 200,
    "G": 250,
    "H": 400,
}

DEFAULT_ELECTRICITY_DEMAND_MEAN = 3000.0  # kWh/a, baseline household electricity use
DEFAULT_ELECTRICITY_DEMAND_STD = 300.0


def heat_demand_for_class(efficiency_class: str, area_m2: float) -> float:
    """Annual heat demand (kWh/a) for a household of `area_m2` living space
    in a building of the given efficiency class."""
    return EFFICIENCY_CLASS_KWH_PER_M2[efficiency_class] * area_m2


def efficiency_class_for_demand(kwh_per_m2: float) -> str:
    """Inverse of `heat_demand_for_class`: map a specific heat demand to the
    class it falls into. Used for districtgenerator buildings, where the class
    is a *result* of year / retrofit / construction type, not an input."""
    for eff_class, upper_bound in EFFICIENCY_CLASS_KWH_PER_M2.items():
        if kwh_per_m2 <= upper_bound:
            return eff_class
    return "H"


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
    def annual_space_heat_demand(self) -> float:
        """kWh/year of space heating demand."""

    @abstractmethod
    def annual_dhw_demand(self) -> float:
        """kWh/year of domestic hot water demand."""

    def annual_heat_demand(self) -> float:
        """kWh/year of total heat demand (space heating + hot water)."""
        return self.annual_space_heat_demand() + self.annual_dhw_demand()

    def annual_pv_generation(self) -> float:
        """kWh/year of PV generation attributed to this household.

        0 by default -- PV is not part of the cost calculation yet. Note that
        annual totals will not be enough for PV: self-consumption depends on
        the coincidence of generation and demand, which only shows up at 15-min
        resolution. Extend `BuildingTimeseries` when you get there.
        """
        return 0.0


class AnnualValueProfile(EnergyProfile):
    """Simplest implementation: fixed annual kWh values.

    `heat_kwh` is treated as space heating and `dhw_kwh` defaults to 0, so
    existing synthetic scenarios behave exactly as before.
    """

    def __init__(self, electricity_kwh: float, heat_kwh: float, dhw_kwh: float = 0.0):
        self._electricity_kwh = electricity_kwh
        self._heat_kwh = heat_kwh
        self._dhw_kwh = dhw_kwh

    def annual_electricity_demand(self) -> float:
        return self._electricity_kwh

    def annual_space_heat_demand(self) -> float:
        return self._heat_kwh

    def annual_dhw_demand(self) -> float:
        return self._dhw_kwh


# --------------------------------------------------------------------------
# districtgenerator time series
# --------------------------------------------------------------------------

# Column names in the districtgenerator demand CSVs. All values are in Watt.
DG_COLUMNS = {"electricity": "elec", "space_heat": "heating", "dhw": "dhw"}
DG_SEPARATOR = ";"


@dataclass
class BuildingTimeseries:
    """Annual energy totals (kWh) for one districtgenerator building.

    The generator writes one CSV per building at building level: `elec` and
    `dhw` are summed over all flats, `heating` comes from the building's
    thermal model and exists only at building level by construction.

    Only annual totals are kept, since that is all the cost function needs.
    The raw series is deliberately dropped -- add it when PV self-consumption
    requires sub-annual resolution.
    """

    electricity_kwh: float
    space_heat_kwh: float
    dhw_kwh: float
    pv_generation_kwh: float = 0.0
    source_path: str | None = None

    @property
    def total_heat_kwh(self) -> float:
        return self.space_heat_kwh + self.dhw_kwh

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        columns: dict[str, str] | None = None,
        separator: str = DG_SEPARATOR,
        pv_path: str | Path | None = None,
        pv_column: str = "pv",
    ) -> "BuildingTimeseries":
        """Read a districtgenerator demand CSV and integrate it to annual kWh.

        The `timestep` column holds hours; its spacing gives the resolution, so
        both the 15-min and the minutely exports work without a flag.
        PV lives in a separate file and is read only if `pv_path` is given.
        """
        columns = columns or DG_COLUMNS
        df = pd.read_csv(path, sep=separator)
        timestep_hours = _timestep_hours(df)

        totals = cls(
            electricity_kwh=_integrate(df[columns["electricity"]], timestep_hours),
            space_heat_kwh=_integrate(df[columns["space_heat"]], timestep_hours),
            dhw_kwh=_integrate(df[columns["dhw"]], timestep_hours),
            source_path=str(path),
        )

        if pv_path is not None:
            pv_df = pd.read_csv(pv_path, sep=separator)
            totals.pv_generation_kwh = _integrate(pv_df[pv_column], _timestep_hours(pv_df))
        return totals


def _timestep_hours(df: pd.DataFrame, timestep_column: str = "timestep") -> float:
    """Resolution of the series in hours, taken from the timestep column."""
    steps = df[timestep_column].diff().dropna()
    return float(steps.iloc[0])


def _integrate(power_w: pd.Series, timestep_hours: float) -> float:
    """Watt series held constant over each step -> annual energy in kWh."""
    return float(power_w.sum() * timestep_hours / 1000.0)


class HouseholdShareProfile(EnergyProfile):
    """One household's share of a building-level `BuildingTimeseries`.

    Space heat is split by living area share, which matches both the physics
    (shared thermal envelope) and the usual German practice of allocating
    heating costs by floor area.

    Electricity and hot water use the same share, scaled by `demand_factor`.
    That factor matters: with an identical share for every flat, c_before and
    c_after both scale by that share, the relative saving comes out identical
    across the building, and every household of the same type votes the same
    way -- the vote degenerates. The districtgenerator does compute per-flat
    electricity and DHW internally (Stromspiegel +-10%, occupants per flat) and
    only sums them on output, so the proper fix is to extract those. Until
    then, `demand_factor` is the explicit, documented stand-in.
    """

    def __init__(
        self,
        building_timeseries: BuildingTimeseries,
        area_share: float,
        demand_factor: float = 1.0,
    ):
        if not 0 < area_share <= 1:
            raise ValueError(f"area_share must be in (0, 1], got {area_share}")
        self._ts = building_timeseries
        self._area_share = area_share
        self._demand_factor = demand_factor

    def annual_electricity_demand(self) -> float:
        return self._ts.electricity_kwh * self._area_share * self._demand_factor

    def annual_space_heat_demand(self) -> float:
        return self._ts.space_heat_kwh * self._area_share

    def annual_dhw_demand(self) -> float:
        return self._ts.dhw_kwh * self._area_share * self._demand_factor

    def annual_pv_generation(self) -> float:
        # Placeholder allocation by area share. The real allocation key is a
        # regulatory choice (static by area vs. dynamic by consumption), not a
        # technical one -- make it an explicit model parameter once PV enters
        # the cost calculation.
        return self._ts.pv_generation_kwh * self._area_share
