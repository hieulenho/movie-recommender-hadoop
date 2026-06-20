package com.movierecommender.recommendation;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.util.List;
import java.util.PriorityQueue;
import org.junit.jupiter.api.Test;

class RecommendationWritableTest {
    @Test
    void constructsValidCandidate() {
        RecommendationCandidate candidate = new RecommendationCandidate(3L, 3.8d);

        assertEquals(3L, candidate.movieId());
        assertEquals(3.8d, candidate.score());
    }

    @Test
    void rejectsInvalidMovieId() {
        assertThrows(IllegalArgumentException.class, () -> new RecommendationCandidate(0L, 3.8d));
    }

    @Test
    void rejectsNonFiniteScore() {
        assertThrows(IllegalArgumentException.class, () -> new RecommendationCandidate(3L, Double.NaN));
        assertThrows(IllegalArgumentException.class, () -> new RecommendationCandidate(3L, Double.POSITIVE_INFINITY));
    }

    @Test
    void ranksHigherScoreBeforeLowerScore() {
        RecommendationCandidate high = new RecommendationCandidate(4L, 4.0d);
        RecommendationCandidate low = new RecommendationCandidate(3L, 3.0d);

        assertTrue(high.compareTo(low) < 0);
    }

    @Test
    void breaksEqualScoreTiesBySmallerMovieId() {
        RecommendationCandidate smallerMovie = new RecommendationCandidate(2L, 4.0d);
        RecommendationCandidate largerMovie = new RecommendationCandidate(3L, 4.0d);

        assertTrue(smallerMovie.compareTo(largerMovie) < 0);
    }

    @Test
    void retainsAtMostKCandidates() {
        List<RecommendationCandidate> retained = TopKRecommendationJob.retainTopK(
                List.of(
                        new RecommendationCandidate(1L, 5.0d),
                        new RecommendationCandidate(2L, 4.0d),
                        new RecommendationCandidate(3L, 3.0d)),
                2);

        assertEquals(2, retained.size());
        assertEquals(List.of(1L, 2L), retained.stream().map(RecommendationCandidate::movieId).toList());
    }

