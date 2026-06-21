# Submission Checklist

## MovieLens 1M Primary Experiment

- [ ] MovieLens 1M archive was acquired from the official GroupLens source.
- [ ] GroupLens license and acknowledgement guidance was reviewed.
- [ ] Raw MovieLens archive and extracted files are not committed.
- [ ] `ratings.dat`, `movies.dat`, and `users.dat` validate.
- [ ] `--strict-official-counts` validates 1,000,209 ratings.
- [ ] `--strict-official-counts` validates 6,040 users.
- [ ] Exact Unix timestamps are preserved in `ratings_with_timestamp.csv`.
- [ ] Leave-one-out by exact timestamp completed.
- [ ] Train/test overlap is zero.
- [ ] Test data does not enter model-building stages.
- [ ] Cosine full run completed.
- [ ] Co-occurrence full run completed.
- [ ] Watched recommendation violations are zero.
- [ ] `results/movielens-1m/method_comparison.csv` exists.
- [ ] `results/movielens-1m/movielens_1m_manifest.json` reports completed status.
- [ ] Streamlit MovieLens cosine mode validates.
- [ ] Streamlit MovieLens co-occurrence mode validates.
- [ ] Streamlit headless health check passes.
- [ ] MovieLens report facts were generated under `target/final-report-data/`.
- [ ] No fixture or GitHub 15-file value was used as a replacement for missing MovieLens values.

## Compatibility And Scalability

- [ ] GitHub reference 15-movie workflow remains available as compatibility validation.
- [ ] GitHub reference results are not described as the primary experiment.
- [ ] Synthetic benchmark results are labeled synthetic and scalability-only.
- [ ] Docker local-mode timing is described as one-container local-mode timing, not cluster scaling.

## Packaging

- [ ] `data/raw/movielens-1m/` is ignored.
- [ ] `results/movielens-1m/` is ignored.
- [ ] `target/final-report-data/` is ignored.
- [ ] `target/final-validation/` is ignored.
- [ ] Submission ZIP excludes `ml-1m.zip`, `ratings.dat`, `movies.dat`, `users.dat`, generated results, raw data, `target/`, logs, secrets, and credentials.
- [ ] Report metrics were copied from generated artifacts, not typed from memory.
- [ ] No commit, push, tag, or release was created unless explicitly requested.
