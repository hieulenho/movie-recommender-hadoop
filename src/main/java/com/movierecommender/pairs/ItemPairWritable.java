package com.movierecommender.pairs;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.WritableComparable;

/** Numeric Hadoop key for an unordered movie pair where firstMovieId < secondMovieId. */
public class ItemPairWritable implements WritableComparable<ItemPairWritable> {
    private long firstMovieId;
    private long secondMovieId;

    public ItemPairWritable() {}

    public ItemPairWritable(long firstMovieId, long secondMovieId) {
        set(firstMovieId, secondMovieId);
    }

    public long getFirstMovieId() {
        return firstMovieId;
    }

    public long getSecondMovieId() {
        return secondMovieId;
    }

    public void set(long firstMovieId, long secondMovieId) {
        validate(firstMovieId, secondMovieId);
        this.firstMovieId = firstMovieId;
        this.secondMovieId = secondMovieId;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(firstMovieId);
        output.writeLong(secondMovieId);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readFirst = input.readLong();
        long readSecond = input.readLong();
        try {
            set(readFirst, readSecond);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public int compareTo(ItemPairWritable other) {
        int firstComparison = Long.compare(firstMovieId, other.firstMovieId);
        if (firstComparison != 0) {
            return firstComparison;
        }
        return Long.compare(secondMovieId, other.secondMovieId);
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof ItemPairWritable that)) {
            return false;
        }
        return firstMovieId == that.firstMovieId && secondMovieId == that.secondMovieId;
    }

    @Override
    public int hashCode() {
        return Objects.hash(firstMovieId, secondMovieId);
    }

    @Override
    public String toString() {
        return firstMovieId + "," + secondMovieId;
    }

    private static void validate(long firstMovieId, long secondMovieId) {
        if (firstMovieId <= 0 || secondMovieId <= 0) {
            throw new IllegalArgumentException("movie IDs must be positive.");
        }
        if (firstMovieId >= secondMovieId) {
            throw new IllegalArgumentException("firstMovieId must be less than secondMovieId.");
        }
    }
}
