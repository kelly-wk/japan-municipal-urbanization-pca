# Changelog

## 1.0.0

- Rebuilt the dataset from pinned official e-Stat workbooks.
- Defined non-overlapping primary and granular municipal geographies.
- Replaced the undocumented 100-row stratified sample with the full target population.
- Separated PCA inputs from later held-out validation outcomes.
- Removed DID and cultivated-land variables from the primary model because of official missingness.
- Replaced per-capita facility rates with spatial facility densities in the primary model.
- Added deterministic PCA, loading/rank bootstrap, sensitivity analyses, tests, data card, and provenance audit.

