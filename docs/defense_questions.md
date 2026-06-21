# Defense Questions

## Why is the full-reference split not time-aware?

The source files used by this project contain `userId,movieId,rating` only. There is no rating date, so a time-aware split would invent information. The final full-reference workflow uses deterministic non-temporal leave-one-out by item: for each eligible user, the highest numeric `movieId` is held out.

## Why is `1970-01-01` present in normalized files?

It is a schema placeholder written after the non-temporal split so the existing Hadoop jobs can consume `userId,movieId,rating,date`. It is not a real timestamp and is never used to choose the held-out test row.

## Is this the complete Netflix Prize dataset?

No. It is the complete 15-movie subset available in `thviet79/Bigdata_Project_Recommender_System`. The official Netflix Prize dataset is much larger.

## How do you prevent train/test leakage?

The workflow splits before Hadoop model-building. User history, item-pair statistics, item similarity, recommendation scoring, and Top-K selection receive train rows only. The manifest records `train_test_overlap_count`, which must be zero.

## How do you prevent recommending watched movies?

The final Top-K Hadoop job joins raw predictions with train user history and removes watched movie IDs. The final manifest records `watched_recommendation_violations`, which must be zero.

## Why are local Docker timings not scalability proof?

The Docker workflow runs Hadoop local mode in one container. It validates reproducibility and stage behavior, but it does not start a multi-node Hadoop cluster, HDFS, or YARN.

## Which method performed better on the available full-reference run?

Cosine has slightly lower RMSE and higher coverage in the recorded full-reference artifacts. Co-occurrence has a slightly higher MRR@K. These differences are tied to the 15-movie undated subset and should not be generalized to the full Netflix corpus.

## What should be said if scalability benchmark files are absent?

Say: "Chưa có dữ liệu thực nghiệm." Do not substitute demo, fixture, synthetic, or local pipeline timing values for real benchmark results.
