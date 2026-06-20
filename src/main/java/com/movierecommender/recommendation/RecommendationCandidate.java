package com.movierecommender.recommendation;

import java.util.Comparator;
import java.util.Locale;

/** Immutable candidate movie score with deterministic final and worst-first ordering. */
public record RecommendationCandidate(long movieId, double score)
        implements Comparable<RecommendationCandidate> {
    public static final Comparator<RecommendationCandidate> FINAL_ORDER =
            Comparator.comparingDouble(RecommendationCandidate::score)
                    .reversed()
                    .thenComparingLong(RecommendationCandidate::movieId);

    public static final Comparator<RecommendationCandidate> WORST_FIRST =
            Comparator.comparingDouble(RecommendationCandidate::score)
                    .thenComparing(Comparator.comparingLong(RecommendationCandidate::movieId).reversed());

    public RecommendationCandidate {
        if (movieId <= 0L) {
            throw new IllegalArgumentException("movieId must be positive.");
        }
        if (!Double.isFinite(score)) {
            throw new IllegalArgumentException("score must be finite.");
        }
    }

    @Override
    public int compareTo(RecommendationCandidate other) {
        return FINAL_ORDER.compare(this, other);
    }

    public boolean isBetterThan(RecommendationCandidate other) {
        return FINAL_ORDER.compare(this, other) < 0;
    }

    public String formatScore() {
        return String.format(Locale.ROOT, "%.10f", score);
    }

    @Override
    public String toString() {
        return movieId + ":" + formatScore();
    }
}
