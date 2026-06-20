package com.movierecommender.recommendation;

import java.util.regex.Pattern;

/** Immutable parsed representation of one raw user-candidate prediction row. */
public record RawPredictionRecord(long userId, long movieId, double score) {
    private static final Pattern POSITIVE_INTEGER = Pattern.compile("[1-9]\\d*");

    public RawPredictionRecord {
        validate(userId, movieId, score);
    }

    /** Parse and validate one raw prediction row. */
    public static RawPredictionRecord parse(String line) {
        return parse(line, "row");
    }

    /** Parse and validate one raw prediction row with context in validation errors. */
    public static RawPredictionRecord parse(String line, String context) {
        if (line == null) {
            throw invalid(context, "row must not be null.");
        }
        if (line.trim().isEmpty()) {
            throw invalid(context, "line must not be blank.");
        }

        String[] sections = line.split("\t", -1);
        if (sections.length != 2) {
            throw invalid(context, "expected exactly one tab between user/movie key and score.");
        }

        String[] keyFields = sections[0].split(",", -1);
        if (keyFields.length != 2) {
            throw invalid(context, "user/movie key must contain exactly two comma-separated fields.");
        }

        long userId = parsePositiveLong(keyFields[0].trim(), "userId", context);
        long movieId = parsePositiveLong(keyFields[1].trim(), "movieId", context);
        double score = parseScore(sections[1].trim(), context);

        return new RawPredictionRecord(userId, movieId, score);
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

    private static double parseScore(String text, String context) {
        final double parsed;
        try {
            parsed = Double.parseDouble(text);
        } catch (NumberFormatException exception) {
            throw invalid(context, "score must be a finite number from 1.0 through 5.0.");
        }
        if (!Double.isFinite(parsed) || parsed < 1.0d || parsed > 5.0d) {
            throw invalid(context, "score must be a finite number from 1.0 through 5.0.");
        }
        return parsed;
    }

    private static void validate(long userId, long movieId, double score) {
        if (userId <= 0 || movieId <= 0) {
            throw new ValidationException("userId and movieId must be positive integers.");
        }
        if (!Double.isFinite(score) || score < 1.0d || score > 5.0d) {
            throw new ValidationException("score must be a finite number from 1.0 through 5.0.");
        }
    }

    private static ValidationException invalid(String context, String message) {
        if (context == null || context.isBlank()) {
            return new ValidationException(message);
        }
        return new ValidationException(context + ": " + message);
    }

    /** Validation failure for malformed raw prediction input. */
    public static class ValidationException extends IllegalArgumentException {
        public ValidationException(String message) {
            super(message);
        }
    }
}
