package com.movierecommender.similarity;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class PairStatisticsRecordTest {
    @Test
    void parsesValidPairStatisticsRow() {
        PairStatisticsRecord record = PairStatisticsRecord.parse("1,2\t3,28,38,42");

        assertEquals(1L, record.firstMovieId());
        assertEquals(2L, record.secondMovieId());
        assertEquals(3L, record.commonUsers());
        assertEquals(28L, record.sumXY());
        assertEquals(38L, record.sumX2());
        assertEquals(42L, record.sumY2());
    }

    @Test
    void trimsFields() {
        PairStatisticsRecord record = PairStatisticsRecord.parse(" 1 , 2 \t 3 , 28 , 38 , 42 ");

        assertEquals(new PairStatisticsRecord(1L, 2L, 3L, 28L, 38L, 42L), record);
    }

    @Test
    void rejectsBlankRow() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("   "));
    }

    @Test
    void rejectsMissingTab() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2,3,28,38,42"));
    }

    @Test
    void rejectsExtraTab() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t3,28\t38,42"));
    }

    @Test
    void rejectsMalformedMoviePair() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2,3\t3,28,38,42"));
    }

    @Test
    void rejectsNonPositiveMovieIds() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("0,2\t3,28,38,42"));
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,-2\t3,28,38,42"));
    }

    @Test
    void rejectsSelfPair() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("2,2\t3,28,38,42"));
    }

    @Test
    void rejectsReversedPairOrdering() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("2,1\t3,28,38,42"));
    }

    @Test
    void rejectsCommonUsersBelowOne() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t0,28,38,42"));
    }

    @Test
    void rejectsInvalidNumericStatistics() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t3,0,38,42"));
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t3,28,-38,42"));
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t3,28,38,abc"));
    }

    @Test
    void rejectsWrongStatisticsFieldCount() {
        assertThrows(PairStatisticsRecord.ValidationException.class, () -> PairStatisticsRecord.parse("1,2\t3,28,38"));
    }
}
