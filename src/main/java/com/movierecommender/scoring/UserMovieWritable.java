package com.movierecommender.scoring;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.WritableComparable;

/** Numeric Hadoop key for one user-candidate movie score. */
public class UserMovieWritable implements WritableComparable<UserMovieWritable> {
    private long userId;
    private long movieId;

    public UserMovieWritable() {}

    public UserMovieWritable(long userId, long movieId) {
        set(userId, movieId);
    }

    public UserMovieWritable(UserMovieWritable other) {
        this(other.userId, other.movieId);
    }

    public long getUserId() {
        return userId;
    }

    public long getMovieId() {
        return movieId;
    }

    public void set(long userId, long movieId) {
        validate(userId, movieId);
        this.userId = userId;
        this.movieId = movieId;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(userId);
        output.writeLong(movieId);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readUserId = input.readLong();
        long readMovieId = input.readLong();
        try {
            set(readUserId, readMovieId);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public int compareTo(UserMovieWritable other) {
        int userComparison = Long.compare(userId, other.userId);
        if (userComparison != 0) {
            return userComparison;
        }
        return Long.compare(movieId, other.movieId);
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof UserMovieWritable that)) {
            return false;
        }
        return userId == that.userId && movieId == that.movieId;
    }

    @Override
    public int hashCode() {
        return Objects.hash(userId, movieId);
    }

    @Override
    public String toString() {
        return userId + "," + movieId;
    }

    private static void validate(long userId, long movieId) {
        if (userId <= 0 || movieId <= 0) {
            throw new IllegalArgumentException("userId and movieId must be positive.");
        }
    }
}
