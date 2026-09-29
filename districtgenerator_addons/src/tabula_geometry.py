"""
TABULA-Geometriefaktoren für die deutschen Wohngebäude-Archetypen.

Die Werte entsprechen den in TEASER 1.3.0 verwendeten
facade_estimation_factors. Benötigt werden hier nur:
    - rt1 + rt2 -> Dachfläche / Referenzfläche
    - gf1 + gf2 -> Grundfläche / Referenzfläche

Quelle:
https://github.com/RWTH-EBC/TEASER/tree/v1.3.0
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TabulaFactors:
    year_start: int
    year_end: int
    roof_factor: float
    ground_factor: float


# Nur die beiden für unsere Rückrechnung relevanten Faktoren.
# Die Werte sind direkt aus TEASER 1.3.0 übernommen.
TABULA_FACTORS: dict[str, tuple[TabulaFactors, ...]] = {
    "MFH": (
        TabulaFactors(0, 1859, 0.41965, 0.18434 + 0.07238),
        TabulaFactors(1860, 1918, 0.32949, 0.32949),
        TabulaFactors(1919, 1948, 0.41169 + 0.08078, 0.33091 + 0.08078),
        TabulaFactors(1949, 1957, 0.56171, 0.56171),
        TabulaFactors(1958, 1968, 0.31035, 0.31035),
        TabulaFactors(1969, 1978, 0.46205, 0.46205),
        TabulaFactors(1979, 1983, 0.37966, 0.37966),
        TabulaFactors(1984, 1994, 0.32057, 0.32057),
        TabulaFactors(1995, 2001, 0.33976, 0.33976),
        TabulaFactors(2002, 2009, 0.26849, 0.28288),
        TabulaFactors(2010, 2015, 0.24605, 0.24605),
        TabulaFactors(2016, 2100, 0.24605, 0.24605),
    ),
    "SFH": (
        TabulaFactors(0, 1859, 0.613, 0.3904),
        TabulaFactors(1860, 1918, 0.585, 0.3211 + 0.2303),
        TabulaFactors(1919, 1948, 0.7063, 0.47822),
        TabulaFactors(1949, 1957, 1.13, 0.559 + 0.161),
        TabulaFactors(1958, 1968, 1.396, 0.957),
        TabulaFactors(1969, 1978, 1.05838, 0.4526 + 0.4277),
        TabulaFactors(1979, 1983, 0.46667, 0.386),
        TabulaFactors(1984, 1994, 0.8213, 0.502),
        TabulaFactors(1995, 2001, 0.947, 0.691),
        TabulaFactors(2002, 2009, 0.58435, 0.543),
        TabulaFactors(2010, 2015, 0.70535, 0.57647),
        TabulaFactors(2016, 2100, 0.70535, 0.57647),
    ),
    "TH": (
        TabulaFactors(1860, 1918, 0.625, 0.625),
        TabulaFactors(1919, 1948, 0.44602, 0.44602),
        TabulaFactors(1949, 1957, 0.54133, 0.54133),
        TabulaFactors(1958, 1968, 0.39487, 0.39487),
        TabulaFactors(1969, 1978, 0.57453, 0.57453),
        TabulaFactors(1979, 1983, 0.9037, 0.67593),
        TabulaFactors(1984, 1994, 0.50703, 0.43828),
        TabulaFactors(1995, 2001, 0.51946, 0.34832),
        TabulaFactors(2002, 2009, 0.60066, 0.46513),
        TabulaFactors(2010, 2015, 0.38622, 0.34592),
        TabulaFactors(2016, 2100, 0.38622, 0.34592),
    ),
    # TEASER 1.3.0 currently exposes these TABULA AB factors only
    # for the following construction-age classes.
    "AB": (
        TabulaFactors(1860, 1918, 0.27961, 0.19747),
        TabulaFactors(1919, 1948, 0.25889, 0.26658),
        TabulaFactors(1949, 1957, 0.22052, 0.22052),
        TabulaFactors(1958, 1968, 0.12339, 0.11814),
        TabulaFactors(1969, 1978, 0.16255, 0.16255),
    ),
}


def get_tabula_factors(building_type: str, year: int) -> TabulaFactors:
    """Gibt die TABULA-Faktoren für Gebäudetyp und Baujahr zurück."""
    if not isinstance(building_type, str):
        raise TypeError("building_type muss ein String sein.")
    if not isinstance(year, int):
        raise TypeError("year muss ein Integer sein.")

    building_type = building_type.upper().strip()

    if building_type not in TABULA_FACTORS:
        raise ValueError(
            f"Keine TABULA-Faktoren für DG-Gebäudetyp {building_type!r} hinterlegt."
        )

    for factor in TABULA_FACTORS[building_type]:
        if factor.year_start <= year <= factor.year_end:
            return factor

    raise ValueError(
        f"Baujahr {year} wird für TABULA-Typ {building_type} nicht unterstützt."
    )


def calculate_dg_area(
    building_type: str,
    year: int,
    real_ground_area_m2: float,
) -> tuple[float, float, float]:
    """
    Berechnet die DG-Referenzfläche rückwärts aus der realen Grundfläche.

    Returns:
        dg_area_m2:
            Fläche, die an DG als 'area' übergeben wird.
        dg_roof_area_m2:
            Von TABULA daraus erzeugte Dachfläche.
        ground_factor:
            TABULA-Faktor der Grundfläche.
    """
    if not isinstance(real_ground_area_m2, (int, float)):
        raise TypeError("real_ground_area_m2 muss numerisch sein.")
    if real_ground_area_m2 <= 0:
        raise ValueError("real_ground_area_m2 muss > 0 sein.")

    factors = get_tabula_factors(building_type, year)

    if factors.ground_factor <= 0:
        raise ValueError(
            f"Grundflächenfaktor für {building_type}/{year} ist nicht positiv."
        )

    dg_area = real_ground_area_m2 / factors.ground_factor
    dg_roof_area = dg_area * factors.roof_factor

    return dg_area, dg_roof_area, factors.ground_factor