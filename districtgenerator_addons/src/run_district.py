"""
Einfacher Einstiegspunkt für DistrictGenerator.

Beispiele:
    python run_district.py -f scenario.csv
    python run_district.py -f buildings.parquet
    python run_district.py -f buildings.parquet --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gis_preprocessor import GisPreprocessor, GisPreprocessorConfig
from simulation_runner import SimulationConfig, run_simulation


SUPPORTED_INPUTS = {".csv", ".parquet", ".gml", ".xml"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DistrictGenerator Wrapper: vorhandene DG-Szenario-CSV ausführen "
            "oder ein GIS-GML/GeoParquet vorverarbeiten und anschließend simulieren."
        )
    )

    parser.add_argument(
        "-f",
        "--file",
        required=True,
        help="Eingabedatei: DG-Szenario-CSV oder GIS-Datei (.parquet/.gml/.xml).",
    )
    parser.add_argument(
        "--env-config",
        default=None,
        help="Optionaler Pfad zu einer DG-.env-Konfiguration.",
    )
    parser.add_argument(
        "--result-dir",
        default="results",
        help="Ausgabeverzeichnis für DG-Ergebnisse (Standard: results).",
    )
    parser.add_argument(
        "--scenario-dir",
        default="generated_scenarios",
        help="Verzeichnis für aus GIS erzeugte Szenario-CSV-Dateien.",
    )
    parser.add_argument(
        "--output-scenario",
        default=None,
        help="Optionaler exakter Pfad für die aus GIS erzeugte Szenario-CSV.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur GIS verarbeiten und CSV schreiben; keine DG-Simulation starten.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Zufalls-Seed für reproduzierbare DG-Stichproben.",
    )

    # GIS-Feldzuordnung
    parser.add_argument(
        "--type-field",
        default=None,
        help="Optionales GIS-Feld, das bereits SFH/TH/MFH/AB enthält.",
    )
    parser.add_argument(
        "--type-map",
        default=None,
        help=(
            "Optionaler JSON-Pfad für die Zuordnung von GIS-Gebäudefunktionen "
            "zu DG-Typen, z.B. {'31001':'SFH','31002':'MFH'}."
        ),
    )
    parser.add_argument("--year-field", default="baujahr")
    parser.add_argument("--footprint-field", default="grundflaeche")
    parser.add_argument("--pv-field", default="solar_pvarea_value")
    parser.add_argument("--pv-side1-field", default=None)
    parser.add_argument("--pv-side2-field", default=None)
    parser.add_argument("--gamma-field", default=None)
    parser.add_argument(
        "--gml-layer",
        default=None,
        help="Optionaler Layername bei GML-Dateien.",
    )

    return parser


def load_type_map(path: str | None) -> dict[str, str]:
    if path is None:
        return {}

    mapping_path = Path(path)
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Type-Mapping nicht gefunden: {mapping_path}")

    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ungültiges JSON in {mapping_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Das Type-Mapping muss ein JSON-Objekt sein.")

    normalized: dict[str, str] = {}
    for key, value in data.items():
        if value not in {"SFH", "TH", "MFH", "AB"}:
            raise ValueError(
                f"Ungültiger DG-Gebäudetyp im Mapping: {value!r}. "
                "Erlaubt sind SFH, TH, MFH, AB."
            )
        normalized[str(key)] = value

    return normalized


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.file).expanduser().resolve()

    if not input_path.is_file():
        parser.error(f"Eingabedatei nicht gefunden: {input_path}")

    suffix = input_path.suffix.lower()

    if suffix not in SUPPORTED_INPUTS:
        parser.error(
            f"Nicht unterstütztes Dateiformat {suffix!r}. "
            "Erlaubt: .csv, .parquet, .gml, .xml"
        )

    try:
        type_map = load_type_map(args.type_map)

        # -------------------------------------------------------------
        # Option 1: Bereits vorhandene DG-Szenario-CSV direkt ausführen.
        # -------------------------------------------------------------
        if suffix == ".csv":
            if args.output_scenario:
                parser.error("--output-scenario ist nur bei GIS-Eingaben sinnvoll.")

            config = SimulationConfig(
                scenario_path=input_path,
                env_path=args.env_config,
                result_dir=Path(args.result_dir),
                seed=args.seed,
            )
            run_simulation(config)
            return 0

        # -------------------------------------------------------------
        # Option 2: GIS -> DG-Szenario-CSV -> DG-Simulation.
        # -------------------------------------------------------------
        output_scenario = (
            Path(args.output_scenario).expanduser().resolve()
            if args.output_scenario
            else Path(args.scenario_dir).expanduser().resolve()
            / f"{input_path.stem}_dg.csv"
        )

        preprocess_config = GisPreprocessorConfig(
            type_field=args.type_field,
            type_mapping=type_map,
            year_field=args.year_field,
            footprint_field=args.footprint_field,
            pv_field=args.pv_field,
            pv_side1_field=args.pv_side1_field,
            pv_side2_field=args.pv_side2_field,
            gamma_field=args.gamma_field,
            gml_layer=args.gml_layer,
        )

        preprocessor = GisPreprocessor(preprocess_config)
        scenario_path = preprocessor.create_scenario(
            input_path=input_path,
            output_scenario=output_scenario,
        )

        print(f"\nGIS-Vorverarbeitung abgeschlossen.")
        print(f"Szenario: {scenario_path}")

        if args.dry_run:
            print("Dry-Run: keine DistrictGenerator-Simulation gestartet.")
            return 0

        simulation_config = SimulationConfig(
            scenario_path=scenario_path,
            env_path=args.env_config,
            result_dir=Path(args.result_dir),
            seed=args.seed,
        )
        run_simulation(simulation_config)
        return 0

    except (FileNotFoundError, ValueError, RuntimeError, ImportError) as exc:
        print(f"\nFEHLER: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            f"\nUNERWARTETER FEHLER: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())