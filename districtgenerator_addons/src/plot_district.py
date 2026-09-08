"""
Plotting for districtgenerator demand output.

Reads the *_timeseries.csv files from districtgenerator/results/demands/ and
builds a DatetimeIndex over them. If districtgenerator/results/generation/ holds
matching decentralPV_* / decentralSTC_* files, they are merged in as the columns
"pv" and "stc". All columns are in W; energy plots convert to kWh using the
resolution inferred from the row count.


RUNNING
-------
Run in the Root folder:

    python plot_district.py --scenario my_district --plot energy --freq ME

Every run first prints the columns available per building. Look at that list
before choosing --cols; it is longer than the README suggests (one
EV_demand_car_N / EV_charging_car_N / Car_availability_car_N triple per
vehicle, plus heating, cooling, elec, dhw, gains, occ, and pv/stc once the
generation files exist).

Note the heat column is called "heating", not "heat".


CHOOSING WHAT TO PLOT
---------------------
--plot   which view:
           profiles  raw power [W] over time, one subplot per building
           energy    stacked energy [kWh] per period, one subplot per building
           balance   demand vs PV generation, generation drawn negative
           duration  load duration curve (sorted power over the year)
           district  one column compared across all buildings
--cols   comma-separated column names, e.g. heating,elec,dhw
         (for --plot district only the first one is used)
--freq   aggregation period for energy/district/balance: h, D, W, ME
--dir    demand directory, default districtgenerator/results/demands
--gendir generation directory, default districtgenerator/results/generation
--save   write to a PNG instead of opening a window


ZOOMING IN
----------
--start and --end take any date string pandas understands. The synthetic
year is 2015 (see YEAR below), so:

    # first month, one bar per day
    python plot_district.py --scenario my_district --plot energy --freq D --start 2015-01-01 --end 2015-01-31

    # a single day, raw power
    python plot_district.py --scenario my_district --plot profiles --cols heating,elec,dhw --start 2015-01-15 --end 2015-01-15

A bare date includes the whole day, so --start X --end X gives exactly day X.

--plot duration ignores --start/--end by design; it always uses the full
year. To restrict it, change df[c] to df.loc[args.start:args.end, c] in
plot_duration().


SIMULATION CONFIG FOR READABLE SHORT WINDOWS
--------------------------------------------
At the default hourly resolution a single day is only 24 points, which is
too coarse to see anything. In your .env.CONFIG.<NAME> file set:

    TIMERESOLUTION=900        # 15 minutes -> 35040 steps/year
                              # 3600 = hourly (default), 1800 = half-hourly

Leave DATARESOLUTION at 3600; that describes the source weather/profile data,
not the output. Then regenerate with calcUserProfiles=True — loading cached
profiles will not change their resolution. Runtime and file size grow roughly
with the step count.

Nothing needs changing in this script: the resolution is inferred from the
number of rows and stored in df.attrs["hours_per_step"].


ADDING A PLOT
-------------
Write a function taking (district, cols, args) and returning a figure,
decorate it with @plot("name"), and it becomes available on --plot.
"district" is {label: DataFrame}. Use to_energy(df, freq) for kWh.

plot_balance builds its bars with ax.bar rather than DataFrame.plot(kind="bar"):
pandas places categorical bars at positions 0..n-1, and adding a raw ax.bar call
on top switches the axis to numeric, which silently misaligns the two sets of
bars. If you mix positive and negative bars, do all of them with ax.bar.


PV AND SOLAR THERMAL
--------------------
The "pv" and "stc" columns exist only if the generation files were written.
generateDemands() does not produce them; that needs the extra step

    data.designDecentralDevices(saveGenerationProfiles=True)

which run_district.py performs when GENERATE_PV = True. 
PV area comes from f_PV1 / f_PV2 in the scenario CSV (fractions of the roof
area, sum must be <= 1), azimuth from gamma_PV (0 = south). The roof pitch is
hardcoded at 35 degrees inside the library and cannot be set from the config.

The generation files are headerless, one value per timestep, in W.
attach_generation() skips any file whose row count does not match the demand
file -- which is what happens if you change TIMERESOLUTION and regenerate only
one of the two.

Do not put pv into a stacked --plot energy: it is generation, not demand, and
stacking it onto the demand bars overstates the total. Use --plot balance, which
draws generation below the zero line:

    python plot_district.py --scenario my_district --plot balance --cols elec,pv --freq ME
"""

