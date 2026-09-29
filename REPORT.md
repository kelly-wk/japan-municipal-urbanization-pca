# PCAに基づく日本の市区町村の都市化指標 / PCA-Based Urbanization Index for Japanese Municipalities

## Abstract

This study builds a reproducible principal-component index of spatial concentration and employment structure for Japanese municipalities. It uses the full, non-overlapping target population from official *Statistical Observations of Municipalities 2024* data published through e-Stat and validates the index against later indicators that were excluded from PCA.

The source release contains 1,917 non-prefecture rows, including both designated-city totals and their subordinate wards. The primary geography retains designated-city totals and Tokyo's 23 special wards while excluding overlapping designated-city wards and the aggregate `特別区部` row. This yields 1,741 non-overlapping units. One municipality has zero 2020 census population and cannot support ratio construction, leaving 1,740 observations for PCA.

Five right-skewed spatial-density fields are transformed with `log(1+x)` and standardized together with two employment-composition shares. PC1 explains 80.27% of standardized variance. Positive scores combine population and facility concentration with a larger tertiary-employment share and a smaller primary-employment share. It is therefore interpreted cautiously as a **spatial-concentration and urban-employment axis**, not an official government urbanization rating.

Across 1,000 municipality bootstraps, the median Spearman correlation between bootstrap and primary PC1 ranks is 0.999991, with a 95% interval of [0.999961, 0.999998]. Later official indicators show associations in the preregistered directions: net migration `rho=0.498`, taxable income per taxpayer `rho=0.597`, and floor area per dwelling `rho=-0.738`. These results support stability and convergent validity while retaining limitations from mixed reference years, spatial dependence, administrative boundaries, and ecological inference.

## 1. Research questions

1. Can population, facility, and employment indicators across Japanese municipalities be summarized by a stable common axis?
2. Does that axis match the proposed interpretation of spatial concentration and non-agricultural employment structure?
3. Does it associate in prespecified directions with later official indicators that never enter PCA?
4. Are conclusions robust to tail handling, transformations, feature domains, and municipal geography?

This is an exploratory measurement study. PCA maximizes explained variance; it does not automatically discover a uniquely true concept of urbanization.

## 2. Data

### 2.1 PCA inputs

The primary inputs come from official e-Stat workbooks for *Statistical Observations of Municipalities 2024*.

| Concept | Construction | Reference year |
|---|---|---:|
| Population density | population / total area | 2020 / 2022 |
| Habitable population density | population / habitable area | 2020 / 2022 |
| Private-establishment density | private establishments / habitable area | 2021 / 2022 |
| Eatery density | eating and drinking places / habitable area | 2021 / 2022 |
| Clinic density | general clinics / habitable area | 2021 / 2022 |
| Primary-employment share | primary-industry workers / employed persons | 2020 |
| Tertiary-employment share | tertiary-industry workers / employed persons | 2020 |

Because the fields are not a single-year cross-section, the index describes structure around 2020–2022 rather than one exact date.

### 2.2 Held-out external indicators

Three outcomes are excluded completely from model specification and taken from the later 2026 publication:

- 2024 net migration per 1,000 registered residents; expected positive association;
- 2024 taxable income per taxpayer; expected positive association;
- 2023 floor area per dwelling; expected negative association because housing is generally smaller in denser municipalities.

This is out-of-feature-set and later-publication validation, not an experiment. It cannot establish causal or policy effects.

### 2.3 Sample flow

| Stage | n |
|---|---:|
| Non-prefecture rows in the 2024 release | 1,917 |
| Non-overlapping target population | 1,741 |
| Valid PCA analysis sample | 1,740 |

The 176 hierarchy exclusions comprise 175 designated-city ward rows and one Tokyo `特別区部` aggregate. One additional row has a zero census-population denominator. The rules are implemented in `src/urban_pca/data.py` and covered by automated tests.

## 3. Methods

### 3.1 Preprocessing

Population density, habitable population density, and the three facility densities are non-negative and strongly right-skewed, so they receive `log(1+x)` transformations. Employment shares remain on their original scale. All seven fields are then standardized over the 1,740-row analysis population.

The primary analysis does not winsorize. A 1st/99th-percentile winsorized specification is retained as a sensitivity analysis.

### 3.2 PCA orientation

PCA is fitted by singular-value decomposition of the standardized matrix. Because component sign is arbitrary, PC1 is oriented so that the population-density coefficient is positive. Results report both unit-length eigenvector coefficients and correlation loadings between standardized variables and component scores.

### 3.3 Bootstrap stability

Using seed `20260929`, municipalities are sampled with replacement 1,000 times. Each replicate refits transformation statistics and PCA, aligns PC1 sign to the primary coefficient vector, and projects all 1,740 municipalities through the refitted model. The outputs include:

- percentile 95% intervals for every PC1 coefficient;
- percentile-rank intervals for every municipality;
- Spearman correlation between each bootstrap ranking and the primary ranking.

