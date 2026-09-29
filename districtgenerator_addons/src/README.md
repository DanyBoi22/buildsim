# DistrictGenerator Wrapper

Kleine Wrapper-Struktur für zwei Startwege:

1. vorhandene DistrictGenerator-Szenario-CSV direkt simulieren
2. GIS-Datei (`.parquet` / `.gml`) vorverarbeiten -> DG-CSV erzeugen -> simulieren

## Dateien

```text
run_district.py
gis_preprocessor.py
tabula_geometry.py
simulation_runner.py
```

### `run_district.py`

CLI und Orchestrierung.

### `gis_preprocessor.py`

Liest reale GIS-Daten und berechnet:
```text
reale Grundfläche
        ↓
TABULA-Grundflächenfaktor
        ↓
DG-Referenzfläche (`area`)
        ↓
DG-Dachfläche
        ↓
reale PV-Fläche / DG-Dachfläche
        ↓
f_PV1 / f_PV2
```

### `tabula_geometry.py`

Enthält die TABULA-Faktoren aus TEASER 1.3.0.

### `simulation_runner.py`

Startet die normale DG-Pipeline über `Datahandler`.

# Verwendung

### Vorhandenes DG-Szenario

```bash
python run_district.py -f dsitrictgenerator/data/scenarios/my_scenario.csv
```

### GIS-GeoParquet

```bash
python run_district.py -f buildings_unified.parquet
```

Dabei wird standardmäßig erzeugt:

```text
generated_scenarios/buildings_unified_dg.csv
generated_scenarios/buildings_unified_dg_preprocessing_report.csv
```
Danach wird automatisch simuliert.

### Anwendungsbeispiele 

- Nur vorverarbeiten

    ```text
    python run_district.py -f buildings_unified.parquet --dry-run
    ```

- Reproduzierbare Stichproben

    ```text
    python run_district.py -f buildings_unified.parquet --seed 1234
    ```

- Eigene DG-Konfiguration

    ```text
    python run_district.py -f buildings_unified.parquet --env-config .env.CONFIG.MY_CONFIG
    ```

# GIS-Felder

Aktuelle werden verwendet:

```text
baujahr
grundflaeche
solar_pvarea_value
```

Zusätzlich werden, sofern vorhanden, Gebäude-Typinformationen aus typischen Feldern verwendet. Für numerische gebaeudefunktion-Codes sollte ein eigenes Mapping angegeben werden.

Beispiel:

```python
{
  "31001": "SFH",
  "31002": "TH",
  "31003": "MFH",
  "31004": "AB"
}
```

Start:

```bash
python run_district.py -f buildings_unified.parquet --type-map hamburg_building_types.json
```

Falls ein direktes DG-Feld existiert:

```bash
python run_district.py -f buildings_unified.parquet --type-field dg_building_type
```

# PV-Seiten

Wenn nur solar_pvarea_value vorhanden ist, wird die gesamte PV-Fläche vorerst Seite 1 zugeordnet:

```text
f_PV1 = PV-Fläche / DG-Dachfläche
f_PV2 = 0
```

Sobald reale PV-Flächen für beide Dachseiten vorhanden sind, können diese
direkt verwendet werden:

```bash
python run_district.py -f buildings_unified.parquet \
    --pv-side1-field pv_area_side1 \
    --pv-side2-field pv_area_side2
```

Eine vorhandene reale Dachausrichtung kann ebenfalls über ein Feld eingespeist werden:

```text
--gamma-field dachausrichtung
```

# Wichtige Modellentscheidung

Diese Version überschreibt bewusst nicht die von DG intern erzeugte Geschosszahl oder Wohnungs-/Bewohnerlogik.

Nur die Eingabe area wird so kalibriert, dass die TABULA-Archetypgeometrie die reale GIS-Grundfläche reproduziert.

Dadurch bleibt die eigentliche DG-Pipeline weitgehend unverändert.
