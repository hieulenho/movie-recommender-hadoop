# Item-Pair Statistics MapReduce Job

## Purpose

Milestone 5 adds the second recommender-specific Hadoop MapReduce job. It reads Milestone 4 user-history records and emits deterministic unordered movie-pair statistics for later similarity calculation.

This milestone stops at aggregate pair statistics. It does not compute cosine similarity, co-occurrence similarity, Top-L neighbors, recommendation scores, watched-item filtering, Top-K output, evaluation metrics, Spark jobs, HDFS/YARN daemons, or a web interface.

## Input Format

Input must use the user-history format:

```text
userId<TAB>movieId:rating,movieId:rating,...
```

`userId` and `movieId` must be positive integers. Ratings must be integers from `1` through `5`. Each row must contain exactly one tab, at least one movie-rating entry, and no duplicate movie IDs for the same user. Movie entries may be in any order; the parser sorts them numerically by movie ID before pair generation.

## Pair Semantics

For each user, the mapper considers every unordered pair of distinct movies in that user's history. For pair `(i, j)` where `i < j`, with ratings `x = rating(user, i)` and `y = rating(user, j)`, it emits one additive contribution:

```text
commonUsers = 1
sumXY = x * y
sumX2 = x * x
sumY2 = y * y
```

Single-item users are valid but emit no item pairs. Self-pairs and reversed duplicate pairs are never emitted.

## Mapper, Combiner, And Reducer

`ItemPairStatisticsMapper` reads `LongWritable,Text` records from `TextInputFormat`, validates each row with `UserHistoryRecord`, and emits:

```text
ItemPairWritable(movieI, movieJ), PairStatsWritable(1, x*y, x*x, y*y)
```

`ItemPairWritable` stores two `long` movie IDs and compares numerically by first movie ID, then second movie ID. It rejects non-positive IDs, self-pairs, and reversed pairs.

`PairStatsCombiner` and `ItemPairStatisticsReducer` add the four long-valued fields. The combiner has no reducer-only side effects. The reducer writes final aggregate statistics.

## Output Format

The reducer output is:

```text
movieIdA,movieIdB<TAB>commonUsers,sumXY,sumX2,sumY2
```

Rules:

- `movieIdA < movieIdB`.
- Movie pair keys are sorted numerically when the job is run with one reducer.
- Statistics are written as signed 64-bit integer text fields.
- There is no header row.

Example:

```text
1,2	3,28,38,42
1,3	2,30,20,50
```

For pair `1,2` in the fixture, three users co-rated both movies. The accumulated values are:

```text
commonUsers = 3
sumXY = 3*5 + 2*4 + 5*1 = 28
sumX2 = 3*3 + 2*2 + 5*5 = 38
sumY2 = 5*5 + 4*4 + 1*1 = 42
```

## Hadoop Counters

`ItemPairStatisticsCounters` includes:

- `INPUT_USER_ROWS`
- `VALID_USER_HISTORIES`
- `USERS_WITH_SINGLE_ITEM`
- `PAIRS_EMITTED`
- `FINAL_UNORDERED_PAIRS`
- `COMMON_USER_CONTRIBUTIONS`

Counters are useful sanity checks, but committed fixture output remains the acceptance oracle.

## Execution

Linux local-mode execution:

```bash
bash scripts/run_item_pair_stats.sh
```

The script defaults to:

```text
tests/fixtures/item-pairs/user-history.txt
target/item-pair-stats-output
```

It builds the Maven classes, runs `ItemPairStatisticsJob --local --reducers 1`, removes only the selected output directory after safety checks, and prints `part-r-00000`.

Windows Docker execution:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_item_pair_stats_docker.ps1
```

The Docker wrapper builds the Maven/Hadoop validation image and compares the default output against `tests/fixtures/item-pairs/expected.txt`. It does not start Hadoop daemons, create a Docker Compose cluster, download Netflix data, or require a globally installed Hadoop command.

## Test Fixture

The committed fixture is:

```text
tests/fixtures/item-pairs/user-history.txt
tests/fixtures/item-pairs/expected.txt
tests/fixtures/item-pairs/malformed-history.txt
```

Expected reducer output:

```text
1,2	3,28,38,42
1,3	2,30,20,50
2,3	1,20,16,25
2,4	1,20,16,25
```

The fixture includes overlapping histories, one single-item user, and a malformed duplicate-movie input for failure testing.

## Relationship To The Python Reference

The accumulated fields match the pair-statistics definitions in `docs/itemcf_reference.md`. Later Hadoop similarity jobs can consume this output to calculate cosine or co-occurrence similarities and compare small fixtures against the Python Item-CF reference.

## Limitations

- No similarity or neighbor output is generated.
- No recommendation scoring, watched-item filtering, Top-K ranking, train/test split, or evaluation is implemented.
- Multiple reducers are supported, but global ordering across reducer part files is not guaranteed.
- Hadoop local mode is not HDFS, YARN, pseudo-distributed mode, or a cluster.
- Native Windows Hadoop execution remains unsupported in this repository; Docker/Linux is the validation target.

The downstream Hadoop stage is Milestone 6: similarity and Top-L neighbors.
