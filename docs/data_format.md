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

## Planned Hadoop Prediction Format

```text
userId,movieId,predictedScore
```

## Planned Hadoop Final Output

```text
userId<TAB>movieId:score,movieId:score
```

## Environment Smoke Output

Milestone 3 includes a temporary Hadoop local-mode smoke output for environment validation only:

```text
lineCount<TAB>5
```

This format is not a recommender data format and is not used by later Item-CF logic.
