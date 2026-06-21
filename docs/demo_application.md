# Streamlit Offline Demo

## Purpose

Milestone 11 adds a local Streamlit application that presents precomputed Hadoop recommendation artifacts. It is a read-only exploration layer for user histories, final Top-K recommendations, offline evaluation metrics, and scalability benchmark results.

The demo does not run Hadoop, Maven, Docker, model training, similarity calculation, recommendation scoring, watched-item filtering, or benchmark orchestration in response to UI interactions.

## Architecture

```text
offline Hadoop artifacts
-> pure Python artifact parsers
-> integrity validation
-> Streamlit read-only presentation layer
```

The recommender algorithm remains in the Java Hadoop pipeline. Streamlit displays artifacts that already exist on disk.

## Data Modes

Bundled sample mode uses tiny fixture rows based on Milestone 8 Top-K semantics and Milestone 9 evaluator fixture metrics. The UI labels it as a demonstration fixture, not as full Netflix Prize or final experimental results. Bundled movie titles are demonstration labels such as `Demo Movie 1`.

Local-artifact mode accepts paths for required user-history and final Top-K recommendation artifacts, plus optional evaluation metrics JSON, benchmark results CSV, and movie metadata CSV.

User-history and recommendation inputs may be either one text file or a Hadoop output directory containing sorted `part-*` files. `_SUCCESS`, hidden files, CRC files, and logs are ignored.

Missing optional artifacts produce warnings and do not break the recommendation tab. Missing required artifacts prevent display of an invalid bundle.

## Formats

The demo reuses documented artifact formats from `docs/data_format.md`: user histories, final Top-K recommendations, Milestone 9 metrics JSON, Milestone 10 benchmark CSV, and optional `movieId,title,year` metadata.

Metadata is display-only. It never changes ranking, scores, filtering, metrics, or integrity checks. Missing metadata falls back to `Movie <movieId>`.

## Integrity Validation

The loader and service validate positive IDs, rating and score ranges, finite scores, duplicate rows, recommendation order, unknown users, and watched-movie recommendation violations. Validation errors are shown concisely in the UI with technical detail in an expander.

## UI Tabs

- `Gợi ý cho người dùng`: user selector, summary metrics, watched table, recommendation table, and selected-user CSV download.
- `Đánh giá mô hình`: Milestone 9 metrics, missing-prediction reporting, leakage diagnostics, and watched-recommendation checks.
- `Khả năng mở rộng`: Milestone 10 benchmark summaries, filtering, successful and failed runs, and stage runtime details.
- `Kiến trúc hệ thống`: pipeline explanation, cosine formula, co-occurrence description, weighted-score formula, leakage prevention, and Docker local-mode limitation.

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

## Cache Policy

`demo/app.py` uses `st.cache_data` for artifact loading. Cache keys include each artifact path, file size, and modification timestamp. For Hadoop output directories, all discovered `part-*` files are included in the signature. The cache never stores open file handles.

## Regenerating Real Artifacts

Evaluation artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_offline_evaluation_docker.ps1 -Method cosine -TopK 2 -TopL 10 -MinCommonUsers 1 -RelevanceThreshold 4
```

Benchmark artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke
```

## Limitations

- The demo is local and read-only.
- It does not provide authentication, feedback collection, remote APIs, metadata downloads, databases, or online recommendation generation.
- Benchmark results are Docker Hadoop local-mode measurements, not multi-node cluster scaling.
- The next milestone is Milestone 12: final documentation, release, and submission.

