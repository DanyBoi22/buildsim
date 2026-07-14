import mesa
from demo_building_sim.building import BuildingAgent
from demo_building_sim.model import DistrictModel
from demo_building_sim.renderer import render_district
import os

PLACE = "Wilhelmsburg, Hamburg, Germany"

def main():
    print(f"Loading district data for: {PLACE}")
    model = DistrictModel(place=PLACE)
    print(f"Loaded {len(list(model.agents))} building agents")
    
    print("Running simulation...")
    for step in range(24):
        model.step()
    
    model_data = model.datacollector.get_model_vars_dataframe()
    agent_data = model.datacollector.get_agent_vars_dataframe()
    
    print("\n--- District total heat demand (kW) per hour ---")
    print(model_data)

    # Save to CSV
    results_folder = "results"
    os.makedirs(results_folder, exist_ok=True)
    results_agent_file = f"{results_folder}/results_agents.csv"
    results_model_file = f"{results_folder}/results_district.csv"
    model_data.to_csv(results_model_file)
    agent_data.to_csv(results_agent_file)
    print("Results saved to {} and {}".format(results_model_file, results_agent_file))

    render_district(model, model.district_data)

if __name__ == "__main__":
    main()


