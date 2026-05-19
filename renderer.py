import folium
import geopandas as gpd
import osmnx as ox
import pandas as pd

import model

def render_district(model, buildings: pd.DataFrame, output_file="district.html"):
    """
    Render the district with building footprints colored by heat demand.
    """
    
    agent_data = model.datacollector.get_agent_vars_dataframe()
    # last timestep
    last_step = agent_data.xs(23, level="Step")

    # TODO> needs to match building IDs
    # For now just assigns demands to footprints as demo
    buildings["heat_demand"] = last_step["heat_demand"].values[:len(buildings)]

    # Plot
    buildings = buildings.to_crs(epsg=4326) # Convert back to WGS84 for Folium
    m = folium.Map(location=[53.49500, 10.01111], zoom_start=16, tiles="cartodb positron")

    for _, row in buildings.iterrows():
        folium.GeoJson(
            row["geometry"],
            style_function=lambda f, d=row["heat_demand"]: {
                "fillColor": "red" if d > 10 else "green",
                "fillOpacity": 0.6,
                "weight": 1
            }
        ).add_to(m)

    if output_file:
        print(f"Saving district visualization to {output_file}")
        m.save(output_file)  # opens in a browser