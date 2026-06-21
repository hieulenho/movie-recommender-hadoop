# Final Presentation Content

## Slide 1: Project Goal

- Build an offline Top-K movie recommender using Item-Based Collaborative Filtering.
- Implement the scalable pipeline with Java Hadoop MapReduce jobs.
- Use MovieLens 1M as the primary real experimental dataset.
- Validate output with deterministic Python utilities, Docker local-mode Hadoop runs, and a read-only Streamlit demo.

## Slide 2: Primary Dataset

- Source: MovieLens 1M from the official GroupLens distribution.
- Files: `ratings.dat`, `movies.dat`, `users.dat`, `README`.
- Ratings: Chưa có kết quả MovieLens 1M.
- Users: Chưa có kết quả MovieLens 1M.
- Rated movies: Chưa có kết quả MovieLens 1M.
- Rating scale: whole-star integers from 1 through 5.
- Timestamp handling: Unix timestamps preserved and converted with UTC.

## Slide 3: Split And Leakage Control

- Split: leave-one-out by exact timestamp.
- Train rows: Chưa có kết quả MovieLens 1M.
- Test rows: Chưa có kết quả MovieLens 1M.
- Train/test overlap rows: Chưa có kết quả MovieLens 1M.
- Hadoop model-building stages consume train rows only.
- Held-out test rows are read only by the evaluator.

## Slide 4: Pipeline

```text
MovieLens 1M ratings.dat
-> exact timestamp preprocessing
-> time-aware split
-> user history
-> shared item-pair statistics
-> cosine / co-occurrence Top-L
-> raw recommendation scoring
-> watched-item filtering and Top-K
-> held-out evaluation
-> read-only demo
```

## Slide 5: Method Comparison

Use `results/movielens-1m/method_comparison.csv`.

| Method | Coverage | RMSE | Precision@K | Recall@K | NDCG@K | MRR@K |
|---|---:|---:|---:|---:|---:|---:|
| cosine | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |
| cooccurrence | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M | Chưa có kết quả MovieLens 1M |

## Slide 6: Scalability

- Synthetic profiles are used for controlled scalability experiments.
- Synthetic rows are not real recommendation-quality results.
- Execution environment: one Docker Hadoop local-mode container.
- Do not claim multi-node speedup.

## Slide 7: Demo

- MovieLens mode loads `results/movielens-1m/`.
- Cosine and co-occurrence are selected from precomputed artifacts.
- Real movie titles and genres come from `movie_metadata.csv`.
- Demo is read-only and does not launch Hadoop, Maven, Docker, or model code.

## Slide 8: Compatibility And Limitations

- GitHub reference 15-movie dataset remains compatibility validation and appendix material.
- Raw MovieLens files are not committed or redistributed.
- Missing predictions are reported, not imputed.
- Docker local mode validates reproducibility, not distributed cluster scaling.
