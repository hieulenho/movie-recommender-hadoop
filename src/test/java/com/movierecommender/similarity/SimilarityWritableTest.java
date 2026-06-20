package com.movierecommender.similarity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import org.junit.jupiter.api.Test;

class SimilarityWritableTest {
    @Test
    void directedPairStatsRejectsInvalidValues() {
        assertThrows(IllegalArgumentException.class, () -> new DirectedPairStatsWritable(0L, 2L, 1L));
        assertThrows(IllegalArgumentException.class, () -> new DirectedPairStatsWritable(2L, 2L, 1L));
        assertThrows(IllegalArgumentException.class, () -> new DirectedPairStatsWritable(1L, 2L, 0L));
    }

    @Test
    void directedPairStatsSerializesRoundTrip() throws Exception {
        DirectedPairStatsWritable original = new DirectedPairStatsWritable(10L, 2L, 3L);
        DirectedPairStatsWritable copy = new DirectedPairStatsWritable();

        copy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(original))));

        assertEquals(original, copy);
        assertEquals(original.hashCode(), copy.hashCode());
        assertEquals("10,2,3", copy.toString());
    }

    @Test
    void similarityRelationRejectsInvalidValues() {
        assertThrows(IllegalArgumentException.class, () -> new SimilarityRelationWritable(0L, 2L, 0.5d, 1L));
        assertThrows(IllegalArgumentException.class, () -> new SimilarityRelationWritable(2L, 2L, 0.5d, 1L));
        assertThrows(IllegalArgumentException.class, () -> new SimilarityRelationWritable(1L, 2L, Double.NaN, 1L));
        assertThrows(IllegalArgumentException.class, () -> new SimilarityRelationWritable(1L, 2L, -0.1d, 1L));
        assertThrows(IllegalArgumentException.class, () -> new SimilarityRelationWritable(1L, 2L, 0.5d, 0L));
    }

    @Test
    void similarityRelationSerializesRoundTrip() throws Exception {
        SimilarityRelationWritable original = new SimilarityRelationWritable(10L, 2L, 0.25d, 3L);
        SimilarityRelationWritable copy = new SimilarityRelationWritable();

        copy.readFields(new DataInputStream(new ByteArrayInputStream(writeBytes(original))));

        assertEquals(original, copy);
        assertEquals(original.hashCode(), copy.hashCode());
        assertEquals("10,2\t0.2500000000,3", copy.toString());
    }

    @Test
    void similarityRelationComparesNumericallyAndBySimilarityDescending() {
        SimilarityRelationWritable sourceTwo = new SimilarityRelationWritable(2L, 10L, 0.9d, 1L);
        SimilarityRelationWritable sourceTen = new SimilarityRelationWritable(10L, 1L, 1.0d, 1L);
        SimilarityRelationWritable betterSimilarity = new SimilarityRelationWritable(2L, 3L, 1.0d, 1L);
        SimilarityRelationWritable lowerNeighborTie = new SimilarityRelationWritable(2L, 4L, 1.0d, 1L);

        assertTrue(sourceTwo.compareTo(sourceTen) < 0);
        assertTrue(betterSimilarity.compareTo(sourceTwo) < 0);
        assertTrue(betterSimilarity.compareTo(lowerNeighborTie) < 0);
    }

    @Test
    void similarityRelationEqualsUsesAllFields() {
        SimilarityRelationWritable relation = new SimilarityRelationWritable(1L, 2L, 0.5d, 3L);

        assertEquals(new SimilarityRelationWritable(1L, 2L, 0.5d, 3L), relation);
        assertNotEquals(new SimilarityRelationWritable(1L, 2L, 0.6d, 3L), relation);
        assertNotEquals(new SimilarityRelationWritable(1L, 3L, 0.5d, 3L), relation);
    }

    @Test
    void formatsSimilarityWithTenDecimalPlaces() {
        assertEquals("0.6831300511", SimilarityRelationWritable.formatSimilarity(0.6831300510639732d));
    }

    private byte[] writeBytes(org.apache.hadoop.io.Writable writable) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        writable.write(new DataOutputStream(bytes));
        return bytes.toByteArray();
    }
}
