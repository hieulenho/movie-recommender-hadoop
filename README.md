# Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce

This repository contains the planned structure and documentation for an academic Big Data project that will build a scalable offline movie recommender system. The final system is intended to use Item-Based Collaborative Filtering with Apache Hadoop MapReduce to generate Top-K movie recommendations from historical rating data.

Current status: **Milestone 4 - User History Hadoop MapReduce Job implemented; full Docker/Linux validation pending**.

The Netflix raw rating preprocessor, local Python Item-CF reference implementation, Maven/Hadoop smoke environment, and User History MapReduce job are implemented. Item-pair statistics, similarity, recommendation scoring, watched-item filtering, Top-K recommendation, train/test evaluation, Spark, a web UI, and Hadoop cluster deployment are not implemented yet.

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
-> prediction
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

Item-pair statistics and similarity jobs are planned for later milestones and are not part of this implementation.
