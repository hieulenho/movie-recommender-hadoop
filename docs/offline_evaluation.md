# Offline Evaluation

## Purpose

Milestone 9 adds a deterministic offline evaluation workflow for the Hadoop Item-CF recommendation pipeline. It measures how raw predicted ratings and final Top-K recommendation lists compare with held-out ratings.

The recommender algorithm remains in Java Hadoop MapReduce. Python standard-library scripts handle only train/test splitting, orchestration, and metric calculation.

## Time-Aware Split

The splitter reads normalized ratings CSV:

```text
userId,movieId,rating,date
```

For each user, ratings are sorted by:

1. date ascending
2. movieId ascending

If a user has at least two distinct movie ratings, the final sorted rating is held out as test data and all earlier ratings are written to train data. If a user has only one rating, it remains in train and the user has no test row.

When multiple ratings have the same latest date, the highest movie ID is held out because movie IDs are sorted ascending before selecting the final row. This deterministic tie-break prevents unstable evaluation splits.

Exact duplicate rows for the same user/movie/rating/date are ignored and counted. Conflicting duplicate user/movie rows fail the split.

## Leakage Prevention

The end-to-end runner executes the Hadoop model-building stages using only the train CSV:

```text
normalized ratings
-> time-aware train/test split
-> train CSV
-> UserHistoryJob
-> ItemPairStatisticsJob
-> ItemSimilarityPipeline
-> RecommendationScoringPipeline
-> TopKRecommendationJob
-> offline evaluator
```

The held-out test CSV bypasses all model-building stages. It is read only by `scripts/evaluate_recommendations.py` after raw predictions and Top-K recommendations have already been generated.

The evaluator treats train/test overlap and final recommendations for watched train movies as fatal errors.

## Metrics

For each held-out test rating, the evaluator looks for a raw prediction with the same `userId,movieId`. Missing predictions are counted and reported; they are not imputed, clipped, or treated as zero.

Rating-prediction metrics:

```text
MAE = mean(abs(actualRating - predictedScore))
RMSE = sqrt(mean((actualRating - predictedScore)^2))
prediction coverage = matched test predictions / all test rows
```

If no test prediction is matched, MAE and RMSE are written as JSON `null`. JSON output is written with `allow_nan=False`, so NaN and Infinity are rejected.

Ranking metrics include only users whose held-out rating is relevant:

```text
relevant if actualRating >= relevanceThreshold
```

Because leave-one-out creates at most one relevant held-out item per user:

```text
hit@K = 1 if the held-out item appears in the first K recommendations, else 0
Precision@K = hit / K
Recall@K = hit
Hit Rate@K = hit
NDCG@K = 1 / log2(rank + 1), if hit, else 0
MRR@K = 1 / rank, if hit, else 0
```

Aggregate ranking metrics are macro averages over ranking-eligible users. Recall@K and Hit Rate@K are numerically equal in this leave-one-out setup because there is only one relevant held-out item per eligible user.

## Evaluator Fixture

For the committed fixture with `K=2` and relevance threshold `4`:

- test rows: `4`
- matched predictions: `3`
- missing predictions: `1`
- prediction coverage: `0.75`
- MAE: approximately `0.6666666667`
- RMSE: approximately `0.7071067812`
- Precision@2: approximately `0.3333333333`
- Recall@2: approximately `0.6666666667`
- Hit Rate@2: approximately `0.6666666667`
- NDCG@2: approximately `0.5436432512`
- MRR@2: `0.5`

## Commands

Run the full offline evaluation in Docker with cosine similarity:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_offline_evaluation_docker.ps1 -Method cosine -TopK 2 -TopL 10 -MinCommonUsers 1 -RelevanceThreshold 4
```

Run the same workflow with row-normalized co-occurrence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_offline_evaluation_docker.ps1 -Method cooccurrence -TopK 2 -TopL 10 -MinCommonUsers 1 -RelevanceThreshold 4
```

The runner writes artifacts under `target/offline-evaluation/`:

- `split/train_ratings.csv`
- `split/test_ratings.csv`
- `split/split_stats.json`
- Hadoop stage output directories under `stages/`
- `evaluator/raw_predictions.txt`
- `evaluator/top_k_recommendations.txt`
- `evaluator/metrics.json`
- `evaluator/metrics.csv`
- `evaluator/per_user_metrics.csv`

## Limitations

- No scalability or worker-count benchmarking.
- No hyperparameter search.
- No popularity or cold-start fallback.
- No movie metadata joins.
- No web interface.
- No Hadoop daemons are started; validation uses Hadoop local mode inside Docker.

Milestone 10 adds scalability and performance benchmark tooling around this local-mode evaluation path. See `docs/scalability_experiments.md`.

Milestone 12 reuses the same leakage-preventing offline evaluation path for both cosine and row-normalized co-occurrence on the 15-movie GitHub reference-repository subset. The held-out test split remains evaluator-only input.