import argparse
import glob
import os
import re

import matplotlib.pyplot as plt
import pandas as pd

GENERATION_DIR = os.path.join("districtgenerator", "results", "generation")
DEMAND_DIR = os.path.join("districtgenerator", "results", "demands")
YEAR = 2015  # arbitrary non-leap year, only used to build a readable time axis

# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------


def load_building(path, year=YEAR):
    """Read one *_timeseries.csv into a DataFrame with a DatetimeIndex.

    All demand columns are in W. Non-numeric columns (e.g. Car_availability)
    are dropped.
    """
    df = pd.read_csv(path, sep=";")
    df = df.drop(columns=["timestep"], errors="ignore")
    df = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")

    hours_per_step = 8760 / len(df)
    df.index = pd.date_range(
        start=f"{year}-01-01", periods=len(df), freq=pd.Timedelta(hours=hours_per_step)
    )
    df.attrs["hours_per_step"] = hours_per_step
    df.attrs["name"] = os.path.basename(path).replace("_timeseries.csv", "")
    return df

def load_district(scenario, demand_dir=DEMAND_DIR, year=YEAR, generation_dir=GENERATION_DIR):
    """Return {building_label: DataFrame} for every building of a scenario."""
    pattern = os.path.join(demand_dir, f"{scenario}_*_timeseries.csv")
    paths = sorted(
        p for p in glob.glob(pattern) if not p.endswith("_timeseries_minutely.csv")
    )
    if not paths:
        raise FileNotFoundError(f"No files matching {pattern}")

    district = {}
    for p in paths:
        df = load_building(p, year=year)
        df = attach_generation(df, df.attrs["name"], generation_dir)
        label = re.sub(rf"^{re.escape(scenario)}_", "", df.attrs["name"])
        district[label] = df
    return district

def attach_generation(df, name, generation_dir=GENERATION_DIR):
    """Add 'pv' and 'stc' columns from results/generation, if those files exist.

    Written by designDecentralDevices(); headerless, one value per timestep, in W.
    """
    for col, prefix in (("pv", "decentralPV_"), ("stc", "decentralSTC_")):
        path = os.path.join(generation_dir, f"{prefix}{name}.csv")
        if not os.path.exists(path):
            continue
        series = pd.read_csv(path, sep=";", header=None).iloc[:, 0]
        if len(series) != len(df):
            print(f"  skipping {os.path.basename(path)}: "
                  f"{len(series)} rows vs {len(df)} in the demand file")
            continue
        df[col] = series.values
    return df

def to_energy(df, freq="D"):
    """Aggregate power [W] to energy [kWh] per period."""
    return df.resample(freq).sum() * df.attrs["hours_per_step"] / 1000.0


# ----------------------------------------------------------------------------
# plot registry
# ----------------------------------------------------------------------------

PLOTS = {}


def plot(name):
    def deco(fn):
        PLOTS[name] = fn
        return fn

    return deco


# ----------------------------------------------------------------------------
# plots
# ----------------------------------------------------------------------------


@plot("profiles")
def plot_profiles(district, cols, args):
    """Raw power profiles over time, one subplot per building."""
    fig, axes = plt.subplots(
        len(district), 1, figsize=(12, 3 * len(district)), sharex=True, squeeze=False
    )
    for ax, (label, df) in zip(axes[:, 0], district.items()):
        sub = df.loc[args.start : args.end, [c for c in cols if c in df]]
        sub.plot(ax=ax, linewidth=0.8)
        ax.set_ylabel("W")
        ax.set_title(label, fontsize=10, loc="left")
        ax.legend(fontsize=8)
    axes[-1, 0].set_xlabel("")
    return fig


