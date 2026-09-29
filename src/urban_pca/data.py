"""Read e-Stat workbooks and construct an auditable municipal dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


REQUIRED_2024 = {
    "A1101",  # census population
    "A1801",  # DID population
    "B1101",  # total land area
    "B1103",  # inhabitable area
    "C2108",  # private establishments
    "C3502",  # wholesale/retail establishments
    "C3107",  # cultivated land
    "F1102",  # employed population
    "F2201",  # primary-industry employment
    "F2221",  # tertiary-industry employment
    "H6130",  # retail stores
    "H6131",  # eating/drinking places
    "H6132",  # large retail stores
    "I5102",  # clinics
}

REQUIRED_2026 = {
    "A2301",  # registered population
    "A5103",  # in-migrants
    "A5104",  # out-migrants
    "C120110",  # taxable income, million yen
    "C120120",  # income-tax payers
    "H2130",  # floor area per dwelling
}


def _clean_code(values: pd.Series) -> pd.Series:
    return (
        values.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


def read_estat_workbook(path: Path) -> pd.DataFrame:
    """Read one official 2024/2026 Statistical Observations XLS workbook.

    The public files use a stable layout: indicator codes are in row 8
    (zero-based row 7), data start in row 11, Japanese/English labels are in
    columns I/J, and the municipality code is the final column.  We validate
    all of these assumptions instead of silently accepting a shifted sheet.
    """

    raw = pd.read_excel(path, header=None, engine="xlrd")
    if raw.shape[0] < 1_500 or raw.shape[1] < 12:
        raise ValueError(f"Unexpected e-Stat sheet dimensions for {path}: {raw.shape}")

    indicator_row = raw.iloc[7]
    indicators = {
        idx: str(value).strip()
        for idx, value in indicator_row.items()
        if pd.notna(value) and str(value).strip()[:1] in set("ABCDEFGHIJ")
    }
    if not indicators:
        raise ValueError(f"No indicator codes found in expected row of {path}")

    raw_codes = _clean_code(raw.iloc[10:, -1])
    keep = raw_codes.str.fullmatch(r"\d{5}", na=False)
    frame = pd.DataFrame(
        {
            "municipality_code": raw_codes.loc[keep],
            "municipality_name_jp": raw.iloc[10:, 8].loc[keep].astype(str).str.strip(),
            "municipality_name_en": raw.iloc[10:, 9].loc[keep].astype(str).str.strip(),
            "source_order": np.arange(len(raw_codes))[keep.to_numpy()],
        }
    )
    for idx, code in indicators.items():
        frame[code] = pd.to_numeric(raw.iloc[10:, idx].loc[keep], errors="coerce")

    if not frame["municipality_code"].is_unique:
        raise ValueError(f"Duplicate municipality codes in {path}")
    if not 1_850 <= len(frame) <= 1_950:
        raise ValueError(f"Unexpected municipality row count in {path}: {len(frame)}")
    return frame.reset_index(drop=True)


def load_estat_directory(directory: Path) -> pd.DataFrame:
    """Merge all official XLS files in a release directory by code."""

    paths = sorted(directory.glob("*.xls"))
    if not paths:
        raise FileNotFoundError(f"No .xls files found in {directory}")

    merged: pd.DataFrame | None = None
    for path in paths:
        frame = read_estat_workbook(path)
        if merged is None:
            merged = frame
            continue
        value_columns = [
            column
            for column in frame.columns
            if column not in {
                "municipality_code",
                "municipality_name_jp",
                "municipality_name_en",
                "source_order",
            }
        ]
        merged = merged.merge(
            frame[["municipality_code", *value_columns]],
            on="municipality_code",
            how="outer",
            validate="one_to_one",
        )
    assert merged is not None
    return merged.sort_values("source_order").reset_index(drop=True)


def classify_hierarchy(frame: pd.DataFrame) -> pd.DataFrame:
    """Classify overlapping city/ward publication rows.

    The official publication prints each designated city immediately before
    its subordinate wards. Tokyo's `特別区部` aggregate is similarly followed
    by the 23 special wards. Primary analysis keeps designated-city totals and
    Tokyo special wards, giving non-overlapping basic municipal units.
    """

    result = frame.sort_values("source_order").copy()
    roles = pd.Series("basic_municipality", index=result.index, dtype="object")
    parents = pd.Series(pd.NA, index=result.index, dtype="object")
    current_parent_index: int | None = None
    current_parent_kind: str | None = None

    for idx, row in result.iterrows():
        name = str(row["municipality_name_jp"]).strip()
        if name == "特別区部":
            current_parent_index = idx
            current_parent_kind = "tokyo"
            roles.loc[idx] = "special_ward_aggregate"
        elif name.endswith("市"):
            current_parent_index = idx
            current_parent_kind = "city"
        elif name.endswith("区") and current_parent_index is not None:
            parent_code = result.loc[current_parent_index, "municipality_code"]
            parents.loc[idx] = parent_code
            if current_parent_kind == "tokyo":
                roles.loc[idx] = "special_ward"
            else:
                roles.loc[idx] = "designated_city_ward"
                roles.loc[current_parent_index] = "designated_city"
        elif not name.endswith("区"):
            current_parent_index = None
            current_parent_kind = None

    result["unit_role"] = roles
    result["parent_code"] = parents
    result["primary_population"] = ~result["unit_role"].isin(
        ["designated_city_ward", "special_ward_aggregate"]
    )
    result["granular_population"] = ~result["unit_role"].isin(
        ["designated_city", "special_ward_aggregate"]
    )
    return result


def _safe_ratio(numerator: pd.Series, denominator: pd.Series, multiplier: float = 1.0) -> pd.Series:
    denominator = denominator.where(denominator > 0)
    return numerator / denominator * multiplier


def construct_dataset(source_2024: Path, source_2026: Path) -> pd.DataFrame:
    """Construct analysis features and temporally held-out outcomes."""

    source = load_estat_directory(source_2024)
    missing = REQUIRED_2024.difference(source.columns)
    if missing:
        raise ValueError(f"2024 source is missing indicators: {sorted(missing)}")
    source = classify_hierarchy(source)

    later = load_estat_directory(source_2026)
    missing = REQUIRED_2026.difference(later.columns)
    if missing:
        raise ValueError(f"2026 source is missing indicators: {sorted(missing)}")
    later = later[["municipality_code", *sorted(REQUIRED_2026)]].rename(
        columns={code: f"validation_{code}" for code in REQUIRED_2026}
    )
    data = source.merge(later, on="municipality_code", how="left", validate="one_to_one")

    population = data["A1101"]
    employed = data["F1102"]
    total_area = data["B1101"]
    data["population_density"] = _safe_ratio(population, total_area)
    data["habitable_population_density"] = _safe_ratio(population, data["B1103"])
    data["did_population_share"] = _safe_ratio(data["A1801"], population)
    data["establishments_per_1000"] = _safe_ratio(data["C2108"], population, 1_000)
    data["commercial_establishments_per_1000"] = _safe_ratio(
        data["C3502"], population, 1_000
    )
    data["retail_stores_per_1000"] = _safe_ratio(data["H6130"], population, 1_000)
    data["eateries_per_1000"] = _safe_ratio(data["H6131"], population, 1_000)
    data["large_retail_stores_per_10000"] = _safe_ratio(
        data["H6132"], population, 10_000
    )
    data["clinics_per_10000"] = _safe_ratio(data["I5102"], population, 10_000)
    data["establishments_per_habitable_km2"] = _safe_ratio(data["C2108"], data["B1103"])
    data["commercial_establishments_per_habitable_km2"] = _safe_ratio(
        data["C3502"], data["B1103"]
    )
    data["retail_stores_per_habitable_km2"] = _safe_ratio(data["H6130"], data["B1103"])
    data["eateries_per_habitable_km2"] = _safe_ratio(data["H6131"], data["B1103"])
    data["large_retail_stores_per_habitable_km2"] = _safe_ratio(
        data["H6132"], data["B1103"]
    )
    data["clinics_per_habitable_km2"] = _safe_ratio(data["I5102"], data["B1103"])
    data["primary_employment_share"] = _safe_ratio(data["F2201"], employed)
    data["tertiary_employment_share"] = _safe_ratio(data["F2221"], employed)
    data["cultivated_land_share"] = _safe_ratio(data["C3107"], total_area)

    registered = data["validation_A2301"]
    data["validation_net_migration_per_1000"] = _safe_ratio(
        data["validation_A5103"] - data["validation_A5104"], registered, 1_000
    )
    data["validation_taxable_income_per_taxpayer_yen"] = _safe_ratio(
        data["validation_C120110"] * 1_000_000,
        data["validation_C120120"],
    )
    data["validation_dwelling_floor_area_m2"] = data["validation_H2130"]

    data["analysis_exclusion_reason"] = ""
    data.loc[~data["primary_population"], "analysis_exclusion_reason"] = "overlapping_hierarchy"
    data.loc[
        data["primary_population"] & ~(population > 0), "analysis_exclusion_reason"
    ] = "zero_census_population"
    data["analysis_eligible"] = data["analysis_exclusion_reason"].eq("")

    derived = [
        "population_density",
        "habitable_population_density",
        "did_population_share",
        "establishments_per_1000",
        "commercial_establishments_per_1000",
        "retail_stores_per_1000",
        "eateries_per_1000",
        "large_retail_stores_per_10000",
        "clinics_per_10000",
        "establishments_per_habitable_km2",
        "commercial_establishments_per_habitable_km2",
        "retail_stores_per_habitable_km2",
        "eateries_per_habitable_km2",
        "large_retail_stores_per_habitable_km2",
        "clinics_per_habitable_km2",
        "primary_employment_share",
        "tertiary_employment_share",
        "cultivated_land_share",
    ]
    primary_required = [
        "population_density",
        "habitable_population_density",
        "establishments_per_habitable_km2",
        "eateries_per_habitable_km2",
        "clinics_per_habitable_km2",
        "primary_employment_share",
        "tertiary_employment_share",
    ]
    invalid = data["analysis_eligible"] & ~np.isfinite(data[primary_required]).all(axis=1)
    data.loc[invalid, "analysis_exclusion_reason"] = "nonfinite_required_indicator"
    data["analysis_eligible"] = data["analysis_exclusion_reason"].eq("")

    columns = [
        "municipality_code",
        "municipality_name_jp",
        "municipality_name_en",
        "unit_role",
        "parent_code",
        "primary_population",
        "granular_population",
        "analysis_eligible",
        "analysis_exclusion_reason",
        *derived,
        "validation_net_migration_per_1000",
        "validation_taxable_income_per_taxpayer_yen",
        "validation_dwelling_floor_area_m2",
    ]
    return data[columns].sort_values("municipality_code").reset_index(drop=True)


def prepare_to_csv(source_2024: Path, source_2026: Path, output: Path) -> pd.DataFrame:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = construct_dataset(source_2024, source_2026)
    data.to_csv(output, index=False, float_format="%.10g")
    return data
