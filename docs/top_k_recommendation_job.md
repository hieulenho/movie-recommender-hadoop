# Watched-Item Filtering And Top-K Recommendation Job

## Purpose

Milestone 8 converts raw user-candidate scores from Milestone 7 into final offline recommendation lists. It removes movies already present in each user's history and keeps at most Top-K unseen candidates per user.

This milestone stops at deterministic final recommendation rows. It does not implement train/test splitting, RMSE, MAE, Precision, Recall, Hit Rate, NDCG, popularity fallback, cold-start fallback, movie-title joins, metadata enrichment, Hadoop daemons, Spark, databases, or a web interface.

## Inputs

User-history rows:

```text
userId<TAB>movieId:rating,movieId:rating,...
```

Raw prediction rows:

```text
userId,movieId<TAB>score
```

Raw scores are parsed as `double` values and must be finite from `1.0` through `5.0`. They are not rounded during parsing.

## Anti-Join Design

The job uses `MultipleInputs` and a reduce-side anti-join grouped by user ID:

- `UserHistoryMapper` parses each history with `UserHistoryRecord` and emits one complete watched-history join record.
- `RawPredictionMapper` parses each score with `RawPredictionRecord` and emits one candidate-score join record.
- `RecommendationJoinKeyWritable` sorts by user ID, record type, then secondary ID. History records use type `0`; prediction records use type `1` and use candidate movie ID as the secondary ID.
- `UserPartitioner` partitions only by user ID.
- `UserGroupingComparator` groups only by user ID.

This gives the reducer each user's history before that user's predictions. The reducer stores only one user's watched history, the previous prediction key for duplicate detection, and a bounded Top-K queue.

## Duplicate Policy

User histories are compared as sorted movie IDs plus ratings. Identical duplicate histories are ignored and counted. Conflicting duplicate histories fail the job clearly.

For a given `(userId, movieId)`, exactly one raw prediction score is expected. Because prediction join keys sort by movie ID, duplicates are adjacent in the reducer. Identical duplicate prediction scores are ignored and counted when `Double.compare(scoreA, scoreB) == 0`. Conflicting duplicate scores fail the job clearly. This is appropriate for scores serialized with fixed ten-decimal text output.

A prediction for a user with no matching history fails the job. A user history with no prediction records is valid and produces no output.

## Watched Filtering And Top-K

For each prediction:

1. Detect exact or conflicting duplicates.
2. Discard the candidate if its movie ID appears in the user's watched set.
3. Otherwise, consider it for the bounded Top-K queue.

Top-K ordering is:

1. score descending
2. movie ID ascending

The priority queue keeps the worst retained candidate first:

1. lower score is worse
2. when scores tie, larger movie ID is worse

When the queue is full, a better candidate replaces the current worst; a worse candidate is discarded. After selection, retained candidates are sorted into final presentation order. List position is the implicit rank starting at `1`.

## Output

Final rows:

```text
userId<TAB>movieId:score,movieId:score,...
```

Rules:

- One row per user with at least one recommendation.
- No header row.
- Scores are formatted with exactly 10 digits after the decimal point using `Locale.ROOT`.
- No trailing comma.
- No watched movie appears.
- No duplicate candidate movie appears.
- With one reducer, user IDs are sorted numerically.
- Recommendations are sorted by score descending, then numeric movie ID ascending.
- Ratings, commonUsers, numerator, denominator, and explicit rank fields are not written.

## Hadoop Counters

`TopKRecommendationCounters` includes:

- `USER_HISTORY_ROWS`
- `EXACT_DUPLICATE_HISTORIES_IGNORED`
- `RAW_PREDICTION_ROWS`
- `EXACT_DUPLICATE_PREDICTIONS_IGNORED`
- `USERS_PROCESSED`
- `USERS_WITHOUT_PREDICTIONS`
- `PREDICTIONS_FILTERED_AS_WATCHED`
- `UNSEEN_CANDIDATES_CONSIDERED`
- `CANDIDATES_DISCARDED_BY_TOP_K`
- `USERS_WITH_NO_UNSEEN_CANDIDATES`
- `USERS_EMITTED`
- `RECOMMENDATIONS_EMITTED`

Counters are sanity checks. Committed fixture output remains the acceptance oracle.

## Execution

Linux local mode:

```bash
bash scripts/run_top_k_recommendations.sh
```

Windows Docker validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_top_k_recommendations_docker.ps1 -TopK 2
```

The scripts default to:

```text
tests/fixtures/top-k-recommendation/user-history.txt
tests/fixtures/top-k-recommendation/raw-predictions.txt
target/top-k-recommendation-output
top-k = 2
```

The Docker wrapper compares default Top-K 2 output against `tests/fixtures/top-k-recommendation/expected-top2.txt`.

## Fixture Explanation

For user `101`, raw scores include watched movies `1` and `2`:

```text
101,1	3.0000000000
101,2	5.0000000000
101,3	3.8000000000
101,4	3.0000000000
```

After filtering watched movies and applying Top-K 2:

```text
101	3:3.8000000000,4:3.0000000000
```

For user `102`, watched movies `2` and `3` are removed. The remaining candidates are ordered by score:

```text
102	4:4.5833333333,1:4.3333333333
```

Users `103` and `104` demonstrate equal-score tie-breaking by movie ID ascending. User `105` is omitted because its only raw candidate is already watched.

## Relationship To The Python Reference

The Python Item-CF reference ranks recommendations by predicted score descending and movie ID ascending after excluding watched movies. This Hadoop job consumes Milestone 7 raw prediction rows rather than recalculating scores, then applies the same filtering and Top-K ordering semantics for the final offline output.

## Limitations

- Train/test splitting and evaluation are handled by the separate Milestone 9 offline evaluation workflow.
- No fallback recommendation for users with no unseen candidates.
- No cold-start handling.
- No movie metadata joins.
- Multiple reducers are supported, but global ordering across reducer part files is not guaranteed.
- Hadoop local mode is not HDFS, YARN, pseudo-distributed mode, or a cluster.
- Native Windows Hadoop execution remains unsupported; Docker/Linux is the validation target.

The next milestone is Milestone 10: scalability and performance experiments.
