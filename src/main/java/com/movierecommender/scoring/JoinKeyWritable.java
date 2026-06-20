package com.movierecommender.scoring;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.WritableComparable;

/** Sort key for reduce-side scoring join grouped by source movie. */
public class JoinKeyWritable implements WritableComparable<JoinKeyWritable> {
    public static final int TYPE_SIMILARITY = 0;
    public static final int TYPE_RATING = 1;

    private long sourceMovieId;
    private int recordType;
    private long secondaryId;

    public JoinKeyWritable() {}

    public JoinKeyWritable(long sourceMovieId, int recordType, long secondaryId) {
        set(sourceMovieId, recordType, secondaryId);
    }

    public long getSourceMovieId() {
        return sourceMovieId;
    }

    public int getRecordType() {
        return recordType;
    }

    public long getSecondaryId() {
        return secondaryId;
    }

    public void set(long sourceMovieId, int recordType, long secondaryId) {
        validate(sourceMovieId, recordType, secondaryId);
        this.sourceMovieId = sourceMovieId;
        this.recordType = recordType;
        this.secondaryId = secondaryId;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(sourceMovieId);
        output.writeInt(recordType);
        output.writeLong(secondaryId);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readSourceMovieId = input.readLong();
        int readRecordType = input.readInt();
        long readSecondaryId = input.readLong();
        try {
            set(readSourceMovieId, readRecordType, readSecondaryId);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public int compareTo(JoinKeyWritable other) {
        int sourceComparison = Long.compare(sourceMovieId, other.sourceMovieId);
        if (sourceComparison != 0) {
            return sourceComparison;
        }
        int typeComparison = Integer.compare(recordType, other.recordType);
        if (typeComparison != 0) {
            return typeComparison;
        }
        return Long.compare(secondaryId, other.secondaryId);
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof JoinKeyWritable that)) {
            return false;
        }
        return sourceMovieId == that.sourceMovieId
                && recordType == that.recordType
                && secondaryId == that.secondaryId;
    }

    @Override
    public int hashCode() {
        return Objects.hash(sourceMovieId, recordType, secondaryId);
    }

    @Override
    public String toString() {
        return sourceMovieId + "," + recordType + "," + secondaryId;
    }

    private static void validate(long sourceMovieId, int recordType, long secondaryId) {
        if (sourceMovieId <= 0L) {
            throw new IllegalArgumentException("sourceMovieId must be positive.");
        }
        if (recordType != TYPE_SIMILARITY && recordType != TYPE_RATING) {
            throw new IllegalArgumentException("recordType must be TYPE_SIMILARITY or TYPE_RATING.");
        }
        if (secondaryId <= 0L) {
            throw new IllegalArgumentException("secondaryId must be positive.");
        }
    }
}
