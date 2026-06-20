package com.movierecommender.scoring;

import java.util.regex.Pattern;

/** Immutable parsed representation of one directed retained similarity row. */
public record DirectedSimilarityRecord(
        long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {
    private static final Pattern POSITIVE_INTEGER = Pattern.compile("[1-9]\\d*");

    public DirectedSimilarityRecord {
        validate(sourceMovieId, neighborMovieId, similarity, commonUsers);
    }

    /** Parse and validate one directed similarity row. */
    public static DirectedSimilarityRecord parse(String line) {
        return parse(line, "row");
    }

    /** Parse and validate one directed similarity row with context in validation errors. */
    public static DirectedSimilarityRecord parse(String line, String context) {
        if (line == null) {
            throw invalid(context, "row must not be null.");
        }
        if (line.trim().isEmpty()) {
            throw invalid(context, "line must not be blank.");
        }

        String[] sections = line.split("\t", -1);
        if (sections.length != 2) {
            throw invalid(context, "expected exactly one tab between directed pair and similarity fields.");
        }

        String[] pairFields = sections[0].split(",", -1);
        if (pairFields.length != 2) {
            throw invalid(context, "directed pair must contain exactly two comma-separated movie IDs.");
        }
        long sourceMovieId = parsePositiveLong(pairFields[0].trim(), "sourceMovieId", context);
        long neighborMovieId = parsePositiveLong(pairFields[1].trim(), "neighborMovieId", context);
        if (sourceMovieId == neighborMovieId) {
            throw invalid(context, "sourceMovieId and neighborMovieId must differ.");
        }

        String[] similarityFields = sections[1].split(",", -1);
        if (similarityFields.length != 2) {
            throw invalid(context, "similarity fields must contain exactly similarity and commonUsers.");
        }
        double similarity = parseSimilarity(similarityFields[0].trim(), context);
        long commonUsers = parsePositiveLong(similarityFields[1].trim(), "commonUsers", context);

        return new DirectedSimilarityRecord(sourceMovieId, neighborMovieId, similarity, commonUsers);
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

    private static double parseSimilarity(String text, String context) {
        final double parsed;
        try {
            parsed = Double.parseDouble(text);
        } catch (NumberFormatException exception) {
            throw invalid(context, "similarity must be a finite number greater than 0.0 and at most 1.0.");
        }
        if (!Double.isFinite(parsed) || parsed <= 0.0d || parsed > 1.0d) {
            throw invalid(context, "similarity must be a finite number greater than 0.0 and at most 1.0.");
        }
        return parsed;
    }

    private static void validate(long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {
        if (sourceMovieId <= 0 || neighborMovieId <= 0) {
            throw new ValidationException("movie IDs must be positive integers.");
        }
        if (sourceMovieId == neighborMovieId) {
            throw new ValidationException("sourceMovieId and neighborMovieId must differ.");
        }
        if (!Double.isFinite(similarity) || similarity <= 0.0d || similarity > 1.0d) {
            throw new ValidationException("similarity must be a finite number greater than 0.0 and at most 1.0.");
        }
        if (commonUsers < 1) {
            throw new ValidationException("commonUsers must be at least 1.");
        }
    }

    private static ValidationException invalid(String context, String message) {
        if (context == null || context.isBlank()) {
            return new ValidationException(message);
        }
        return new ValidationException(context + ": " + message);
    }

    /** Validation failure for malformed directed similarity input. */
    public static class ValidationException extends IllegalArgumentException {
        public ValidationException(String message) {
            super(message);
        }
    }
}
