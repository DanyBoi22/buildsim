"""
Districtgenerator-Lauf mit fester Wohnungs- und Bewohnerzahl.

Wohnungszahl und Bewohner sind keine CSV-Felder, sondern werden in users.py
gewuerfelt. Dieses Skript ueberschreibt die beiden zustaendigen Methoden,
bevor generateBuildings() laeuft, und laesst danach alles unveraendert weiter.

Aufruf:
    python run_district.py

Danach z.B.:
    python plot_district.py --scenario my_district --plot energy --freq ME
"""

import random as rd

from districtgenerator.classes import Datahandler
from districtgenerator.classes import users as dg_users

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

SCENARIO = "my_district"
ENV_CONFIG = ".env.CONFIG.MY_CONFIG"

SEED = 1234
# int -> reproduzierbare Wohnungs-/Bewohnerzahlen. None -> jeder Lauf anders.

FLAT_AREA = 75.0
# m2 pro Wohnung fuer MFH und AB. nb_flats = round(area / FLAT_AREA).
# Bei area=600 und FLAT_AREA=75 also 8 Wohnungen.
# None -> originale Zensus-Ziehung der Lib.
# SFH und TH haben per Definition immer genau eine Wohnung.

OCCUPANTS = 2
# Bewohner pro Wohnung. Erlaubt:
#   int   -> jede Wohnung gleich viele, z.B. 2
#   list  -> pro Wohnung, wird bei Bedarf zyklisch wiederholt,
#            z.B. [1, 2, 2, 3, 1, 2, 4, 2]
#   None  -> originale stochastische Ziehung der Lib
# HARTE GRENZE: nur ganze Zahlen 1..5. Die Stromspiegel-Tabelle und
# richardsonpy sind auf diesen Bereich definiert; alles andere wirft
# einen KeyError.

GENERATE_PV = True

CALC_PROFILES = True
SAVE_PROFILES = True

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------

_orig_flats = dg_users.Users.generate_number_flats_and_rooms
_orig_occ = dg_users.Users.generate_number_occupants

RESIDENTIAL_MULTI = ("MFH", "AB")
RESIDENTIAL_ALL = ("SFH", "TH", "MFH", "AB")


def _patched_flats(self, area):
    if FLAT_AREA and self.building in RESIDENTIAL_MULTI:
        self.nb_flats = max(round(area / FLAT_AREA), 2)
    else:
        _orig_flats(self, area)


def _patched_occupants(self, area):
    if OCCUPANTS is None or self.building not in RESIDENTIAL_ALL:
        _orig_occ(self, area)
        return

    if isinstance(OCCUPANTS, int):
        values = [OCCUPANTS] * self.nb_flats
    else:
        values = [OCCUPANTS[i % len(OCCUPANTS)] for i in range(self.nb_flats)]

    clamped = [min(max(int(v), 1), 5) for v in values]
    if clamped != [int(v) for v in values]:
        print(f"  Warnung: Bewohnerzahlen auf 1..5 begrenzt -> {clamped}")

    self.nb_occ = clamped


dg_users.Users.generate_number_flats_and_rooms = _patched_flats
dg_users.Users.generate_number_occupants = _patched_occupants

# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------


def main():

    if SEED is not None:
        rd.seed(SEED)

    data = Datahandler(scenario_name=SCENARIO, env_path=ENV_CONFIG)
    data.generateEnvironment()
    data.initializeBuildings()
    data.generateBuildings()

    print("\nGebaeude nach dem Patch:")
    for b in data.district:
        f = b["buildingFeatures"]
        u = b["user"]
        print(
            f"  id {f['id']:>2}  {f['building']:<4} {f['area']:>6.0f} m2"
            f"  Wohnungen {u.nb_flats:>3}"
            f"  Bewohner {u.nb_occ}"
            f"  Strom/a {u.annual_el_demand:>7.0f} kWh"
        )


    data.generateDemands(calcUserProfiles=CALC_PROFILES, saveUserProfiles=SAVE_PROFILES)

    if GENERATE_PV:
        data.designDecentralDevices(saveGenerationProfiles=True)

    print("\nJahressummen:")
    hours_per_step = data.time["timeResolution"] / 3600
    for b in data.district:
        f = b["buildingFeatures"]
        u = b["user"]
        kwh = lambda x: sum(x) * hours_per_step / 1000
        pv = f"  PV {kwh(u.generationPV):>7.0f} kWh" if GENERATE_PV else ""
        print(
            f"  id {f['id']:>2}  {f['building']:<4}"
            f"  Heizung {kwh(u.heat):>9.0f} kWh"
            f"  TWW {kwh(u.dhw):>7.0f} kWh"
            f"  Strom {kwh(u.elec):>7.0f} kWh"
            f"{pv}"
            f"  Heizlast {b['envelope'].heatload / 1000:>6.1f} kW"
        )

    return data


if __name__ == "__main__":
    main()