This reflects sampling and model-estimation uncertainty. It does not include official-statistics measurement error, spatial dependence, or historical revision uncertainty.

### 3.4 External validation

Spearman associations between PC1 and the three held-out outcomes use 2,000 paired bootstrap replicates for 95% intervals. Conventional p-values are Holm-adjusted across the three outcomes. Because municipalities are spatially dependent, interpretation emphasizes effect sizes and intervals rather than p-values.

## 4. Results

### 4.1 Explained variance

PC1 explains 80.27% of standardized variance and PC2 explains 9.18%; the first two axes explain 89.45% cumulatively.

### 4.2 PC1 loadings

| Variable | Coefficient | Correlation loading | Bootstrap 95% interval |
|---|---:|---:|---:|
| Private establishments / habitable km² | 0.413 | 0.978 | [0.411, 0.415] |
| Habitable population density | 0.409 | 0.969 | [0.407, 0.411] |
| Eateries / habitable km² | 0.402 | 0.952 | [0.399, 0.404] |
| Population density | 0.389 | 0.921 | [0.386, 0.391] |
| Clinics / habitable km² | 0.383 | 0.909 | [0.380, 0.386] |
| Tertiary-employment share | 0.304 | 0.721 | [0.293, 0.315] |
| Primary-employment share | -0.332 | -0.788 | [-0.338, -0.327] |

All coefficient signs remain unchanged across the 1,000 bootstrap replicates.

### 4.3 Ranking stability

The median bootstrap rank correlation is 0.999991, with a 95% interval of [0.999961, 0.999998]. Resampling municipalities therefore changes the ranking very little under the selected fields and released values.

This must not be interpreted as exact knowledge of a true urbanization rank. The interval excludes measurement error, reference-year differences, boundary changes, spatial-model uncertainty, and alternative theoretical definitions.

### 4.4 External validation

| Held-out outcome | n | Spearman rho | Bootstrap 95% interval |
|---|---:|---:|---:|
| 2024 net migration per 1,000 residents | 1,740 | 0.498 | [0.458, 0.535] |
| 2024 taxable income per taxpayer | 1,740 | 0.597 | [0.556, 0.636] |
| 2023 floor area per dwelling | 1,059 | -0.738 | [-0.772, -0.700] |

All directions match the prespecified expectations. Floor-area coverage is lower, so that result applies to the 1,059 observed municipalities rather than the entire primary population.

### 4.5 Sensitivity analysis

| Specification | n | PC1 explained variance | Score correlation with primary model |
|---|---:|---:|---:|
| 1%/99% winsorization | 1,740 | 0.811 | 1.000 |
| No log transformation | 1,740 | 0.684 | 0.960 |
| Extended 12-field complete cases | 792 | 0.753 | 0.994 |
| Per-capita facility rates | 1,740 | 0.484 | 0.935 |
| Drop population-concentration domain | 1,740 | 0.782 | 0.986 |
| Drop facility domain | 1,740 | 0.769 | 0.988 |
| Drop employment-structure domain | 1,740 | 0.921 | 0.985 |
| Split designated cities into wards | 1,895 | 0.820 | 1.000 |

The index is stable to winsorization, single-domain removal, and geography. Removing log transformations retains a high rank correlation but reduces explained variance. Per-capita facility rates yield substantially lower explained variance and facility coefficients opposite to the intended interpretation; they are therefore unsuitable as the primary definition.

## 5. Interpretation and limitations

The evidence supports a stable common axis of spatial concentration and urban employment structure. Its input directions are coherent, and it shows moderate-to-strong convergence with later migration, income, and housing indicators.

The study does **not** support claims that:

- PC1 is the unique or official definition of urbanization;
- it measures municipal governance quality;
- municipality-level associations apply to individuals;
- urbanization causes migration, income, or housing differences;
- small rank differences justify funding, sanctions, or performance decisions.

Major limitations are mixed input years, shared area denominators, unmodeled spatial dependence, changing administrative boundaries, incomplete floor-area coverage, and the linear unsupervised nature of PCA.

## 6. Reproducibility

```bash
make setup
make reproduce
```

The reviewed processed snapshot supports offline reproduction. `make fetch` and `make prepare` rebuild it from official workbooks after checking pinned hashes. Numerical outputs, sample-flow records, sensitivities, and source metadata are committed under `results/` and `provenance/`.

## 7. References

- [e-Stat: Statistical Observations of Municipalities 2024](https://www.e-stat.go.jp/stat-search/files?cycle=0&kikan=00200&layout=dataset&page=1&result_page=1&tclass1=000001218561&tclass2val=0&toukei=00200502&tstat=000001218560)
- [Statistics Bureau of Japan: Statistical Observations of Prefectures and Municipalities](https://www.stat.go.jp/data/ssds/)
- [Statistics Bureau of Japan: municipal-statistics overview](https://www.stat.go.jp/data/s-sugata/gaiyou.htm)
- [e-Stat terms of use](https://www.e-stat.go.jp/terms-of-use)
