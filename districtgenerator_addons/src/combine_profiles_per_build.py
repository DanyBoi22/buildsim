import os
import pandas as pd


IN_DIR = "./results"
OUT_DIR = "./profiles"
N_BUILDINGS = 30


def new_name(i):
    btype = "ABCDEFGHIJ"[9 - i % 10]   # ones digit: 9 -> A, ..., 0 -> J
    refurb = i // 10                  # tens digit: 0 none, 1 simple, 2 advanced
    return f"MFH_{btype}_{refurb}"


# ---------------------------------------------------------------------------
# Profile configuration
# ---------------------------------------------------------------------------

# Keep all source-column definitions here. Adding another profile later only
# requires adding it to this dictionary and to the result DataFrame below.
PROFILE_COLUMNS = {
    "elec": "elec",
    "heating": "heating",
    "dhw": "dhw",
}


def load_building_profiles(i):
    """Load the timeseries and PV profiles belonging to one building."""
    ts_path = os.path.join(
        IN_DIR, f"demands/buildings_unified_30_mfh_dg_{i}_MFH_timeseries.csv"
    )
    pv_path = os.path.join(
        IN_DIR, f"generation/decentralPV_buildings_unified_30_mfh_dg_{i}_MFH.csv"
    )

    ts = pd.read_csv(ts_path, sep=";")
    pv = pd.read_csv(pv_path, header=None)

    return ts, pv


def build_building_result(i):
    """Combine all required profiles of one building into one DataFrame."""
    ts, pv = load_building_profiles(i)

    required_columns = ["timestep", *PROFILE_COLUMNS.values()]
    missing_columns = [
        column for column in required_columns
        if column not in ts.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Building {i}: missing columns in timeseries file: "
            f"{', '.join(missing_columns)}"
        )

    if len(ts) != len(pv):
        raise ValueError(
            f"Building {i}: timeseries and PV profiles have different lengths "
            f"({len(ts)} vs. {len(pv)})."
        )

    return pd.DataFrame({
        "timestep": ts["timestep"],
        "elec": ts[PROFILE_COLUMNS["elec"]],
        "heating": ts[PROFILE_COLUMNS["heating"]],
        "dhw": ts[PROFILE_COLUMNS["dhw"]],
        "pv": pv.iloc[:, 0],
    })


def write_building_result(name, result):
    """Write one combined CSV file for one building."""
    os.makedirs(OUT_DIR, exist_ok=True)

    output_path = os.path.join(OUT_DIR, f"{name}.csv")
    result.to_csv(output_path, sep=";", index=False)


def main():
    for i in range(N_BUILDINGS):
        name = new_name(i)

        try:
            result = build_building_result(i)
            write_building_result(name, result)
            print(f"Created: {name}.csv")

        except FileNotFoundError as error:
            print(f"Skipping {name}: input file not found: {error}")

        except (ValueError, KeyError) as error:
            print(f"Skipping {name}: invalid input data: {error}")

        except Exception as error:
            print(f"Skipping {name}: unexpected error: {error}")


if __name__ == "__main__":
    main()
