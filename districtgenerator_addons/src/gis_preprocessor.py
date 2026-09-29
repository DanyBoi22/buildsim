"""
GIS -> DistrictGenerator Szenario.

Unterstützte Eingaben:
    - GeoParquet
    - GML/XML

Die GIS-Datei wird nicht in das DG-Format "hineininterpretiert".
Stattdessen entsteht eine normale DistrictGenerator-Szenario-CSV.

Für die Geometriekalibrierung gilt:
    dg_area = reale Grundfläche / TABULA-Grundflächenfaktor

Für PV gilt:
    f_PV1 = PV-Fläche Seite 1 / DG-Dachfläche
    f_PV2 = PV-Fläche Seite 2 / DG-Dachfläche

Wenn keine PV-Seitenfelder vorhanden sind, wird die gesamte verfügbare
PV-Fläche zunächst Seite 1 zugeordnet. Die spätere Bestimmung einer realen
Dachausrichtung kann damit separat ergänzt werden.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tabula_geometry import calculate_dg_area


DG_TYPES = {"SFH", "TH", "MFH", "AB"}

SCENARIO_COLUMNS = [
    "id",
    "building",
    "year",
    "retrofit",
    "construction_type",
    "night_setback",
    "area",
    "heater",
    "dhw_heater",
    "cooling",
    "EV",
    "f_TES",
    "f_BAT",
    "f_PV1",
    "f_PV2",
    "f_STC",
    "gamma_PV",
    "ev_charging",
]


@dataclass(frozen=True)
class GisPreprocessorConfig:
    type_field: str | None = None
    type_mapping: dict[str, str] = field(default_factory=dict)

    year_field: str = "baujahr"
    footprint_field: str = "grundflaeche"
    pv_field: str = "solar_pvarea_value"

    pv_side1_field: str | None = None
    pv_side2_field: str | None = None
    gamma_field: str | None = None

    gml_layer: str | None = None

    # Diese Werte betreffen nur die DG-Szenario-CSV.
    retrofit: int = 0
    construction_type: int = 2
    night_setback: int = 0
    heater: str = "HP"
    dhw_heater: str = "EH_DHW"
    cooling: int = 0
    ev: int = 0
    f_tes: float = 35.0
    f_bat: float = 1.0
    f_stc: float = 0.0
    ev_charging: str = "on_demand"

    default_gamma_pv: float = 0.0


class GisPreprocessor:
    """Verarbeitet eine GIS-Datei und erzeugt eine DG-Szenario-CSV."""

    def __init__(self, config: GisPreprocessorConfig):
        self.config = config

    def create_scenario(
        self,
        input_path: Path,
        output_scenario: Path,
    ) -> Path:
        input_path = Path(input_path).expanduser().resolve()
        output_scenario = Path(output_scenario).expanduser().resolve()

        if not input_path.is_file():
            raise FileNotFoundError(f"GIS-Datei nicht gefunden: {input_path}")

        gdf = self._load_gis(input_path)

        output_scenario.parent.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, Any]] = []
        report_rows: list[dict[str, Any]] = []

        for new_id, (_, row) in enumerate(gdf.iterrows()):
            building_type = self._get_building_type(row)
            year = self._get_year(row)
            real_ground_area = self._get_positive_number(
                row,
                self.config.footprint_field,
                "Grundfläche",
            )

            dg_area, dg_roof_area, ground_factor = calculate_dg_area(
                building_type=building_type,
                year=year,
                real_ground_area_m2=real_ground_area,
            )

            pv_side1, pv_side2, pv_total = self._get_pv_areas(row)

            if pv_total < 0:
                raise ValueError(
                    f"Gebäude {new_id}: PV-Fläche darf nicht negativ sein."
                )

            if pv_total > dg_roof_area * 1.000001:
                raise ValueError(
                    f"Gebäude {new_id}: verfügbare PV-Fläche {pv_total:.2f} m² "
                    f"ist größer als die von DG erzeugte Dachfläche "
                    f"{dg_roof_area:.2f} m²."
                )

            f_pv1 = pv_side1 / dg_roof_area if dg_roof_area > 0 else 0.0
            f_pv2 = pv_side2 / dg_roof_area if dg_roof_area > 0 else 0.0

            if f_pv1 < 0 or f_pv2 < 0 or f_pv1 + f_pv2 > 1.000001:
                raise ValueError(
                    f"Gebäude {new_id}: ungültige PV-Faktoren "
                    f"f_PV1={f_pv1:.6f}, f_PV2={f_pv2:.6f}."
                )

            gamma_pv = self._get_gamma(row)

            rows.append(
                {
                    "id": new_id,
                    "building": building_type,
                    "year": year,
                    "retrofit": self.config.retrofit,
                    "construction_type": self.config.construction_type,
                    "night_setback": self.config.night_setback,
                    "area": round(dg_area, 6),
                    "heater": self.config.heater,
                    "dhw_heater": self.config.dhw_heater,
                    "cooling": self.config.cooling,
                    "EV": self.config.ev,
                    "f_TES": self.config.f_tes,
                    "f_BAT": self.config.f_bat,
                    "f_PV1": round(f_pv1, 8),
                    "f_PV2": round(f_pv2, 8),
                    "f_STC": self.config.f_stc,
                    "gamma_PV": gamma_pv,
                    "ev_charging": self.config.ev_charging,
                }
            )

            report_rows.append(
                {
                    "dg_id": new_id,
                    "gis_identifier": row.get("identifier", ""),
                    "building": building_type,
                    "year": year,
                    "real_ground_area_m2": real_ground_area,
                    "tabula_ground_factor": ground_factor,
                    "dg_area_m2": dg_area,
                    "tabula_roof_factor": dg_roof_area / dg_area,
                    "dg_roof_area_m2": dg_roof_area,
                    "pv_area_side1_m2": pv_side1,
                    "pv_area_side2_m2": pv_side2,
                    "pv_area_total_m2": pv_total,
                    "f_PV1": f_pv1,
                    "f_PV2": f_pv2,
                    "gamma_PV": gamma_pv,
                }
            )

        if not rows:
            raise ValueError("Die GIS-Datei enthält keine Gebäude.")

        scenario_df = pd.DataFrame(rows, columns=SCENARIO_COLUMNS)
        scenario_df.to_csv(
            output_scenario,
            sep=";",
            index=False,
            encoding="utf-8",
        )

        report_path = output_scenario.with_name(
            output_scenario.stem + "_preprocessing_report.csv"
        )
        pd.DataFrame(report_rows).to_csv(
            report_path,
            sep=";",
            index=False,
            encoding="utf-8",
        )

        print(f"Erzeugte Gebäude: {len(rows)}")
        print(f"Szenario-CSV:      {output_scenario}")
        print(f"Preprocessing:     {report_path}")

        return output_scenario

    def _load_gis(self, path: Path):
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise ImportError(
                "Für GML/GeoParquet wird geopandas benötigt. "
                "Für GeoParquet zusätzlich pyarrow/fastparquet."
            ) from exc

        suffix = path.suffix.lower()

        try:
            if suffix == ".parquet":
                gdf = gpd.read_parquet(path)
            elif suffix in {".gml", ".xml"}:
                kwargs = {}
                if self.config.gml_layer:
                    kwargs["layer"] = self.config.gml_layer
                gdf = gpd.read_file(path, **kwargs)
            else:
                raise ValueError(
                    f"Nicht unterstützte GIS-Datei: {path.suffix!r}"
                )
        except Exception as exc:
            raise RuntimeError(
                f"GIS-Datei konnte nicht gelesen werden: {path}\n{exc}"
            ) from exc

        if gdf.empty:
            raise ValueError(f"GIS-Datei enthält keine Gebäude: {path}")

        required = {
            self.config.year_field,
            self.config.footprint_field,
        }

        missing = sorted(required - set(gdf.columns))
        if missing:
            raise ValueError(
                "Folgende erforderliche GIS-Spalten fehlen: "
                + ", ".join(missing)
            )

        return gdf

    def _get_building_type(self, row: pd.Series) -> str:
        # 1) Direkte DG-Spalte hat Vorrang.
        candidate_columns = []
        if self.config.type_field:
            candidate_columns.append(self.config.type_field)
        candidate_columns += [
            "building",
            "building_type",
            "dg_building_type",
            "gebaeudefunktion",
        ]

        for column in candidate_columns:
            if column not in row.index:
                continue

            value = row.get(column)
            if value is None or self._is_nan(value):
                continue

            value_string = str(value).strip()

            if value_string in DG_TYPES:
                return value_string

            mapped = self.config.type_mapping.get(value_string)
            if mapped in DG_TYPES:
                return mapped

        # 2) Einfache heuristische Klassifikation für Textdaten.
        text = " ".join(
            str(row.get(column, "")).lower()
            for column in (
                "gebaeudefunktion",
                "bauweise",
                "weitereGebaeudefunktion",
                "art",
                "name",
            )
        )

        high_rise = row.get("hochhaus")
        if isinstance(high_rise, bool) and high_rise:
            return "AB"

        if "reihen" in text:
            return "TH"

        if "mehrfamil" in text or "wohnblock" in text:
            return "MFH"

        if "einfamil" in text:
            return "SFH"

        # 3) Keine unsichere Klassifikation erzwingen.
        source_values = {
            str(row.get(column))
            for column in candidate_columns
            if column in row.index
            and row.get(column) is not None
            and not self._is_nan(row.get(column))
        }

        raise ValueError(
            "Gebäudetyp konnte nicht eindeutig bestimmt werden. "
            f"GIS-Werte: {sorted(source_values)!r}. "
            "Nutze --type-field oder --type-map."
        )

    def _get_year(self, row: pd.Series) -> int:
        value = row.get(self.config.year_field)

        if value is None or self._is_nan(value):
            raise ValueError(
                f"Gebäude {row.get('identifier', '<ohne ID>')}: "
                f"Baujahr fehlt."
            )

        try:
            year = int(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Ungültiges Baujahr: {value!r}") from exc

        if year < 0 or year > 2100:
            raise ValueError(f"Ungültiges Baujahr: {year}")

        return year

    def _get_positive_number(
        self,
        row: pd.Series,
        column: str,
        label: str,
    ) -> float:
        if column not in row.index:
            raise ValueError(f"GIS-Spalte fehlt: {column}")

        value = row.get(column)

        if value is None or self._is_nan(value):
            raise ValueError(
                f"Gebäude {row.get('identifier', '<ohne ID>')}: "
                f"{label} fehlt."
            )

        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Gebäude {row.get('identifier', '<ohne ID>')}: "
                f"{label} ist nicht numerisch: {value!r}"
            ) from exc

        if not math.isfinite(result) or result <= 0:
            raise ValueError(
                f"Gebäude {row.get('identifier', '<ohne ID>')}: "
                f"{label} muss > 0 sein."
            )

        return result

    def _get_pv_areas(self, row: pd.Series) -> tuple[float, float, float]:
        side1_column = self.config.pv_side1_field
        side2_column = self.config.pv_side2_field

        if side1_column and side2_column:
            side1 = self._get_optional_nonnegative(row, side1_column)
            side2 = self._get_optional_nonnegative(row, side2_column)
            return side1, side2, side1 + side2

        total = self._get_optional_nonnegative(row, self.config.pv_field)

        # Ohne reale Orientierungs-/Seiteninformation landet zunächst alles
        # auf Seite 1. Später können echte Seitenflächen verwendet werden.
        return total, 0.0, total

    def _get_optional_nonnegative(
        self,
        row: pd.Series,
        column: str,
    ) -> float:
        if column not in row.index:
            return 0.0

        value = row.get(column)

        if value is None or self._is_nan(value):
            return 0.0

        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"GIS-Spalte {column!r} enthält einen ungültigen Wert: {value!r}"
            ) from exc

        if not math.isfinite(result) or result < 0:
            raise ValueError(
                f"GIS-Spalte {column!r} muss >= 0 sein."
            )

        return result

    def _get_gamma(self, row: pd.Series) -> float:
        if not self.config.gamma_field:
            return self.config.default_gamma_pv

        if self.config.gamma_field not in row.index:
            return self.config.default_gamma_pv

        value = row.get(self.config.gamma_field)

        if value is None or self._is_nan(value):
            return self.config.default_gamma_pv

        try:
            gamma = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Ungültiger PV-Azimutwert: {value!r}"
            ) from exc

        if gamma < -180 or gamma > 180:
            raise ValueError("gamma_PV muss zwischen -180° und +180° liegen.")

        return gamma

    @staticmethod
    def _is_nan(value: Any) -> bool:
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False