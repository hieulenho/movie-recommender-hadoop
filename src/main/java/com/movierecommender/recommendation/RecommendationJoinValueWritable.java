package com.movierecommender.recommendation;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Arrays;
import java.util.Objects;
import org.apache.hadoop.io.Writable;

/** Tagged join value carrying either one user history or one raw prediction. */
public class RecommendationJoinValueWritable implements Writable {
    private int recordType;
    private long[] watchedMovieIds = new long[0];
    private int[] watchedRatings = new int[0];
    private long movieId;
    private double score;

    public RecommendationJoinValueWritable() {}

    public static RecommendationJoinValueWritable forHistory(long[] watchedMovieIds, int[] watchedRatings) {
        RecommendationJoinValueWritable writable = new RecommendationJoinValueWritable();
        writable.setHistory(watchedMovieIds, watchedRatings);
        return writable;
    }

    public static RecommendationJoinValueWritable forPrediction(long movieId, double score) {
        RecommendationJoinValueWritable writable = new RecommendationJoinValueWritable();
        writable.setPrediction(movieId, score);
        return writable;
    }

    public RecommendationJoinValueWritable(RecommendationJoinValueWritable other) {
        this.recordType = other.recordType;
        this.watchedMovieIds = other.watchedMovieIds.clone();
        this.watchedRatings = other.watchedRatings.clone();
        this.movieId = other.movieId;
        this.score = other.score;
    }

    public boolean isHistory() {
        return recordType == RecommendationJoinKeyWritable.TYPE_HISTORY;
    }

    public boolean isPrediction() {
        return recordType == RecommendationJoinKeyWritable.TYPE_PREDICTION;
    }

    public int getRecordType() {
        return recordType;
    }

    public long[] getWatchedMovieIds() {
        return watchedMovieIds.clone();
    }

    public int[] getWatchedRatings() {
        return watchedRatings.clone();
    }

    public long getMovieId() {
        return movieId;
    }

    public double getScore() {
        return score;
    }

    public void setHistory(long[] watchedMovieIds, int[] watchedRatings) {
        validateHistory(watchedMovieIds, watchedRatings);
        this.recordType = RecommendationJoinKeyWritable.TYPE_HISTORY;
        this.watchedMovieIds = watchedMovieIds.clone();
        this.watchedRatings = watchedRatings.clone();
        this.movieId = 0L;
        this.score = 0.0d;
    }

    public void setPrediction(long movieId, double score) {
        validatePrediction(movieId, score);
        this.recordType = RecommendationJoinKeyWritable.TYPE_PREDICTION;
        this.watchedMovieIds = new long[0];
        this.watchedRatings = new int[0];
        this.movieId = movieId;
        this.score = score;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeInt(recordType);
        output.writeInt(watchedMovieIds.length);
        for (long watchedMovieId : watchedMovieIds) {
            output.writeLong(watchedMovieId);
        }
        output.writeInt(watchedRatings.length);
        for (int watchedRating : watchedRatings) {
            output.writeInt(watchedRating);
        }
        output.writeLong(movieId);
        output.writeDouble(score);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        int readRecordType = input.readInt();
        int watchedCount = input.readInt();
        if (watchedCount < 0) {
            throw new IOException("watched movie count must not be negative.");
        }
        long[] readWatchedMovieIds = new long[watchedCount];
        for (int index = 0; index < watchedCount; index++) {
            readWatchedMovieIds[index] = input.readLong();
        }
        int ratingCount = input.readInt();
        if (ratingCount < 0) {
            throw new IOException("watched rating count must not be negative.");
        }
        int[] readWatchedRatings = new int[ratingCount];
        for (int index = 0; index < ratingCount; index++) {
            readWatchedRatings[index] = input.readInt();
        }
        long readMovieId = input.readLong();
        double readScore = input.readDouble();
        try {
            if (readRecordType == RecommendationJoinKeyWritable.TYPE_HISTORY) {
                setHistory(readWatchedMovieIds, readWatchedRatings);
            } else if (readRecordType == RecommendationJoinKeyWritable.TYPE_PREDICTION) {
                setPrediction(readMovieId, readScore);
            } else {
                throw new IllegalArgumentException("recordType must be TYPE_HISTORY or TYPE_PREDICTION.");
            }
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof RecommendationJoinValueWritable that)) {
            return false;
        }
        return recordType == that.recordType
                && movieId == that.movieId
                && Double.compare(score, that.score) == 0
                && Arrays.equals(watchedMovieIds, that.watchedMovieIds)
                && Arrays.equals(watchedRatings, that.watchedRatings);
    }

    @Override
    public int hashCode() {
        int result = Objects.hash(recordType, movieId, score);
        result = 31 * result + Arrays.hashCode(watchedMovieIds);
        result = 31 * result + Arrays.hashCode(watchedRatings);
        return result;
    }

    @Override
    public String toString() {
        if (isHistory()) {
            return "history:" + Arrays.toString(watchedMovieIds) + ":" + Arrays.toString(watchedRatings);
        }
        if (isPrediction()) {
            return "prediction:" + movieId + "," + Double.toString(score);
        }
        return "unknown:" + recordType;
    }

    private static void validateHistory(long[] watchedMovieIds, int[] watchedRatings) {
        if (watchedMovieIds == null || watchedRatings == null || watchedMovieIds.length == 0) {
            throw new IllegalArgumentException("watched history must contain at least one movie.");
        }
        if (watchedMovieIds.length != watchedRatings.length) {
            throw new IllegalArgumentException("watched movie IDs and ratings must have equal length.");
        }
        long previous = 0L;
        for (int index = 0; index < watchedMovieIds.length; index++) {
            long watchedMovieId = watchedMovieIds[index];
            if (watchedMovieId <= 0L) {
                throw new IllegalArgumentException("watched movie IDs must be positive.");
            }
            int watchedRating = watchedRatings[index];
            if (watchedRating < 1 || watchedRating > 5) {
                throw new IllegalArgumentException("watched ratings must be from 1 through 5.");
            }
            if (watchedMovieId <= previous) {
                throw new IllegalArgumentException("watched movie IDs must be sorted and unique.");
            }
            previous = watchedMovieId;
        }
    }

    private static void validatePrediction(long movieId, double score) {
        if (movieId <= 0L) {
            throw new IllegalArgumentException("movieId must be positive.");
        }
        if (!Double.isFinite(score) || score < 1.0d || score > 5.0d) {
            throw new IllegalArgumentException("score must be a finite number from 1.0 through 5.0.");
        }
    }
}
