package com.movierecommender.pairs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import org.junit.jupiter.api.Test;

class ItemPairWritableTest {
    @Test
    void constructsValidPair() {
        ItemPairWritable pair = new ItemPairWritable(1L, 3L);

        assertEquals(1L, pair.getFirstMovieId());
        assertEquals(3L, pair.getSecondMovieId());
    }

    @Test
    void rejectsSelfPair() {
        assertThrows(IllegalArgumentException.class, () -> new ItemPairWritable(3L, 3L));
    }

    @Test
    void rejectsNonPositiveIds() {
        assertThrows(IllegalArgumentException.class, () -> new ItemPairWritable(0L, 3L));
        assertThrows(IllegalArgumentException.class, () -> new ItemPairWritable(1L, 0L));
    }

    @Test
    void rejectsReversedConstruction() {
        assertThrows(IllegalArgumentException.class, () -> new ItemPairWritable(3L, 1L));
    }

    @Test
    void comparesPairsNumerically() {
        ItemPairWritable lower = new ItemPairWritable(2L, 3L);
        ItemPairWritable higher = new ItemPairWritable(10L, 11L);

        assertTrue(lower.compareTo(higher) < 0);
    }

    @Test
    void serializesRoundTrip() throws Exception {
        ItemPairWritable original = new ItemPairWritable(2L, 10L);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        original.write(new DataOutputStream(bytes));

        ItemPairWritable roundTrip = new ItemPairWritable();
        roundTrip.readFields(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray())));

        assertEquals(original, roundTrip);
    }

    @Test
    void equalsAndHashCodeAreConsistent() {
        ItemPairWritable first = new ItemPairWritable(1L, 2L);
        ItemPairWritable same = new ItemPairWritable(1L, 2L);
        ItemPairWritable different = new ItemPairWritable(1L, 3L);

        assertEquals(first, same);
        assertEquals(first.hashCode(), same.hashCode());
        assertNotEquals(first, different);
    }

    @Test
    void toStringIsDeterministic() {
        assertEquals("1,3", new ItemPairWritable(1L, 3L).toString());
    }
}
