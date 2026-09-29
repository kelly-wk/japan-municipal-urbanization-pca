from __future__ import annotations

import numpy as np
import pandas as pd

from urban_pca.analysis import (
    PRIMARY_FEATURES,
    VALIDATION_OUTCOMES,
    bootstrap_stability,
    fit_pca,
)


def _fixture(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(17)
    latent = np.linspace(-2, 2, n)
    frame = pd.DataFrame(index=range(n))
    for index, feature in enumerate(PRIMARY_FEATURES):
        sign = -1 if feature in {"primary_employment_share", "cultivated_land_share"} else 1
        values = sign * latent + rng.normal(0, 0.15 + index * 0.005, n)
        if feature in {
            "population_density",
            "habitable_population_density",
            "establishments_per_habitable_km2",
            "eateries_per_habitable_km2",
            "clinics_per_habitable_km2",
        }:
            values = np.exp(values - values.min())
        else:
            values = (values - values.min()) / (values.max() - values.min())
        frame[feature] = values
    return frame


def test_pc1_is_oriented_toward_population_density() -> None:
    fit = fit_pca(_fixture())
    position = PRIMARY_FEATURES.index("population_density")
    assert fit.components[0, position] > 0
    assert fit.explained_variance_ratio[0] > 0.7


def test_bootstrap_is_deterministic() -> None:
    frame = _fixture()
    fit = fit_pca(frame)
    first, first_rank, first_percentiles = bootstrap_stability(frame, fit, 15, 123)
    second, second_rank, second_percentiles = bootstrap_stability(frame, fit, 15, 123)
    pd.testing.assert_frame_equal(first, second)
    assert first_rank == second_rank
    np.testing.assert_allclose(first_percentiles, second_percentiles)


def test_validation_columns_are_not_pca_features() -> None:
    validation_columns = set(VALIDATION_OUTCOMES.values())
    assert validation_columns.isdisjoint(PRIMARY_FEATURES)
