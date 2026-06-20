package com.movierecommender.history;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalDate;
import org.junit.jupiter.api.Test;

class NormalizedRatingTest {
    @Test
    void parsesValidNormalizedRow() {
        NormalizedRating rating = NormalizedRating.parse("101,3,5,2005-01-03");

        assertEquals(101L, rating.userId());
        assertEquals(3L, rating.movieId());
        assertEquals(5, rating.rating());
        assertEquals(LocalDate.of(2005, 1, 3), rating.date());
        assertEquals("2005-01-03", rating.dateText());
    }

    @Test
    void trimsWhitespaceAroundFields() {
        NormalizedRating rating = NormalizedRating.parse(" 101 , 3 , 5 , 2005-01-03 ");

        assertEquals(101L, rating.userId());
        assertEquals(3L, rating.movieId());
        assertEquals(5, rating.rating());
        assertEquals(LocalDate.of(2005, 1, 3), rating.date());
    }

    @Test
    void rejectsExactCsvHeaderAsDataRow() {
        NormalizedRating.ValidationException exception =
                assertRejects(NormalizedRating.HEADER);

        assertTrue(exception.getMessage().contains("header"));
    }

    @Test
    void rejectsWrongNumberOfFields() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,3,5,2005-01-03,extra");

        assertTrue(exception.getMessage().contains("4 comma-separated fields"));
    }

    @Test
    void rejectsUserIdZero() {
        NormalizedRating.ValidationException exception =
                assertRejects("0,3,5,2005-01-03");

        assertTrue(exception.getMessage().contains("userId"));
    }

    @Test
    void rejectsNegativeUserId() {
        NormalizedRating.ValidationException exception =
                assertRejects("-101,3,5,2005-01-03");

        assertTrue(exception.getMessage().contains("userId"));
    }

    @Test
    void rejectsInvalidMovieId() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,0,5,2005-01-03");

        assertTrue(exception.getMessage().contains("movieId"));
    }

    @Test
    void rejectsRatingBelowOne() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,3,0,2005-01-03");

        assertTrue(exception.getMessage().contains("rating"));
    }

    @Test
    void rejectsRatingAboveFive() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,3,6,2005-01-03");

        assertTrue(exception.getMessage().contains("rating"));
    }

    @Test
    void rejectsNonIntegerRating() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,3,4.5,2005-01-03");

        assertTrue(exception.getMessage().contains("rating"));
    }

    @Test
    void rejectsInvalidIsoDate() {
        NormalizedRating.ValidationException exception =
                assertRejects("101,3,5,2005-02-30");

        assertTrue(exception.getMessage().contains("date"));
    }

    @Test
    void rejectsEmptyLine() {
        NormalizedRating.ValidationException exception = assertRejects("   ");

        assertTrue(exception.getMessage().contains("empty"));
    }

    @Test
    void rejectsMalformedText() {
        NormalizedRating.ValidationException exception =
                assertRejects("this is not normalized rating text");

        assertTrue(exception.getMessage().contains("4 comma-separated fields"));
    }

    private NormalizedRating.ValidationException assertRejects(String line) {
        return assertThrows(
                NormalizedRating.ValidationException.class,
                () -> NormalizedRating.parse(line));
    }
}
