"""Minimal example: run the model for N years with a rising price scenario
and print the resulting KPIs.
"""

from model import DistrictModel
from price_model import DeterministicPriceModel

N_YEARS = 20

# Deterministic scenario: electricity roughly flat, gas rising steadily
# (illustrates the "Sensitivitaet gegenueber Preisentwicklung" KPI).
price_model = DeterministicPriceModel(
    electricity_prices=[0.35 + 0.01 * year for year in range(N_YEARS)],
    gas_prices=[0.12 + 0.02 * year for year in range(N_YEARS)],
)

model = DistrictModel(
    n_buildings=10,
    households_per_building=8,
    majority_threshold=0.5,  # try 0.7 or 1.0 for the other two variants
    price_model=price_model,
    seed=42,
)

for _ in range(N_YEARS):
    model.step()

model_df = model.datacollector.get_model_vars_dataframe()
print(model_df)

building_df = model.datacollector.get_agenttype_vars_dataframe(model.buildings[0].__class__)
print(building_df.tail(10))

print("\n--- Building overview ---")
print(model.building_overview())

print("\n--- Household overview ---")
print(model.household_overview())
