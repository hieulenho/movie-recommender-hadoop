# Data Formats

Exact formats may be refined by later milestones, but all changes must remain documented and version-controlled.

## Netflix Raw Format

Netflix-style raw files group ratings under a movie identifier line ending with a colon.

```text
1:
1488844,3,2005-09-06
822109,5,2005-05-13
```

## Implemented Normalized Rating CSV Format

Milestone 1 implements the normalized CSV format produced by `scripts/preprocess_netflix.py`. See `docs/preprocessing.md` for validation rules, duplicate handling, CLI usage, and statistics definitions.

The CSV header is always:

```text
userId,movieId,rating,date
```

Example:

```text
1488844,1,3,2005-09-06
822109,1,5,2005-05-13
```

Rows are written with UTF-8 encoding through the Python `csv` module.

## Implemented Item-CF Neighbor CSV Format

Milestone 2 implements the neighbor CSV format produced by `scripts/itemcf_reference.py`.

```text
sourceMovieId,neighborMovieId,similarity,commonUsers
```

Rows are ordered by source movie ID ascending, similarity descending, and neighbor movie ID ascending. Similarity values are written with 12 decimal places.

## Implemented Item-CF Recommendation CSV Format

Milestone 2 implements the recommendation CSV format produced by `scripts/itemcf_reference.py`.

```text
userId,rank,movieId,score
```

Rows are ordered by user ID ascending and rank ascending. Scores are written with 12 decimal places.

## Implemented User-History Format

```text
userId<TAB>movieId:rating,movieId:rating
```

Milestone 4 adds the Hadoop user-history implementation and fixture format.

Rules:

- One output record is written per user.
- The key is the numeric user ID.
- The key and value are separated by one tab.
- Movie entries are separated by commas.
- Each movie entry is `movieId:rating`.
- Movie IDs are sorted numerically ascending within each history.
- Ratings are written as integers.
- Dates are used for duplicate validation but are not written to the output.
- Exact duplicate normalized records are ignored after the first occurrence.
- Conflicting duplicate user/movie records fail the job.

Example:

```text
101	1:4,3:5
102	1:3,2:5
```

## Implemented Hadoop Item-Pair Statistics Format

Milestone 5 adds the Hadoop item-pair statistics implementation and fixture format.

```text
movieIdA,movieIdB<TAB>commonUsers,sumXY,sumX2,sumY2
```

Rules:

- `movieIdA` and `movieIdB` are positive integer movie IDs.
- `movieIdA < movieIdB`; self-pairs and reversed duplicate pairs are not written.
- `commonUsers` is the number of users who rated both movies.
- `sumXY` is the sum of `rating(user, movieIdA) * rating(user, movieIdB)` over common users.
- `sumX2` is the sum of squared ratings for `movieIdA` over common users.
- `sumY2` is the sum of squared ratings for `movieIdB` over common users.
- With one reducer, pair keys are sorted numerically by `movieIdA`, then `movieIdB`.
- There is no header row.

Example:

```text
1,2	3,28,38,42
1,3	2,30,20,50
```

## Implemented Hadoop Directed Similarity Format

```text
sourceMovieId,neighborMovieId<TAB>similarity,commonUsers
```

Milestone 6 adds the Hadoop item-similarity and Top-L neighbor implementation.

Rules:

- Rows are directed retained neighbor relations.
- The key contains `sourceMovieId,neighborMovieId`.
- The value contains `similarity,commonUsers`.
- Similarity is written with exactly 10 digits after the decimal point.
- Cosine produces equal values for both directions of an eligible unordered pair.
- Row-normalized co-occurrence may be asymmetric because each source movie has its own denominator.
- `min-common-users` filtering is applied before co-occurrence denominators and Top-L selection.
- Top-L neighbors are ordered by similarity descending, then numeric neighbor movie ID ascending.
- There is no header row.

Example:

```text
1,2	0.3000000000,3
3,1	0.2500000000,2
```

## Implemented Hadoop Raw Prediction Format

```text
userId,movieId<TAB>score
```

Milestone 7 adds the Hadoop recommendation scoring implementation and fixture format.

Rules:

- Rows are raw user-candidate prediction scores.
- Scores are calculated from retained directed Top-L similarities and user ratings.
- Scores are written with exactly 10 digits after the decimal point.
- With one reducer, rows are sorted numerically by user ID, then movie ID.
- Watched movies may remain in this raw output by design.
- There is no header row.

Example:

```text
101,3	3.8000000000
```

## Implemented Hadoop Final Top-K Recommendation Output

```text
userId<TAB>movieId:score,movieId:score
```

Milestone 8 adds watched-item filtering and deterministic Top-K recommendation-list serialization.

Rules:

- One row is written per user with at least one unseen recommendation.
- Watched movie IDs are excluded.
- Each recommendation entry is `movieId:score`.
- Entries are comma-separated with no trailing comma.
- Scores are written with exactly 10 digits after the decimal point.
- Recommendation list position is the implicit rank starting at `1`.
- Entries are ordered by score descending, then numeric movie ID ascending.
- With one reducer, user IDs are sorted numerically.
- There is no header row.

Example:

```text
101	3:3.8000000000,4:3.0000000000
```

## Implemented Train/Test Evaluation Rating CSV Formats

Milestone 9 writes train and test splits using the same normalized ratings CSV header:

```text
userId,movieId,rating,date
```

The split is leave-one-out-by-time per user. Train and test rows are ordered by user ID ascending, date ascending, and movie ID ascending. The test file contains at most one row per user. Users with only one rating remain train-only.

## Implemented Evaluation Metrics JSON

The evaluator writes readable UTF-8 JSON with `allow_nan=False`.

Required fields include:

- `evaluation_method`
- `k`
- `relevance_threshold`
- `test_rows`
- `matched_test_predictions`
- `missing_test_predictions`
- `prediction_coverage`
- `mae`
- `rmse`
- `ranking_eligible_users`
- `ranking_hits`
- `users_with_recommendations`
- `recommendation_user_coverage`
- `precision_at_k`
- `recall_at_k`
- `hit_rate_at_k`
- `ndcg_at_k`
- `mrr_at_k`
- `watched_recommendations_found`
- `train_test_overlap_rows`

When no held-out rating has a matching raw prediction, `mae` and `rmse` are JSON `null`.

## Implemented Evaluation Metrics CSV

The one-row metrics CSV header is:

```text
method,k,relevanceThreshold,testRows,matchedPredictions,predictionCoverage,mae,rmse,rankingEligibleUsers,hits,precisionAtK,recallAtK,hitRateAtK,ndcgAtK,mrrAtK
```

Decimal values use a stable dot decimal representation and are suitable for import into reports or spreadsheets.

## Implemented Per-User Evaluation CSV

The per-user diagnostic CSV header is:

```text
userId,testMovieId,actualRating,predictedScore,absoluteError,squaredError,isRelevant,recommendationRank,hit,ndcg,mrr,recommendationCount
```

Empty fields are used when a held-out rating has no raw prediction, no recommendation rank, or no calculable prediction error.

## Evaluation Split Statistics JSON

The split statistics JSON includes `split_method` set to `leave-one-out-by-time`, `holdout_per_user` set to `1`, duplicate counts, user/item counts, and train/test row counts. The invariant `train_rows + test_rows = accepted_ratings` must hold.

## Environment Smoke Output

Milestone 3 includes a temporary Hadoop local-mode smoke output for environment validation only:

```text
lineCount<TAB>5
```

This format is not a recommender data format and is not used by later Item-CF logic.
