# Final Results Summary

## Full Reference Dataset

The final full-reference run uses the 15 movie files available in `thviet79/Bigdata_Project_Recommender_System`, not the complete official Netflix Prize dataset.

| Field | Value |
|---|---:|
| Rating rows | 21629 |
| Distinct users | 20537 |
| Distinct movies | 15 |
| Train rows | 20741 |
| Test rows | 888 |
| Train/test overlap rows | 0 |
| Watched recommendation violations | 0 |

Source rows are `userId,movieId,rating` and contain no rating dates. The full-reference run therefore uses `deterministic-leave-one-out-by-item`: for each eligible user, ratings are sorted by numeric `movieId` and the highest `movieId` is held out. The placeholder date `1970-01-01` is written only after splitting for Hadoop schema compatibility.

## Method Comparison

| Method | Coverage | MAE | RMSE | Precision@K | Recall@K | NDCG@K | MRR@K | Local-mode seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cosine | 0.8592342342 | 1.2628957245 | 1.6590045822 | 0.0258675079 | 0.1293375394 | 0.0558198181 | 0.0328075710 | 27.285297 |
| cooccurrence | 0.8547297297 | 1.2684552218 | 1.6720603280 | 0.0233438486 | 0.1167192429 | 0.0554198178 | 0.0362250263 | 38.672707 |

These values come from `results/full-reference-dataset/method_comparison.csv`.

## Scalability

Chưa có dữ liệu thực nghiệm.

No real `target/scalability-benchmark/benchmark_results.csv` artifact was present during finalization. Docker Hadoop local-mode timings in the full-reference workflow should be described as single-container reproducibility timings, not multi-node scaling evidence.
