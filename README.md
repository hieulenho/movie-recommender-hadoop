# Scalable Movie Recommender System Using Item-Based Collaborative Filtering and Hadoop MapReduce

This repository contains the planned structure and documentation for an academic Big Data project that will build a scalable offline movie recommender system. The final system is intended to use Item-Based Collaborative Filtering with Apache Hadoop MapReduce to generate Top-K movie recommendations from historical rating data.

Current status: **Milestone 1 - Netflix Prize Dataset Preprocessing completed**.

The Netflix raw rating preprocessor is implemented. No Item-Based Collaborative Filtering algorithm, Hadoop job, MapReduce job, web UI, or evaluation code has been implemented yet.

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

Large datasets, processed data, generated outputs, build artifacts, secrets, and local environment files must not be committed to Git. Contents under `data/raw` and `data/processed` are ignored except for placeholder files. Only tiny reviewable sample files may be committed under `data/sample`.

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

Additional setup, Hadoop execution, recommendation, and evaluation instructions will be added in later milestones.
