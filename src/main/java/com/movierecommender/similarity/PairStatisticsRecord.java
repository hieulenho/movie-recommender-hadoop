package com.movierecommender.similarity;

import java.util.regex.Pattern;

/** Immutable parsed representation of one item-pair statistics row. */
public record PairStatisticsRecord(
        long firstMovieId,
        long secondMovieId,
        long commonUsers,
        long sumXY,
        long sumX2,
        long sumY2) {
    private static final Pattern POSITIVE_INTEGER = Pattern.compile("[1-9]\\d*");

    public PairStatisticsRecord {
        if (firstMovieId <= 0 || secondMovieId <= 0) {
            throw new ValidationException("movie IDs must be positive integers.");
        }
        if (firstMovieId >= secondMovieId) {
            throw new ValidationException("firstMovieId must be less than secondMovieId.");
        }
        if (commonUsers < 1) {
            throw new ValidationException("commonUsers must be at least 1.");
        }
        if (sumXY <= 0 || sumX2 <= 0 || sumY2 <= 0) {
            throw new ValidationException("sumXY, sumX2, and sumY2 must be positive.");
        }
    }

    /** Parse and validate one item-pair statistics row. */
    public static PairStatisticsRecord parse(String line) {
        return parse(line, "row");
    }

    /** Parse and validate one item-pair statistics row with context in validation errors. */
    public static PairStatisticsRecord parse(String line, String context) {
        if (line == null) {
            throw invalid(context, "row must not be null.");
        }
        if (line.trim().isEmpty()) {
            throw invalid(context, "line must not be blank.");
        }

        String[] sections = line.split("\t", -1);
        if (sections.length != 2) {
            throw invalid(context, "expected exactly one tab between movie pair and statistics.");
        }

        String[] pairFields = sections[0].split(",", -1);
        if (pairFields.length != 2) {
            throw invalid(context, "movie pair must contain exactly two comma-separated IDs.");
        }
        long firstMovieId = parsePositiveLong(pairFields[0].trim(), "firstMovieId", context);
        long secondMovieId = parsePositiveLong(pairFields[1].trim(), "secondMovieId", context);
        if (firstMovieId >= secondMovieId) {
            throw invalid(context, "firstMovieId must be less than secondMovieId.");
        }

        String[] statsFields = sections[1].split(",", -1);
        if (statsFields.length != 4) {
            throw invalid(context, "statistics must contain exactly four comma-separated fields.");
        }
        long commonUsers = parsePositiveLong(statsFields[0].trim(), "commonUsers", context);
        long sumXY = parsePositiveLong(statsFields[1].trim(), "sumXY", context);
        long sumX2 = parsePositiveLong(statsFields[2].trim(), "sumX2", context);
        long sumY2 = parsePositiveLong(statsFields[3].trim(), "sumY2", context);

        return new PairStatisticsRecord(firstMovieId, secondMovieId, commonUsers, sumXY, sumX2, sumY2);
    }

    private static long parsePositiveLong(String text, String fieldName, String context) {
        if (!POSITIVE_INTEGER.matcher(text).matches()) {
            throw invalid(context, fieldName + " must be a positive integer.");
        }
        try {
            return Long.parseLong(text);
        } catch (NumberFormatException exception) {
            throw invalid(context, fieldName + " must fit in a signed 64-bit integer.");
        }
    }

    private static ValidationException invalid(String context, String message) {
        if (context == null || context.isBlank()) {
            return new ValidationException(message);
        }
        return new ValidationException(context + ": " + message);
    }

    /** Validation failure for malformed item-pair statistics input. */
    public static class ValidationException extends IllegalArgumentException {
        public ValidationException(String message) {
            super(message);
        }
    }
}
