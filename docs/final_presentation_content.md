# Final Presentation Content Placeholders

## Full Reference Dataset Slide

- Dataset statistics location: `results/full-reference-dataset/normalized/dataset_stats.json`.
- Normalized CSV location: `results/full-reference-dataset/normalized/ratings.csv`.
- Metadata location: `results/full-reference-dataset/metadata/movie_metadata.csv`.
- Split statistics location: `results/full-reference-dataset/split/split_stats.json`.
- Note that the source files contain `userId,movieId,rating` with no rating date; evaluation uses deterministic non-temporal holdout.

## Method Comparison Slide

- Cosine/co-occurrence comparison table: `results/full-reference-dataset/method_comparison.csv`.
- Cosine metrics: `results/full-reference-dataset/cosine/metrics.json`.
- Co-occurrence metrics: `results/full-reference-dataset/cooccurrence/metrics.json`.

## Demo Slide

- Streamlit screenshot should show local artifacts loaded from `results/full-reference-dataset/`.
- Recommended local-artifact paths:
  - User history: `results/full-reference-dataset/cosine/user-history/`
  - Recommendations: `results/full-reference-dataset/cosine/recommendations/`
  - Metadata: `results/full-reference-dataset/metadata/movie_metadata.csv`
  - Evaluation metrics: `results/full-reference-dataset/cosine/metrics.json`
  - Benchmark or comparison CSV: `results/full-reference-dataset/method_comparison.csv`
