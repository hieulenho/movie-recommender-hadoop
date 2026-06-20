# User History MapReduce Job

## Purpose

Milestone 4 adds the first recommender-specific Hadoop MapReduce job. It converts Milestone 1 normalized rating CSV rows into deterministic user histories that later item-pair statistics jobs can consume.

This milestone stops at user-history construction. It does not implement item-pair generation, similarity, recommendation scoring, filtering, evaluation, Spark, HDFS/YARN daemons, or a web interface.

## Input Format

Input must be normalized CSV with the exact header:

```text
userId,movieId,rating,date
```

Each data row has exactly four unquoted comma-separated fields:

```text
101,3,5,2005-01-03
```

`userId` and `movieId` must be positive integers, `rating` must be an integer from `1` through `5`, and `date` must be a valid `YYYY-MM-DD` date. Whitespace around fields is trimmed. Empty data lines, wrong field counts, invalid IDs, invalid ratings, invalid dates, and malformed header-like rows fail the job.

## Mapper Behavior

`UserHistoryJob.UserHistoryMapper` reads `LongWritable,Text` records from `TextInputFormat`.

- It increments `INPUT_ROWS` for every input record.
- It skips only the exact header text `userId,movieId,rating,date` and increments `HEADER_ROWS`.
- It parses other lines with `NormalizedRating`.
- It emits `LongWritable userId` and a `Text` value containing `movieId,rating,date`.

The date is included in the mapper value so the reducer can validate duplicates before the final history omits dates.

## Shuffle And Grouping

Hadoop groups mapper output by `userId`. With one reducer, `LongWritable` keys make user output numerically ordered. Multiple reducers are supported through `--reducers N`, but global file ordering across reducer part files is not guaranteed.

## Reducer Behavior

`UserHistoryJob.UserHistoryReducer` receives one user at a time. It stores ratings in a `TreeMap` keyed by movie ID, so final movie entries are sorted numerically ascending.

The reducer writes:

```text
userId<TAB>movieId:rating,movieId:rating,...
```

There is no trailing comma and dates are not written to final histories.

## Duplicate Rules

For the same `userId` and `movieId`:

- If `rating` and `date` are identical, the later exact duplicate is ignored and `EXACT_DUPLICATES_IGNORED` is incremented.
- If either `rating` or `date` differs, the job fails with a conflicting duplicate error.

Duplicate handling does not depend on reducer value order.

## Hadoop Counters

`UserHistoryCounters` includes:

- `INPUT_ROWS`
- `HEADER_ROWS`
- `VALID_RATING_ROWS`
- `EXACT_DUPLICATES_IGNORED`
- `USERS_EMITTED`
- `OUTPUT_RATINGS`

Counters are informational checks, not a substitute for output validation.

## Execution

Linux local-mode execution:

```bash
bash scripts/run_user_history.sh
```

The script defaults to:

```text
tests/fixtures/user-history/ratings.csv
target/user-history-output
```

It builds the Maven classes, runs `UserHistoryJob --local --reducers 1`, removes only the selected output directory after safety checks, and prints `part-r-00000`.

Windows Docker execution:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_user_history_docker.ps1
```

The Docker wrapper builds the existing Maven/Hadoop validation image and runs the POSIX script inside a short-lived Linux container. It does not start Hadoop daemons, create a Docker Compose cluster, download Netflix data, or require a globally installed Hadoop command.

## Test Fixture

The committed fixture is:

```text
tests/fixtures/user-history/ratings.csv
tests/fixtures/user-history/expected.txt
tests/fixtures/user-history/conflicting-ratings.csv
```

Expected reducer output:

```text
101	1:4,3:5
102	1:3,2:5
103	2:4,4:5
104	5:3
```

The main fixture includes out-of-order movie rows, repeated users, overlapping histories, one exact duplicate, at least five movies, and one single-movie user. The conflicting fixture contains a duplicate user/movie pair with a different rating.

## Relationship To The Python Reference

The Python Item-CF reference already defines the duplicate policy for normalized ratings. The Hadoop user-history job follows the same exact-duplicate and conflicting-duplicate rules so later Hadoop outputs can be compared against committed fixtures and the Python reference on small data.

## Limitations

- No item-pair statistics are generated.
- No similarity or neighbor output is generated.
- No recommendation scoring, watched-item filtering, Top-K ranking, train/test split, or evaluation is implemented.
- Hadoop local mode is not HDFS, YARN, pseudo-distributed mode, or a cluster.
- Native Windows Hadoop execution remains unsupported in this repository; Docker/Linux is the validation target.

The downstream Hadoop stage is Milestone 5: item-pair statistics.
