import geopandas as gpd
from demo_building_sim.building_data.osm import get_buildings
from demo_building_sim.building_data.tabula import get_heat_demand_per_m2, classify_osm_building

def load_district(place: str) -> gpd.GeoDataFrame:
    """
    Main entry point. Returns one row per building with all
    parameters needed to initialise a BuildingAgent.
    """
    buildings = get_buildings(place)
    
    # Map OSM tags to TABULA types
    buildings["building_type"] = buildings["building"].apply(
        lambda x: classify_osm_building(str(x))
    )
    
    # TODO> Later enrich from Zensus, WMS, or user input
    # For now construction period is unknown from OSM
    buildings["construction_period"] = "1969_1978"  # placeholder
    
    # Look up heat demand
    buildings["heat_demand_per_m2"] = buildings.apply(
        lambda row: get_heat_demand_per_m2(
            row["building_type"],
            row["construction_period"]
        ),
        axis=1
    )
    
    # Keep only what the model needs
    result = buildings[[
        "building_id",
        "area_m2",
        "building_type",
        "construction_period",
        "heat_demand_per_m2",
        "geometry"
    ]].copy()
    
    return result