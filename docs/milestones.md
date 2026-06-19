# Milestones

| Milestone | Objective | Expected Output | Acceptance Criteria |
| --- | --- | --- | --- |
| Milestone 0: Project initialization | Completed: create repository structure and architecture documentation. | Initial folders, documentation, `.gitignore`, and placeholders. | Completed with no implementation code and documented scope, architecture, milestones, data formats, and references. |
| Milestone 1: Netflix dataset preprocessing | Completed: convert raw Netflix-style records into normalized ratings. | Python preprocessing utility, tests, documentation, and tiny sample input. | Completed after unit tests passed; input parsing is tested, output format is documented, and large raw data remains untracked. |
| Milestone 2: Python Item-CF reference implementation | Completed: build a small deterministic reference algorithm for validation. | Python reference utility, tests, fixture data, neighbor output, recommendation output, and statistics output. | Completed after unit tests passed; results are reproducible and suitable for comparing future MapReduce job outputs. |
| Milestone 3: Maven and Hadoop environment | Next: add Java build configuration and local Hadoop execution plan. | Maven project files and environment notes. | Java build runs locally and Hadoop commands are documented without committing generated files. |
| Milestone 4: User-history MapReduce job | Group ratings by user. | User-history output records. | Job output matches documented format and reference expectations on fixtures. |
| Milestone 5: Item-pair statistics | Generate co-rated movie-pair statistics. | Pair count and rating-statistic records. | Pair generation is deterministic and tested on known user histories. |
| Milestone 6: Similarity and Top-L neighbors | Compute item-item similarity and retain strongest neighbors. | Similarity records with limited neighbors per movie. | Similarity scores and neighbor ordering match reference calculations. |
| Milestone 7: Recommendation score calculation | Predict candidate movie scores for users. | User-movie prediction records. | Predictions exclude malformed inputs and match reference outputs on fixtures. |
| Milestone 8: Watched-item filtering and Top-K | Remove watched items and rank recommendations. | Final Top-K recommendation records. | Watched movies are excluded and ranking is deterministic. |
| Milestone 9: Train/test split and evaluation | Evaluate recommendation quality on held-out ratings. | Evaluation metrics and reports. | Metrics are documented, reproducible, and calculated from versioned scripts. |
| Milestone 10: Hadoop scalability experiments | Measure performance across larger data sizes or cluster settings. | Experiment logs, summaries, and charts. | Experiments record inputs, configuration, runtime, and limitations. |
| Milestone 11: Optional demo | Display precomputed recommendations. | Simple demo that reads recommendation files. | Demo does not rerun Hadoop jobs for each request. |
| Milestone 12: Documentation and final delivery | Finalize report, setup notes, and delivery artifacts. | Complete documentation and final project report. | A reviewer can understand, build, run, and evaluate the project from documented steps. |
