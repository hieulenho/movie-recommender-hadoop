# Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce

This repository contains the planned structure and documentation for an academic Big Data project that will build a scalable offline movie recommender system. The final system is intended to use Item-Based Collaborative Filtering with Apache Hadoop MapReduce to generate Top-K movie recommendations from historical rating data.

Current status: **Milestone 7 - Recommendation Score Calculation Hadoop MapReduce Pipeline completed**.

The Netflix raw rating preprocessor, local Python Item-CF reference implementation, Maven/Hadoop smoke environment, User History MapReduce job, Item-Pair Statistics MapReduce job, Item Similarity/Top-L Neighbors MapReduce pipeline, and raw Recommendation Scoring MapReduce pipeline are implemented. Watched-item filtering, Top-K recommendation, train/test evaluation, Spark, a web UI, and Hadoop cluster deployment are not implemented yet.

## Main Objectives

- Define a clean repository structure for a Hadoop-based recommender project.
- Document the planned architecture, data formats, and milestone roadmap.
- Prepare the project for later implementation of preprocessing, MapReduce jobs, evaluation, and optional demo components.
- Keep implementation decisions traceable through version-controlled documentation.

## Planned Technologies

- Java
- Apache Hadoop MapReduce
- HDFS
- Maven
- Python for preprocessing, validation, and evaluation
- Docker as a possible local Hadoop environment

## Planned Pipeline

```text
raw data
-> preprocessing
-> user histories
-> item-pair statistics
-> item similarity
-> recommendation scoring
-> filtering watched movies
-> Top-K recommendations
-> evaluation
```

## Repository Structure

```text
.
|-- README.md
|-- AGENTS.md
|-- .gitignore
|-- docs/
|   |-- project_scope.md
|   |-- architecture.md
|   |-- milestones.md
|   |-- data_format.md
|   |-- preprocessing.md
|   |-- itemcf_reference.md
|   |-- user_history_job.md
|   |-- item_pair_statistics_job.md
|   |-- item_similarity_job.md
|   |-- recommendation_scoring_job.md
|   |-- hadoop_environment.md
|   `-- references.md
|-- data/
|   |-- raw/
|   |-- sample/
|   `-- processed/
|-- scripts/
|-- src/
|   |-- main/
|   |   |-- java/
|   |   `-- resources/
|   `-- test/
|       |-- java/
|       `-- resources/
|-- tests/
|   `-- fixtures/
|-- results/
`-- report/
```

## Data Policy

Large datasets, processed data, generated outputs, build artifacts, secrets, and local environment files must not be committed to Git. Contents under `data/raw`, `data/processed`, and generated `results` outputs are ignored except for placeholder files. Only tiny reviewable sample files may be committed under `data/sample`.

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

Generated files under `results` are local outputs and are not committed.

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

Native Windows Hadoop local-mode execution can require unsupported Hadoop Windows binaries. Do not add `winutils.exe`, do not hard-code `HADOOP_HOME`, and use the Docker/Linux validation path for real local-mode Hadoop integration tests on Windows.

Hadoop local mode is not a distributed cluster. HDFS and YARN are not started in this project environment.

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

Movie pairs are unordered with `movieIdA < movieIdB`. The statistics match the Python Item-CF reference definitions and are intended for the similarity milestone.

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

Similarity rows are directed. Cosine emits symmetric values for both directions; row-normalized co-occurrence may be asymmetric. Similarity values are formatted with exactly 10 digits after the decimal point. Recommendation scoring consumes this directed Top-L output in Milestone 7.

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

Scores are weighted averages over retained directed Top-L similarities and are formatted with exactly 10 digits after the decimal point. Raw prediction rows may include movies the user has already rated; watched-item filtering and Top-K ranking are deferred to Milestone 8.
