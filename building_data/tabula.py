import pandas as pd

# Simplified TABULA lookup
# Keys: (building_type, construction_period)
# Values: specific heat demand in kWh/m²/year
# Source: IWU TABULA Germany
# https://episcope.eu/building-typology/country/de/

TABULA_HEAT_DEMAND = {
    ("SFH", "before_1919"):  247,
    ("SFH", "1919_1948"):    221,
    ("SFH", "1949_1957"):    213,
    ("SFH", "1958_1968"):    193,
    ("SFH", "1969_1978"):    164,
    ("SFH", "1979_1983"):    134,
    ("SFH", "1984_1994"):    113,
    ("SFH", "1995_2001"):     88,
    ("SFH", "2002_2009"):     67,
    ("SFH", "after_2009"):    44,

    ("MFH", "before_1919"):  182,
    ("MFH", "1919_1948"):    168,
    ("MFH", "1949_1957"):    159,
    ("MFH", "1958_1968"):    145,
    ("MFH", "1969_1978"):    131,
    ("MFH", "1979_1983"):    112,
    ("MFH", "1984_1994"):     96,
    ("MFH", "1995_2001"):     76,
    ("MFH", "2002_2009"):     60,
    ("MFH", "after_2009"):    40,
}

def get_heat_demand_per_m2(building_type: str, construction_period: str) -> float:
    """
    Return specific heat demand in kWh/m²/year from TABULA lookup.
    Falls back to a default if combination not found.
    """
    key = (building_type, construction_period)
    return TABULA_HEAT_DEMAND.get(key, 150.0)  # 150 as fallback

def classify_osm_building(osm_building_tag: str) -> str:
    """
    Map OSM building tag to TABULA building type.
    Extend this as needed.
    """
    sfh_tags = {"house", "detached", "semidetached_house", "yes"}
    mfh_tags = {"apartments", "residential", "terrace"}
    
    if osm_building_tag in sfh_tags:
        return "SFH"  # Single Family House
    elif osm_building_tag in mfh_tags:
        return "MFH"  # Multi Family House
    else:
        return "MFH"  # default assumption for urban areas