"""Minimal example: run the model for N years with a rising price scenario,
once with the synthetic population and once with districtgenerator profiles.
"""

from functools import partial

from agents_districtgen import BuildingSpec, build_districtgen_population
from model import DistrictModel, build_synthetic_population
from price_model import DeterministicPriceModel

N_YEARS = 20
DISTRICTGEN = False  # set to False to run only the synthetic population

# Deterministic scenario: electricity roughly flat, gas rising steadily
# (illustrates the "Sensitivitaet gegenueber Preisentwicklung" KPI).
price_model = DeterministicPriceModel(
    electricity_prices=[0.35 + 0.01 * year for year in range(N_YEARS)],
    gas_prices=[0.12 + 0.02 * year for year in range(N_YEARS)],
)

if DISTRICTGEN:
    # --- districtgenerator population ------------------------------------------
    # One BuildingSpec per building. The scenario fields mirror the
    # districtgenerator scenario CSV, so the same objects can later drive profile
    # generation via `spec.to_scenario_row()`.
    specs = [
        BuildingSpec(id=0, building="MFH", year=1960, retrofit=0, area=560.0, n_flats=8, demand_csv="dg_out/my_district_0_MFH_timeseries.csv"), # one file per building
        BuildingSpec(id=1, building="MFH", year=1978, retrofit=0, area=560.0,n_flats=8, demand_csv="dg_out/my_district_1_MFH_timeseries.csv"),

    ]

    districtgen = DistrictModel(
        population_builder=partial(
            build_districtgen_population,
            specs=specs,
            # Stand-in for the per-flat spread the generator computes internally
            # but does not export. Set to 0.0 for a strict proportional split.
            demand_factor_std=0.15,
        ),
        majority_threshold=0.5,
        price_model=price_model,
        seed=42,
    )

    
    for _ in range(N_YEARS):
        districtgen.step()

    print(f"\n=== DistrictGenerator Population ===")
    print(districtgen.datacollector.get_model_vars_dataframe().tail(5))
    print("\n--- Building overview ---")
    print(districtgen.building_overview())
    print("\n--- Household overview (first rows) ---")
    print(districtgen.household_overview().head(5))
else:
    # --- synthetic population --------------------------------------------------
    synthetic = DistrictModel(
        population_builder=partial(
            build_synthetic_population, n_buildings=10, households_per_building=8
        ),
        majority_threshold=0.5,  # try 0.7 or 1.0 for the other two variants
        price_model=price_model,
        seed=42,
    )

    for _ in range(N_YEARS):
        synthetic.step()

    print(f"\n=== Synthetic Population ===")
    print(synthetic.datacollector.get_model_vars_dataframe().tail(5))
    print("\n--- Building overview ---")
    print(synthetic.building_overview())
    print("\n--- Household overview (first rows) ---")
    print(synthetic.household_overview().head(5))