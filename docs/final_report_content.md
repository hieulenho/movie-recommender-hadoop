# Final Report Content Placeholders

## Full Reference Dataset

- Complete reference-dataset row count: copy from `results/full-reference-dataset/normalized/dataset_stats.json`.
- Distinct users: copy from `distinct_users`.
- Distinct source movies: should be `15`.
- Source date status: copy from `source_date_status`; for the GitHub reference run it should be `unavailable`.
- Split protocol: copy `deterministic-leave-one-out-by-item` from `split/split_stats.json`.
- Exact duplicates ignored: copy from `exact_duplicates_ignored`.

## Method Metrics

- Cosine metrics: copy from `results/full-reference-dataset/cosine/metrics.json`.
- Co-occurrence metrics: copy from `results/full-reference-dataset/cooccurrence/metrics.json`.
- Method comparison: copy from `results/full-reference-dataset/method_comparison.csv`.
- Full-run timing: copy `totalPipelineSeconds` and stage timing columns from `method_comparison.csv`.

## Limitations

- The full reference run uses all 15 movie files from the GitHub reference repository.
- It is not the complete official Netflix Prize dataset.
- The source files contain `userId,movieId,rating` and no rating date.
- The full-reference metrics use deterministic non-temporal holdout, not leave-one-out-by-time.
- Do not compare those metrics against dated fixture/evaluation runs as if the protocols were identical.
- The small movie count limits item-item coverage, candidate diversity, and generalizability of quality metrics.
- Hadoop local-mode Docker timing is not multi-node cluster scaling evidence.
