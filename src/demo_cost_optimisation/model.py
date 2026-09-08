"""District model: runs the yearly step (households vote -> buildings decide
-> collect data). One model step = one year.

The model itself is agent-class agnostic. Which agents populate it is decided
by the `population_builder` passed in: `build_synthetic_population` for the
generated scenarios, `build_districtgen_population` (in `agents_districtgen`)
for districtgenerator profiles. A builder takes the model and returns the list
of building agents, each with its households already attached.
"""

from collections.abc import Callable

import mesa
import pandas as pd
from mesa.agent import AgentSet

from agents import AgentType, BuildingAgent, HouseholdAgent
from energy_profiles import (
    EFFICIENCY_CLASS_KWH_PER_M2,
    AnnualValueProfile,
    electricity_demand_for_household_gauss,
    heat_demand_for_class,
)
from price_model import DeterministicPriceModel, PriceModel


def build_synthetic_population(
    model: "DistrictModel",
    n_buildings: int = 8,
    households_per_building: int = 8,
    agent_type_shares: dict[AgentType, float] | None = None,
    efficiency_classes: list[str] | None = None,
    electricity_demand_mean: float | None = 3000.0,
    electricity_demand_std: float | None = 300.0,
    average_household_area_m2: float = 70.0,
    **household_kwargs,
) -> list[BuildingAgent]:
    """The original synthetic population: efficiency class drawn per building,
    heat from the class table, electricity drawn per household."""
    agent_type_shares = agent_type_shares or {
        AgentType.A: 1 / 3, AgentType.B: 1 / 3, AgentType.C: 1 / 3
    }
    efficiency_classes = efficiency_classes or list(EFFICIENCY_CLASS_KWH_PER_M2)

    buildings = []
    for _ in range(n_buildings):
        # Efficiency class is assigned per building. All households in the same
        # building share the same efficiency class.
        eff_class = model.random.choice(efficiency_classes)

        building = BuildingAgent(
            model, efficiency_class=eff_class,
            majority_threshold=model.majority_threshold,
        )
        buildings.append(building)

        for _ in range(households_per_building):
            # introduce some variability in household sizes
            household_area_m2 = round(model.random.gauss(average_household_area_m2, 10.0), 1)
            agent_type = model.random.choices(
                list(agent_type_shares.keys()),
                weights=list(agent_type_shares.values()), k=1,
            )[0]

            heat_kwh = heat_demand_for_class(efficiency_class=eff_class, area_m2=household_area_m2)
            elec_kwh = electricity_demand_for_household_gauss(
                mean=electricity_demand_mean, std=electricity_demand_std
            )
            profile = AnnualValueProfile(electricity_kwh=elec_kwh, heat_kwh=heat_kwh)

            household = HouseholdAgent(
                model, agent_type=agent_type, energy_profile=profile,
                price_model=model.price_model, area_m2=household_area_m2,
                **household_kwargs,
            )
            building.households.append(household)

    return buildings


class DistrictModel(mesa.Model):
    def __init__(
        self,
        population_builder: Callable[["DistrictModel"], list] | None = None,
        majority_threshold: float = 0.7,  # 0.5 / 0.7 / 1.0 -> the three variants
        price_model: PriceModel | None = None,
        seed=None,
    ):
        super().__init__(seed=seed)

        self.majority_threshold = majority_threshold
        self.price_model = price_model or DeterministicPriceModel(
            electricity_prices=[0.35], gas_prices=[0.12]
        )
        self.current_year = 0

        # Builders read majority_threshold and price_model off the model, so
        # they must run after those are set.
        builder = population_builder or build_synthetic_population
        self.buildings = builder(self)
        self.households = [h for b in self.buildings for h in b.households]

        # Explicit sets instead of agents_by_type: that dict keys on the exact
        # concrete class, so hardcoding it would break for the districtgenerator
        # agents.
        self._household_set = AgentSet(self.households, random=self.random)
        self._building_set = AgentSet(self.buildings, random=self.random)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "share_transformed": lambda m: sum(b.transformed for b in m.buildings) / len(m.buildings),
                "share_failed": lambda m: sum(b.failed_this_year for b in m.buildings) / len(m.buildings),
            },
            agenttype_reporters={
                type(self.buildings[0]): {
                    "transformed": "transformed",
                    "yes_share": "last_yes_share",
                    "efficiency_class": "efficiency_class",
                },
                type(self.households[0]): {
                    "agent_type": lambda a: a.agent_type.value,
                    "wants_transformation": "wants_transformation",
                    "c_before": "c_before",
                    "c_after": "c_after",
                },
            },
        )

    def step(self):
        self._household_set.shuffle_do("step")
        self._building_set.do("step")
        self.datacollector.collect(self)
        self.current_year += 1

    def building_overview(self) -> pd.DataFrame:
        """One row per building: static specs + current status."""
        return pd.DataFrame([
            {
                "building_id": b.unique_id,
                "efficiency_class": b.efficiency_class,
                "majority_threshold": b.majority_threshold,
                "n_households": len(b.households),
                "avg_area_m2": sum(h.area_m2 for h in b.households) / len(b.households) if b.households else 0,
                "transformed": b.transformed,
                "yes_share": b.last_yes_share,
            }
            for b in self.buildings
        ])

    def household_overview(self) -> pd.DataFrame:
        """One row per household: building assignment + specs.

        can be filtered/grouped directly, e.g. `df.groupby(["efficiency_class", "agent_type"])`.
        """
        return pd.DataFrame([
            {
                "household_id": h.unique_id,
                "building_id": b.unique_id,
                "efficiency_class": b.efficiency_class,
                "agent_type": h.agent_type.value,
                "area_m2": h.area_m2,
                "elec_kwh": round(h.energy_profile.annual_electricity_demand(), 1),
                "space_heat_kwh": round(h.energy_profile.annual_space_heat_demand(), 1),
                "dhw_kwh": round(h.energy_profile.annual_dhw_demand(), 1),
                "c_before": round(h.c_before, 2),
                "c_after": round(h.c_after, 2),
                "wants_transformation": h.wants_transformation,
            }
            for b in self.buildings
            for h in b.households
        ])
