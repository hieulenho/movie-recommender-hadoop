package com.movierecommender.scoring;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class DirectedSimilarityRecordTest {
    @Test
    void parsesValidRow() {
        DirectedSimilarityRecord record = DirectedSimilarityRecord.parse("1,3\t0.4000000000,2");

        assertEquals(1L, record.sourceMovieId());
        assertEquals(3L, record.neighborMovieId());
        assertEquals(0.4d, record.similarity());
        assertEquals(2L, record.commonUsers());
    }

    @Test
    void rejectsBlankRow() {
        assertMessageContains("   ", "blank");
    }

    @Test
    void rejectsMissingTab() {
        assertMessageContains("1,3 0.4000000000,2", "tab");
    }

    @Test
    void rejectsWrongFieldCount() {
        assertMessageContains("1,3\t0.4000000000,2,extra", "exactly");
    }

    @Test
    void rejectsNonPositiveSourceId() {
        assertMessageContains("0,3\t0.4000000000,2", "sourceMovieId");
    }

    @Test
    void rejectsNonPositiveNeighborId() {
        assertMessageContains("1,0\t0.4000000000,2", "neighborMovieId");
    }

    @Test
    void rejectsSelfRelation() {
        assertMessageContains("1,1\t0.4000000000,2", "differ");
    }

    @Test
    void rejectsNaN() {
        assertMessageContains("1,3\tNaN,2", "similarity");
    }

    @Test
    void rejectsInfinity() {
        assertMessageContains("1,3\tInfinity,2", "similarity");
    }

    @Test
    void rejectsZeroSimilarity() {
        assertMessageContains("1,3\t0.0,2", "similarity");
    }

    @Test
    void rejectsSimilarityGreaterThanOne() {
        assertMessageContains("1,3\t1.0000000001,2", "similarity");
    }

    @Test
    void rejectsCommonUsersBelowOne() {
        assertMessageContains("1,3\t0.4000000000,0", "commonUsers");
    }

    private void assertMessageContains(String line, String expectedText) {
        DirectedSimilarityRecord.ValidationException exception = assertThrows(
                DirectedSimilarityRecord.ValidationException.class,
                () -> DirectedSimilarityRecord.parse(line));
        assertTrue(exception.getMessage().contains(expectedText));
    }
}
