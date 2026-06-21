# Streamlit Offline Demo

## Purpose

The Streamlit application is a read-only presentation layer over precomputed recommendation artifacts. MovieLens 1M is the primary real-artifact mode for final validation. The GitHub reference dataset remains available as compatibility mode, and the bundled sample remains available for UI smoke testing.

The demo does not run Hadoop, Maven, Docker, preprocessing, model training, similarity calculation, recommendation scoring, watched-item filtering, or benchmark orchestration in response to UI interactions.

## Architecture

```text
precomputed offline artifacts
-> pure Python artifact parsers
-> integrity validation
-> Streamlit read-only presentation layer
```

The recommender algorithm remains in the Java Hadoop pipeline. Streamlit displays artifacts that already exist on disk.

## Data Modes

MovieLens mode defaults to:

- `results/movielens-1m/common/user-history`
- `results/movielens-1m/<method>/recommendations`
- `results/movielens-1m/<method>/metrics.json`
- `results/movielens-1m/normalized/movie_metadata.csv`
- `results/movielens-1m/method_comparison.csv`
- `results/movielens-1m/movielens_1m_manifest.json`

The similarity selector switches between cosine and co-occurrence by loading different precomputed artifacts. It never recomputes recommendations.

GitHub reference mode loads the preserved 15-movie compatibility workflow. Bundled sample mode uses tiny fixture rows and is labeled as a demonstration fixture, not final experimental output. Custom local-artifact mode accepts explicit paths for required user-history and recommendation artifacts plus optional metrics, benchmark, metadata, manifest, and method-comparison files.

User-history and recommendation inputs may be either one text file or a Hadoop output directory containing sorted `part-*` files. `_SUCCESS`, hidden files, CRC files, and logs are ignored.

## Formats

The demo reuses documented formats from `docs/data_format.md`: user histories, final Top-K recommendations, metrics JSON, synthetic benchmark CSV, and optional movie metadata. Metadata may be either:

```text
movieId,title,year
movieId,title,year,genres
```

Metadata is display-only. It never changes ranking, scores, filtering, metrics, or integrity checks. Missing metadata falls back to `Movie <movieId>`.

## Integrity Validation

The loader and service validate positive IDs, rating and score ranges, finite scores, duplicate rows, recommendation order, unknown users, metadata coverage, and watched-movie recommendation violations. Validation errors are shown concisely in the UI.

## UI Tabs

- `User recommendations`: user selector, watched count, recommendation count, rating/score averages, watched movies, Top-K recommendations, genres, and selected-user CSV download.
- `Evaluation`: MovieLens evaluation metrics, missing-prediction reporting, method comparison, train/test overlap, and watched-recommendation diagnostics.
- `Scalability`: synthetic benchmark summaries. Synthetic scalability rows are shown separately from MovieLens quality metrics.
- `Architecture`: MovieLens timestamp preprocessing, exact temporal split, train-only Hadoop pipeline, cosine/co-occurrence, Top-K, evaluator, and Docker local-mode limitation.

## Installation

Install demo-only dependencies in an isolated environment:

```powershell
python -m pip install -r requirements-demo.txt
```

The dependency is intentionally not added to `pom.xml` or the Hadoop Maven Docker image.

## Run Commands

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

POSIX:

```bash
bash scripts/run_demo.sh
```

Demo tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_demo.ps1
```

Final MovieLens validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_streamlit_final.ps1 -Method cosine
```

## Cache Policy

`demo/app.py` uses `st.cache_data` for artifact loading. Cache keys include each artifact path, file size, and modification timestamp. For Hadoop output directories, all discovered `part-*` files are included in the signature.

## Regenerating Artifacts

MovieLens primary artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_movielens_1m_docker.ps1 -DatasetDir data/raw/movielens-1m/ml-1m -Resume
```

Synthetic benchmark artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke
```

## Limitations

- The demo is local and read-only.
- It does not provide authentication, feedback collection, remote APIs, metadata downloads, databases, or online recommendation generation.
- Benchmark results are Docker Hadoop local-mode measurements, not multi-node cluster scaling.
- Raw MovieLens files and generated MovieLens results remain untracked.
