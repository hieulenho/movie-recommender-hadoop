package com.movierecommender.recommendation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.util.ToolRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class TopKRecommendationJobTest {
    private static final Path USER_HISTORY_INPUT =
            Path.of("tests", "fixtures", "top-k-recommendation", "user-history.txt");
    private static final Path RAW_PREDICTION_INPUT =
            Path.of("tests", "fixtures", "top-k-recommendation", "raw-predictions.txt");
    private static final Path EXPECTED_TOP2 =
            Path.of("tests", "fixtures", "top-k-recommendation", "expected-top2.txt");
    private static final Path MALFORMED_PREDICTION_INPUT =
            Path.of("tests", "fixtures", "top-k-recommendation", "malformed-prediction.txt");
    private static final Path CONFLICTING_PREDICTION_INPUT =
            Path.of("tests", "fixtures", "top-k-recommendation", "conflicting-predictions.txt");

    @TempDir
    Path tempDir;

    @Test
    void rejectsMissingArguments() throws Exception {
        int result = ToolRunner.run(new Configuration(), new TopKRecommendationJob(), new String[] {"--local"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsExtraPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new TopKRecommendationJob(),
                new String[] {
                    "--local",
                    USER_HISTORY_INPUT.toString(),
                    RAW_PREDICTION_INPUT.toString(),
                    tempDir.resolve("output").toString(),
                    "extra"
                });

        assertNotEquals(0, result);
    }

    @Test
    void rejectsReducersBelowOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new TopKRecommendationJob(),
                new String[] {
                    "--local",
                    "--reducers",
                    "0",
                    USER_HISTORY_INPUT.toString(),
                    RAW_PREDICTION_INPUT.toString(),
                    tempDir.resolve("output").toString()
                });

        assertNotEquals(0, result);
    }

    @Test
    void rejectsTopKBelowOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new TopKRecommendationJob(),
                new String[] {
                    "--local",
                    "--top-k",
                    "0",
                    USER_HISTORY_INPUT.toString(),
                    RAW_PREDICTION_INPUT.toString(),
                    tempDir.resolve("output").toString()
                });

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenUserHistoryInputDoesNotExist() throws Exception {
        int result = runLocalTopK(
                tempDir.resolve("missing-history.txt"),
                RAW_PREDICTION_INPUT,
                tempDir.resolve("missing-history-output"),
                2);

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenRawPredictionInputDoesNotExist() throws Exception {
        int result = runLocalTopK(
                USER_HISTORY_INPUT,
                tempDir.resolve("missing-raw.txt"),
                tempDir.resolve("missing-raw-output"),
                2);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenOutputAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2);

        assertNotEquals(0, result);
    }

    @Test
    void runsRealHadoopJobInLocalMode() throws Exception {
        Path output = tempDir.resolve("top-k-output");

        int result = runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
    }

    @Test
    void matchesExpectedTop2Exactly() throws Exception {
        Path output = tempDir.resolve("expected-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2));

        assertEquals(Files.readAllLines(EXPECTED_TOP2), readOutputLines(output));
    }

    @Test
    void neverOutputsWatchedMovie() throws Exception {
        Path output = tempDir.resolve("watched-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2));

        Map<Long, List<RecommendationEntry>> recommendations = readRecommendations(output);
        assertFalse(movieIds(recommendations.get(101L)).contains(1L));
        assertFalse(movieIds(recommendations.get(101L)).contains(2L));
        assertFalse(movieIds(recommendations.get(102L)).contains(2L));
        assertFalse(movieIds(recommendations.get(102L)).contains(3L));
    }

    @Test
    void keepsNoMoreThanTopKMoviesPerUser() throws Exception {
        Path output = tempDir.resolve("top-k-cap-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2));

        for (List<RecommendationEntry> entries : readRecommendations(output).values()) {
            assertTrue(entries.size() <= 2);
        }
    }

    @Test
    void breaksScoreTiesByMovieIdAscending() throws Exception {
        Path output = tempDir.resolve("tie-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2));

        assertEquals(List.of(2L, 3L), movieIds(readRecommendations(output).get(103L)));
        assertEquals(List.of(2L, 3L), movieIds(readRecommendations(output).get(104L)));
    }

    @Test
    void omitsUserWithNoUnseenCandidates() throws Exception {
        Path output = tempDir.resolve("omit-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, output, 2));

        assertFalse(readRecommendations(output).containsKey(105L));
    }

    @Test
    void producesNumericallySortedUserOutputWithOneReducer() throws Exception {
        Path userHistory = tempDir.resolve("numeric-user-history.txt");
        Path rawPredictions = tempDir.resolve("numeric-raw.txt");
        Path output = tempDir.resolve("numeric-output");
        Files.writeString(userHistory, "10\t1:5\n2\t1:5\n");
        Files.writeString(rawPredictions, "10,3\t4.0000000000\n2,3\t4.0000000000\n");

        assertEquals(0, runLocalTopK(userHistory, rawPredictions, output, 2));

        assertEquals(List.of("2\t3:4.0000000000", "10\t3:4.0000000000"), readOutputLines(output));
    }

    @Test
    void repeatedRunsProduceDeterministicLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, firstOutput, 2));
        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, RAW_PREDICTION_INPUT, secondOutput, 2));

        assertEquals(readOutputLines(firstOutput), readOutputLines(secondOutput));
    }

    @Test
    void failsOnMalformedPredictionInput() throws Exception {
        Path output = tempDir.resolve("malformed-output");

        int result = runLocalTopK(USER_HISTORY_INPUT, MALFORMED_PREDICTION_INPUT, output, 2);

        assertNotEquals(0, result);
    }

    @Test
    void ignoresIdenticalDuplicatePredictions() throws Exception {
        Path rawPredictions = tempDir.resolve("duplicate-raw.txt");
        Path output = tempDir.resolve("duplicate-output");
        Files.writeString(
                rawPredictions,
                Files.readString(RAW_PREDICTION_INPUT) + "101,3\t3.8000000000\n");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, rawPredictions, output, 2));

        assertEquals(Files.readAllLines(EXPECTED_TOP2), readOutputLines(output));
    }

    @Test
    void failsOnConflictingDuplicatePredictions() throws Exception {
        Path output = tempDir.resolve("conflicting-output");

        int result = runLocalTopK(USER_HISTORY_INPUT, CONFLICTING_PREDICTION_INPUT, output, 2);

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenPredictionUserHasNoHistory() throws Exception {
        Path rawPredictions = tempDir.resolve("no-history-raw.txt");
        Path output = tempDir.resolve("no-history-output");
        Files.writeString(rawPredictions, "999,3\t4.0000000000\n");

        int result = runLocalTopK(USER_HISTORY_INPUT, rawPredictions, output, 2);

        assertNotEquals(0, result);
    }

    @Test
    void producesNoOutputForHistoryWithNoPredictions() throws Exception {
        Path rawPredictions = tempDir.resolve("empty-raw.txt");
        Path output = tempDir.resolve("no-predictions-output");
        Files.writeString(rawPredictions, "");

        assertEquals(0, runLocalTopK(USER_HISTORY_INPUT, rawPredictions, output, 2));

        assertEquals(List.of(), readOutputLines(output));
    }

    @Test
    void producesNoOutputWhenAllCandidatesAreWatched() throws Exception {
        Path userHistory = tempDir.resolve("all-watched-history.txt");
        Path rawPredictions = tempDir.resolve("all-watched-raw.txt");
        Path output = tempDir.resolve("all-watched-output");
        Files.writeString(userHistory, "105\t1:5\n");
        Files.writeString(rawPredictions, "105,1\t5.0000000000\n");

        assertEquals(0, runLocalTopK(userHistory, rawPredictions, output, 2));

        assertEquals(List.of(), readOutputLines(output));
    }

    @Test
    void ignoresIdenticalDuplicateHistories() throws Exception {
        Path userHistory = tempDir.resolve("duplicate-history.txt");
        Path rawPredictions = tempDir.resolve("duplicate-history-raw.txt");
        Path output = tempDir.resolve("duplicate-history-output");
        Files.writeString(userHistory, "101\t1:5,2:3\n101\t1:5,2:3\n");
        Files.writeString(rawPredictions, "101,3\t3.8000000000\n");

        assertEquals(0, runLocalTopK(userHistory, rawPredictions, output, 2));

        assertEquals(List.of("101\t3:3.8000000000"), readOutputLines(output));
    }

    @Test
    void failsOnConflictingDuplicateHistories() throws Exception {
        Path userHistory = tempDir.resolve("conflicting-history.txt");
        Path rawPredictions = tempDir.resolve("conflicting-history-raw.txt");
        Path output = tempDir.resolve("conflicting-history-output");
        Files.writeString(userHistory, "101\t1:5,2:3\n101\t1:4,2:3\n");
        Files.writeString(rawPredictions, "101,3\t3.8000000000\n");

        int result = runLocalTopK(userHistory, rawPredictions, output, 2);

        assertNotEquals(0, result);
    }

    private int runLocalTopK(Path userHistoryInput, Path rawPredictionInput, Path output, int topK)
            throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new TopKRecommendationJob(),
                new String[] {
                    "--local",
                    "--reducers",
                    "1",
                    "--top-k",
                    Integer.toString(topK),
                    userHistoryInput.toString(),
                    rawPredictionInput.toString(),
                    output.toString()
                });
    }

    private List<String> readOutputLines(Path output) throws Exception {
        return Files.readAllLines(output.resolve("part-r-00000"));
    }

    private Map<Long, List<RecommendationEntry>> readRecommendations(Path output) throws Exception {
        Map<Long, List<RecommendationEntry>> recommendations = new LinkedHashMap<>();
        for (String line : readOutputLines(output)) {
            String[] sections = line.split("\t", -1);
            assertEquals(2, sections.length);
            long userId = Long.parseLong(sections[0]);
            List<RecommendationEntry> entries = new ArrayList<>();
            for (String entry : sections[1].split(",", -1)) {
                String[] fields = entry.split(":", -1);
                assertEquals(2, fields.length);
                entries.add(new RecommendationEntry(Long.parseLong(fields[0]), Double.parseDouble(fields[1])));
            }
            recommendations.put(userId, entries);
        }
        return recommendations;
    }

    private List<Long> movieIds(List<RecommendationEntry> entries) {
        return entries.stream().map(RecommendationEntry::movieId).toList();
    }

    private record RecommendationEntry(long movieId, double score) {}
}
