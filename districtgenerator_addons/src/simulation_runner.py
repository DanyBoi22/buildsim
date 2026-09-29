"""
Gemeinsamer Runner für beide Eingangsvarianten:

1. vorhandene DistrictGenerator-Szenario-CSV
2. zuvor aus GIS erzeugte DistrictGenerator-Szenario-CSV
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class SimulationConfig:
    scenario_path: Path
    env_path: str | None = None
    result_dir: Path = Path("results")

    calc_user_profiles: bool = True
    save_user_profiles: bool = True
    generate_pv: bool = True

    seed: int | None = None


def run_simulation(config: SimulationConfig):
    scenario_path = Path(config.scenario_path).expanduser().resolve()
    result_dir = Path(config.result_dir).expanduser().resolve()

    if not scenario_path.is_file():
        raise FileNotFoundError(
            f"DistrictGenerator-Szenario nicht gefunden: {scenario_path}"
        )

    if scenario_path.suffix.lower() != ".csv":
        raise ValueError(
            f"Der Simulation-Runner erwartet eine CSV, bekommen: "
            f"{scenario_path.suffix}"
        )

    if config.seed is not None:
        _seed_random_generators(config.seed)

    try:
        from districtgenerator.classes.datahandler import Datahandler
    except ImportError as exc:
        raise ImportError(
            "DistrictGenerator konnte nicht importiert werden. "
            "Aktiviere die virtuelle Umgebung, in der DG installiert ist."
        ) from exc

    result_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== DistrictGenerator ===")
    print(f"Szenario: {scenario_path}")
    print(f"Ergebnisse: {result_dir}")

    # Datahandler kann eine Szenario-CSV über scenario_file_path laden.
    # Dadurch muss die generierte GIS-CSV nicht in DGs data/scenarios liegen.
    data = Datahandler(
        scenario_name=scenario_path.stem,
        scenario_file_path=str(scenario_path.parent),
        resultPath=str(result_dir),
        env_path=config.env_path,
    )

    print("1/5 Umgebung erzeugen ...")
    data.generateEnvironment()

    print("2/5 Gebäude initialisieren ...")
    data.initializeBuildings()

    print("3/5 Gebäude erzeugen ...")
    data.generateBuildings()

    print("4/5 Bedarfsprofile erzeugen ...")
    data.generateDemands(
        calcUserProfiles=config.calc_user_profiles,
        saveUserProfiles=config.save_user_profiles,
    )

    if config.generate_pv:
        print("5/5 PV/Erzeugung dimensionieren ...")
        data.designDecentralDevices(saveGenerationProfiles=True)
    else:
        print("5/5 PV-Dimensionierung übersprungen.")

    _print_building_summary(data)
    return data


def _seed_random_generators(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _print_building_summary(data) -> None:
    print("\n=== Gebäudezusammenfassung ===")

    hours_per_step = data.time["timeResolution"] / 3600.0

    def kwh(profile) -> float:
        return sum(profile) * hours_per_step / 1000.0

    for b in data.district:
        f = b["buildingFeatures"]
        e = b["envelope"]
        u = b["user"]
        
        pv_value = ""
        if hasattr(u, "generationPV") and u.generationPV is not None:
            pv_value = f"  PV {kwh(u.generationPV):8.0f} kWh"


        print(f"\nBuilding {f['id']} ({f['building']})")

        print(f"Wohnungen:          {u.nb_flats}")
        print(f"Bewohner:           {u.nb_occ}")

        print(f"Gesamtfläche:       {f['area']} m²")
        print(f"Dachfläche:         {e.A['opaque']['roof']} m²")
        print(f"Grundfläche:        {e.A['opaque']['groundfloor']} m²")

        print(f"Implizierte Höhe:   {e.V / e.A['opaque']['groundfloor']:.2f} m")
        print(f"Gesamtfläche / Grundfläche: {f['area'] / e.A['opaque']['groundfloor']:.2f}")

        print(f"Volumen:            {e.V} m³")
        print(f"Externe Wände:      {e.A['opaque']['walls']} m²")

        print(f"Strombedarf:        {kwh(u.elec):8.0f} kWh")
        print(f"PV:                 {pv_value}")
            