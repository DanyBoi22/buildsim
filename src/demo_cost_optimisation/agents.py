"""Household and building agents.

Household decision logic (Type A/B/C) is implemented as small functions in
`DECISION_RULES`, keyed by `AgentType`. To add a new type or change a rule,
add/replace one function -- no class hierarchy needed.
"""

import mesa
from enum import Enum
from price_model import PriceModel
from energy_profiles import EnergyProfile

GAS_BOILER_EFFICIENCY = 0.90  # heat -> gas consumption
HEAT_PUMP_COP = 4.0  # heat -> heat pump electricity consumption
SAVINGS_THRESHOLD = 0.2  # relative cost saving required to count as "significant" (e.g. 0.2 = 20% cheaper)


class AgentType(Enum):
    A = "A"  # always votes to transform
    B = "B"  # votes yes if not more expensive (c_after <= c_before)
    C = "C"  # votes yes only for a "significant" saving


def _decide_type_a(c_before: float, c_after: float) -> bool:
    return True


def _decide_type_b(c_before: float, c_after: float) -> bool:
    return c_after <= c_before


def _decide_type_c(c_before: float, c_after: float) -> bool:
    # Open parameter: relative cost saving required to count as "significant".
    # Set via `SAVINGS_THRESHOLD` (e.g. 0.2 = 20% cheaper).
    if c_before <= 0:
        return False
    relative_saving = (c_before - c_after) / c_before
    return relative_saving >= SAVINGS_THRESHOLD


DECISION_RULES = {
    AgentType.A: _decide_type_a,
    AgentType.B: _decide_type_b,
    AgentType.C: _decide_type_c,
}


class HouseholdAgent(mesa.Agent):
    def __init__(self, model: mesa.Model, agent_type: AgentType, energy_profile: EnergyProfile, price_model: PriceModel, area_m2: float = 70.0, 
                 gas_efficiency: float = GAS_BOILER_EFFICIENCY, heat_pump_cop: float = HEAT_PUMP_COP, investment_cost: float = 10000.0):
        super().__init__(model)
        self.agent_type = agent_type
        self.energy_profile = energy_profile
        self.price_model = price_model
        self.area_m2 = area_m2
        self.c_before = 0.0
        self.c_after = 0.0
        self.wants_transformation = False

        self.gas_efficiency = gas_efficiency
        self.heat_pump_cop = heat_pump_cop
        self.investment_cost = investment_cost

    def step(self):
        year = self.model.current_year
        elec_price = self.price_model.electricity_price(year)
        gas_price = self.price_model.gas_price(year)

        heat_demand = self.energy_profile.annual_heat_demand()
        elec_demand = self.energy_profile.annual_electricity_demand()

        # c_before = cost of current heating system (gas boiler) + electricity demand
        gas_consumption = heat_demand / self.gas_efficiency
        self.c_before = elec_demand * elec_price + gas_consumption * gas_price

        # c_after = cost of new heating system (heat pump) + electricity demand + investemt cost
        # Investment shares intentionally excluded for now
        hp_consumption = heat_demand / self.heat_pump_cop
        self.c_after = (elec_demand + hp_consumption) * elec_price + self.investment_cost

        self.wants_transformation = DECISION_RULES[self.agent_type](self.c_before, self.c_after)


class BuildingAgent(mesa.Agent):
    def __init__(self, model: mesa.Model, efficiency_class: str, majority_threshold: float = 0.5):
        super().__init__(model)
        self.transformed = False
        self.last_yes_share = 0.0
        self.efficiency_class = efficiency_class
        self.majority_threshold = majority_threshold
        self.households: list[HouseholdAgent] = []  # filled in after creation

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
