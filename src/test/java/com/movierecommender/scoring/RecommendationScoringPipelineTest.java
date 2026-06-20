package com.movierecommender.scoring;

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

class RecommendationScoringPipelineTest {
    private static final double TOLERANCE = 1.0e-12;
    private static final Path USER_HISTORY_INPUT =
            Path.of("tests", "fixtures", "recommendation-scoring", "user-history.txt");
    private static final Path SIMILARITY_INPUT =
            Path.of("tests", "fixtures", "recommendation-scoring", "similarity.txt");
    private static final Path EXPECTED_OUTPUT =
            Path.of("tests", "fixtures", "recommendation-scoring", "expected.txt");
    private static final Path MALFORMED_SIMILARITY_INPUT =
            Path.of("tests", "fixtures", "recommendation-scoring", "malformed-similarity.txt");

    @TempDir
    Path tempDir;

    @Test
    void calculatesOneSourceContribution() {
        assertEquals(2.0d, RecommendationScoringPipeline.contributionNumerator(0.4d, 5), TOLERANCE);
        assertEquals(0.4d, RecommendationScoringPipeline.contributionDenominator(0.4d), TOLERANCE);
    }

    @Test
    void combinesMultipleSourceItemContributions() {
        ScoreContributionWritable sum = new ScoreContributionWritable(2.0d, 0.4d, 1L);

        sum.add(new ScoreContributionWritable(1.8d, 0.6d, 1L));

        assertEquals(3.8d, sum.getNumerator(), TOLERANCE);
        assertEquals(1.0d, sum.getDenominator(), TOLERANCE);
        assertEquals(2L, sum.getContributingItems());
    }

    @Test
    void dividesNumeratorByDenominatorCorrectly() {
        assertEquals(3.8d, RecommendationScoringPipeline.score(3.8d, 1.0d), TOLERANCE);
    }

    @Test
    void usesAbsoluteSimilarityInDenominator() {
        assertEquals(0.7d, RecommendationScoringPipeline.contributionDenominator(-0.7d), TOLERANCE);
    }

    @Test
    void preservesFullPrecisionBeforeFinalFormatting() {
        double numerator = 1.0d / 3.0d;
        double denominator = 0.2d;

        assertEquals(numerator / denominator, RecommendationScoringPipeline.score(numerator, denominator));
    }

    @Test
    void formatsScoresWithExactlyTenDecimalPlaces() {
        assertEquals("4.3333333333", RecommendationScoringPipeline.formatScore(13.0d / 3.0d));
    }

