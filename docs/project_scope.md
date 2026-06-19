# Project Scope

## Problem

The project addresses the problem of recommending movies to users based on historical rating behavior. Given a large collection of user-movie ratings, the planned system will estimate which unwatched movies may be relevant to each user and produce ranked recommendation lists.

## Purpose of Item-Based Collaborative Filtering

Item-Based Collaborative Filtering compares movies according to how similarly users have rated them. Instead of directly searching for similar users, the approach builds relationships between items and uses a user's past ratings to score candidate movies.

This approach is suitable for an offline recommender because item similarities can be precomputed and reused when generating recommendations.

## Why Hadoop MapReduce

Hadoop MapReduce is planned for the core batch computations because rating datasets can become too large for single-machine processing. MapReduce provides a distributed processing model for grouping user histories, counting item-pair statistics, computing similarities, and producing recommendation scores over data stored in HDFS.

## Functional Scope

- Convert raw rating data into normalized records.
- Build user histories from normalized ratings.
- Generate item-pair co-rating statistics.
- Compute item-item similarity scores.
- Use similarities and user histories to predict candidate movie scores.
- Remove movies the user has already watched or rated.
- Produce Top-K recommendations for users.
- Evaluate recommendation quality using a held-out test set.

## Out of Scope for the First Version

- Real-time recommendation updates.
- Online model serving.
- Deep learning or content-based recommendation.
- Personalized explanations for recommendations.
- Production authentication, authorization, or user account management.
- Distributed streaming pipelines.
- Automated dataset downloading.

## Expected Final Input and Output

The expected final input is a normalized rating dataset containing user identifiers, movie identifiers, ratings, and dates.

The expected final output is a ranked Top-K recommendation list per user, stored as text records that can be evaluated offline or read by an optional demo application.

## Main Limitations

- Cold start: new users and new movies may not have enough ratings for reliable recommendations.
- Sparse ratings: many users rate only a small fraction of available movies.
- Popularity bias: popular movies may dominate similarity and recommendation results.
- Batch-processing latency: recommendations are refreshed after batch jobs, not immediately after each rating.
- Item-pair explosion: generating co-rated item pairs can become expensive for users with long histories.
