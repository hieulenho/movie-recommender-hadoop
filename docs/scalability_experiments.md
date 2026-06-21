# Scalability Experiments

## Purpose

Milestone 10 adds a reproducible benchmark workflow for the completed offline Hadoop Item-CF pipeline. It measures how cost and recommendation quality change as input size and configuration change.

The benchmark runs the real train-only Hadoop workflow from Milestone 9:

```text
normalized or synthetic ratings
-> time-aware train/test split
-> train-only UserHistoryJob
-> ItemPairStatisticsJob
-> ItemSimilarityPipeline
-> RecommendationScoringPipeline
-> TopKRecommendationJob
-> offline evaluator
-> benchmark metrics and summary
```

Held-out test rows are read only by the evaluator. They are never passed to model-building stages.

## Runtime Interpretation

The authoritative runtime for this repository is Linux Docker with Hadoop local mode. Results measure:

- input-size scaling
- stage-level runtime
- output-row and byte growth
- configuration sensitivity
- recommendation-quality changes

They do not measure a multi-node Hadoop cluster, HDFS throughput, YARN scheduling, or horizontal worker scaling.

## Profiles

Profiles live in `config/scalability_profiles.json`.

| Profile | Intended Use | Sizes | Methods | Notes |
| --- | --- | --- | --- | --- |
| smoke | Normal validation and CI-like local checks | 250, 1000, 3000 ratings | cosine, cooccurrence | Fixed `min-common-users=1`, `top-l=10`, `top-k=5`, `reducers=1`, one repetition. |
| standard | Report-oriented local benchmark | about 10000, 25000, 50000 ratings | cosine, cooccurrence | One repetition; configuration varies across sizes for sensitivity checks. |
| extended | Manual large local benchmark | about 100000, 250000, 500000 ratings | cosine, cooccurrence | May require substantial time and memory. Do not run for normal validation. |

Smoke is the default validation profile.

## Synthetic Data

`scripts/generate_synthetic_ratings.py` creates normalized CSV files with the exact header:

```text
userId,movieId,rating,date
```

The generator uses `random.Random(seed)`, positive integer IDs, integer ratings from 1 through 5, deterministic dates, no duplicate user/movie pairs, and deterministic ordering by user ID, date, then movie ID.

Synthetic item assignment combines popular shared items with cyclic coverage so item-pair and similarity stages have co-rating overlap. When dimensions allow it, every generated item appears at least once.

Synthetic data is always labeled as `synthetic` in dataset statistics, manifests, CSV/JSON results, and summaries. Synthetic benchmark results must not be described as Netflix Prize benchmark results.

## External Normalized Input Mode

The runner also accepts an existing normalized CSV:

```powershell
python scripts/run_scalability_experiments.py --input data/processed/ratings.csv
```

The input schema is validated exactly. The source file is not modified. For different target sizes, the runner creates deterministic user-preserving subsets in the benchmark output directory: users are sorted numerically and complete user histories are selected until the requested row count is reached or exceeded.

The dataset type is recorded as `external-normalized`. The benchmark records row count, user count, item count, file size, and SHA-256, but documentation must not record machine-specific absolute host paths.

## Measurement Definitions

Durations are measured with `time.perf_counter()` and written in seconds:

- dataset generation or dataset selection
- split
- user history
- pair statistics
- similarity
- scoring
- Top-K
- evaluation
- total pipeline time
- total run time

Output rows are counted across all Hadoop `part-*` files. `_SUCCESS`, CRC files, hidden files, and logs are ignored.

Tracked output growth includes:

- rating rows
- train rows
- test rows
- user-history rows
- unordered item-pair rows
- directed similarity rows
- raw prediction rows
- users with final recommendation rows
- total recommendation items

Byte counts are measured from input CSV files and Hadoop text `part-*` outputs.

## Counter Policy

This milestone does not invent Hadoop counters and does not parse fragile human-readable Hadoop logs as the source of truth. If reliable structured counters are not available, counter fields are recorded as unavailable. Reports should rely on measured runtime, rows, bytes, and output growth.

Do not claim HDFS bytes, shuffle bytes, or scheduler behavior were measured by this local-mode benchmark.

## Commands

Run the smoke benchmark in Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke
```

Run the standard profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile standard
```

Run one filtered experiment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke -ExperimentFilter smoke-cosine-250-ratings
```

Resume completed runs and skip only valid completed manifests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke -Resume
```

The extended profile is for manual experiments only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile extended
```

Generated artifacts are written under `target/scalability-benchmark/` by default.

## Result Artifacts

Benchmark root:

- `benchmark_manifest.json`
- `benchmark_results.csv`
- `benchmark_results.json`
- `benchmark_summary.md`
- `method_comparison.csv`
- `size_scaling.csv`
- `failures.json`
- `datasets/`
- `runs/`

Each completed run contains:

- `run_manifest.json`
- `stage_metrics.json`
- `evaluation_metrics.json`
- `split_stats.json`
- `dataset_stats.json`
- `logs/`

When `--keep-stage-output` is not used, heavy Hadoop stage directories are removed after measurements and combined evaluator inputs are preserved.

## Summary Calculations

`scripts/summarize_scalability_results.py` reads `benchmark_results.csv` and writes:

- `benchmark_summary.md`
- `method_comparison.csv`
- `size_scaling.csv`

Calculated fields include:

- runtime growth factor relative to the smallest dataset in the same profile and method
- ratings throughput: `ratingsRows / totalPipelineSeconds`
- pair growth relative to ratings
- similarity growth relative to pair rows
- recommendation user coverage
- stage percentage of total pipeline time
- mean, min, max, and population standard deviation when multiple repetitions exist

Zero denominators produce empty fields, not NaN or Infinity.

The summary reports measured ratios. It does not automatically label runtime growth as linear, quadratic, or sublinear, and it does not make statistical claims from a single repetition.

## Using Results In A Report

Use smoke results to prove the workflow is reproducible. Use standard results for a stronger local-mode performance discussion. Include:

- the profile and exact experiment IDs
- dataset type
- method
- Top-L, Top-K, min-common-users, reducers
- row counts and output growth
- runtime table by stage
- quality metrics from the evaluator
- local-mode limitations

## Limitations

- Runs use one Docker container and Hadoop local mode.
- No Hadoop daemons are started.
- No Docker Compose cluster is created.
- No Spark, database, online serving, metadata enrichment, or fallback recommender is included in the benchmark workflow. The later Streamlit demo reads completed artifacts only.
- Synthetic datasets are controlled benchmark inputs, not real Netflix Prize measurements.

Milestone 11 adds the optional demonstration application stage over already generated artifacts.
