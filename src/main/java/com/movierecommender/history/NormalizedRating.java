package com.movierecommender.history;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.regex.Pattern;

/** Immutable representation of one validated normalized rating CSV row. */
public record NormalizedRating(long userId, long movieId, int rating, LocalDate date) {
    public static final String HEADER = "userId,movieId,rating,date";

    private static final Pattern POSITIVE_INTEGER = Pattern.compile("[1-9]\\d*");
    private static final Pattern ISO_DATE = Pattern.compile("\\d{4}-\\d{2}-\\d{2}");

    public NormalizedRating {
        if (userId <= 0) {
            throw new ValidationException("userId must be a positive integer.");
        }
        if (movieId <= 0) {
            throw new ValidationException("movieId must be a positive integer.");
        }
        if (rating < 1 || rating > 5) {
            throw new ValidationException("rating must be an integer from 1 through 5.");
        }
        if (date == null) {
            throw new ValidationException("date must be a valid YYYY-MM-DD date.");
        }
        if (date.getYear() < 1) {
            throw new ValidationException("date must be a valid YYYY-MM-DD date.");
        }
    }

    /** Return true only for the exact normalized CSV header line. */
    public static boolean isExactHeader(String line) {
        return HEADER.equals(line);
    }

    /** Parse a normalized rating data row without Hadoop-specific behavior. */
    public static NormalizedRating parse(String line) {
        return parse(line, "row");
    }

    /** Parse a normalized rating data row and prefix validation errors with context. */
    public static NormalizedRating parse(String line, String context) {
        if (line == null) {
            throw invalid(context, "row must not be null.");
        }
        if (isExactHeader(line)) {
            throw invalid(context, "CSV header is not a rating data row.");
        }
        if (line.trim().isEmpty()) {
            throw invalid(context, "data line must not be empty.");
        }

        String[] rawFields = line.split(",", -1);
        if (rawFields.length != 4) {
            throw invalid(context, "expected exactly 4 comma-separated fields.");
        }

        String userText = rawFields[0].trim();
        String movieText = rawFields[1].trim();
        String ratingText = rawFields[2].trim();
        String dateText = rawFields[3].trim();

        long parsedUserId = parsePositiveLong(userText, "userId", context);
        long parsedMovieId = parsePositiveLong(movieText, "movieId", context);
        int parsedRating = parseRating(ratingText, context);
        LocalDate parsedDate = parseIsoDate(dateText, context);
        return new NormalizedRating(parsedUserId, parsedMovieId, parsedRating, parsedDate);
    }

    /** Return the date in the deterministic normalized CSV representation. */
    public String dateText() {
        return date.toString();
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

    private static int parseRating(String text, String context) {
        final int parsedRating;
        try {
            parsedRating = Integer.parseInt(text);
        } catch (NumberFormatException exception) {
            throw invalid(context, "rating must be an integer from 1 through 5.");
        }
        if (parsedRating < 1 || parsedRating > 5) {
            throw invalid(context, "rating must be an integer from 1 through 5.");
        }
        return parsedRating;
    }

    private static LocalDate parseIsoDate(String text, String context) {
        if (!ISO_DATE.matcher(text).matches()) {
            throw invalid(context, "date must be a valid YYYY-MM-DD date.");
        }
        try {
            LocalDate parsedDate = LocalDate.parse(text);
            if (parsedDate.getYear() < 1 || !parsedDate.toString().equals(text)) {
                throw invalid(context, "date must be a valid YYYY-MM-DD date.");
            }
            return parsedDate;
        } catch (DateTimeParseException exception) {
            throw invalid(context, "date must be a valid YYYY-MM-DD date.");
        }
    }

    private static ValidationException invalid(String context, String message) {
        if (context == null || context.isBlank()) {
            return new ValidationException(message);
        }
        return new ValidationException(context + ": " + message);
    }

    /** Validation failure for malformed normalized rating input. */
    public static class ValidationException extends IllegalArgumentException {
        public ValidationException(String message) {
            super(message);
        }
    }
}
