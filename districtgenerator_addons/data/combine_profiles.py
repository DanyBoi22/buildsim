import os
import pandas as pd

IN_DIR = "./profiles"   # folder with the 60 input files
OUT_DIR = "./results"                # where the 3 output files go
N_BUILDINGS = 30


def new_name(i):
    btype = "ABCDEFGHIJ"[9 - i % 10]   # ones digit: 9 -> A, ..., 0 -> J
    refurb = i // 10                    # tens digit: 0 none, 1 simple, 2 advanced
    return f"MFH_{btype}_{refurb}"


heat, elec, pv = {}, {}, {}

for i in range(N_BUILDINGS):
    ts = pd.read_csv(os.path.join(IN_DIR, f"my_district_{i}_MFH_timeseries.csv"), sep=";")
    gen = pd.read_csv(os.path.join(IN_DIR, f"decentralPV_my_district_{i}_MFH.csv"), header=None)

    name = new_name(i)
    heat[name] = ts["heating"]
    elec[name] = ts["elec"]
    pv[name] = gen[0]

timestep = ts["timestep"]

for label, data in [("heating_demand", heat), ("electricity_demand", elec), ("pv_generation", pv)]:
    df = pd.DataFrame(data)
    df = df[sorted(df.columns)]
    df.insert(0, "timestep", timestep)
    df.to_csv(os.path.join(OUT_DIR, f"{label}.csv"), sep=";", index=False)
