# Data card

## Dataset

`data/processed/municipal_indicators.csv` is a derived, municipality-level snapshot built from official e-Stat Excel files for *Statistical Observations of Municipalities 2024* and *2026*. It contains 1,917 non-prefecture publication rows so geography decisions remain auditable. Boolean fields identify the primary non-overlapping target population and the alternative ward-level geography.

## Population and unit of observation

The source publication includes both designated-city totals and subordinate ward rows. They overlap geographically and cannot appear together in an analysis that treats rows as independent units.

The primary population:

- keeps designated-city totals;
- removes their 175 subordinate ward rows;
- removes the aggregate `特別区部` row;
- keeps the 23 Tokyo special wards;
- retains all other municipalities.

This yields 1,741 non-overlapping units. One unit has zero 2020 census population and is retained in the file but excluded from ratio-based PCA, leaving 1,740 observations.

The alternative `granular_population` removes 20 designated-city totals and keeps their wards. After the zero-denominator exclusion, it supplies 1,895 observations for sensitivity analysis.

## Fields used in primary PCA

| Field | Definition | Transformation |
|---|---|---|
| `population_density` | 2020 census population / 2022 total area | `log1p`, then z-score |
| `habitable_population_density` | 2020 census population / 2022 inhabitable area | `log1p`, then z-score |
| `establishments_per_habitable_km2` | 2021 private establishments / 2022 inhabitable area | `log1p`, then z-score |
| `eateries_per_habitable_km2` | 2021 eating/drinking places / 2022 inhabitable area | `log1p`, then z-score |
| `clinics_per_habitable_km2` | 2021 general clinics / 2022 inhabitable area | `log1p`, then z-score |
| `primary_employment_share` | 2020 primary-industry workers / employed persons | z-score |
| `tertiary_employment_share` | 2020 tertiary-industry workers / employed persons | z-score |

## Held-out validation fields

| Field | Definition | Coverage in primary analysis |
|---|---|---:|
| `validation_net_migration_per_1000` | 2024 net in-migration / registered population × 1,000 | 1,740 |
| `validation_taxable_income_per_taxpayer_yen` | 2024 taxable income / income-tax payers | 1,740 |
| `validation_dwelling_floor_area_m2` | 2023 floor area per dwelling | 1,059 |

These fields never enter feature selection, scaling, or PCA.

## Missing data

The primary seven features are complete for 1,740 analyzable rows. DID population is unavailable for over half of the primary target population in the official file; it is not converted to zero and appears only in an extended complete-case sensitivity model. Cultivated-land coverage is also incomplete. Detailed counts are in `results/data_quality.csv`.

Official symbols that cannot be parsed as numeric—including `...`—remain missing. No generic zero fill or median imputation is used.

## Source and rights

Source: Statistics Bureau of Japan, *Statistical Observations of Municipalities 2024* and *2026*, distributed through e-Stat. The [e-Stat terms of use](https://www.e-stat.go.jp/terms-of-use) permit reuse with attribution and state compatibility with CC BY 4.0; numerical data and simple tables may not be copyrightable. This project nevertheless preserves full attribution and documents that the data were processed.

Raw workbooks are not committed. `scripts/download_sources.py` downloads them from e-Stat and verifies pinned SHA-256 hashes. The processed snapshot is committed so the reviewed results can be reproduced without relying on future network availability.

## Appropriate use

- exploratory regional structure research;
- methods teaching and replication;
- generating hypotheses for spatial models;
- comparing alternative measurement definitions.

## Inappropriate use

- municipal funding, sanctions, or performance evaluation;
- causal policy claims;
- individual-level inference;
- treating small rank differences as substantive certainty;
- mixing primary and granular geography flags in one unweighted analysis.

## Known limitations

Reference years differ across fields; municipalities are spatially dependent; shared area denominators induce correlation; administrative boundaries can change; no measurement-error model is available; the dataset contains aggregate public statistics and no individual records.

