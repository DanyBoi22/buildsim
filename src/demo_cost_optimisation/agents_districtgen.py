"""Agents for districtgenerator-backed scenarios.

Differences to the synthetic agents in `agents.py`:
  * separate COPs for space heating and hot water (hot water needs ~60 C flow
    temperature vs. ~35 C for space heating, so one COP overstates the heat pump)
  * investment enters as an annuity per year, not as a lump sum every year
  * the building carries its districtgenerator scenario parameters, and its
    efficiency class is derived from the generated demand instead of drawn at random
  * PV is carried but not yet part of the cost calculation

The decision rules themselves are imported from `agents.py` -- Type A/B/C mean
the same thing regardless of where the demand data comes from.
"""

from dataclasses import dataclass, field

import mesa

from agents import DECISION_RULES, AgentType
from model import DistrictModel
from energy_profiles import (
    BuildingTimeseries,
    EnergyProfile,
    HouseholdShareProfile,
    efficiency_class_for_demand,
)
from price_model import PriceModel

GAS_BOILER_EFFICIENCY = 0.90
COP_SPACE_HEAT = 3.5  # ~35 C flow
COP_DHW = 2.5  # ~60 C flow


def annuity(investment: float, interest_rate: float, lifetime_years: int) -> float:
    """Constant yearly payment that repays `investment` over `lifetime_years`.

    The current synthetic agent adds the full investment to `c_after` in every
    year, which mixes a one-off stock with a yearly flow. This converts it to
    the yearly flow the cost comparison actually needs.
    """
    if lifetime_years <= 0:
        raise ValueError("lifetime_years must be positive")
    if interest_rate == 0:
        return investment / lifetime_years
    q = 1 + interest_rate
    return investment * (q**lifetime_years * interest_rate) / (q**lifetime_years - 1)


@dataclass
class BuildingSpec:
    """One districtgenerator scenario row plus the parameters the simulation
    needs on top of it.

    The field names mirror the districtgenerator scenario CSV so the same
    object can drive both the profile generation and the simulation.
    """

    # districtgenerator scenario columns
    id: int
    building: str = "MFH"  # SFH, TH, MFH, AB, ...
    year: int = 1970
    construction_type: int = 1  # 0 lightweight, 1 medium, 2 heavyweight
    retrofit: int = 0  # 0 existing, 1 usual, 2 advanced
    area: float = 560.0  # reference floor area of the whole building, m^2
    night_setback: int = 0
    heating: str = "BOI"  # heat generator assumed by the generator
    EV: float = 0.0
    fTES: float = 35.0
    fBAT: float = 0.0
    fPV: float = 0.0
    fSTC: float = 0.0
    gammaPV: float = 0.0
    EV_charging: str = "on-demand"

    # simulation-only parameters
    n_flats: int = 8
    demand_csv: str | None = None  # districtgenerator output for this building
    pv_csv: str | None = None

    SCENARIO_COLUMNS = (
        "id", "building", "year", "construction_type", "retrofit", "area",
        "night_setback", "heating", "EV", "fTES", "fBAT", "fPV", "fSTC",
        "gammaPV", "EV_charging",
    )

    def to_scenario_row(self) -> dict:
        """The subset of fields that go into the districtgenerator scenario CSV."""
        return {column: getattr(self, column) for column in self.SCENARIO_COLUMNS}

    @property
    def area_per_flat(self) -> float:
        """The districtgenerator splits a building's floor area equally across
        its flats, so this is a single number rather than a distribution."""
        return self.area / self.n_flats


class DistrictGenHouseholdAgent(mesa.Agent):
    def __init__(
        self,
        model: mesa.Model,
        agent_type: AgentType,
        energy_profile: EnergyProfile,
        price_model: PriceModel,
        area_m2: float,
        gas_efficiency: float = GAS_BOILER_EFFICIENCY,
        cop_space_heat: float = COP_SPACE_HEAT,
        cop_dhw: float = COP_DHW,
        annual_investment_cost: float = 0.0,
    ):
        super().__init__(model)
        self.agent_type = agent_type
        self.energy_profile = energy_profile
        self.price_model = price_model
        self.area_m2 = area_m2

        self.gas_efficiency = gas_efficiency
        self.cop_space_heat = cop_space_heat
        self.cop_dhw = cop_dhw
        self.annual_investment_cost = annual_investment_cost

        self.c_before = 0.0
        self.c_after = 0.0
        self.wants_transformation = False

    def step(self):
        year = self.model.current_year
        elec_price = self.price_model.electricity_price(year)
        gas_price = self.price_model.gas_price(year)

        elec_demand = self.energy_profile.annual_electricity_demand()
        space_heat = self.energy_profile.annual_space_heat_demand()
        dhw = self.energy_profile.annual_dhw_demand()

        # Before: gas boiler covers space heating and hot water alike.
        # districtgenerator heat demand is useful heat (5R1C/7R2C model), so
        # dividing by the boiler efficiency is correct and not double counting.
        gas_consumption = (space_heat + dhw) / self.gas_efficiency
        self.c_before = elec_demand * elec_price + gas_consumption * gas_price

        # After: heat pump, with a separate COP per temperature level.
        hp_consumption = space_heat / self.cop_space_heat + dhw / self.cop_dhw
        self.c_after = ((elec_demand + hp_consumption) * elec_price + self.annual_investment_cost)
        # PV is deliberately absent here: annual totals cannot express
        # self-consumption. See EnergyProfile.annual_pv_generation.

        self.wants_transformation = DECISION_RULES[self.agent_type](self.c_before, self.c_after)


