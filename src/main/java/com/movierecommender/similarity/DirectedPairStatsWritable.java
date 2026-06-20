package com.movierecommender.similarity;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.Writable;

/** Directed co-occurrence candidate used before row-normalized similarity is calculated. */
public class DirectedPairStatsWritable implements Writable {
    private long sourceMovieId;
    private long neighborMovieId;
    private long commonUsers;

    public DirectedPairStatsWritable() {}

    public DirectedPairStatsWritable(long sourceMovieId, long neighborMovieId, long commonUsers) {
        set(sourceMovieId, neighborMovieId, commonUsers);
    }

    public DirectedPairStatsWritable(DirectedPairStatsWritable other) {
        this(other.sourceMovieId, other.neighborMovieId, other.commonUsers);
    }

    public long getSourceMovieId() {
        return sourceMovieId;
    }

    public long getNeighborMovieId() {
        return neighborMovieId;
    }

    public long getCommonUsers() {
        return commonUsers;
    }

    public void set(long sourceMovieId, long neighborMovieId, long commonUsers) {
        validate(sourceMovieId, neighborMovieId, commonUsers);
        this.sourceMovieId = sourceMovieId;
        this.neighborMovieId = neighborMovieId;
        this.commonUsers = commonUsers;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(sourceMovieId);
        output.writeLong(neighborMovieId);
        output.writeLong(commonUsers);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readSource = input.readLong();
        long readNeighbor = input.readLong();
        long readCommonUsers = input.readLong();
        try {
            set(readSource, readNeighbor, readCommonUsers);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof DirectedPairStatsWritable that)) {
            return false;
        }
        return sourceMovieId == that.sourceMovieId
                && neighborMovieId == that.neighborMovieId
                && commonUsers == that.commonUsers;
    }

    @Override
    public int hashCode() {
        return Objects.hash(sourceMovieId, neighborMovieId, commonUsers);
    }

    @Override
    public String toString() {
        return sourceMovieId + "," + neighborMovieId + "," + commonUsers;
    }

    private static void validate(long sourceMovieId, long neighborMovieId, long commonUsers) {
        if (sourceMovieId <= 0 || neighborMovieId <= 0) {
            throw new IllegalArgumentException("movie IDs must be positive.");
        }
        if (sourceMovieId == neighborMovieId) {
            throw new IllegalArgumentException("sourceMovieId and neighborMovieId must differ.");
        }
        if (commonUsers < 1) {
            throw new IllegalArgumentException("commonUsers must be at least 1.");
        }
    }
}
