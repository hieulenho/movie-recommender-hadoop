package com.movierecommender.scoring;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.Objects;
import org.apache.hadoop.io.Writable;

/** Tagged join value for either a retained similarity neighbor or one user rating. */
public class JoinValueWritable implements Writable {
    private int recordType;
    private long neighborMovieId;
    private double similarity;
    private long commonUsers;
    private long userId;
    private int rating;

    public JoinValueWritable() {}

    public static JoinValueWritable forSimilarity(long neighborMovieId, double similarity, long commonUsers) {
        JoinValueWritable writable = new JoinValueWritable();
        writable.setSimilarity(neighborMovieId, similarity, commonUsers);
        return writable;
    }

    public static JoinValueWritable forRating(long userId, int rating) {
        JoinValueWritable writable = new JoinValueWritable();
        writable.setRating(userId, rating);
        return writable;
    }

    public JoinValueWritable(JoinValueWritable other) {
        this.recordType = other.recordType;
        this.neighborMovieId = other.neighborMovieId;
        this.similarity = other.similarity;
        this.commonUsers = other.commonUsers;
        this.userId = other.userId;
        this.rating = other.rating;
    }

    public boolean isSimilarity() {
        return recordType == JoinKeyWritable.TYPE_SIMILARITY;
    }

    public boolean isRating() {
        return recordType == JoinKeyWritable.TYPE_RATING;
    }

    public int getRecordType() {
        return recordType;
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

    public long getUserId() {
        return userId;
    }

    public int getRating() {
        return rating;
    }

    public void setSimilarity(long neighborMovieId, double similarity, long commonUsers) {
        validateSimilarity(neighborMovieId, similarity, commonUsers);
        this.recordType = JoinKeyWritable.TYPE_SIMILARITY;
        this.neighborMovieId = neighborMovieId;
        this.similarity = similarity;
        this.commonUsers = commonUsers;
        this.userId = 0L;
        this.rating = 0;
    }

    public void setRating(long userId, int rating) {
        validateRating(userId, rating);
        this.recordType = JoinKeyWritable.TYPE_RATING;
        this.neighborMovieId = 0L;
        this.similarity = 0.0d;
        this.commonUsers = 0L;
        this.userId = userId;
        this.rating = rating;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeInt(recordType);
        output.writeLong(neighborMovieId);
        output.writeDouble(similarity);
        output.writeLong(commonUsers);
        output.writeLong(userId);
        output.writeInt(rating);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        int readRecordType = input.readInt();
        long readNeighborMovieId = input.readLong();
        double readSimilarity = input.readDouble();
        long readCommonUsers = input.readLong();
        long readUserId = input.readLong();
        int readRating = input.readInt();
        try {
            if (readRecordType == JoinKeyWritable.TYPE_SIMILARITY) {
                setSimilarity(readNeighborMovieId, readSimilarity, readCommonUsers);
            } else if (readRecordType == JoinKeyWritable.TYPE_RATING) {
                setRating(readUserId, readRating);
            } else {
                throw new IllegalArgumentException("recordType must be TYPE_SIMILARITY or TYPE_RATING.");
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
        if (!(other instanceof JoinValueWritable that)) {
            return false;
        }
        return recordType == that.recordType
                && neighborMovieId == that.neighborMovieId
                && Double.compare(similarity, that.similarity) == 0
                && commonUsers == that.commonUsers
                && userId == that.userId
                && rating == that.rating;
    }

    @Override
    public int hashCode() {
        return Objects.hash(recordType, neighborMovieId, similarity, commonUsers, userId, rating);
    }

    @Override
    public String toString() {
        if (isSimilarity()) {
            return "similarity:" + neighborMovieId + "," + Double.toString(similarity) + "," + commonUsers;
        }
        if (isRating()) {
            return "rating:" + userId + "," + rating;
        }
        return "unknown:" + recordType;
    }

    private static void validateSimilarity(long neighborMovieId, double similarity, long commonUsers) {
        if (neighborMovieId <= 0L) {
            throw new IllegalArgumentException("neighborMovieId must be positive.");
        }
        if (!Double.isFinite(similarity) || similarity <= 0.0d || similarity > 1.0d) {
            throw new IllegalArgumentException("similarity must be finite, greater than 0.0, and at most 1.0.");
        }
        if (commonUsers < 1L) {
            throw new IllegalArgumentException("commonUsers must be at least 1.");
        }
    }

    private static void validateRating(long userId, int rating) {
        if (userId <= 0L) {
            throw new IllegalArgumentException("userId must be positive.");
        }
        if (rating < 1 || rating > 5) {
            throw new IllegalArgumentException("rating must be an integer from 1 through 5.");
        }
    }
}
