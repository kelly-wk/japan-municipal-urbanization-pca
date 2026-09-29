from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from urban_pca.data import classify_hierarchy


PROJECT = Path(__file__).resolve().parents[1]


def test_hierarchy_classification_is_non_overlapping() -> None:
    frame = pd.DataFrame(
        {
            "municipality_code": ["01100", "01101", "01102", "13100", "13101", "13102", "01202"],
            "municipality_name_jp": ["札幌市", "中央区", "北区", "特別区部", "千代田区", "中央区", "函館市"],
            "municipality_name_en": ["Sapporo", "Chuo", "Kita", "Ku-area", "Chiyoda", "Chuo", "Hakodate"],
            "source_order": range(7),
        }
    )
    classified = classify_hierarchy(frame).set_index("municipality_code")
    assert classified.loc["01100", "unit_role"] == "designated_city"
    assert classified.loc["01101", "unit_role"] == "designated_city_ward"
    assert classified.loc["13100", "unit_role"] == "special_ward_aggregate"
    assert classified.loc["13101", "unit_role"] == "special_ward"
    assert classified.loc["01100", "primary_population"]
    assert not classified.loc["01101", "primary_population"]
    assert not classified.loc["13100", "primary_population"]
    assert classified.loc["13101", "primary_population"]


def test_shipped_snapshot_invariants() -> None:
    data = pd.read_csv(
        PROJECT / "data/processed/municipal_indicators.csv",
        dtype={"municipality_code": str},
    )
    assert len(data) == 1_917
    assert data["municipality_code"].is_unique
    assert int(data["primary_population"].sum()) == 1_741
    assert int(data["analysis_eligible"].sum()) == 1_740
    required = [
        "population_density",
        "habitable_population_density",
        "establishments_per_habitable_km2",
        "eateries_per_habitable_km2",
        "clinics_per_habitable_km2",
        "primary_employment_share",
        "tertiary_employment_share",
    ]
    eligible = data.loc[data["analysis_eligible"], required]
    assert np.isfinite(eligible).all(axis=None)