@plot("energy")
def plot_energy(district, cols, args):
    """Aggregated energy per period, stacked bars, one subplot per building."""
    fig, axes = plt.subplots(
        len(district), 1, figsize=(12, 3 * len(district)), sharex=True, squeeze=False
    )
    for ax, (label, df) in zip(axes[:, 0], district.items()):
        e = to_energy(df.loc[args.start : args.end], args.freq)
        e = e[[c for c in cols if c in e]]
        e.index = e.index.strftime("%b" if args.freq.startswith("M") else "%d.%m")
        e.plot(kind="bar", stacked=True, ax=ax, width=0.8)
        ax.set_ylabel("kWh")
        ax.set_title(label, fontsize=10, loc="left")
        ax.legend(fontsize=8)
        ax.tick_params(axis="x", rotation=45)
    return fig


@plot("duration")
def plot_duration(district, cols, args):
    """Load duration curve: sorted power over hours of the year."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for label, df in district.items():
        for c in cols:
            if c in df:
                series = df[c].sort_values(ascending=False).reset_index(drop=True)
                ax.plot(series.values, label=f"{label} · {c}", linewidth=1.0)
    ax.set_xlabel("Hours of the year (sorted)")
    ax.set_ylabel("W")
    ax.legend(fontsize=8)
    return fig


@plot("district")
def plot_district_total(district, cols, args):
    """One column per building, side by side, aggregated per period."""
    fig, ax = plt.subplots(figsize=(12, 5))
    col = cols[0]
    frame = pd.DataFrame(
        {
            label: to_energy(df.loc[args.start : args.end], args.freq)[col]
            for label, df in district.items()
            if col in df
        }
    )
    frame.index = frame.index.strftime("%b" if args.freq.startswith("M") else "%d.%m")
    frame.plot(kind="bar", ax=ax, width=0.8)
    ax.set_ylabel(f"{col} [kWh]")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=8)
    return fig

@plot("balance")
def plot_balance(district, cols, args):
    """PV generation against electric demand. Generation is drawn negative."""
    import numpy as np

    fig, axes = plt.subplots(
        len(district), 1, figsize=(12, 3 * len(district)), sharex=True, squeeze=False
    )
    for ax, (label, df) in zip(axes[:, 0], district.items()):
        e = to_energy(df.loc[args.start : args.end], args.freq)
        x = np.arange(len(e))
        bottom = np.zeros(len(e))
        for c in [c for c in cols if c in e and c != "pv"]:
            ax.bar(x, e[c].values, width=0.8, bottom=bottom, label=c)
            bottom = bottom + e[c].values
        if "pv" in e:
            ax.bar(x, -e["pv"].values, width=0.8, color="orange", label="pv")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(
            e.index.strftime("%b" if args.freq.startswith("M") else "%d.%m"), rotation=45
        )
        ax.set_ylabel("kWh")
        ax.set_title(label, fontsize=10, loc="left")
        ax.legend(fontsize=8)
    return fig


# ----------------------------------------------------------------------------
# cli
# ----------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", required=True)
    p.add_argument("--dir", default=DEMAND_DIR)
    p.add_argument("--gendir", default=GENERATION_DIR) 
    p.add_argument("--plot", default="profiles", choices=sorted(PLOTS))
    p.add_argument("--cols", default="heating,elec,dhw")
    p.add_argument("--freq", default="ME", help="pandas offset: D, W, ME")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--save", default=None)
    args = p.parse_args()

    district = load_district(args.scenario, args.dir, generation_dir=args.gendir)
    cols = [c.strip() for c in args.cols.split(",")]

    print(f"{len(district)} buildings, columns available:")
    for label, df in district.items():
        print(f"  {label}: {list(df.columns)}")

    fig = PLOTS[args.plot](district, cols, args)
    fig.tight_layout()
    if args.save:
        fig.savefig(args.save, dpi=150)
        print(f"saved to {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
