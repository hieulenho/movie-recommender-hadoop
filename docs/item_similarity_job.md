# Item Similarity And Top-L Neighbors MapReduce Pipeline

## Purpose

Milestone 6 converts Milestone 5 item-pair statistics into directed item similarities and retains at most Top-L neighbors per source movie. The output is consumed by the Milestone 7 recommendation score calculation pipeline.

This milestone stops at directed retained neighbor rows. It does not join similarities with user ratings, score recommendations, filter watched movies, produce Top-K recommendations, split train/test data, evaluate RMSE or ranking metrics, enrich movie metadata, start Hadoop daemons, add Spark, or add a web interface.

## Input Format

Input rows must be:

```text
movieIdA,movieIdB<TAB>commonUsers,sumXY,sumX2,sumY2
```

`movieIdA < movieIdB`. Movie IDs must be positive integers. `commonUsers`, `sumXY`, `sumX2`, and `sumY2` must be positive integers, with `commonUsers >= 1`. Malformed rows fail the job; they are not silently ignored.

## Minimum Common Users

`--min-common-users N` defaults to `1` and must be at least `1`. Pairs below this threshold are discarded before directed relations, co-occurrence denominators, and Top-L truncation are calculated.

## Cosine Similarity

For unordered pair `(i, j)` where `i < j`:

```text
similarity(i, j) = sumXY / sqrt(sumX2 * sumY2)
```

The pipeline emits both directed relations `i -> j` and `j -> i`. The two cosine values are equal. Computation uses `double` precision and does not round before final output formatting.

## Row-Normalized Co-Occurrence

Co-occurrence first turns each eligible unordered pair into two directed relations. For source movie `i`:

```text
similarity(i, j) = commonUsers(i, j) / sum_commonUsers(i, k)
```

The denominator sums all eligible neighbors `k` for source `i` before Top-L truncation. Because each source movie can have a different denominator, co-occurrence can be asymmetric. The retained Top-L values are not renormalized after truncation.

## Top-L Behavior

`--top-l L` defaults to `50` and must be at least `1`. For each source movie, the reducer keeps at most `L` neighbors ordered by:

1. similarity descending
2. neighbor movie ID ascending

This tie-breaking is numeric and deterministic. Self-relations are not emitted.

## Output Format

Final rows are individual directed retained relations:

```text
sourceMovieId,neighborMovieId<TAB>similarity,commonUsers
```

Similarity values are serialized with exactly 10 digits after the decimal point. There is no header row. With one reducer, output is ordered by source movie ID ascending, then similarity descending, then neighbor movie ID ascending.

Example:

```text
1,2	0.3000000000,3
```

## Hadoop Pipeline Stages

For cosine:

1. Parse pair-statistics rows, apply `min-common-users`, calculate cosine, and write both directed relations to a controlled SequenceFile intermediate directory.
2. Group directed relations by source movie and retain Top-L neighbors.

For co-occurrence:

1. Parse pair-statistics rows, apply `min-common-users`, and emit both directed common-user counts.
2. Group by source movie, calculate the source denominator from all eligible neighbors, normalize directed co-occurrence similarities, and write them to the same intermediate format.
3. Group directed similarities by source movie and retain Top-L neighbors.

The implementation stores only one source movie's neighbors in reducer memory, not the complete similarity graph in one JVM.

## Intermediate Path Policy

The driver derives a controlled intermediate directory from the final output path:

```text
<output-name>-item-similarity-intermediate
```

The final output path and the derived intermediate path must not already exist. On success, the driver deletes only this pipeline-owned intermediate path. On failure, it preserves the intermediate path when present for diagnosis.

The provided shell script removes only its selected output and derived intermediate path after safety checks.

## Hadoop Counters

`ItemSimilarityCounters` includes:

- `INPUT_PAIR_ROWS`
- `VALID_PAIR_ROWS`
- `PAIRS_FILTERED_BY_MIN_COMMON_USERS`
- `DIRECTED_RELATIONS_CREATED`
- `ZERO_DENOMINATOR_RELATIONS_SKIPPED`
- `SOURCE_ITEMS`
- `DIRECTED_RELATIONS_BEFORE_TOP_L`
- `DIRECTED_RELATIONS_AFTER_TOP_L`

Counters are sanity checks. Committed expected fixture output remains the acceptance oracle.

## Execution

Linux local-mode cosine:

```bash
bash scripts/run_item_similarity.sh cosine
```

Linux local-mode co-occurrence:

```bash
bash scripts/run_item_similarity.sh cooccurrence
```

Windows Docker cosine:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_item_similarity_docker.ps1 -Method cosine
```

Windows Docker co-occurrence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_item_similarity_docker.ps1 -Method cooccurrence
```

The scripts default to:

```text
tests/fixtures/similarity/pair-stats.txt
target/item-similarity-output
min-common-users = 1
top-l = 3
```

The Docker wrapper compares default output against the committed expected fixture for the selected method.

## Fixture Calculations

For pair `1,2`:

```text
commonUsers = 3
sumXY = 28
sumX2 = 38
sumY2 = 42
cosine = 28 / sqrt(38 * 42) = 0.7010861872
```

This pair is not retained in the default cosine Top-3 for source `1` because neighbors `4`, `5`, and `10` all have similarity `1.0000000000` and tie-break by numeric neighbor ID.

For co-occurrence source `1`, eligible common-user counts are:

```text
1->2 = 3
1->3 = 2
1->4 = 1
1->5 = 2
1->10 = 2
denominator = 10
```

Therefore:

```text
1,2	0.3000000000,3
1,3	0.2000000000,2
1,5	0.2000000000,2
```

Neighbor `10` ties at `0.2000000000` but is excluded from Top-3 because neighbor ID `5` sorts before `10`. For source `3`, the denominator is `8`, so `3->1 = 2/8 = 0.2500000000`, while `1->3 = 2/10 = 0.2000000000`; this documents the expected asymmetry.

## Relationship To The Python Reference

The formulas, min-common-users filtering, co-occurrence denominator timing, and Top-L ordering match `scripts/itemcf_reference.py`. The Hadoop output uses tab-separated directed relation rows instead of the Python reference CSV header because Milestone 7 will consume these rows directly.

## Limitations

- No recommendation scores are calculated.
- No watched-item filtering or Top-K recommendation output is generated.
- Multiple reducers are supported, but global ordering across reducer part files is not guaranteed.
- Hadoop local mode is not HDFS, YARN, pseudo-distributed mode, or a cluster.
- Native Windows Hadoop execution remains unsupported in this repository; Docker/Linux is the validation target.

The downstream Hadoop stage is Milestone 7: recommendation score calculation.
