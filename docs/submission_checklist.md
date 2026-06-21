# Submission Checklist

- [ ] All 15 reference rating files were processed: `mv_0000001.txt` through `mv_0000015.txt`.
- [ ] `movie_titles.txt` was converted to `movie_metadata.csv`.
- [ ] Normalized row count was verified against `dataset_stats.json`.
- [ ] Raw dataset files under `data/raw/github-reference/` are not committed.
- [ ] Generated full-run outputs under `results/full-reference-dataset/` are not committed.
- [ ] Report metrics were copied from generated artifacts, not typed from memory.
- [ ] Dataset is described as a 15-movie GitHub reference-repository subset.
- [ ] Report does not describe the run as the complete official Netflix Prize dataset.
- [ ] `train_test_overlap_count` is zero in `full_dataset_manifest.json`.
- [ ] `watched_recommendation_violations` is zero in `full_dataset_manifest.json`.
- [ ] Both cosine and co-occurrence statuses are completed.
- [ ] Docker local-mode timing is described as single-container local-mode timing.
