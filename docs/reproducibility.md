# Reproducibility

## Environment

Required host tools:

- Python 3.10 or newer
- Java 17
- Maven
- Docker Desktop for Windows validation of Hadoop local-mode jobs

Install demo dependencies when Streamlit validation is needed:

```powershell
python -m pip install -r requirements.txt
```

## Full Reference Dataset

Place the GitHub reference-repository files locally under:

```text
data/raw/github-reference/
```

Required files are `movie_titles.txt` and `mv_0000001.txt` through `mv_0000015.txt`. Raw files are ignored and must not be committed.

Run the full local-mode Docker workflow:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_reference_dataset_docker.ps1 -DatasetDir data/raw/github-reference -TopL 10 -TopK 5 -MinCommonUsers 1 -RelevanceThreshold 4
```

The source has no rating dates. The split is deterministic non-temporal leave-one-out by highest `movieId`; it is not a time-aware split.

## Final Validation

Run Python tests:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Run Java packaging when Java 17 and Maven are available:

```powershell
mvn package
```

Run Docker Hadoop validation on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test_hadoop_maven_docker.ps1
```

Build report facts from generated artifacts:

```powershell
python scripts/build_final_report_data.py --output-dir target/final-report-data
```

Validate the Streamlit demo artifacts:

```powershell
python scripts/validate_streamlit_final.py
```

Assemble the final validation manifest:

```powershell
python scripts/run_final_validation.py
```

The all-in-one wrapper is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_final_validation.ps1
```

Use `-SkipDocker` or `-SkipStreamlitServer` only when documenting why that validation was not run.

## Submission Package

Build the tracked-file source package:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_submission_package.ps1
```

During local pre-commit review only, `-IncludeUntracked` can include new non-ignored source/docs files. Do not include raw datasets, generated results, `target`, `dist`, build outputs, secrets, or logs.

## Generated Outputs

Generated artifacts are intentionally ignored:

```text
results/full-reference-dataset/
target/final-report-data/
target/final-validation/
dist/
```

Only source code, tests, scripts, and documentation should be committed.
