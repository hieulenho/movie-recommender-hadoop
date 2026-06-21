# Final Results Summary

## Primary MovieLens 1M Dataset

MovieLens 1M is the primary real experimental dataset. Populate this summary from `target/final-report-data/` after a completed full run.

| Field | Value |
|---|---:|
| Rating rows | Chưa có kết quả MovieLens 1M |
| Distinct users | Chưa có kết quả MovieLens 1M |
| Distinct rated movies | Chưa có kết quả MovieLens 1M |
| Metadata movies | Chưa có kết quả MovieLens 1M |
| Train rows | Chưa có kết quả MovieLens 1M |
| Test rows | Chưa có kết quả MovieLens 1M |
| Train/test overlap rows | Chưa có kết quả MovieLens 1M |
| Watched recommendation violations | Chưa có kết quả MovieLens 1M |

The split is deterministic leave-one-out by exact timestamp. The latest timestamp per user is held out, with highest movie ID used only as the tie-breaker for equal timestamps.

## Method Comparison

Use `results/movielens-1m/method_comparison.csv`.

| Method | Coverage | MAE | RMSE | Precision@K | Recall@K | NDCG@K | MRR@K | Local-mode seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cosine | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |
| cooccurrence | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |

## Compatibility

The GitHub reference 15-movie dataset remains useful for workflow regression and appendix discussion. It is not the primary final-quality experiment.

## Scalability

Synthetic benchmark rows remain scalability-only evidence. Docker Hadoop local-mode timings should be described as single-container reproducibility timings, not multi-node scaling evidence.
