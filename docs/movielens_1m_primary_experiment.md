# MovieLens 1M Primary Experiment

MovieLens 1M is the primary real experimental dataset for the final evaluation, report, presentation, and Streamlit demo.

## Dataset Roles

- MovieLens 1M: primary real experiment and primary offline evaluation dataset.
- GitHub reference 15-movie dataset: compatibility and workflow validation only.
- Synthetic datasets: controlled scalability experiments only.

Metrics from these roles use different protocols and should not be presented as directly interchangeable.

## Source And Acknowledgement

Acquire MovieLens 1M only from the official GroupLens source:

```text
https://files.grouplens.org/datasets/movielens/ml-1m.zip
```

Review the included README/license before use and include the GroupLens acknowledgement in the report or slides. Do not commit, redistribute, or package `ml-1m.zip`, `ratings.dat`, `movies.dat`, or `users.dat`.

## Acquisition

Optional downloader:

```powershell
python scripts/download_movielens_1m.py --output-dir data/raw/movielens-1m
```

Verification without network:

```powershell
python scripts/download_movielens_1m.py --output-dir data/raw/movielens-1m --verify-only
```

Manual mode is also supported. Downstream scripts accept a directory containing:

```text
ratings.dat
movies.dat
users.dat
README
```

## Source Formats

`ratings.dat`:

```text
UserID::MovieID::Rating::Timestamp
```

`movies.dat`:

```text
MovieID::Title::Genres
```

`users.dat`:

```text
UserID::Gender::Age::Occupation::Zip-code
```

The recommender does not use demographic attributes.

## Preprocessing

```powershell
python scripts/preprocess_movielens_1m.py `
  --dataset-dir data/raw/movielens-1m/ml-1m `
  --output-dir results/movielens-1m/normalized `
  --strict-official-counts
```

Outputs:

```text
results/movielens-1m/normalized/
|-- ratings_with_timestamp.csv
|-- movie_metadata.csv
|-- dataset_stats.json
`-- preprocessing_manifest.json
```

Timestamps are converted with UTC, never local time. `ratings_with_timestamp.csv` keeps the original Unix timestamp and writes:

```text
userId,movieId,rating,timestamp,dateTimeUtc,date
```

`movie_metadata.csv` writes:

```text
movieId,title,year,genres
```

Metadata enriches the UI only and does not change recommendation scores or ranking.

## Temporal Split

```powershell
python scripts/split_movielens_1m.py `
  --input results/movielens-1m/normalized/ratings_with_timestamp.csv `
  --output-dir results/movielens-1m/split
```

The split is deterministic leave-one-out by exact timestamp. Per user:

1. Sort by timestamp ascending.
2. Break equal-timestamp ties by movie ID ascending.
3. Hold out the final record, so equal latest timestamps hold out the highest movie ID.

The Hadoop model-building stages receive only `train_ratings.csv`. The held-out `test_ratings.csv` is used only by the evaluator.

## Full Docker Run

Preflight:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts/run_movielens_1m_docker.ps1 `
  -DatasetDir data/raw/movielens-1m/ml-1m `
  -TopL 50 `
  -TopK 10 `
  -MinCommonUsers 5 `
  -RelevanceThreshold 4 `
  -Reducers 4 `
  -PreflightOnly
```

Full run:

```powershell
powershell -ExecutionPolicy Bypass `
  -File scripts/run_movielens_1m_docker.ps1 `
  -DatasetDir data/raw/movielens-1m/ml-1m `
  -TopL 50 `
  -TopK 10 `
  -MinCommonUsers 5 `
  -RelevanceThreshold 4 `
  -Reducers 4 `
  -Resume
```

Defaults are documented experiment defaults, not a claim of universal optimality.

## Output Structure

```text
results/movielens-1m/
|-- normalized/
|-- split/
|-- common/
|   |-- user-history/
|   `-- pair-statistics/
|-- cosine/
|   |-- similarity/
|   |-- raw-predictions/
|   |-- recommendations/
|   |-- metrics.json
|   |-- metrics.csv
|   `-- per_user_metrics.csv
|-- cooccurrence/
|-- logs/
|-- report-artifacts/
|-- method_comparison.csv
|-- stage_metrics.json
`-- movielens_1m_manifest.json
```

`common/pair-statistics` is produced once and shared by cosine and co-occurrence.

## Resume Behavior

Each stage writes a manifest under `results/movielens-1m/logs/stage-manifests/`. A stage may be skipped only when the previous manifest is completed, input signatures match, parameters match, and required outputs exist. `-ForceStage` reruns the named stage and its downstream stages.

Only pipeline-owned generated paths under `results/` are deleted. Raw MovieLens files are never deleted by the runner.

## Report And Streamlit

Build report facts:

```powershell
python scripts/build_final_report_data.py --output-dir target/final-report-data
```

Validate Streamlit artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_streamlit_final.ps1 -Method cosine
```

Run the demo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

The Streamlit app is read-only. It selects precomputed MovieLens artifacts and never runs Hadoop, Maven, Docker, or model code from UI interactions.

## Limitations

- Docker Hadoop local mode is a reproducibility environment, not a multi-node cluster.
- Synthetic scalability results are controlled input-size experiments, not real recommendation-quality metrics.
- Missing predictions are reported and are not imputed as zero.
- Raw MovieLens data and generated MovieLens results are ignored by Git and excluded from the submission package.
