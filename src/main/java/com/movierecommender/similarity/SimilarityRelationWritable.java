package com.movierecommender.similarity;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Locale;
import java.util.Objects;
import org.apache.hadoop.io.WritableComparable;

/** Directed similarity relation ordered by source, similarity descending, then neighbor ID. */
public class SimilarityRelationWritable implements WritableComparable<SimilarityRelationWritable> {
    private long sourceMovieId;
    private long neighborMovieId;
    private double similarity;
    private long commonUsers;

    public SimilarityRelationWritable() {}

    public SimilarityRelationWritable(
            long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {
        set(sourceMovieId, neighborMovieId, similarity, commonUsers);
    }

    public SimilarityRelationWritable(SimilarityRelationWritable other) {
        this(other.sourceMovieId, other.neighborMovieId, other.similarity, other.commonUsers);
    }

    public long getSourceMovieId() {
        return sourceMovieId;
    }

    public long getNeighborMovieId() {
        return neighborMovieId;
    }

    public double getSimilarity() {
        return similarity;
    }

    public long getCommonUsers() {
        return commonUsers;
    }

    public void set(long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {
        validate(sourceMovieId, neighborMovieId, similarity, commonUsers);
        this.sourceMovieId = sourceMovieId;
        this.neighborMovieId = neighborMovieId;
        this.similarity = similarity;
        this.commonUsers = commonUsers;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(sourceMovieId);
        output.writeLong(neighborMovieId);
        output.writeDouble(similarity);
        output.writeLong(commonUsers);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readSource = input.readLong();
        long readNeighbor = input.readLong();
        double readSimilarity = input.readDouble();
        long readCommonUsers = input.readLong();
        try {
            set(readSource, readNeighbor, readSimilarity, readCommonUsers);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public int compareTo(SimilarityRelationWritable other) {
        int sourceComparison = Long.compare(sourceMovieId, other.sourceMovieId);
        if (sourceComparison != 0) {
            return sourceComparison;
        }
        int similarityComparison = Double.compare(other.similarity, similarity);
        if (similarityComparison != 0) {
            return similarityComparison;
        }
        return Long.compare(neighborMovieId, other.neighborMovieId);
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof SimilarityRelationWritable that)) {
            return false;
        }
        return sourceMovieId == that.sourceMovieId
                && neighborMovieId == that.neighborMovieId
                && Double.compare(similarity, that.similarity) == 0
                && commonUsers == that.commonUsers;
    }

    @Override
    public int hashCode() {
        return Objects.hash(sourceMovieId, neighborMovieId, similarity, commonUsers);
    }

    @Override
    public String toString() {
        return sourceMovieId
                + ","
                + neighborMovieId
                + "\t"
                + formatSimilarity(similarity)
                + ","
                + commonUsers;
    }

    public static String formatSimilarity(double value) {
        return String.format(Locale.ROOT, "%.10f", value);
    }

    private static void validate(
            long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {
        if (sourceMovieId <= 0 || neighborMovieId <= 0) {
            throw new IllegalArgumentException("movie IDs must be positive.");
        }
        if (sourceMovieId == neighborMovieId) {
            throw new IllegalArgumentException("sourceMovieId and neighborMovieId must differ.");
        }
        if (!Double.isFinite(similarity) || similarity < 0.0d) {
            throw new IllegalArgumentException("similarity must be a finite non-negative number.");
        }
        if (commonUsers < 1) {
            throw new IllegalArgumentException("commonUsers must be at least 1.");
        }
    }
}
