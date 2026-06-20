package com.movierecommender.pairs;

import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;
import java.util.regex.Pattern;

/** Immutable representation of one validated user-history input row. */
public record UserHistoryRecord(long userId, List<ItemRating> ratings) {
    private static final Pattern POSITIVE_INTEGER = Pattern.compile("[1-9]\\d*");

    public UserHistoryRecord {
        if (userId <= 0) {
            throw new ValidationException("userId must be a positive integer.");
        }
        if (ratings == null || ratings.isEmpty()) {
            throw new ValidationException("history must contain at least one movie entry.");
        }
        ratings = List.copyOf(ratings);
    }

    /** Parse and validate one user-history row. */
    public static UserHistoryRecord parse(String line) {
        return parse(line, "row");
    }

    /** Parse and validate one user-history row with context in validation errors. */
    public static UserHistoryRecord parse(String line, String context) {
        if (line == null) {
            throw invalid(context, "row must not be null.");
        }
        if (line.trim().isEmpty()) {
            throw invalid(context, "line must not be empty.");
        }

        String[] sections = line.split("\t", -1);
        if (sections.length != 2) {
            throw invalid(context, "expected exactly one tab between user ID and history.");
        }

        long parsedUserId = parsePositiveLong(sections[0].trim(), "userId", context);
        String historyText = sections[1].trim();
        if (historyText.isEmpty()) {
            throw invalid(context, "history must contain at least one movie entry.");
        }

        TreeMap<Long, ItemRating> ratingsByMovie = new TreeMap<>();
        for (String rawEntry : historyText.split(",", -1)) {
            String entry = rawEntry.trim();
            if (entry.isEmpty()) {
                throw invalid(context, "movie-rating entry must not be empty.");
            }
            String[] fields = entry.split(":", -1);
            if (fields.length != 2) {
                throw invalid(context, "movie-rating entry must contain exactly one colon.");
            }

            long movieId = parsePositiveLong(fields[0].trim(), "movieId", context);
            int rating = parseRating(fields[1].trim(), context);
            if (ratingsByMovie.containsKey(movieId)) {
                throw invalid(context, "duplicate movieId in user history: " + movieId + ".");
            }
            ratingsByMovie.put(movieId, new ItemRating(movieId, rating));
        }

        return new UserHistoryRecord(parsedUserId, new ArrayList<>(ratingsByMovie.values()));
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

    private static ValidationException invalid(String context, String message) {
        if (context == null || context.isBlank()) {
            return new ValidationException(message);
        }
        return new ValidationException(context + ": " + message);
    }

    /** Immutable movie-rating entry sorted by movie ID in parsed histories. */
    public record ItemRating(long movieId, int rating) {
        public ItemRating {
            if (movieId <= 0) {
                throw new ValidationException("movieId must be a positive integer.");
            }
            if (rating < 1 || rating > 5) {
                throw new ValidationException("rating must be an integer from 1 through 5.");
            }
        }
    }

    /** Validation failure for malformed user-history input. */
    public static class ValidationException extends IllegalArgumentException {
        public ValidationException(String message) {
            super(message);
        }
    }
}
