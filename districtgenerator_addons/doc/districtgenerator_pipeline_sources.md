# Districtgenerator — Pipeline and Sources

Scope: electricity demand, heat demand, DHW, and PV generation. Verified against
the `develop` branch. Code anchors are given as grep patterns rather than line
numbers, because line numbers differ noticeably between commits.

---

## 0. Documentation status

| Source | What it covers | Where |
|---|---|---|
| JOSS paper (peer-reviewed) | Electricity, occupancy, DHW, internal gains, 5R1C heating, design heat load | [10.21105/joss.07657](https://doi.org/10.21105/joss.07657) |
| ECOS 2024 conference paper | Tool overview, webtool | [10.52202/077185-0106](https://doi.org/10.52202/077185-0106) |
| Sphinx site | API reference, auto-generated from docstrings — i.e. the code | https://rwth-ebc.github.io/districtgenerator/master/docs/README.html |
| `docs/EXAMPLES.md`, `README.md` | Usage, partly outdated (e.g. the scenario CSV column list) | repo |

**Not covered by any publication:** PV, solar thermal, the 7R2C model, electric
vehicles, and the MILP operation optimisation. The JOSS paper (published July
2025) lists these under "Further development". For these the code and its inline
citations are the only reference.

**One drift to be aware of:** the paper states DHW profiles come from pyCity
(Schiefelbein et al., 2019). The current code uses OpenDHW instead. If you cite
the paper for the DHW method, you would be citing something the code no longer
does.

---

## 1. Electricity demand

Two stages: a statistical annual value, then a shape normalised to it.

### 1.1 Annual consumption per dwelling

A lookup table of eight consumption breakpoints per building type and occupant
count (1–5). A uniform draw selects one of seven bands (p ≈ 0.143 each), then a
uniform integer is drawn between the two bracketing values.

- Code: `classes/users.py`, `generate_annual_el_consumption_residential`,
  `consumption_range = {...}`
- Source, cited in code: Stromspiegel für Deutschland (co2online), methodology at
  <https://www.stromspiegel.de/ueber-uns-partner/methodik-des-stromspiegels/>
- Source, cited in paper: co2online (2019), *Stromspiegel für Deutschland*

The occupant count is itself drawn (Gaussian around a type-dependent mean); the
dwelling count for MFH/AB is drawn from a floor-area distribution.

- Code: `classes/users.py`, `generate_number_flats_and_rooms`,
  `generate_number_occupants`
- Source, cited in code: Federal Statistical Office (Destatis), Zensus 2022,
  <https://www.zensus2022.de/>, plus the Destatis *Wohnen* tables for rented and
  owner-occupied dwellings

### 1.2 Time series

Bottom-up appliance switching conditioned on an occupancy Markov chain, then
scaled to the drawn annual demand (`do_normalization=True`). Lighting is a
separate model driven by measured irradiance, with a randomised lamp inventory
per dwelling.

- Code: `classes/profiles.py`, `generate_el_profile_residential`;
  `import richardsonpy.classes.stochastic_el_load_wrapper`
- Source: Richardson, I., Thomson, M., Infield, D., Clifford, C. (2010).
  *Domestic electricity use: A high-resolution energy demand model.* Energy and
  Buildings 42(10), 1878–1887. <https://doi.org/10.1016/j.enbuild.2010.05.023>

The `elec` column excludes space heating, DHW and EV charging.

---

## 2. Internal gains

Deterministic conversion of occupancy, lighting and appliance power into heat:

```
gains = occ_profile · 70 W  +  light_load · 0.80  +  app_load · 0.66
```

The appliance factor is derived in the code as 0.75 · 0.80 + 0.25 · 0.25, on the
assumption that a quarter of appliance electricity (dishwasher, washing machine)
leaves the zone via waste water.

- Code: `classes/profiles.py`, `generate_gain_profile_residential`
- Source, cited in code: Elsland, R., Peksen, I., Wietschel, M. (2014). *Are
  Internal Heat Gains Underestimated in Thermal Performance Evaluation of
  Buildings?* Energy Procedia 62, 32–41.

---

## 3. Heat

Two distinct outputs. Do not confuse them.

### 3.1 Design heat load — `heatload` in `*_static.csv`

Steady-state transmission plus ventilation loss at the design outdoor
temperature, with thermal-bridge surcharge, ground correction factors and a
re-heat allowance of 20 W/m².

- Code: `classes/envelope_5R1C.py`, `calcHeatLoad`,
  `_calcTransmissionCoefficients`
- Sources, cited in code:
  - DIN EN 12831-1, §6.3.2.5 and Table 7 — reduction factor *f*ix,k
  - DIN/TS 12831-1, §4.3.1 — annual outdoor temperature correction *f*θann;
    groundwater influence explicitly neglected
  - DIN/TS 12831-1, Table 2 — thermal bridge surcharge, category A
  - DIN/TS 12831 — 20 W/m² re-heat allowance
- Source, cited in paper: DIN EN 12831-1:2017-09, *Energy performance of
  buildings — Method for calculation of the design heat load — Part 1*.
  <https://doi.org/10.31030/2571775>

The same standard supplies the design outdoor temperatures for the selectable
German sites.

The method argument also accepts `"bivalent"` and `"heatlimit"`, which produce
the `bivalent` and `heatlimit` values in the static file.

### 3.2 Hourly heat demand — `heating` column

A reduced-order dynamic model, selected by `THERMAL_MODEL_TYPE`.

**5R1C** (the variant described in the paper):

- Code: `functions/_5R1C.py`, `classes/envelope_5R1C.py`,
  `calcNormativeProperties`
- Source: DIN EN ISO 13790:2008-09, *Energy performance of buildings —
  Calculation of energy use for space heating and cooling*, simplified hourly
  method. The code cites individual clauses inline — §7.2.2.2 eq. 9, §8.3.1
  eq. 18, §9.3.1 eq. 21, §11.4.3–11.4.6, §12.2.2, Annex C eq. C.1 — which makes
  it unusually auditable.

**7R2C** (code only, not in any publication):

- Code: `functions/_7R2C.py`, `classes/envelope_7R2C.py`
- Source, cited in code: VDI 6007, with surface parameters per §6.4

Supporting standards, cited in both envelope modules:

| Quantity | Standard |
|---|---|
| Effective material heat capacity | DIN EN ISO 13786:2008-04, Annex A.2.4 (effective thickness method) |
| Surface heat transfer resistances | DIN EN ISO 6946, Table 1 |
| Ground coupling | DIN EN ISO 13370, Annex A.5 eq. A8 |
| Cooling load, static | VDI 2078 (1996) and DIN EN ISO 13790 |
| Cooling setpoint | DIN 4108-2 (summer thermal protection) |

### 3.3 Envelope and weather inputs

- Geometry, U-values, material layers: TEASER, populated from TABULA archetypes
  by building type, age class and retrofit level.
  - Remmen, P. et al. (2018). *TEASER: An open tool for urban energy modelling of
    building stocks.* Journal of Building Performance Simulation 11(1), 84–98.
    <https://doi.org/10.1080/19401493.2017.1283539>
  - Loga, T., Stein, B., Diefenbach, N., Born, R. (2015). *Deutsche
    Wohngebäudetypologie*, 2nd ed., IWU. ISBN 978-3-941140-47-9
- Weather: ortsgenaue Testreferenzjahre, 16 German climate zones, TRY 2015 and
  2045, normal / warm / cold variants.
  - BBSR (2020), *Ortsgenaue Testreferenzjahre von Deutschland für mittlere und
    extreme Witterungsverhältnisse*
  - DWD Klimaberatungsmodul, <https://kunden.dwd.de/obt/>

---

## 4. Domestic hot water

Daily draw-off volume per person by building type, then a stochastic tapping
profile, then conversion to thermal power.

- Default volume: 40 l/(person·day) for SFH, MFH, TH, AB
- Code: `data_handling/config.py`, `mean_drawoff_vol_per_day`
- Source, cited in code: DIN EN 12831-3/A100, Table NA.4 for residential; SIA
  2024 *Standard-Nutzungsbedingungen für die Energie- und Gebäudetechnik* for
  non-residential
- Profile generator: OpenDHW, <https://github.com/RWTH-EBC/OpenDHW>
  (`classes/profiles.py`, `generate_dhw_profile`)
- Paper cites instead: DIN 4708-1:1994-04 for the standard load (unit dwelling
  method) and pyCity (Schiefelbein et al., 2019) for the profile. Neither
  appears in the current code.

---

## 5. Photovoltaics and solar thermal

**No publication covers this.** Computed in `designDecentralDevices()`, not in
`generateDemands()`.

### 5.1 Irradiance on the tilted plane

Sun position geometry, then an anisotropic sky model splitting beam, circumsolar,
horizon-brightening and ground-reflected components.

- Code: `classes/solar.py`, `getGeometry`, `getIncidenceAngle`,
  `getTotalRadiationTiltedSurface`
- Sources, cited in code:
  - Duffie, J., Beckman, W. (2013). *Solar Engineering of Thermal Processes*,
    4th ed. Specific equations named inline: 1.8.1 (p. 24), 2.15.1 (p. 89),
    2.16.12 (p. 94)
  - Perez, R. et al. (1990). *Modeling daylight availability and irradiance
    components from direct and global irradiance.* Solar Energy 44(5), 271–289.
    Table 6 coefficients; the code notes that EnergyPlus Engineering Reference
    Table 22 (p. 147) holds higher-precision values.

### 5.2 Module efficiency

Temperature-dependent efficiency:

```
η(t) = η_ref · (1 − γ · [T_air(t) − T_ref + (T_NOCT − T_air(t)) · G(t)/G_NOCT])
```

- Code: `classes/solar.py`, `calcPVAndSTCProfile`
- Source, cited in code: Dubey, S., Sarvaiya, J. N., Seshadri, B. (2013).
  *Temperature Dependent Photovoltaic (PV) Efficiency and Its Effect on PV
  Production in the World — A Review.* Energy Procedia 33. The code names
  page 313, formula 5.
- Defaults: `D_PV__ETA_EL_REF` 0.199, `D_PV__GAMMA` 0.003 /K,
  `D_PV__T_CELL_REF` 25 °C, `D_PV__T_CELL_NOCT` 44 °C, `D_PV__G_NOCT` 800 W/m²

### 5.3 Power

```
P(t) = A_roof · (1 − Σκ) · (η₁(t)·G₁(t)·f_PV1 + η₂(t)·G₂(t)·f_PV2)
```

Nine loss factors — inverter, wiring, connections, soiling, shading, mismatch,
NPR, availability, LID — summing to 0.16 by default. **They are summed, not
compounded**; compounding would give 0.149. No source is cited for the
individual values.

Two further code-only facts with no documented basis:

- Roof pitch is hardcoded as `beta=[35]` in `classes/datahandler.py`,
  `designDecentralDevices`. Only the azimuth comes from `gamma_PV` in the
  scenario CSV.
- `D_PV__P_NOMINAL` and `D_PV__AREA_REAL` exist in the config but never enter
  this formula. There is no inverter clipping and no module count.

### 5.4 Solar thermal

Standard collector efficiency curve, cut off below η = 0.01:

```
η_STC = c0 − c1·ΔT/G − c2·ΔT²/G
```

Defaults `D_STC__ZERO_LOSS` 0.786, `FIRST_ORDER` 0.003345, `SECOND_ORDER`
0.0000142. No source cited.

---

## 6. Heat pump sink temperature

Relevant if you compute heat pump electricity yourself. A mapping from age class
and retrofit level to supply/return temperature, with an optional cap
representing low-invasive measures.

- Code: `data_handling/config.py`, `hp_sink_temp_levels`;
  `functions/opti_central.py`, `compute_decentral_hp_sink_temperature`
- COP formulation: Carnot with a quality grade,
  `COP = grade · (273.15 + T_sink) / (T_sink − T_e)`, `D_HP__GRADE` 0.4
- No source is cited for the temperature table or the grade value.

The function is importable and runs without a solver.

---

## 7. What is stochastic

| Deterministic | Stochastic |
|---|---|
| Weather (TRY) | Dwelling count (Zensus distribution) |
| Envelope, U-values, areas (TABULA) | Occupants per dwelling |
| Design heat load | Annual electricity per dwelling (Stromspiegel band) |
| Hourly heat demand | Appliance switching, lighting (richardsonpy) |
| Internal-gain conversion factors | DHW tapping events (OpenDHW) |
| PV and STC, entirely | Vehicle segment, battery size, daily distance |

There is no seeding in the library. `random.seed()` before `generateBuildings()`
fixes dwelling counts, occupants and annual demands; the profile generation runs
in a thread pool sharing global RNG state, so bit-exact reproducibility of the
time series is not guaranteed.

---

## 8. Verifying these claims in your own clone

```bash
grep -rn "consumption_range" districtgenerator/classes/users.py
grep -rn "Zensus 2022" districtgenerator/classes/users.py
grep -rn "Elsland" districtgenerator/classes/profiles.py
grep -rn "12831" districtgenerator/classes/envelope_5R1C.py
grep -rn "13790" districtgenerator/classes/envelope_5R1C.py
grep -rn "VDI 6007" districtgenerator/classes/envelope_7R2C.py
grep -rn "Duffie\|Perez" districtgenerator/classes/solar.py
grep -rn "Dubey" districtgenerator/classes/solar.py
grep -rn "mean_drawoff_vol_per_day" districtgenerator/data_handling/config.py
grep -rn "hp_sink_temp_levels" districtgenerator/data_handling/config.py
```

Your clone is on an older commit than the one documented here — your
`datahandler.py` is roughly 400 lines shorter and your `users.py` lacks
`is_residential`. Run `git log -1 --oneline` and check before relying on any
section above.

---

## Citation

```bibtex
@article{Henn2025,
  doi       = {10.21105/joss.07657},
  url       = {https://doi.org/10.21105/joss.07657},
  year      = {2025},
  publisher = {The Open Journal},
  volume    = {10},
  number    = {111},
  pages     = {7657},
  author    = {Henn, Sarah and Sch{\"o}lzel, Joel David and Beckh{\"o}lter, Tobias
               and W{\"u}ller, Carla and Hamze, Rawad and M{\"u}ller, Dirk},
  title     = {Districtgenerator: Generating building-specific load profiles
               for residential districts.},
  journal   = {Journal of Open Source Software}
}
```
