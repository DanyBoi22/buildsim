import mesa
from demo_building_sim.building import BuildingAgent 
from demo_building_sim.building_data.loader import load_district

class DistrictModel(mesa.Model):
    def __init__(self, place: str):
        super().__init__()

        self.place = place
        self.district_data = load_district(place)
        
        # Creates one agent per building
        for _, row in self.district_data.iterrows():
            BuildingAgent(self, params=row.to_dict())
        
        self.datacollector = mesa.DataCollector(
            agent_reporters={
                "heat_demand":        "heat_demand",
                "building_type":      "building_type",
                "area_m2":            "area_m2",
                "geometry":           "geometry", 
            },
            model_reporters={
                "total_heat_demand_kw": lambda m: sum(
                    a.heat_demand for a in m.agents
                )
            }
        )
    
    def step(self):
        self.datacollector.collect(self) # collect data before agents step
        self.agents.shuffle_do("step") # randomize order of agent steps each time