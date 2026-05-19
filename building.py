import mesa

class BuildingAgent(mesa.Agent):
    def __init__(self, model, params: dict):
        super().__init__(model=model)
        
        self.building_id        = params["building_id"]
        self.area_m2            = params["area_m2"]
        self.building_type      = params["building_type"]
        self.construction_period = params["construction_period"]
        self.heat_demand_per_m2 = params["heat_demand_per_m2"]
        self.geometry           = params["geometry"]

        self.heat_demand = 0.0  # kWh, updated each step
    
    def step(self):
        # Calculate heat demand
        # TODO>Later dynamic calculation based on weather, occupancy, etc.
        annual_demand = self.area_m2 * self.heat_demand_per_m2
        self.heat_demand = annual_demand / 8760  # hourly value