    @Test
    void replacesCurrentWorstCandidateCorrectly() {
        PriorityQueue<RecommendationCandidate> top =
                new PriorityQueue<>(2, RecommendationCandidate.WORST_FIRST);
        TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(1L, 5.0d));
        TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(4L, 3.0d));

        TopKRecommendationJob.OfferResult result =
                TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(2L, 4.0d));

        assertEquals(TopKRecommendationJob.OfferResult.RETAINED_AND_DISCARDED_PREVIOUS, result);
        assertEquals(List.of(1L, 2L), TopKRecommendationJob.retainTopK(top, 2).stream()
                .map(RecommendationCandidate::movieId)
                .toList());
    }

    @Test
    void discardsWorseCandidateWhenQueueIsFull() {
        PriorityQueue<RecommendationCandidate> top =
                new PriorityQueue<>(2, RecommendationCandidate.WORST_FIRST);
        TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(1L, 5.0d));
        TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(2L, 4.0d));

        TopKRecommendationJob.OfferResult result =
                TopKRecommendationJob.offerCandidate(top, 2, new RecommendationCandidate(3L, 3.0d));

        assertEquals(TopKRecommendationJob.OfferResult.REJECTED_CANDIDATE, result);
        assertEquals(2, top.size());
    }

    @Test
    void producesFinalSortedOrder() {
        List<RecommendationCandidate> retained = TopKRecommendationJob.retainTopK(
                List.of(
                        new RecommendationCandidate(4L, 3.0d),
                        new RecommendationCandidate(3L, 3.8d),
                        new RecommendationCandidate(2L, 3.8d)),
                3);

        assertEquals(List.of(2L, 3L, 4L), retained.stream().map(RecommendationCandidate::movieId).toList());
    }

    @Test
    void formatsExactlyTenDecimalPlacesWithLocaleRootDecimal() {
        assertEquals("3.8000000000", new RecommendationCandidate(3L, 3.8d).formatScore());
        assertEquals("3:3.8000000000", new RecommendationCandidate(3L, 3.8d).toString());
    }

    @Test
    void detectsWatchedMovies() {
        assertTrue(TopKRecommendationJob.isWatched(new long[] {1L, 2L, 10L}, 10L));
        assertFalse(TopKRecommendationJob.isWatched(new long[] {1L, 2L, 10L}, 3L));
    }

    @Test
    void joinKeySortsHistoryBeforePredictionsAndComparesNumerically() {
        RecommendationJoinKeyWritable history =
                new RecommendationJoinKeyWritable(10L, RecommendationJoinKeyWritable.TYPE_HISTORY, 0L);
        RecommendationJoinKeyWritable prediction =
                new RecommendationJoinKeyWritable(10L, RecommendationJoinKeyWritable.TYPE_PREDICTION, 2L);
        RecommendationJoinKeyWritable earlierUser =
                new RecommendationJoinKeyWritable(2L, RecommendationJoinKeyWritable.TYPE_PREDICTION, 10L);

        assertTrue(history.compareTo(prediction) < 0);
        assertTrue(earlierUser.compareTo(history) < 0);
    }

    @Test
    void userPartitionerAndGroupingComparatorUseOnlyUserId() {
        RecommendationJoinKeyWritable history =
                new RecommendationJoinKeyWritable(10L, RecommendationJoinKeyWritable.TYPE_HISTORY, 0L);
        RecommendationJoinKeyWritable prediction =
                new RecommendationJoinKeyWritable(10L, RecommendationJoinKeyWritable.TYPE_PREDICTION, 2L);
        UserPartitioner partitioner = new UserPartitioner();
        UserGroupingComparator groupingComparator = new UserGroupingComparator();

        assertEquals(0, groupingComparator.compare(history, prediction));
        assertEquals(
                partitioner.getPartition(
                        history,
                        RecommendationJoinValueWritable.forHistory(new long[] {1L}, new int[] {5}),
                        5),
                partitioner.getPartition(
                        prediction,
                        RecommendationJoinValueWritable.forPrediction(2L, 4.0d),
                        5));
    }

    @Test
    void joinValueSerializesHistoryAndPredictionRoundTrips() throws Exception {
        RecommendationJoinValueWritable history =
                RecommendationJoinValueWritable.forHistory(new long[] {1L, 2L}, new int[] {5, 3});
        RecommendationJoinValueWritable prediction = RecommendationJoinValueWritable.forPrediction(3L, 3.8d);
        RecommendationJoinValueWritable historyCopy = new RecommendationJoinValueWritable();
        RecommendationJoinValueWritable predictionCopy = new RecommendationJoinValueWritable();

        historyCopy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(history))));
        predictionCopy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(prediction))));

        assertEquals(history, historyCopy);
        assertArrayEquals(new long[] {1L, 2L}, historyCopy.getWatchedMovieIds());
        assertArrayEquals(new int[] {5, 3}, historyCopy.getWatchedRatings());
        assertEquals(prediction, predictionCopy);
        assertEquals("prediction:3,3.8", predictionCopy.toString());
    }

    @Test
    void joinValueRejectsInvalidHistoryAndPrediction() {
        assertThrows(
                IllegalArgumentException.class,
                () -> RecommendationJoinValueWritable.forHistory(new long[] {2L, 1L}, new int[] {5, 3}));
        assertThrows(
                IllegalArgumentException.class,
                () -> RecommendationJoinValueWritable.forHistory(new long[] {1L}, new int[] {6}));
        assertThrows(
                IllegalArgumentException.class,
                () -> RecommendationJoinValueWritable.forPrediction(0L, 4.0d));
        assertThrows(
                IllegalArgumentException.class,
                () -> RecommendationJoinValueWritable.forPrediction(3L, 6.0d));
    }

    @Test
    void candidateEqualsAndHashCodeAreStable() {
        RecommendationCandidate candidate = new RecommendationCandidate(3L, 3.8d);

        assertEquals(new RecommendationCandidate(3L, 3.8d), candidate);
        assertNotEquals(new RecommendationCandidate(4L, 3.8d), candidate);
        assertEquals(new RecommendationCandidate(3L, 3.8d).hashCode(), candidate.hashCode());
    }

    private byte[] writeBytes(org.apache.hadoop.io.Writable writable) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        writable.write(new DataOutputStream(bytes));
        return bytes.toByteArray();
    }
}
