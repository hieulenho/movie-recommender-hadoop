package com.movierecommender.pairs;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import org.junit.jupiter.api.Test;

class PairStatsWritableTest {
    @Test
    void constructsValues() {
        PairStatsWritable stats = new PairStatsWritable(1L, 20L, 16L, 25L);

        assertEquals(1L, stats.getCommonUsers());
        assertEquals(20L, stats.getSumXY());
        assertEquals(16L, stats.getSumX2());
        assertEquals(25L, stats.getSumY2());
    }

    @Test
    void addsStatistics() {
        PairStatsWritable stats = new PairStatsWritable(1L, 15L, 9L, 25L);
        stats.add(new PairStatsWritable(1L, 8L, 4L, 16L));

        assertEquals("2,23,13,41", stats.toString());
    }

    @Test
    void serializesRoundTrip() throws Exception {
        PairStatsWritable original = new PairStatsWritable(3L, 28L, 38L, 42L);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        original.write(new DataOutputStream(bytes));

        PairStatsWritable roundTrip = new PairStatsWritable();
        roundTrip.readFields(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray())));

        assertEquals(original.toString(), roundTrip.toString());
    }

    @Test
    void toStringIsDeterministic() {
        assertEquals("3,28,38,42", new PairStatsWritable(3L, 28L, 38L, 42L).toString());
    }

    @Test
    void usesLongValues() {
        long large = (long) Integer.MAX_VALUE + 10L;
        PairStatsWritable stats = new PairStatsWritable(large, large, large, large);

        assertEquals(large + "," + large + "," + large + "," + large, stats.toString());
    }
}
