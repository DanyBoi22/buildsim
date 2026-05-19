import osmnx as ox
import geopandas as gpd

def get_buildings(place: str) -> gpd.GeoDataFrame:
    """
    Fetch building footprints from OSM for a given place string.
    Returns a GeoDataFrame with one row per building.
    """
    tags = {"building": True}
    buildings = ox.features_from_place(place, tags=tags)
    
    # Keep only useful columns
    cols = ["geometry", "building", "addr:street", "addr:housenumber"]
    cols = [c for c in cols if c in buildings.columns]
    buildings = buildings[cols].copy()
    
    # Calculate area in m² (project to metric CRS first)
    buildings = buildings.to_crs(epsg=25832)  # UTM zone 32N, standard for Germany
    buildings["area_m2"] = buildings.geometry.area
    
    # Drop anything without usable geometry or area
    buildings = buildings[buildings["area_m2"] > 10].reset_index(drop=True)
    buildings["building_id"] = buildings.index
    
    return buildings