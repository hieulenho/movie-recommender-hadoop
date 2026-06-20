package com.movierecommender.scoring;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import org.junit.jupiter.api.Test;

class ScoringWritableTest {
    @Test
    void userMovieKeyConstructsValidKey() {
        UserMovieWritable key = new UserMovieWritable(101L, 3L);

        assertEquals(101L, key.getUserId());
        assertEquals(3L, key.getMovieId());
    }

    @Test
    void userMovieKeyRejectsNonPositiveIds() {
        assertThrows(IllegalArgumentException.class, () -> new UserMovieWritable(0L, 1L));
        assertThrows(IllegalArgumentException.class, () -> new UserMovieWritable(1L, 0L));
    }

    @Test
    void userMovieKeyComparesNumerically() {
        UserMovieWritable userTwoMovieTen = new UserMovieWritable(2L, 10L);
        UserMovieWritable userTenMovieOne = new UserMovieWritable(10L, 1L);
        UserMovieWritable userTwoMovieThree = new UserMovieWritable(2L, 3L);

        assertTrue(userTwoMovieTen.compareTo(userTenMovieOne) < 0);
        assertTrue(userTwoMovieThree.compareTo(userTwoMovieTen) < 0);
    }

    @Test
    void userMovieKeySerializesRoundTrip() throws Exception {
        UserMovieWritable original = new UserMovieWritable(101L, 3L);
        UserMovieWritable copy = new UserMovieWritable();

        copy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(original))));

        assertEquals(original, copy);
        assertEquals(original.hashCode(), copy.hashCode());
    }

    @Test
    void userMovieKeyEqualsAndHashCodeUseBothFields() {
        UserMovieWritable key = new UserMovieWritable(101L, 3L);

        assertEquals(new UserMovieWritable(101L, 3L), key);
        assertNotEquals(new UserMovieWritable(101L, 4L), key);
        assertEquals(new UserMovieWritable(101L, 3L).hashCode(), key.hashCode());
    }

    @Test
    void userMovieKeyHasStableToString() {
        assertEquals("101,3", new UserMovieWritable(101L, 3L).toString());
    }

    @Test
    void scoreContributionConstructsValidContribution() {
        ScoreContributionWritable contribution = new ScoreContributionWritable(2.0d, 0.4d, 1L);

        assertEquals(2.0d, contribution.getNumerator());
        assertEquals(0.4d, contribution.getDenominator());
        assertEquals(1L, contribution.getContributingItems());
    }

    @Test
    void scoreContributionAddsCorrectly() {
        ScoreContributionWritable sum = new ScoreContributionWritable(2.0d, 0.4d, 1L);

        sum.add(new ScoreContributionWritable(1.8d, 0.6d, 1L));

        assertEquals(3.8d, sum.getNumerator(), 1.0e-12);
        assertEquals(1.0d, sum.getDenominator(), 1.0e-12);
        assertEquals(2L, sum.getContributingItems());
    }

    @Test
    void scoreContributionSerializesRoundTrip() throws Exception {
        ScoreContributionWritable original =
                new ScoreContributionWritable(1.0d / 3.0d, 0.25d, 2L);
        ScoreContributionWritable copy = new ScoreContributionWritable();

        copy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(original))));

        assertEquals(original.getNumerator(), copy.getNumerator());
        assertEquals(original.getDenominator(), copy.getDenominator());
        assertEquals(original.getContributingItems(), copy.getContributingItems());
    }

    @Test
    void scoreContributionPreservesDoublePrecision() {
        ScoreContributionWritable contribution =
                new ScoreContributionWritable(0.123456789012345d, 0.333333333333333d, 1L);

        assertEquals(0.123456789012345d, contribution.getNumerator());
        assertEquals(0.333333333333333d, contribution.getDenominator());
    }

    @Test
    void scoreContributionRejectsNonFiniteValues() {
        assertThrows(IllegalArgumentException.class, () -> new ScoreContributionWritable(Double.NaN, 1.0d, 1L));
        assertThrows(
                IllegalArgumentException.class,
                () -> new ScoreContributionWritable(1.0d, Double.POSITIVE_INFINITY, 1L));
    }

    @Test
    void scoreContributionRejectsNegativeDenominator() {
        assertThrows(IllegalArgumentException.class, () -> new ScoreContributionWritable(1.0d, -0.1d, 1L));
    }

    @Test
    void joinKeySortsSimilarityRecordsBeforeRatings() {
        JoinKeyWritable similarity = new JoinKeyWritable(2L, JoinKeyWritable.TYPE_SIMILARITY, 3L);
        JoinKeyWritable rating = new JoinKeyWritable(2L, JoinKeyWritable.TYPE_RATING, 101L);

        assertTrue(similarity.compareTo(rating) < 0);
    }

    @Test
    void joinKeyGroupsAndPartitionsBySourceMovie() {
        JoinKeyWritable left = new JoinKeyWritable(2L, JoinKeyWritable.TYPE_SIMILARITY, 3L);
        JoinKeyWritable right = new JoinKeyWritable(2L, JoinKeyWritable.TYPE_RATING, 101L);
        SourceMovieGroupingComparator groupingComparator = new SourceMovieGroupingComparator();
        SourceMoviePartitioner partitioner = new SourceMoviePartitioner();

        assertEquals(0, groupingComparator.compare(left, right));
        assertEquals(
                partitioner.getPartition(left, JoinValueWritable.forSimilarity(3L, 0.5d, 1L), 7),
                partitioner.getPartition(right, JoinValueWritable.forRating(101L, 4), 7));
    }

    @Test
    void joinValueSerializesSimilarityAndRatingRoundTrips() throws Exception {
        JoinValueWritable similarity = JoinValueWritable.forSimilarity(3L, 0.4d, 2L);
        JoinValueWritable rating = JoinValueWritable.forRating(101L, 5);

        JoinValueWritable similarityCopy = new JoinValueWritable();
        JoinValueWritable ratingCopy = new JoinValueWritable();
        similarityCopy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(similarity))));
        ratingCopy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(rating))));

        assertEquals(similarity, similarityCopy);
        assertEquals(rating, ratingCopy);
        assertEquals("similarity:3,0.4,2", similarityCopy.toString());
        assertEquals("rating:101,5", ratingCopy.toString());
    }

    private byte[] writeBytes(org.apache.hadoop.io.Writable writable) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        writable.write(new DataOutputStream(bytes));
        return bytes.toByteArray();
    }
}
