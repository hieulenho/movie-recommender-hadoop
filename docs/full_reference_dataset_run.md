# Full Reference Dataset Run

## Purpose

Milestone 12 adds a reproducible run for the complete dataset subset included in the referenced GitHub repository `thviet79/Bigdata_Project_Recommender_System`.

After the MovieLens 1M migration, this workflow is compatibility and regression validation only. It is not the primary final evaluation dataset and should appear in reports as appendix or secondary evidence.

This run uses all 15 committed movie rating files from `Movie_DataSet`:

```text
mv_0000001.txt
mv_0000002.txt
mv_0000003.txt
mv_0000004.txt
mv_0000005.txt
mv_0000006.txt
mv_0000007.txt
mv_0000008.txt
mv_0000009.txt
mv_0000010.txt
mv_0000011.txt
mv_0000012.txt
mv_0000013.txt
mv_0000014.txt
mv_0000015.txt
```

It also requires `movie_titles.txt`. This is the complete GitHub reference-repository subset used by this project, not the complete official Netflix Prize dataset.

## Acquisition

Place the files manually under:

```text
data/raw/github-reference/
```

Do not commit those raw files. The `data/raw/*` ignore rule keeps them local.

## Validation

The runner requires exactly the 15 rating files above and `movie_titles.txt`. The source rating files use the already transformed GitHub reference format:

```text
userId,movieId,rating
```

There is no CSV header, no `movieId:` colon header, and no rating date column. The runner fails if a rating file is missing, empty, not a regular file, contains malformed nonblank rows, has a row whose `movieId` does not match the numeric ID in the filename, or includes unexpected `mv_*.txt` files.

Malformed nonblank rows are fatal for this full reference run. Blank lines may be ignored and counted. Duplicate `userId,movieId` records with the same rating are ignored and counted; conflicting duplicate ratings fail clearly.

## Preprocessing

The workflow uses explicit `github-reference-3col` parsing and writes Hadoop-compatible normalized artifacts:

```text
results/full-reference-dataset/normalized/ratings.csv
results/full-reference-dataset/normalized/dataset_stats.json
```

The normalized CSV header is exactly:

```text
userId,movieId,rating,date
```

Rows are sorted by user ID ascending, date ascending, then movie ID ascending. The dataset statistics JSON records source hashes, normalized CSV hash, row counts, duplicate count, user/movie counts, date range, rating range, and ratings-per-movie values without absolute host paths.

Because the GitHub reference files do not contain dates, the source date status is recorded as unavailable. The workflow first performs a deterministic non-temporal split on undated records, then writes `1970-01-01` as a fixed schema placeholder so existing Hadoop jobs can consume `userId,movieId,rating,date`. The placeholder never determines the held-out item and must not be interpreted as a real rating timestamp.

## Metadata

`scripts/convert_reference_movie_titles.py` converts:

```text
data/raw/github-reference/movie_titles.txt
```

to:

```text
results/full-reference-dataset/metadata/movie_metadata.csv
```

The metadata CSV header is:

```text
movieId,title,year
```

Titles with commas are handled through CSV parsing. Blank year values are allowed when the source metadata has no year column.

## Full Pipeline

Run from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_reference_dataset_docker.ps1 -DatasetDir data/raw/github-reference -TopL 10 -TopK 5 -MinCommonUsers 1 -RelevanceThreshold 4
```

The Docker wrapper builds the existing Maven/Hadoop validation image, mounts the repository, and runs `scripts/run_full_reference_dataset.sh`. It does not use Docker Compose, does not start Hadoop daemons, does not add `winutils.exe`, and does not copy raw data into the Docker image layer.

The POSIX script runs:

```text
validate 15 raw files
-> parse github-reference-3col ratings
-> convert movie metadata
-> deterministic leave-one-out-by-item split
-> add fixed placeholder date for Hadoop schema compatibility
-> cosine Hadoop stages
-> cosine evaluation
-> cooccurrence Hadoop stages
-> cooccurrence evaluation
-> report artifact export
-> manifest and method comparison
```

For each user, ratings are sorted by `movieId` ascending. If the user has at least two distinct rated movies, the highest `movieId` is held out for evaluation. Single-rating users remain train-only and are excluded from evaluation. The held-out test CSV is never supplied to UserHistoryJob, ItemPairStatisticsJob, ItemSimilarityPipeline, RecommendationScoringPipeline, or TopKRecommendationJob.

## Output Artifacts

Generated files are written under:

```text
results/full-reference-dataset/
```

Important outputs:

- `normalized/ratings.csv`
- `normalized/dataset_stats.json`
- `metadata/movie_metadata.csv`
- `split/train_ratings.csv`
- `split/test_ratings.csv`
- `split/split_stats.json`
- `cosine/metrics.json`
- `cooccurrence/metrics.json`
- `method_comparison.csv`
- `full_dataset_manifest.json`
- `report-artifacts/`
- `logs/`

Use `metadata/movie_metadata.csv`, `split/train_ratings.csv`, `cosine/recommendations/`, `cosine/metrics.json`, and `method_comparison.csv` as local-artifact paths in the Streamlit demo. Switch the method paths to `cooccurrence/` to inspect the second method.

## Runtime And Limitations

The run uses one Docker container and Hadoop local mode. Runtime can vary by machine, Docker cache, disk speed, JVM startup time, and Maven dependency cache state. These timings are not multi-node cluster scaling results.

The source contains only 15 movie files, so the report must discuss the limitation that item coverage is tiny compared with the official Netflix Prize dataset. The workflow may still contain many rating rows, but it is not the complete official Netflix Prize corpus.

Results from this deterministic non-temporal holdout must not be compared as if they used the same evaluation protocol as earlier dated fixture workflows that use leave-one-out-by-time.

## Failure Recovery

The runner removes only its owned output directory under `results/full-reference-dataset/` when restarting. It never deletes `data/raw/github-reference/`. Logs are preserved inside the output directory until the next owned rerun.

If a stage fails, inspect:

```text
results/full-reference-dataset/logs/
```

Then rerun the Docker command after correcting the input or environment issue.

## Git Policy

Do not commit raw files under `data/raw/github-reference/`. Do not commit generated full-run outputs under `results/full-reference-dataset/` or `target/full-reference-dataset/`.
