# Recommendation Scoring MapReduce Pipeline

## Purpose

Milestone 7 joins user histories from Milestone 4 with directed Top-L item similarities from Milestone 6 and calculates raw Item-Based Collaborative Filtering scores for user-candidate movie pairs.

This milestone stops at raw prediction scores. It does not filter watched movies, rank Top-K recommendations, add fallback recommendations, split train/test data, calculate evaluation metrics, join movie metadata, start Hadoop daemons, add Spark, or add a web interface.

## Inputs

User-history rows:

```text
userId<TAB>movieId:rating,movieId:rating,...
```

Directed similarity rows:

```text
sourceMovieId,neighborMovieId<TAB>similarity,commonUsers
```

Similarity rows are retained directed neighbor relations from Milestone 6. For source movie `j` and candidate movie `c`, only retained relation `j -> c` may contribute to a score. Similarities are parsed as `double` values and must be finite, greater than `0.0`, and at most `1.0`.

## Formula

For user `u` and candidate movie `c`:

```text
score(u,c) =
sum(similarity(j,c) * rating(u,j))
/
sum(abs(similarity(j,c)))
```

The sums use all retained directed similarities from movies `j` already rated by the user. Intermediate numerator and denominator values are not rounded.

## Reduce-Side Join Design

Stage A uses `MultipleInputs`:

- `UserHistoryMapper` parses one complete user history with `UserHistoryRecord` and emits one rating join record per rated movie.
- `SimilarityMapper` parses one directed similarity row with `DirectedSimilarityRecord` and emits one neighbor join record for its source movie.
- `JoinKeyWritable` sorts by source movie ID, then record type, then secondary ID. Similarity records use type `0`; rating records use type `1`.
- `SourceMoviePartitioner` partitions only by source movie ID.
- `SourceMovieGroupingComparator` groups only by source movie ID.

This secondary-sort design gives each reducer one source movie at a time with similarity records ordered before rating records. The reducer stores only that source movie's retained Top-L neighbor list, then streams rating records and emits additive score contributions. It does not keep all user histories or all similarities in a JVM-wide collection.

For source movie `j`, user `u`, rating `r`, neighbor `c`, and similarity `s`, `JoinReducer` emits:

```text
key   = UserMovieWritable(u,c)
value = ScoreContributionWritable(s*r, abs(s), 1)
```

Watched candidates are intentionally retained in this raw output. Filtering them is Milestone 8.

## Intermediate Output

Stage A writes typed `UserMovieWritable` and `ScoreContributionWritable` records with `SequenceFileOutputFormat`.

The intermediate path is derived from the final output path:

```text
<output-name>-recommendation-scoring-intermediate
```

The final output and intermediate path must not already exist. The driver deletes only this pipeline-owned intermediate path after success. On failure, it preserves the intermediate output when present for diagnosis.

## Aggregation

Stage B reads the typed contributions with `SequenceFileInputFormat`.

`ContributionCombiner` sums numerator, denominator, and contributing item count. It does not calculate, format, or round final scores, so it is safe regardless of how often Hadoop invokes it.

`FinalScoreReducer` sums all contributions for each user-candidate key, skips only zero-denominator keys, calculates `numerator / denominator`, and writes final text rows.

## Output

Final rows:

```text
userId,movieId<TAB>score
```

Rules:

- No header row.
- Exactly one row per user-candidate pair.
- Scores are formatted with exactly 10 digits after the decimal point using `Locale.ROOT`.
- With one reducer, rows sort numerically by user ID and then movie ID.
- Watched movies may remain in output by design.
- No numerator, denominator, contributing count, rank, or common-user count is written.

## Hadoop Counters

Stage A counters:

- `USER_HISTORY_ROWS`
- `USER_RATING_JOIN_RECORDS`
- `SIMILARITY_INPUT_ROWS`
- `VALID_SIMILARITY_ROWS`
- `SOURCE_MOVIES_JOINED`
- `SOURCE_MOVIES_WITHOUT_SIMILARITIES`
- `CONTRIBUTIONS_EMITTED`

Stage B counters:

- `USER_CANDIDATE_KEYS`
- `CONTRIBUTIONS_AGGREGATED`
- `ZERO_DENOMINATOR_KEYS_SKIPPED`
- `PREDICTION_ROWS`

Counters are sanity checks; fixture output remains the acceptance oracle.

## Execution

Linux local mode:

```bash
bash scripts/run_recommendation_scoring.sh
```

Windows Docker validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_recommendation_scoring_docker.ps1
```

The scripts default to:

```text
tests/fixtures/recommendation-scoring/user-history.txt
tests/fixtures/recommendation-scoring/similarity.txt
target/recommendation-scoring-output
```

The Docker wrapper compares default output against `tests/fixtures/recommendation-scoring/expected.txt`.

## Fixture Calculations

For user `101`, movie `3`, ratings are `1=5` and `2=3`:

```text
numerator = 0.4*5 + 0.6*3 = 3.8
denominator = abs(0.4) + abs(0.6) = 1.0
score = 3.8
```

For user `102`, movie `1`, ratings are `2=4` and `3=5`:

```text
numerator = 0.8*4 + 0.4*5 = 5.2
denominator = abs(0.8) + abs(0.4) = 1.2
score = 4.3333333333
```

For user `102`, movie `4`, ratings are `2=4` and `3=5`:

```text
numerator = 0.5*4 + 0.7*5 = 5.5
denominator = abs(0.5) + abs(0.7) = 1.2
score = 4.5833333333
```

The expected output intentionally includes watched candidates such as `101,1`, `101,2`, `102,2`, and `102,3`. This confirms that watched-item filtering is deferred.

## Relationship To The Python Reference

The weighted-average formula matches `scripts/itemcf_reference.py`, but Milestone 7 intentionally differs from the reference recommendation writer by keeping watched candidates in raw scoring output. The Python reference removes watched movies when producing Top-K recommendations; that behavior belongs to the later Hadoop filtering and ranking milestone.

## Limitations

- No watched-item filtering.
- No Top-K ranking.
- No popularity or cold-start fallback.
- No evaluation metrics.
- Multiple reducers are supported, but global ordering across reducer part files is not guaranteed.
- Hadoop local mode is not HDFS, YARN, pseudo-distributed mode, or a cluster.
- Native Windows Hadoop execution remains unsupported; Docker/Linux is the validation target.

The next milestone is Milestone 8: watched-item filtering and Top-K ranking.
