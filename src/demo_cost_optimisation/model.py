"""District model: builds the population of buildings/households, runs the
yearly step (households vote -> buildings decide -> collect data).

One model step = one year.
"""

import mesa
import pandas as pd
from agents import AgentType, BuildingAgent, HouseholdAgent
from energy_profiles import EFFICIENCY_CLASS_KWH_PER_M2, AnnualValueProfile, heat_demand_for_class, electricity_demand_for_household_gauss
from price_model import DeterministicPriceModel, PriceModel

class DistrictModel(mesa.Model):
    def __init__(
        self,
        n_buildings: int = 8,
        households_per_building: int = 8,
        majority_threshold: float = 0.7,  # 0.5 / 0.7 / 1.0 -> the three variants
        agent_type_shares: dict[AgentType, float] | None = None,
        efficiency_classes: list[str] | None = None,
        electricity_demand_mean: float | None = 3000.0,
        electricity_demand_std: float | None = 300.0,
        price_model: PriceModel | None = None,
        average_household_area_m2: float = 70.0,
        seed=None,
    ):
        super().__init__(seed=seed)

        self.majority_threshold = majority_threshold
        self.price_model = price_model or DeterministicPriceModel(electricity_prices=[0.35], gas_prices=[0.12])
        self.current_year = 0

        agent_type_shares = agent_type_shares or {AgentType.A: 1 / 3, AgentType.B: 1 / 3, AgentType.C: 1 / 3}
        efficiency_classes = efficiency_classes or list(EFFICIENCY_CLASS_KWH_PER_M2)

        self.buildings: list[BuildingAgent] = []
        for _ in range(n_buildings):
            # Efficiency class is assigned per building. All households in the same building share the same efficiency class.
            eff_class = self.random.choice(efficiency_classes)        

            building = BuildingAgent(self, efficiency_class=eff_class, majority_threshold=majority_threshold)
            self.buildings.append(building)

            for _ in range(households_per_building):
                # introduce some variability in household sizes
                household_area_m2 = round(self.random.gauss(average_household_area_m2, 10.0), 1)  
                agent_type = self.random.choices(list(agent_type_shares.keys()), weights=list(agent_type_shares.values()), k=1)[0]
                
                # Heat demand based on household efficiency class and area. 
                # Electricity demand is modeled as a normal distribution around a mean value, with some standard deviation.
                heat_kwh = heat_demand_for_class(efficiency_class=eff_class, area_m2=household_area_m2)
                elec_kwh = electricity_demand_for_household_gauss(mean=electricity_demand_mean, std=electricity_demand_std)
                profile = AnnualValueProfile(electricity_kwh=elec_kwh, heat_kwh=heat_kwh)
                
                household = HouseholdAgent(self, agent_type=agent_type, energy_profile=profile, price_model=self.price_model, area_m2=household_area_m2)
                building.households.append(household)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "share_transformed": lambda m: sum(b.transformed for b in m.buildings) / len(m.buildings),
                "share_failed": lambda m: sum(b.failed_this_year for b in m.buildings) / len(m.buildings),
            },
            agenttype_reporters={
                BuildingAgent: {
                    "transformed": "transformed",
                    "yes_share": "last_yes_share",
                    "efficiency_class": "efficiency_class",
                },
                HouseholdAgent: {
                    "agent_type": lambda a: a.agent_type.value,
                    "wants_transformation": "wants_transformation",
                    "c_before": "c_before",
                    "c_after": "c_after",
                },
            },
        )

    def step(self):
        self.agents_by_type[HouseholdAgent].shuffle_do("step")
        self.agents_by_type[BuildingAgent].do("step")
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
                "c_before": h.c_before,
                "c_after": h.c_after,
                "wants_transformation": h.wants_transformation,
            }
            for b in self.buildings
            for h in b.households
        ])