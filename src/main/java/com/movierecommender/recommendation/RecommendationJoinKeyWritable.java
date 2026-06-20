package com.movierecommender.recommendation;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.WritableComparable;

/** Sort key for Top-K recommendation anti-join grouped by user ID. */
public class RecommendationJoinKeyWritable implements WritableComparable<RecommendationJoinKeyWritable> {
    public static final int TYPE_HISTORY = 0;
    public static final int TYPE_PREDICTION = 1;

    private long userId;
    private int recordType;
    private long secondaryId;

    public RecommendationJoinKeyWritable() {}

    public RecommendationJoinKeyWritable(long userId, int recordType, long secondaryId) {
        set(userId, recordType, secondaryId);
    }

    public long getUserId() {
        return userId;
    }

    public int getRecordType() {
        return recordType;
    }

    public long getSecondaryId() {
        return secondaryId;
    }

    public void set(long userId, int recordType, long secondaryId) {
        validate(userId, recordType, secondaryId);
        this.userId = userId;
        this.recordType = recordType;
        this.secondaryId = secondaryId;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(userId);
        output.writeInt(recordType);
        output.writeLong(secondaryId);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        long readUserId = input.readLong();
        int readRecordType = input.readInt();
        long readSecondaryId = input.readLong();
        try {
            set(readUserId, readRecordType, readSecondaryId);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public int compareTo(RecommendationJoinKeyWritable other) {
        int userComparison = Long.compare(userId, other.userId);
        if (userComparison != 0) {
            return userComparison;
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
        if (!(other instanceof RecommendationJoinKeyWritable that)) {
            return false;
        }
        return userId == that.userId && recordType == that.recordType && secondaryId == that.secondaryId;
    }

    @Override
    public int hashCode() {
        return Objects.hash(userId, recordType, secondaryId);
    }

    @Override
    public String toString() {
        return userId + "," + recordType + "," + secondaryId;
    }

    private static void validate(long userId, int recordType, long secondaryId) {
        if (userId <= 0L) {
            throw new IllegalArgumentException("userId must be positive.");
        }
        if (recordType != TYPE_HISTORY && recordType != TYPE_PREDICTION) {
            throw new IllegalArgumentException("recordType must be TYPE_HISTORY or TYPE_PREDICTION.");
        }
        if (secondaryId < 0L) {
            throw new IllegalArgumentException("secondaryId must not be negative.");
        }
        if (recordType == TYPE_PREDICTION && secondaryId == 0L) {
            throw new IllegalArgumentException("prediction secondaryId must be positive.");
        }
    }
}