class DistrictGenBuildingAgent(mesa.Agent):
    def __init__(
        self,
        model: mesa.Model,
        spec: BuildingSpec,
        timeseries: BuildingTimeseries,
        majority_threshold: float = 0.5,
    ):
        super().__init__(model)
        self.spec = spec
        self.timeseries = timeseries
        self.majority_threshold = majority_threshold
        self.transformed = False
        self.last_yes_share = 0.0
        self.households: list[DistrictGenHouseholdAgent] = []

    @property
    def specific_heat_demand(self) -> float:
        """kWh/(m^2*a), space heating only -- the quantity the Energieausweis
        classes are defined on."""
        return self.timeseries.space_heat_kwh / self.spec.area

    @property
    def efficiency_class(self) -> str:
        """Derived from the generated demand rather than drawn at random, so it
        follows from year / retrofit / construction type via TABULA."""
        return efficiency_class_for_demand(self.specific_heat_demand)

    def step(self):
        if self.transformed:
            return

        yes_votes = sum(h.wants_transformation for h in self.households)
        self.last_yes_share = yes_votes / len(self.households)

        if self.last_yes_share >= self.majority_threshold:
            self.transformed = True

    @property
    def failed_this_year(self) -> bool:
        """Willingness existed (>0% yes) but the majority threshold was not
        reached -- the classic collective-action failure case."""
        return (not self.transformed) and self.last_yes_share > 0


def build_districtgen_population(
    #model: mesa.Model,
    model: DistrictModel,
    specs: list[BuildingSpec],
    agent_type_shares: dict[AgentType, float] | None = None,
    demand_factor_std: float = 0.0,
    investment_per_flat: float = 10000.0,
    interest_rate: float = 0.03,
    lifetime_years: int = 20,
    **household_kwargs,
) -> list[DistrictGenBuildingAgent]:
    """Population builder for districtgenerator scenarios.

    `demand_factor_std` adds a lognormal spread to each household's electricity
    and hot water demand. Leave it at 0 for a strict proportional split -- but
    see `HouseholdShareProfile` for why that makes every household of the same
    type vote identically.
    """
    agent_type_shares = agent_type_shares or {
        AgentType.A: 1 / 3, AgentType.B: 1 / 3, AgentType.C: 1 / 3
    }
    yearly_investment = annuity(investment_per_flat, interest_rate, lifetime_years)

    buildings = []
    for spec in specs:
        if spec.demand_csv is None:
            raise ValueError(f"BuildingSpec id={spec.id} has no demand_csv")
        timeseries = BuildingTimeseries.from_csv(spec.demand_csv, pv_path=spec.pv_csv)

        building = DistrictGenBuildingAgent(
            model, spec=spec, timeseries=timeseries,
            majority_threshold=model.majority_threshold,
        )
        buildings.append(building)

        area_share = 1.0 / spec.n_flats
        for _ in range(spec.n_flats):
            agent_type = model.random.choices(
                list(agent_type_shares.keys()),
                weights=list(agent_type_shares.values()), k=1,
            )[0]
            demand_factor = (
                model.random.lognormvariate(0.0, demand_factor_std)
                if demand_factor_std > 0 else 1.0
            )
            profile = HouseholdShareProfile(
                timeseries, area_share=area_share, demand_factor=demand_factor
            )
            household = DistrictGenHouseholdAgent(
                model,
                agent_type=agent_type,
                energy_profile=profile,
                price_model=model.price_model,
                area_m2=spec.area_per_flat,
                annual_investment_cost=yearly_investment,
                **household_kwargs,
            )
            building.households.append(household)

    return buildings
