# Python Item-CF Reference

## Purpose

The Python Item-Based Collaborative Filtering reference implementation provides a deterministic local model for small and medium normalized rating datasets. Its main purpose is to make expected Item-CF behavior easy to test before later Java Hadoop MapReduce jobs are implemented.

This reference path is independent of Hadoop. Future MapReduce stages can compare their intermediate and final outputs against this implementation on small fixtures.

## Input Format

The input is the Milestone 1 normalized ratings CSV:

```text
userId,movieId,rating,date
101,1,5,2005-01-01
101,2,4,2005-01-02
```

The header must be exactly `userId,movieId,rating,date`. User IDs and movie IDs must be positive integers, ratings must be integers from `1` through `5`, and dates must be valid `YYYY-MM-DD` values.

Exact duplicate rows are ignored after the first occurrence. If the same user rates the same movie with a different rating or date, the input is considered ambiguous and the run fails.

## Pair Statistics

For each user, the implementation considers unordered pairs of distinct movies rated by that user. For item pair `(i, j)` where `i < j`, and ratings `x = rating(user, i)` and `y = rating(user, j)`, it accumulates:

```text
common_users += 1
sum_xy += x * y
sum_x2 += x * x
sum_y2 += y * y
```

Self-pairs are never created.

## Co-Occurrence Similarity

Co-occurrence uses row-normalized common-user counts. After item pairs below `min_common_users` are removed, each directed relation is:

```text
similarity(i, j) = common_users(i, j) / sum_common_users(i, k)
```

The denominator uses all eligible neighbors `k` for source item `i` before Top-L truncation. The resulting directed values can be asymmetric.

## Cosine Similarity

Cosine similarity uses only users who rated both items:

```text
similarity(i, j) = sum_xy / sqrt(sum_x2 * sum_y2)
```

The implementation does not subtract user averages, and it does not implement adjusted cosine or Pearson correlation.

## Minimum Common Users

`--min-common-users` defaults to `1` and must be at least `1`. Item pairs with fewer common users are discarded before directed similarities are produced. For co-occurrence, this filtering also happens before row normalization.

## Top-L Neighbors

`--top-l` defaults to `50` and must be positive. For each source movie, neighbors are sorted by similarity descending, then neighbor movie ID ascending. At most Top-L neighbors are retained independently for each source movie.

## Recommendation Scoring

For user `u` and unseen candidate movie `c`, the score uses directed retained similarities from movies already rated by the user:

```text
score(u, c) =
sum(similarity(j, c) * rating(u, j))
/
sum(abs(similarity(j, c)))
```

Only retained Top-L relations from rated source item `j` to unseen candidate `c` contribute. Intermediate calculations are not rounded.

## Watched-Item Filtering

Movies already rated by the user are never recommended. Users with no valid unseen candidates may have no output rows. The implementation does not generate fallback popular-movie recommendations.

The Hadoop Milestone 7 raw scoring pipeline intentionally stops before this filtering step, so its `userId,movieId<TAB>score` output may still include movies already present in the user's history. Hadoop watched-item filtering is deferred to Milestone 8.

## Top-K Recommendations

`--top-k` defaults to `10` and must be positive. Recommendations are sorted by predicted score descending, then movie ID ascending. Ranks start at `1`.

## CLI Examples

Cosine:

```powershell
python scripts/itemcf_reference.py --input data/processed/ratings.csv --method cosine --min-common-users 1 --top-l 50 --top-k 10 --neighbors-output results/reference/cosine_neighbors.csv --recommendations-output results/reference/cosine_recommendations.csv --stats-output results/reference/cosine_stats.json
```

Co-occurrence:

```powershell
python scripts/itemcf_reference.py --input data/processed/ratings.csv --method cooccurrence --min-common-users 1 --top-l 50 --top-k 10 --neighbors-output results/reference/cooccurrence_neighbors.csv --recommendations-output results/reference/cooccurrence_recommendations.csv --stats-output results/reference/cooccurrence_stats.json
```

## Output Formats

Neighbor CSV:

```text
sourceMovieId,neighborMovieId,similarity,commonUsers
```

Recommendation CSV:

```text
userId,rank,movieId,score
```

Similarity and score values are written with 12 decimal places for stable CSV output.

## Statistics

The statistics JSON includes:

- `method`
- `input_file`
- `users`
- `items`
- `input_rows`
- `accepted_ratings`
- `exact_duplicate_rows_ignored`
- `unordered_item_pairs`
- `eligible_unordered_item_pairs`
- `directed_similarity_entries_before_top_l`
- `directed_similarity_entries_after_top_l`
- `users_with_recommendations`
- `recommendation_rows`
- `min_common_users`
- `top_l`
- `top_k`

`accepted_ratings` counts unique valid rating records after exact duplicate rows have been ignored.

## Limitations

- Offline batch recommendation only.
- No cold-start solution for new users or movies.
- No movie-content features.
- No user or item bias terms.
- No adjusted cosine.
- No fallback recommendation.
- Not designed for full Netflix-scale processing.
- Evaluation metrics are deferred to Milestone 9.
