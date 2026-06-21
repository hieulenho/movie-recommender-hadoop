# Final Report Content

## Primary Dataset And Scope

The final report uses MovieLens 1M as the primary real experimental dataset.

Report generated values from `target/final-report-data/` after running:

```powershell
python scripts/build_final_report_data.py --output-dir target/final-report-data
```

Primary artifact sources:

- `results/movielens-1m/normalized/dataset_stats.json`
- `results/movielens-1m/split/split_stats.json`
- `results/movielens-1m/method_comparison.csv`
- `results/movielens-1m/stage_metrics.json`
- `results/movielens-1m/movielens_1m_manifest.json`
- `target/final-validation/streamlit_movielens_1m_validation.json`

Required dataset facts:

- Dataset: MovieLens 1M
- Role: primary real experiment
- Rating rows: Chưa có kết quả MovieLens 1M
- Distinct users: Chưa có kết quả MovieLens 1M
- Distinct rated movies: Chưa có kết quả MovieLens 1M
- Metadata movies: Chưa có kết quả MovieLens 1M
- Rating scale: whole-star integer ratings from 1 through 5
- Timestamp range UTC: Chưa có kết quả MovieLens 1M

Do not substitute the GitHub 15-file dataset when a MovieLens value is missing.

## Split Protocol

MovieLens 1M uses deterministic leave-one-out by exact timestamp:

1. Sort each user's ratings by Unix timestamp ascending.
2. Break equal timestamps by movie ID ascending.
3. Hold out the final record.

Required split facts:

- Split method: leave-one-out-by-exact-timestamp
- Train rows: Chưa có kết quả MovieLens 1M
- Test rows: Chưa có kết quả MovieLens 1M
- Train/test overlap rows: Chưa có kết quả MovieLens 1M

The held-out test set must not enter user-history, pair-statistics, similarity, scoring, or Top-K stages.

## Pipeline Parameters

Document the actual run parameters from the MovieLens manifest:

- Top-L: Chưa có kết quả MovieLens 1M
- Top-K: Chưa có kết quả MovieLens 1M
- Minimum common users: Chưa có kết quả MovieLens 1M
- Relevance threshold: Chưa có kết quả MovieLens 1M
- Reducers: Chưa có kết quả MovieLens 1M

Defaults are documented experiment defaults, not universal optima.

## Method Metrics

Use `results/movielens-1m/method_comparison.csv`.

| Method | Coverage | MAE | RMSE | Precision@K | Recall@K | HitRate@K | NDCG@K | MRR@K | Total seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cosine | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |
| cooccurrence | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |

Do not claim statistical significance from one deterministic run.

## Stage Outputs And Runtime

Use `results/movielens-1m/stage_metrics.json` for row counts, byte counts, and runtime by stage.

Call out that `common/pair-statistics` is built once and shared by cosine and co-occurrence.

## Streamlit Validation

The Streamlit demo is read-only. It loads MovieLens user-history, recommendations, metadata, metrics, and optional synthetic benchmark artifacts. It does not run Hadoop, Maven, Docker, preprocessing, or model-building jobs.

Recommended MovieLens artifact paths:

- User history: `results/movielens-1m/common/user-history/`
- Cosine recommendations: `results/movielens-1m/cosine/recommendations/`
- Co-occurrence recommendations: `results/movielens-1m/cooccurrence/recommendations/`
- Metadata: `results/movielens-1m/normalized/movie_metadata.csv`
- Metrics: `results/movielens-1m/<method>/metrics.json`

Report validation status from `target/final-validation/streamlit_movielens_1m_validation.json`.

## Compatibility And Scalability Sections

The GitHub 15-file workflow should appear as compatibility or appendix validation only. It should not be described as the final recommendation-quality dataset.

Synthetic benchmark results should appear only in the scalability section. Docker Hadoop local mode is single-container reproducibility validation, not multi-node cluster speedup.

## Limitations

- Raw MovieLens 1M files are not redistributed or committed.
- Missing predictions are reported and are not imputed as zero.
- Docker Hadoop local mode does not start HDFS/YARN daemons and does not measure distributed cluster scaling.
- Generated results under `results/movielens-1m/` and `target/final-report-data/` remain untracked.
