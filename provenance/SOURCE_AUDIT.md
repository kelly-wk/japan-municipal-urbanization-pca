# Official Source Audit and Publication Boundary

## Canonical sources

Every analytical value is rebuilt from *Statistical Observations of Municipalities* workbooks distributed through Japan's e-Stat portal. The 2024 release supplies the seven PCA inputs; the later 2026 release supplies outcomes that are held out of PCA and used only for external validation.

[`scripts/download_sources.py`](../scripts/download_sources.py) records the official URLs, e-Stat release identifiers, and expected SHA-256 hashes. [`manifest.json`](manifest.json) provides the machine-readable source and processed-snapshot record.

## Source and transformation checks

1. Every downloaded workbook must match its pinned SHA-256 hash.
2. Official missing-value symbols remain missing; they are never converted to zero.
3. Designated-city totals and subordinate wards are flagged so overlapping geographies cannot silently enter the same primary analysis.
4. The primary population is built from 1,741 non-overlapping municipal units; one zero-denominator unit is excluded from ratio-based PCA, leaving 1,740 observations.
5. PCA inputs and external-validation outcomes are separated before feature transformation.
6. Source-field coverage, sample flow, sensitivity specifications, and processed-snapshot hashes are committed as machine-readable results.

## Analytical design decisions

- The primary index uses the complete nationwide, non-overlapping target population rather than a convenience sample.
- Facility variables are defined per inhabitable square kilometre in the primary analysis; per-capita definitions remain a documented sensitivity check.
- Variables with material official missingness, including DID population and cultivated land, remain outside the primary complete-feature index.
- External indicators are used to assess descriptive convergence, not to claim causality or construct an official government score.

## Publication boundary

Included:

- original analysis code and automated tests;
- official aggregate statistics transformed with attribution;
- the reviewed processed snapshot, derived results, and SVG figures;
- official source identifiers and cryptographic hashes.

Excluded:

- raw e-Stat workbooks, which remain downloadable from the official source;
- personal information, local paths, credentials, and unrelated source material;
- any claim that the index is official, causal, or suitable for municipal performance evaluation.
