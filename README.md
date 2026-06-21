# Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce

This repository contains an academic Big Data project that builds a scalable offline movie recommender system. The system uses Item-Based Collaborative Filtering with Apache Hadoop MapReduce to generate Top-K movie recommendations from historical rating data.

## Project Resources

- **Project Drive & Dataset Link:** [Google Drive Folder](https://drive.google.com/drive/folders/1kx6gTTwtkcqMryqnqhO1ph2iiQI_Kw5J?usp=drive_link)

## Dataset Roles

- **MovieLens 1M** is the primary experimental dataset for evaluation and the Streamlit demo.
- **GitHub reference 15-movie dataset** is used for compatibility and regression workflow validation.
- **Synthetic datasets** are used for controlled scalability experiments.

## Technologies

- Java
- Apache Hadoop MapReduce
- HDFS
- Maven
- Python (for preprocessing, validation, and evaluation)
- Streamlit (for the local read-only demo)
- Docker (for the local Hadoop environment)

## Pipeline

```text
MovieLens 1M ratings.dat
-> exact timestamp preprocessing
-> time-aware train/test split
-> train-only user histories
-> shared item-pair statistics
-> cosine / co-occurrence similarity
-> recommendation scoring
-> filtering watched movies
-> Top-K recommendations
-> held-out evaluation
-> read-only demo
```

MovieLens 1M uses deterministic leave-one-out by exact Unix timestamp. The GitHub reference dataset has no rating dates, so it relies on deterministic non-temporal leave-one-out by the highest numeric `movieId`.

## Repository Structure

```text
.
|-- README.md
|-- .gitignore
|-- docs/
|-- demo/
|-- .streamlit/
|-- data/
|   |-- raw/
|   |-- sample/
|   `-- processed/
|-- scripts/
|-- src/
|   |-- main/
|   `-- test/
|-- tests/
|-- results/
`-- report/
```

## Data Policy

Large datasets, processed data, generated outputs, build artifacts, secrets, and local environment files are ignored by Git. Only reviewable sample files are committed under `data/sample` or `demo/sample`.

MovieLens 1M raw files can be acquired from the official GroupLens source or the Project Drive linked above.

## MovieLens 1M Primary Experiment

Optional official download:

```powershell
python scripts/download_movielens_1m.py --output-dir data/raw/movielens-1m
```

Offline verification of an existing manual download:

```powershell
python scripts/download_movielens_1m.py --output-dir data/raw/movielens-1m --verify-only
```

Preprocess and validate:

```powershell
python scripts/preprocess_movielens_1m.py `
  --dataset-dir data/raw/movielens-1m/ml-1m `
  --output-dir results/movielens-1m/normalized `
  --strict-official-counts
```

Preflight the full Docker workflow without Hadoop jobs:

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

Run or resume the full MovieLens 1M pipeline:

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

Generate report data:

```powershell
python scripts/build_final_report_data.py --output-dir target/final-report-data
```

Run the read-only Streamlit demo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

See [docs/movielens_1m_primary_experiment.md](docs/movielens_1m_primary_experiment.md) for the complete primary experiment procedure.

## Preprocessing Usage

Run the sample Netflix preprocessor from the repository root:

```powershell
python scripts/preprocess_netflix.py --input-dir data/sample/netflix --output data/processed/ratings.csv --stats-output data/processed/preprocess_stats.json
```

The command writes a normalized CSV with this header:

```text
userId,movieId,rating,date
```

Run the unit tests with:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

## Python Item-CF Reference Usage

Run the cosine reference model:

```powershell
python scripts/itemcf_reference.py --input data/processed/ratings.csv --method cosine --min-common-users 1 --top-l 50 --top-k 10 --neighbors-output results/reference/cosine_neighbors.csv --recommendations-output results/reference/cosine_recommendations.csv --stats-output results/reference/cosine_stats.json
```

Run the co-occurrence reference model:

```powershell
python scripts/itemcf_reference.py --input data/processed/ratings.csv --method cooccurrence --min-common-users 1 --top-l 50 --top-k 10 --neighbors-output results/reference/cooccurrence_neighbors.csv --recommendations-output results/reference/cooccurrence_recommendations.csv --stats-output results/reference/cooccurrence_stats.json
```

## Final Validation

Build report-ready facts from the generated MovieLens 1M artifacts:

```powershell
python scripts/build_final_report_data.py --output-dir target/final-report-data
```

Validate final Streamlit demo artifacts:

```powershell
python scripts/validate_streamlit_final.py
```

Run the final manifest check:

```powershell
python scripts/run_final_validation.py
```

The optional all-in-one Windows wrapper runs Python tests, compile checks, Maven packaging, Docker Hadoop validation, demo validation, report-data extraction, and final manifest assembly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_final_validation.ps1
```

Build the final source/documentation submission package:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_submission_package.ps1
```

The full-reference GitHub workflow is still available for compatibility validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_reference_dataset_docker.ps1
```

## Java, Maven, and Hadoop Smoke Usage

Prerequisites for host validation:

- Java 17
- Maven
- Apache Hadoop dependencies resolved through Maven

Compile and run Java tests:

```powershell
mvn clean test
```

Package the normal Maven JAR:

```powershell
mvn package
```

Run the local-mode Hadoop smoke job:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_hadoop_smoke.ps1
```

Optional Docker validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_hadoop_maven_docker.ps1
```

## User History Hadoop Job Usage

Run the fixture user-history job in Linux local mode:

```bash
bash scripts/run_user_history.sh
```

Run the same validation from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_user_history_docker.ps1
```

The output format is:

```text
userId<TAB>movieId:rating,movieId:rating,...
```

Movie IDs are sorted numerically within each user history. Exact duplicate normalized rating records are ignored, while conflicting duplicate user/movie rows fail the job.

## Item-Pair Statistics Hadoop Job Usage

Run the fixture item-pair statistics job in Linux local mode:

```bash
bash scripts/run_item_pair_stats.sh
```

Run the same validation from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_item_pair_stats_docker.ps1
```

The output format is:

```text
movieIdA,movieIdB<TAB>commonUsers,sumXY,sumX2,sumY2
```

## Item Similarity Hadoop Pipeline Usage

Run fixture cosine similarity in Linux local mode:

```bash
bash scripts/run_item_similarity.sh cosine
```

Run fixture co-occurrence similarity in Linux local mode:

```bash
bash scripts/run_item_similarity.sh cooccurrence
```

Run the same validations from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_item_similarity_docker.ps1 -Method cosine
powershell -ExecutionPolicy Bypass -File scripts/run_item_similarity_docker.ps1 -Method cooccurrence
```

The output format is:

```text
sourceMovieId,neighborMovieId<TAB>similarity,commonUsers
```

## Recommendation Scoring Hadoop Pipeline Usage

Run fixture raw recommendation scoring in Linux local mode:

```bash
bash scripts/run_recommendation_scoring.sh
```

Run the same validation from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_recommendation_scoring_docker.ps1
```

The output format is:

```text
userId,movieId<TAB>score
```

## Top-K Recommendation Hadoop Job Usage

Run fixture watched-item filtering and Top-K recommendation output in Linux local mode:

```bash
bash scripts/run_top_k_recommendations.sh
```

Run the same validation from Windows through Docker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_top_k_recommendations_docker.ps1 -TopK 2
```

The final offline output format is:

```text
userId<TAB>movieId:score,movieId:score,...
```

## Offline Evaluation Usage

The evaluation workflow creates a deterministic leave-one-out-by-time train/test split, builds all Hadoop recommender artifacts from the train split only, and evaluates raw predictions plus final Top-K recommendations against the held-out test ratings.

Run the full Docker evaluation with cosine similarity:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_offline_evaluation_docker.ps1 -Method cosine -TopK 2 -TopL 10 -MinCommonUsers 1 -RelevanceThreshold 4
```

Run the same workflow with row-normalized co-occurrence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_offline_evaluation_docker.ps1 -Method cooccurrence -TopK 2 -TopL 10 -MinCommonUsers 1 -RelevanceThreshold 4
```

Generated evaluation artifacts include `split_stats.json`, `metrics.json`, `metrics.csv`, and `per_user_metrics.csv` under `target/offline-evaluation/`.

## Scalability Benchmark Usage

The benchmark executes the Hadoop and evaluation workflow in Linux Docker local mode. Smoke is the normal validation profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke
```

The smoke profile runs three increasing synthetic dataset sizes, approximately 250, 1000, and 3000 ratings, with both cosine and row-normalized co-occurrence similarity.

Run the standard profile for longer report-oriented local measurements:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile standard
```

The extended profile may take significantly longer and can require more memory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile extended
```

Generated benchmark artifacts are written under `target/scalability-benchmark/` by default. 

## Streamlit Demo Usage

The read-only Streamlit app presents precomputed offline artifacts. The app can load the bundled sample fixture or local artifacts produced by the existing offline evaluation and benchmark workflows. 

Install the demo dependency:

```powershell
python -m pip install -r requirements-demo.txt
```

Run the demo from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

Or run it from a POSIX shell:

```bash
bash scripts/run_demo.sh
```

Run the demo-focused tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_demo.ps1
```

## Full Reference Dataset Run

This run supports the complete dataset subset committed in the referenced GitHub repository. 

Run the full Docker workflow:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_reference_dataset_docker.ps1 -DatasetDir data/raw/github-reference -TopL 10 -TopK 5 -MinCommonUsers 1 -RelevanceThreshold 4
```

The workflow validates raw rating files, performs a deterministic non-temporal leave-one-out-by-item split, runs similarity methods through the Hadoop local-mode pipeline, evaluates them, and exports report-ready tables.
