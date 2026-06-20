package com.movierecommender.pairs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class UserHistoryRecordTest {
    @Test
    void parsesValidHistory() {
        UserHistoryRecord record = UserHistoryRecord.parse("101\t1:4,3:5");

        assertEquals(101L, record.userId());
        assertEquals(List.of(new UserHistoryRecord.ItemRating(1L, 4), new UserHistoryRecord.ItemRating(3L, 5)),
                record.ratings());
    }

    @Test
    void parsesSingleItemHistory() {
        UserHistoryRecord record = UserHistoryRecord.parse("104\t5:3");

        assertEquals(104L, record.userId());
        assertEquals(List.of(new UserHistoryRecord.ItemRating(5L, 3)), record.ratings());
    }

    @Test
    void trimsSurroundingWhitespace() {
        UserHistoryRecord record = UserHistoryRecord.parse(" 101 \t 1:4 , 3:5 ");

        assertEquals(101L, record.userId());
        assertEquals(List.of(new UserHistoryRecord.ItemRating(1L, 4), new UserHistoryRecord.ItemRating(3L, 5)),
                record.ratings());
    }

    @Test
    void sortsMovieEntriesNumerically() {
        UserHistoryRecord record = UserHistoryRecord.parse("101\t10:2,2:4,1:5");

        assertEquals(List.of(1L, 2L, 10L), record.ratings().stream()
                .map(UserHistoryRecord.ItemRating::movieId)
                .toList());
    }

    @Test
    void rejectsEmptyLine() {
        assertMessageContains("   ", "empty");
    }

    @Test
    void rejectsMissingTab() {
        assertMessageContains("101 1:4,3:5", "tab");
    }

    @Test
    void rejectsMoreThanOneTabSeparatedHistorySection() {
        assertMessageContains("101\t1:4\t3:5", "tab");
    }

    @Test
    void rejectsUserIdZero() {
        assertMessageContains("0\t1:4", "userId");
    }

    @Test
    void rejectsNegativeUserId() {
        assertMessageContains("-1\t1:4", "userId");
    }

    @Test
    void rejectsNonIntegerUserId() {
        assertMessageContains("abc\t1:4", "userId");
    }

    @Test
    void rejectsEmptyHistory() {
        assertMessageContains("101\t ", "history");
    }

    @Test
    void rejectsMalformedMovieRatingEntry() {
        assertMessageContains("101\t1:4:5", "colon");
    }

    @Test
    void rejectsMovieIdZero() {
        assertMessageContains("101\t0:4", "movieId");
    }

    @Test
    void rejectsNegativeMovieId() {
        assertMessageContains("101\t-1:4", "movieId");
    }

    @Test
    void rejectsRatingBelowOne() {
        assertMessageContains("101\t1:0", "rating");
    }

    @Test
    void rejectsRatingAboveFive() {
        assertMessageContains("101\t1:6", "rating");
    }

    @Test
    void rejectsNonIntegerRating() {
        assertMessageContains("101\t1:five", "rating");
    }

    @Test
    void rejectsDuplicateMovieIds() {
        assertMessageContains("101\t1:4,1:5", "duplicate");
    }

    private void assertMessageContains(String line, String expectedText) {
        UserHistoryRecord.ValidationException exception = assertThrows(
                UserHistoryRecord.ValidationException.class,
                () -> UserHistoryRecord.parse(line));
        assertTrue(exception.getMessage().contains(expectedText));
    }
}