    @Test
    void rejectsMissingArguments() throws Exception {
        int result = ToolRunner.run(new Configuration(), new RecommendationScoringPipeline(), new String[] {"--local"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsExtraPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new RecommendationScoringPipeline(),
                new String[] {
                    "--local",
                    USER_HISTORY_INPUT.toString(),
                    SIMILARITY_INPUT.toString(),
                    tempDir.resolve("output").toString(),
                    "extra"
                });

        assertNotEquals(0, result);
    }

    @Test
    void rejectsReducersBelowOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new RecommendationScoringPipeline(),
                new String[] {
                    "--local",
                    "--reducers",
                    "0",
                    USER_HISTORY_INPUT.toString(),
                    SIMILARITY_INPUT.toString(),
                    tempDir.resolve("output").toString()
                });

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenUserHistoryInputDoesNotExist() throws Exception {
        int result = runLocalScoring(
                tempDir.resolve("missing-user-history.txt"),
                SIMILARITY_INPUT,
                tempDir.resolve("missing-user-output"));

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenSimilarityInputDoesNotExist() throws Exception {
        int result = runLocalScoring(
                USER_HISTORY_INPUT,
                tempDir.resolve("missing-similarity.txt"),
                tempDir.resolve("missing-similarity-output"));

        assertNotEquals(0, result);
    }

    @Test
    void failsWhenFinalOutputAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void runsRealTwoStagePipelineInLocalMode() throws Exception {
        Path output = tempDir.resolve("scoring-output");

        int result = runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
    }

    @Test
    void matchesExpectedOutputExactly() throws Exception {
        Path output = tempDir.resolve("expected-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        assertEquals(Files.readAllLines(EXPECTED_OUTPUT), readOutputLines(output));
    }

    @Test
    void aggregatesMultipleContributionsForOneCandidate() throws Exception {
        Path output = tempDir.resolve("aggregate-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        assertEquals(3.8d, readScores(output).get("101,3"), 1.0e-10);
    }

    @Test
    void producesNoDuplicateUserCandidateRows() throws Exception {
        Path output = tempDir.resolve("duplicates-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        Set<String> keys = new HashSet<>();
        for (String line : readOutputLines(output)) {
            assertTrue(keys.add(line.split("\t", -1)[0]));
        }
    }

    @Test
    void sortsUserAndMovieIdsNumericallyWithOneReducer() throws Exception {
        Path userHistory = tempDir.resolve("numeric-user-history.txt");
        Path similarity = tempDir.resolve("numeric-similarity.txt");
        Path output = tempDir.resolve("numeric-output");
        Files.writeString(userHistory, "10\t2:5\n");
        Files.writeString(similarity, "2,10\t0.8000000000,1\n2,3\t0.7000000000,1\n");

        assertEquals(0, runLocalScoring(userHistory, similarity, output));

        assertEquals(List.of("10,3\t5.0000000000", "10,10\t5.0000000000"), readOutputLines(output));
    }

    @Test
    void keepsWatchedCandidatesInRawScoringOutput() throws Exception {
        Path output = tempDir.resolve("watched-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        List<String> lines = readOutputLines(output);
        assertTrue(lines.stream().anyMatch(line -> line.startsWith("101,1\t")));
        assertTrue(lines.stream().anyMatch(line -> line.startsWith("101,2\t")));
        assertTrue(lines.stream().anyMatch(line -> line.startsWith("102,2\t")));
        assertTrue(lines.stream().anyMatch(line -> line.startsWith("102,3\t")));
    }

    @Test
    void failsOnMalformedSimilarityInput() throws Exception {
        Path output = tempDir.resolve("malformed-output");

        int result = runLocalScoring(USER_HISTORY_INPUT, MALFORMED_SIMILARITY_INPUT, output);

        assertNotEquals(0, result);
    }

    @Test
    void repeatedRunsProduceDeterministicLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, firstOutput));
        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, secondOutput));

        assertEquals(readOutputLines(firstOutput), readOutputLines(secondOutput));
    }

    @Test
    void cleansControlledIntermediateOutputAfterSuccess() throws Exception {
        Path output = tempDir.resolve("cleanup-output");
        Path intermediate = tempDir.resolve("cleanup-output-recommendation-scoring-intermediate");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        assertFalse(Files.exists(intermediate));
    }

    @Test
    void finalOutputContainsExactlyOneScoreField() throws Exception {
        Path output = tempDir.resolve("format-output");

        assertEquals(0, runLocalScoring(USER_HISTORY_INPUT, SIMILARITY_INPUT, output));

        for (String line : readOutputLines(output)) {
            String[] sections = line.split("\t", -1);
            assertEquals(2, sections.length);
            assertFalse(sections[1].contains(","));
        }
    }

    private int runLocalScoring(Path userHistoryInput, Path similarityInput, Path output) throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new RecommendationScoringPipeline(),
                new String[] {
                    "--local",
                    "--reducers",
                    "1",
                    userHistoryInput.toString(),
                    similarityInput.toString(),
                    output.toString()
                });
    }

    private List<String> readOutputLines(Path output) throws Exception {
        return Files.readAllLines(output.resolve("part-r-00000"));
    }

    private Map<String, Double> readScores(Path output) throws Exception {
        Map<String, Double> scores = new LinkedHashMap<>();
        for (String line : readOutputLines(output)) {
            String[] sections = line.split("\t", -1);
            assertEquals(2, sections.length);
            scores.put(sections[0], Double.parseDouble(sections[1]));
        }
        return scores;
    }
}
