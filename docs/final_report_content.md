# Final Report Content

## Dataset And Scope

The final dataset run uses all 15 movie files available in the GitHub reference repository `thviet79/Bigdata_Project_Recommender_System`. It is not the complete official Netflix Prize dataset.

The input format is `userId,movieId,rating`. The source has no rating dates, so the full-reference workflow records `source_has_dates = false` and `source_date_status = unavailable`.

Key generated facts:

- Ratings: 21629
- Distinct users: 20537
- Distinct movies: 15
- Exact duplicate rows ignored: 0
- Normalized CSV SHA-256: `66a9c5c4e282467d0cbeb849cbd842a40682fac8fc737a8bce44f1025da4fc01`

## Split Protocol

The full-reference split is `deterministic-leave-one-out-by-item`. For each eligible user, ratings are sorted by numeric movie ID and the highest movie ID is held out. Users with only one rating remain train-only.

The placeholder date `1970-01-01` is added only after splitting so Hadoop jobs can read the existing `userId,movieId,rating,date` schema. It must not be interpreted as a real timestamp.

Split facts:

- Train rows: 20741
- Test rows: 888
- Train/test overlap rows: 0

## Method Metrics

| Method | Coverage | MAE | RMSE | Precision@K | Recall@K | HitRate@K | NDCG@K | MRR@K | Total seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cosine | 0.8592342342 | 1.2628957245 | 1.6590045822 | 0.0258675079 | 0.1293375394 | 0.1293375394 | 0.0558198181 | 0.0328075710 | 27.285297 |
| cooccurrence | 0.8547297297 | 1.2684552218 | 1.6720603280 | 0.0233438486 | 0.1167192429 | 0.1167192429 | 0.0554198178 | 0.0362250263 | 38.672707 |

Source files:

- `results/full-reference-dataset/method_comparison.csv`
- `results/full-reference-dataset/cosine/metrics.json`
- `results/full-reference-dataset/cooccurrence/metrics.json`

## Demo Validation

The Streamlit demo is read-only. It loads user-history, recommendation, metadata, metrics, and optional benchmark artifacts. It does not run Hadoop, Maven, Docker, preprocessing, or model-building jobs.

Recommended full-reference artifact paths:

- User history: `results/full-reference-dataset/cosine/user-history/`
- Recommendations: `results/full-reference-dataset/cosine/recommendations/`
- Metadata: `results/full-reference-dataset/metadata/movie_metadata.csv`
- Metrics: `results/full-reference-dataset/cosine/metrics.json`

## Limitations

- The final run uses a 15-movie GitHub reference subset, not the complete official Netflix Prize corpus.
- The source has no dates; evaluation is deterministic non-temporal holdout, not leave-one-out-by-time.
- The small movie count limits item-item coverage, candidate diversity, and generalizability.
- Docker Hadoop local-mode timing is single-container reproducibility timing, not multi-node cluster scaling.
- Scalability benchmark status: Chưa có dữ liệu thực nghiệm.
