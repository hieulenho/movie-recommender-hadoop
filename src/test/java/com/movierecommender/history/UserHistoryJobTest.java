package com.movierecommender.history;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.util.ToolRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class UserHistoryJobTest {
    private static final Path FIXTURE_INPUT =
            Path.of("tests", "fixtures", "user-history", "ratings.csv");
    private static final Path EXPECTED_OUTPUT =
            Path.of("tests", "fixtures", "user-history", "expected.txt");
    private static final Path CONFLICTING_INPUT =
            Path.of("tests", "fixtures", "user-history", "conflicting-ratings.csv");

    @TempDir
    Path tempDir;

    @Test
    void rejectsMissingCommandLineArguments() throws Exception {
        int result = ToolRunner.run(new Configuration(), new UserHistoryJob(), new String[] {"--local"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsTooManyPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new UserHistoryJob(),
                new String[] {"--local", "input", "output", "extra"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsReducersLessThanOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new UserHistoryJob(),
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
    void runsActualUserHistoryJobInLocalMode() throws Exception {
        Path output = tempDir.resolve("user-history-output");

        int result = runLocalUserHistoryJob(FIXTURE_INPUT, output);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
        assertEquals(Files.readAllLines(EXPECTED_OUTPUT), readOutputLines(output));
    }

    @Test
    void sortsUsersNumericallyWithOneReducer() throws Exception {
        Path output = tempDir.resolve("sorted-users-output");
        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, output));

        List<Long> userIds = readOutputLines(output).stream()
                .map(line -> Long.parseLong(line.split("\t", -1)[0]))
                .toList();

        assertEquals(List.of(101L, 102L, 103L, 104L), userIds);
    }

    @Test
    void sortsMovieIdsNumericallyWithinEachHistory() throws Exception {
        Path output = tempDir.resolve("sorted-movies-output");
        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, output));

        for (String line : readOutputLines(output)) {
            List<Long> movieIds = parseMovieIds(line);
            List<Long> sortedMovieIds = new ArrayList<>(movieIds);
            sortedMovieIds.sort(Long::compareTo);

            assertEquals(sortedMovieIds, movieIds);
        }
    }

    @Test
    void ignoresExactDuplicateNormalizedRecords() throws Exception {
        Path output = tempDir.resolve("exact-duplicate-output");
        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, output));

        assertTrue(readOutputLines(output).contains("101\t1:4,3:5"));
    }

    @Test
    void producesEachMovieOnlyOncePerUser() throws Exception {
        Path output = tempDir.resolve("unique-movies-output");
        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, output));

        for (String line : readOutputLines(output)) {
            List<Long> movieIds = parseMovieIds(line);

            assertEquals(new HashSet<>(movieIds).size(), movieIds.size());
        }
    }

    @Test
    void failsOnConflictingDuplicateUserMovieRecords() throws Exception {
        Path output = tempDir.resolve("conflicting-output");

        int result = runLocalUserHistoryJob(CONFLICTING_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenOutputPathAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalUserHistoryJob(FIXTURE_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenInputPathDoesNotExist() throws Exception {
        Path output = tempDir.resolve("missing-input-output");

        int result = runLocalUserHistoryJob(tempDir.resolve("missing.csv"), output);

        assertNotEquals(0, result);
    }

    @Test
    void failsOnIncorrectHeaderContent() throws Exception {
        Path input = tempDir.resolve("bad-header.csv");
        Files.writeString(input, "userId,movieId,rating,wrong\n101,1,4,2005-01-01\n");

        int result = runLocalUserHistoryJob(input, tempDir.resolve("bad-header-output"));

        assertNotEquals(0, result);
    }

    @Test
    void repeatedLocalRunsProduceSameLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, firstOutput));
        assertEquals(0, runLocalUserHistoryJob(FIXTURE_INPUT, secondOutput));

        assertEquals(readOutputLines(firstOutput), readOutputLines(secondOutput));
    }

    private int runLocalUserHistoryJob(Path input, Path output) throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new UserHistoryJob(),
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

    private List<Long> parseMovieIds(String line) {
        String[] fields = line.split("\t", -1);
        assertEquals(2, fields.length);
        assertFalse(fields[1].isBlank());

        List<Long> movieIds = new ArrayList<>();
        for (String entry : fields[1].split(",")) {
            int separator = entry.indexOf(':');
            movieIds.add(Long.parseLong(entry.substring(0, separator)));
        }
        return movieIds;
    }
}
