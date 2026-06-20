package com.movierecommender.recommendation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RawPredictionRecordTest {
    @Test
    void parsesValidPrediction() {
        RawPredictionRecord record = RawPredictionRecord.parse("101,3\t3.8000000000");

        assertEquals(101L, record.userId());
        assertEquals(3L, record.movieId());
        assertEquals(3.8d, record.score());
    }

    @Test
    void trimsSurroundingWhitespace() {
        RawPredictionRecord record = RawPredictionRecord.parse(" 101 , 3 \t 3.8000000000 ");

        assertEquals(new RawPredictionRecord(101L, 3L, 3.8d), record);
    }

    @Test
    void rejectsBlankInput() {
        assertMessageContains("   ", "blank");
    }

    @Test
    void rejectsMissingTab() {
        assertMessageContains("101,3 3.8000000000", "tab");
    }

    @Test
    void rejectsExtraTabSeparatedSections() {
        assertMessageContains("101,3\t3.8000000000\textra", "tab");
    }

    @Test
    void rejectsWrongUserMovieFieldCount() {
        assertMessageContains("101,3,4\t3.8000000000", "two");
    }

    @Test
    void rejectsUserIdZero() {
        assertMessageContains("0,3\t3.8000000000", "userId");
    }

    @Test
    void rejectsNegativeUserId() {
        assertMessageContains("-1,3\t3.8000000000", "userId");
    }

    @Test
    void rejectsMovieIdZero() {
        assertMessageContains("101,0\t3.8000000000", "movieId");
    }

    @Test
    void rejectsNegativeMovieId() {
        assertMessageContains("101,-3\t3.8000000000", "movieId");
    }

    @Test
    void rejectsNonIntegerId() {
        assertMessageContains("abc,3\t3.8000000000", "userId");
    }

    @Test
    void rejectsNaNScore() {
        assertMessageContains("101,3\tNaN", "score");
    }

    @Test
    void rejectsPositiveInfinity() {
        assertMessageContains("101,3\tInfinity", "score");
    }

    @Test
    void rejectsNegativeInfinity() {
        assertMessageContains("101,3\t-Infinity", "score");
    }

    @Test
    void rejectsScoreBelowOne() {
        assertMessageContains("101,3\t0.9999999999", "score");
    }

    @Test
    void rejectsScoreAboveFive() {
        assertMessageContains("101,3\t5.0000000001", "score");
    }

    private void assertMessageContains(String line, String expectedText) {
        RawPredictionRecord.ValidationException exception = assertThrows(
                RawPredictionRecord.ValidationException.class,
                () -> RawPredictionRecord.parse(line));
        assertTrue(exception.getMessage().contains(expectedText));
    }
}
