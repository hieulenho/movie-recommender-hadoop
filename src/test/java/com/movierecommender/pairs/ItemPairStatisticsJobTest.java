package com.movierecommender.pairs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.util.ToolRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ItemPairStatisticsJobTest {
    private static final Path FIXTURE_INPUT =
            Path.of("tests", "fixtures", "item-pairs", "user-history.txt");
    private static final Path EXPECTED_OUTPUT =
            Path.of("tests", "fixtures", "item-pairs", "expected.txt");
    private static final Path MALFORMED_INPUT =
            Path.of("tests", "fixtures", "item-pairs", "malformed-history.txt");

    @TempDir
    Path tempDir;

    @Test
    void rejectsMissingCommandLineArguments() throws Exception {
        int result = ToolRunner.run(new Configuration(), new ItemPairStatisticsJob(), new String[] {"--local"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsTooManyPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new ItemPairStatisticsJob(),
                new String[] {"--local", "input", "output", "extra"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsReducersLessThanOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new ItemPairStatisticsJob(),
                new String[] {
                    "--local",
                    "--reducers",
                    "0",
                    FIXTURE_INPUT.toString(),
                    tempDir.resolve("invalid-reducers-output").toString()
                });

        assertNotEquals(0, result);
    }

    @Test
    void runsActualItemPairStatisticsJobInLocalMode() throws Exception {
        Path output = tempDir.resolve("item-pair-stats-output");

        int result = runLocalItemPairStatisticsJob(FIXTURE_INPUT, output);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
        assertEquals(Files.readAllLines(EXPECTED_OUTPUT), readOutputLines(output));
    }

    @Test
    void computesExpectedStatisticsForPairOneTwo() throws Exception {
        Path output = tempDir.resolve("pair-one-two-output");
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, output));

        Map<String, PairStats> statsByPair = readStatsByPair(output);

        assertEquals(new PairStats(3L, 28L, 38L, 42L), statsByPair.get("1,2"));
    }

    @Test
    void sumsCommonUserContributionsAcrossAllPairs() throws Exception {
        Path output = tempDir.resolve("common-user-contributions-output");
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, output));

        long totalCommonUsers = readStatsByPair(output).values().stream()
                .mapToLong(PairStats::commonUsers)
                .sum();

        assertEquals(7L, totalCommonUsers);
    }

    @Test
    void doesNotEmitPairsForSingleItemUsers() throws Exception {
        Path output = tempDir.resolve("single-item-user-output");
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, output));

        for (Pair pair : readPairs(output)) {
            assertNotEquals(5L, pair.firstMovieId());
            assertNotEquals(5L, pair.secondMovieId());
        }
    }

    @Test
    void emitsOnlyUnorderedNonSelfPairs() throws Exception {
        Path output = tempDir.resolve("unordered-pairs-output");
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, output));

        Set<String> observedPairs = new HashSet<>();
        for (Pair pair : readPairs(output)) {
            assertTrue(pair.firstMovieId() < pair.secondMovieId());
            assertTrue(observedPairs.add(pair.firstMovieId() + "," + pair.secondMovieId()));
            assertFalse(observedPairs.contains(pair.secondMovieId() + "," + pair.firstMovieId()));
        }
    }

    @Test
    void sortsPairsNumericallyWithOneReducer() throws Exception {
        Path output = tempDir.resolve("sorted-pairs-output");
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, output));

        List<Pair> pairs = readPairs(output);
        List<Pair> sortedPairs = new ArrayList<>(pairs);
        sortedPairs.sort(Pair::compareTo);

        assertEquals(sortedPairs, pairs);
    }

    @Test
    void returnsNonZeroForMalformedUserHistoryInput() throws Exception {
        Path output = tempDir.resolve("malformed-output");

        int result = runLocalItemPairStatisticsJob(MALFORMED_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenOutputPathAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalItemPairStatisticsJob(FIXTURE_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenInputPathDoesNotExist() throws Exception {
        Path output = tempDir.resolve("missing-input-output");

        int result = runLocalItemPairStatisticsJob(tempDir.resolve("missing.txt"), output);

        assertNotEquals(0, result);
    }

    @Test
    void repeatedLocalRunsProduceSameLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, firstOutput));
        assertEquals(0, runLocalItemPairStatisticsJob(FIXTURE_INPUT, secondOutput));

        assertEquals(readOutputLines(firstOutput), readOutputLines(secondOutput));
    }

    private int runLocalItemPairStatisticsJob(Path input, Path output) throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new ItemPairStatisticsJob(),
                new String[] {
                    "--local",
                    "--reducers",
                    "1",
                    input.toString(),
                    output.toString()
                });
    }

    private List<String> readOutputLines(Path output) throws Exception {
        return Files.readAllLines(output.resolve("part-r-00000"));
    }

    private List<Pair> readPairs(Path output) throws Exception {
        return readStatsByPair(output).keySet().stream()
                .map(ItemPairStatisticsJobTest::parsePair)
                .toList();
    }

    private Map<String, PairStats> readStatsByPair(Path output) throws Exception {
        Map<String, PairStats> statsByPair = new LinkedHashMap<>();
        for (String line : readOutputLines(output)) {
            String[] fields = line.split("\t", -1);
            assertEquals(2, fields.length);
            assertFalse(fields[0].isBlank());
            assertFalse(fields[1].isBlank());
            statsByPair.put(fields[0], parseStats(fields[1]));
        }
        return statsByPair;
    }

    private static Pair parsePair(String text) {
        String[] fields = text.split(",", -1);
        assertEquals(2, fields.length);
        return new Pair(Long.parseLong(fields[0]), Long.parseLong(fields[1]));
    }

    private static PairStats parseStats(String text) {
        String[] fields = text.split(",", -1);
        assertEquals(4, fields.length);
        return new PairStats(
                Long.parseLong(fields[0]),
                Long.parseLong(fields[1]),
                Long.parseLong(fields[2]),
                Long.parseLong(fields[3]));
    }

    private record Pair(long firstMovieId, long secondMovieId) implements Comparable<Pair> {
        @Override
        public int compareTo(Pair other) {
            int firstComparison = Long.compare(firstMovieId, other.firstMovieId);
            if (firstComparison != 0) {
                return firstComparison;
            }
            return Long.compare(secondMovieId, other.secondMovieId);
        }
    }

    private record PairStats(long commonUsers, long sumXY, long sumX2, long sumY2) {}
}
