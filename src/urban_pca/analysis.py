"""PCA, stability analysis, sensitivity checks, and held-out validation."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr


PRIMARY_FEATURES = [
    "population_density",
    "habitable_population_density",
    "establishments_per_habitable_km2",
    "eateries_per_habitable_km2",
    "clinics_per_habitable_km2",
    "primary_employment_share",
    "tertiary_employment_share",
]

EXTENDED_FEATURES = [
    *PRIMARY_FEATURES,
    "did_population_share",
    "commercial_establishments_per_habitable_km2",
    "retail_stores_per_habitable_km2",
    "large_retail_stores_per_habitable_km2",
    "cultivated_land_share",
]

LOG_FEATURES = {
    "population_density",
    "habitable_population_density",
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
}

DOMAINS = {
    "population_concentration": [
        "population_density",
        "habitable_population_density",
    ],
    "services": [
        "establishments_per_habitable_km2",
        "eateries_per_habitable_km2",
        "clinics_per_habitable_km2",
    ],
    "employment_structure": [
        "primary_employment_share",
        "tertiary_employment_share",
    ],
}

VALIDATION_OUTCOMES = {
    "net_migration_per_1000_2024": "validation_net_migration_per_1000",
    "taxable_income_per_taxpayer_2024": "validation_taxable_income_per_taxpayer_yen",
    "dwelling_floor_area_m2_2023": "validation_dwelling_floor_area_m2",
}


@dataclass(frozen=True)
class PreprocessState:
    features: tuple[str, ...]
    lower: np.ndarray
    upper: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    log_mask: np.ndarray


@dataclass(frozen=True)
class PCAFit:
    features: tuple[str, ...]
    state: PreprocessState
    components: np.ndarray
    scores: np.ndarray
    eigenvalues: np.ndarray
    explained_variance_ratio: np.ndarray
    standardized: np.ndarray


def _transform_raw(values: np.ndarray, features: Iterable[str], use_log: bool = True) -> tuple[np.ndarray, np.ndarray]:
    transformed = np.asarray(values, dtype=float).copy()
    features = tuple(features)
    log_mask = np.array([use_log and feature in LOG_FEATURES for feature in features])
    if np.any(log_mask):
        if np.any(transformed[:, log_mask] < 0):
            raise ValueError("log1p features must be non-negative")
        transformed[:, log_mask] = np.log1p(transformed[:, log_mask])
    return transformed, log_mask


def preprocess_fit(
    frame: pd.DataFrame,
    features: Iterable[str],
    *,
    winsor: tuple[float, float] | None = None,
    use_log: bool = True,
) -> tuple[np.ndarray, PreprocessState]:
    features = tuple(features)
    values, log_mask = _transform_raw(frame.loc[:, features].to_numpy(), features, use_log)
    if not np.isfinite(values).all():
        raise ValueError("PCA feature matrix contains missing or infinite values")
    if winsor is None:
        lower = np.full(values.shape[1], -np.inf)
        upper = np.full(values.shape[1], np.inf)
    else:
        lower = np.quantile(values, winsor[0], axis=0)
        upper = np.quantile(values, winsor[1], axis=0)
    clipped = np.clip(values, lower, upper)
    mean = clipped.mean(axis=0)
    scale = clipped.std(axis=0, ddof=1)
    if np.any(scale <= 0):
        constant = [features[i] for i in np.flatnonzero(scale <= 0)]
        raise ValueError(f"Constant PCA features: {constant}")
    standardized = (clipped - mean) / scale
    state = PreprocessState(features, lower, upper, mean, scale, log_mask)
    return standardized, state


def preprocess_apply(frame: pd.DataFrame, state: PreprocessState) -> np.ndarray:
    # Copy is essential: repeated bootstrap projections must never mutate the
    # source DataFrame through a NumPy view.
    values = frame.loc[:, state.features].to_numpy(dtype=float, copy=True)
    if np.any(state.log_mask):
        values[:, state.log_mask] = np.log1p(values[:, state.log_mask])
    values = np.clip(values, state.lower, state.upper)
    standardized = (values - state.mean) / state.scale
    if not np.isfinite(standardized).all():
        raise ValueError("Projection produced non-finite standardized values")
    return standardized


def _pca_from_standardized(
    standardized: np.ndarray,
    features: Iterable[str],
    state: PreprocessState,
    orient_to: str = "population_density",
) -> PCAFit:
    _, singular, vt = np.linalg.svd(standardized, full_matrices=False)
    eigenvalues = singular**2 / (len(standardized) - 1)
    components = vt.copy()
    # einsum avoids spurious Accelerate/BLAS overflow warnings observed for a
    # small, perfectly finite matrix on macOS while producing the same product.
    scores = np.einsum("ij,kj->ik", standardized, components)
    feature_tuple = tuple(features)
    if orient_to not in feature_tuple:
        orient_to = (
            "tertiary_employment_share"
            if "tertiary_employment_share" in feature_tuple
            else feature_tuple[0]
        )
    orient_index = feature_tuple.index(orient_to)
    if components[0, orient_index] < 0:
        components[0] *= -1
        scores[:, 0] *= -1
    explained = eigenvalues / eigenvalues.sum()
    return PCAFit(feature_tuple, state, components, scores, eigenvalues, explained, standardized)


def fit_pca(
    frame: pd.DataFrame,
    features: Iterable[str] = PRIMARY_FEATURES,
    *,
    winsor: tuple[float, float] | None = None,
    use_log: bool = True,
) -> PCAFit:
    standardized, state = preprocess_fit(frame, features, winsor=winsor, use_log=use_log)
    return _pca_from_standardized(standardized, tuple(features), state)


def project_pc1(frame: pd.DataFrame, fit: PCAFit) -> np.ndarray:
    return np.einsum("ij,j->i", preprocess_apply(frame, fit.state), fit.components[0])


def _safe_spearman(x: np.ndarray, y: np.ndarray) -> float:
    result = spearmanr(x, y, nan_policy="omit")
    return float(result.statistic)


def bootstrap_stability(
    frame: pd.DataFrame,
    baseline: PCAFit,
    n_bootstrap: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, float], np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(frame)
    coefficients = np.empty((n_bootstrap, len(baseline.features)))
    rank_correlations = np.empty(n_bootstrap)
    percentile_ranks = np.empty((n_bootstrap, n), dtype=np.float32)
    baseline_rank = rankdata(baseline.scores[:, 0], method="average")

    for iteration in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)
        sample = frame.iloc[indices]
        boot = fit_pca(sample, baseline.features)
        component = boot.components[0].copy()
        if np.dot(component, baseline.components[0]) < 0:
            component *= -1
        coefficients[iteration] = component
        full_standardized = preprocess_apply(frame, boot.state)
        full_scores = np.einsum("ij,j->i", full_standardized, component)
        ranks = rankdata(full_scores, method="average")
        percentile_ranks[iteration] = ranks / n * 100
        rank_correlations[iteration] = _safe_spearman(baseline_rank, ranks)

    summary = pd.DataFrame(
        {
            "feature": baseline.features,
            "coefficient": baseline.components[0],
            "bootstrap_median": np.median(coefficients, axis=0),
            "ci_2_5": np.quantile(coefficients, 0.025, axis=0),
            "ci_97_5": np.quantile(coefficients, 0.975, axis=0),
            "same_sign_probability": np.mean(
                np.sign(coefficients) == np.sign(baseline.components[0]), axis=0
            ),
        }
    )
    rank_summary = {
        "median_spearman": float(np.median(rank_correlations)),
        "ci_2_5": float(np.quantile(rank_correlations, 0.025)),
        "ci_97_5": float(np.quantile(rank_correlations, 0.975)),
        "replicates": int(n_bootstrap),
    }
    return summary, rank_summary, percentile_ranks


def _bootstrap_spearman_ci(x: np.ndarray, y: np.ndarray, n_bootstrap: int, rng: np.random.Generator) -> tuple[float, float]:
    n = len(x)
    values = np.empty(n_bootstrap)
    for iteration in range(n_bootstrap):
        indices = rng.integers(0, n, size=n)
        values[iteration] = _safe_spearman(x[indices], y[indices])
    return float(np.nanquantile(values, 0.025)), float(np.nanquantile(values, 0.975))


def _holm_adjust(p_values: np.ndarray) -> np.ndarray:
    order = np.argsort(p_values)
    adjusted = np.empty_like(p_values, dtype=float)
    running = 0.0
    count = len(p_values)
    for position, index in enumerate(order):
        value = min(1.0, (count - position) * p_values[index])
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def external_validation(
    frame: pd.DataFrame,
    scores: np.ndarray,
    n_bootstrap: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float | int | str]] = []
    for label, column in VALIDATION_OUTCOMES.items():
        outcome = frame[column].to_numpy(dtype=float)
        keep = np.isfinite(outcome) & np.isfinite(scores)
        result = spearmanr(scores[keep], outcome[keep])
        lower, upper = _bootstrap_spearman_ci(
            scores[keep], outcome[keep], n_bootstrap, rng
        )
        rows.append(
            {
                "outcome": label,
                "source_column": column,
                "n": int(keep.sum()),
                "spearman_rho": float(result.statistic),
                "ci_2_5": lower,
                "ci_97_5": upper,
                "p_value": float(result.pvalue),
            }
        )
    validation = pd.DataFrame(rows)
    validation["holm_p_value"] = _holm_adjust(validation["p_value"].to_numpy())
    return validation


def sensitivity_checks(data: pd.DataFrame, analysis: pd.DataFrame, baseline: PCAFit) -> pd.DataFrame:
    baseline_scores = baseline.scores[:, 0]
    rows: list[dict[str, float | int | str]] = []

    alternatives = [
        ("winsorization_1_99", PRIMARY_FEATURES, (0.01, 0.99), True),
        ("no_log_transforms", PRIMARY_FEATURES, None, False),
        ("extended_12_feature_set", EXTENDED_FEATURES, None, True),
        (
            "original_per_capita_service_rates",
            [
                "population_density",
                "habitable_population_density",
                "establishments_per_1000",
                "eateries_per_1000",
                "clinics_per_10000",
                "primary_employment_share",
                "tertiary_employment_share",
            ],
            None,
            True,
        ),
    ]
    for name, features, winsor, use_log in alternatives:
        complete = np.isfinite(analysis[features]).all(axis=1)
        subset = analysis.loc[complete]
        alternative = fit_pca(subset, features, winsor=winsor, use_log=use_log)
        rows.append(
            {
                "analysis": name,
                "n": len(subset),
                "pc1_explained_variance": alternative.explained_variance_ratio[0],
                "score_spearman_vs_primary": _safe_spearman(
                    baseline_scores[complete.to_numpy()], alternative.scores[:, 0]
                ),
            }
        )

    for domain, omitted in DOMAINS.items():
        features = [feature for feature in PRIMARY_FEATURES if feature not in omitted]
        alternative = fit_pca(analysis, features)
        rows.append(
            {
                "analysis": f"leave_out_{domain}",
                "n": len(analysis),
                "pc1_explained_variance": alternative.explained_variance_ratio[0],
                "score_spearman_vs_primary": _safe_spearman(
                    baseline_scores, alternative.scores[:, 0]
                ),
            }
        )

    granular = data.loc[
        data["granular_population"]
        & np.isfinite(data[PRIMARY_FEATURES]).all(axis=1)
    ].copy()
    granular_fit = fit_pca(granular, PRIMARY_FEATURES)
    common_codes = analysis["municipality_code"].isin(granular["municipality_code"])
    common_primary = analysis.loc[common_codes]
    common_granular = granular.set_index("municipality_code").loc[
        common_primary["municipality_code"]
    ]
    rows.append(
        {
            "analysis": "granular_ward_geography",
            "n": len(granular),
            "pc1_explained_variance": granular_fit.explained_variance_ratio[0],
            "score_spearman_vs_primary": _safe_spearman(
                baseline_scores[common_codes.to_numpy()],
                project_pc1(common_granular, granular_fit),
            ),
        }
    )
    return pd.DataFrame(rows)


def _write_plots(
    output: Path,
    baseline: PCAFit,
    loading_summary: pd.DataFrame,
    validation: pd.DataFrame,
    analysis: pd.DataFrame,
) -> None:
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "svg.hashsalt": "japan-municipal-urbanization-pca",
    })

    fig, ax = plt.subplots(figsize=(7, 4.5))
    components = np.arange(1, len(baseline.explained_variance_ratio) + 1)
    ax.plot(components, baseline.explained_variance_ratio * 100, marker="o")
    ax.set(xlabel="Principal component", ylabel="Explained variance (%)", xticks=components)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(figure_dir / "scree.svg", metadata={"Date": None})
    plt.close(fig)

    plot = loading_summary.sort_values("coefficient")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    colors = ["#9b3a32" if value < 0 else "#1f6f8b" for value in plot["coefficient"]]
    ax.barh(plot["feature"], plot["coefficient"], color=colors)
    ax.errorbar(
        plot["coefficient"],
        np.arange(len(plot)),
        xerr=np.vstack(
            [
                plot["coefficient"] - plot["ci_2_5"],
                plot["ci_97_5"] - plot["coefficient"],
            ]
        ),
        fmt="none",
        ecolor="#333333",
        capsize=2,
        linewidth=0.8,
    )
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set(xlabel="PC1 coefficient (bootstrap 95% interval)")
    fig.tight_layout()
    fig.savefig(figure_dir / "pc1_coefficients.svg", metadata={"Date": None})
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    scores = baseline.scores[:, 0]
    for axis, (label, column) in zip(axes, VALIDATION_OUTCOMES.items()):
        outcome = analysis[column].to_numpy(float)
        keep = np.isfinite(outcome)
        # Thousands of vector circle nodes inflate the SVG to almost 800 KB.
        # Rasterize only the point layer at export time; axes, labels, titles,
        # and gridlines remain resolution-independent vector elements.
        axis.scatter(
            scores[keep],
            outcome[keep],
            s=7,
            alpha=0.35,
            color="#1f6f8b",
            edgecolors="none",
            rasterized=True,
        )
        rho = validation.loc[validation["outcome"].eq(label), "spearman_rho"].iloc[0]
        axis.set_title(f"{label}\nSpearman rho={rho:.2f}", fontsize=9)
        axis.set_xlabel("PC1 score")
        axis.grid(color="#e5e5e5", linewidth=0.5)
    axes[0].set_ylabel("Held-out outcome")
    fig.tight_layout()
    fig.savefig(
        figure_dir / "external_validation.svg",
        metadata={"Date": None},
        dpi=180,
    )
    plt.close(fig)


def run_analysis(
    input_csv: Path,
    output: Path,
    *,
    seed: int = 20260929,
    bootstrap: int = 1_000,
    validation_bootstrap: int = 2_000,
) -> dict[str, object]:
    data = pd.read_csv(input_csv, dtype={"municipality_code": str, "parent_code": str})
    analysis = data.loc[data["analysis_eligible"]].copy().reset_index(drop=True)
    if len(analysis) < 1_700:
        raise ValueError(f"Unexpectedly small primary analysis population: {len(analysis)}")
    if not np.isfinite(analysis[PRIMARY_FEATURES]).all(axis=1).all():
        raise ValueError("Eligible rows contain non-finite primary features")

    output.mkdir(parents=True, exist_ok=True)
    baseline = fit_pca(analysis, PRIMARY_FEATURES)
    loading_summary, rank_summary, percentile_ranks = bootstrap_stability(
        analysis, baseline, bootstrap, seed
    )

    correlation_loadings = baseline.components.T * np.sqrt(baseline.eigenvalues)
    loading_summary["correlation_loading"] = correlation_loadings[:, 0]
    loading_summary.to_csv(output / "pc1_loadings.csv", index=False, float_format="%.8g")

    explained = pd.DataFrame(
        {
            "component": np.arange(1, len(baseline.eigenvalues) + 1),
            "eigenvalue": baseline.eigenvalues,
            "explained_variance_ratio": baseline.explained_variance_ratio,
            "cumulative_explained_variance": np.cumsum(baseline.explained_variance_ratio),
        }
    )
    explained.to_csv(output / "explained_variance.csv", index=False, float_format="%.8g")

    correlations = analysis[PRIMARY_FEATURES].corr(method="spearman")
    correlations.index.name = "feature"
    correlations.to_csv(output / "feature_spearman_correlations.csv", float_format="%.8g")

    quality_columns = [*EXTENDED_FEATURES, *VALIDATION_OUTCOMES.values()]
    primary_rows = data.loc[data["primary_population"]]
    quality_rows = []
    for column in quality_columns:
        values = pd.to_numeric(primary_rows[column], errors="coerce").to_numpy(float)
        finite = np.isfinite(values)
        quality_rows.append(
            {
                "field": column,
                "population_rows": len(primary_rows),
                "finite_rows": int(finite.sum()),
                "missing_or_nonfinite_rows": int((~finite).sum()),
                "missing_or_nonfinite_fraction": float((~finite).mean()),
            }
        )
    pd.DataFrame(quality_rows).to_csv(
        output / "data_quality.csv", index=False, float_format="%.8g"
    )

    sample_flow = pd.DataFrame(
        [
            {"stage": "published_non_prefecture_rows", "n": len(data)},
            {"stage": "non_overlapping_primary_population", "n": int(data["primary_population"].sum())},
            {"stage": "primary_pca_analysis", "n": len(analysis)},
        ]
    )
    sample_flow.to_csv(output / "sample_flow.csv", index=False)

    per_capita_features = [
        "population_density",
        "habitable_population_density",
        "establishments_per_1000",
        "eateries_per_1000",
        "clinics_per_10000",
        "primary_employment_share",
        "tertiary_employment_share",
    ]
    per_capita_fit = fit_pca(analysis, per_capita_features)
    per_capita_loadings = pd.DataFrame(
        {
            "feature": per_capita_features,
            "coefficient": per_capita_fit.components[0],
            "correlation_loading": per_capita_fit.components[0]
            * np.sqrt(per_capita_fit.eigenvalues[0]),
        }
    )
    per_capita_loadings.to_csv(
        output / "original_per_capita_pc1_loadings.csv",
        index=False,
        float_format="%.8g",
    )

    scores = analysis[
        ["municipality_code", "municipality_name_jp", "municipality_name_en", "unit_role"]
    ].copy()
    scores["pc1_score"] = baseline.scores[:, 0]
    scores["pc2_score"] = baseline.scores[:, 1]
    scores["pc1_percentile_rank"] = rankdata(baseline.scores[:, 0]) / len(scores) * 100
    scores["rank_percentile_ci_2_5"] = np.quantile(percentile_ranks, 0.025, axis=0)
    scores["rank_percentile_ci_97_5"] = np.quantile(percentile_ranks, 0.975, axis=0)
    scores = scores.sort_values("pc1_score", ascending=False)
    scores.to_csv(output / "municipality_scores.csv", index=False, float_format="%.8g")

    validation = external_validation(
        analysis, baseline.scores[:, 0], validation_bootstrap, seed + 1
    )
    validation.to_csv(output / "external_validation.csv", index=False, float_format="%.8g")

    sensitivity = sensitivity_checks(data, analysis, baseline)
    sensitivity.to_csv(output / "sensitivity.csv", index=False, float_format="%.8g")

    metrics: dict[str, object] = {
        "seed": seed,
        "published_non_prefecture_rows": int(len(data)),
        "primary_population_rows": int(data["primary_population"].sum()),
        "analysis_rows": int(len(analysis)),
        "excluded_rows": {
            str(key): int(value)
            for key, value in data.loc[~data["analysis_eligible"], "analysis_exclusion_reason"]
            .value_counts()
            .items()
        },
        "features": PRIMARY_FEATURES,
        "pc1_explained_variance_ratio": float(baseline.explained_variance_ratio[0]),
        "pc2_explained_variance_ratio": float(baseline.explained_variance_ratio[1]),
        "bootstrap_rank_stability": rank_summary,
        "external_validation": validation.to_dict(orient="records"),
        "sensitivity": sensitivity.to_dict(orient="records"),
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_plots(output, baseline, loading_summary, validation, analysis)
    return metrics
