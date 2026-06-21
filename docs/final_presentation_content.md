# Final Presentation Content

## Slide 1: Project Goal

- Build an offline Top-K movie recommender using Item-Based Collaborative Filtering.
- Implement the scalable pipeline with Java Hadoop MapReduce jobs.
- Validate output with deterministic Python utilities, Docker local-mode Hadoop runs, and a read-only Streamlit demo.

## Slide 2: Full Reference Dataset

- Source: `thviet79/Bigdata_Project_Recommender_System`.
- Scope: all 15 available `mv_*.txt` files in that repository.
- Rows: 21629 ratings, 20537 users, 15 movies.
- Input schema: `userId,movieId,rating`.
- Date status: no source rating dates.

## Slide 3: Split And Leakage Control

- Split: deterministic non-temporal leave-one-out by highest movie ID.
- Train rows: 20741; test rows: 888.
- Train/test overlap rows: 0.
- Hadoop model-building stages consume train rows only.
- Placeholder date `1970-01-01` exists only for schema compatibility after splitting.

## Slide 4: Pipeline

```text
normalize raw ratings
-> split train/test
-> user history
-> item-pair statistics
-> item similarity Top-L
-> raw recommendation scoring
-> watched-item filtering and Top-K
-> offline evaluation
-> read-only demo
```

## Slide 5: Method Comparison

| Method | Coverage | RMSE | Precision@K | Recall@K | NDCG@K | MRR@K |
|---|---:|---:|---:|---:|---:|---:|
| cosine | 0.8592342342 | 1.6590045822 | 0.0258675079 | 0.1293375394 | 0.0558198181 | 0.0328075710 |
| cooccurrence | 0.8547297297 | 1.6720603280 | 0.0233438486 | 0.1167192429 | 0.0554198178 | 0.0362250263 |

## Slide 6: Demo

- Local artifacts can be loaded from `results/full-reference-dataset/cosine/`.
- Demo displays user history, recommendations, evaluation metrics, and optional benchmark tables.
- Demo is read-only and does not launch Hadoop or modify outputs.

## Slide 7: Limitations

- This is a 15-movie GitHub subset, not the full official Netflix Prize dataset.
- Full-reference evaluation is non-temporal because the source has no dates.
- Docker Hadoop local mode validates reproducibility, not multi-node cluster scaling.
- Scalability benchmark: Chưa có dữ liệu thực nghiệm.
