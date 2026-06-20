package com.movierecommender.similarity;

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

class ItemSimilarityPipelineTest {
    private static final double TOLERANCE = 1.0e-9;
    private static final Path FIXTURE_INPUT = Path.of("tests", "fixtures", "similarity", "pair-stats.txt");
    private static final Path COSINE_EXPECTED =
            Path.of("tests", "fixtures", "similarity", "cosine-expected-top3.txt");
    private static final Path COOCCURRENCE_EXPECTED =
            Path.of("tests", "fixtures", "similarity", "cooccurrence-expected-top3.txt");
    private static final Path MALFORMED_INPUT =
            Path.of("tests", "fixtures", "similarity", "malformed-pair-stats.txt");

    @TempDir
    Path tempDir;

    @Test
    void computesCosineCorrectly() {
        PairStatisticsRecord record = PairStatisticsRecord.parse("1,2\t3,28,38,42");

        double similarity = ItemSimilarityPipeline.cosineSimilarity(record);

        assertEquals(28.0d / Math.sqrt(38.0d * 42.0d), similarity, TOLERANCE);
    }

    @Test
    void producesSymmetricDirectedCosineValues() {
        PairStatisticsRecord record = PairStatisticsRecord.parse("1,2\t3,28,38,42");

        double leftToRight = ItemSimilarityPipeline.cosineSimilarity(record);
        double rightToLeft = ItemSimilarityPipeline.cosineSimilarity(record);

        assertEquals(leftToRight, rightToLeft, TOLERANCE);
    }

    @Test
    void computesCooccurrenceDenominatorCorrectly() {
        assertEquals(0.25d, ItemSimilarityPipeline.cooccurrenceSimilarity(2L, 8L), TOLERANCE);
    }

    @Test
    void computesAsymmetricCooccurrenceCorrectly() {
        double oneToThree = ItemSimilarityPipeline.cooccurrenceSimilarity(2L, 10L);
        double threeToOne = ItemSimilarityPipeline.cooccurrenceSimilarity(2L, 8L);

        assertEquals(0.2d, oneToThree, TOLERANCE);
        assertEquals(0.25d, threeToOne, TOLERANCE);
        assertNotEquals(oneToThree, threeToOne);
    }

    @Test
    void rejectsInvalidMethod() throws Exception {
        int result = runLocalSimilarity("pearson", FIXTURE_INPUT, tempDir.resolve("invalid-method"), 1, 3);

        assertNotEquals(0, result);
    }

    @Test
    void rejectsTopLBelowOne() throws Exception {
        int result = runLocalSimilarity("cosine", FIXTURE_INPUT, tempDir.resolve("invalid-top-l"), 1, 0);

        assertNotEquals(0, result);
    }

    @Test
    void rejectsMinCommonUsersBelowOne() throws Exception {
        int result = runLocalSimilarity("cosine", FIXTURE_INPUT, tempDir.resolve("invalid-min-common"), 0, 3);

        assertNotEquals(0, result);
    }

    @Test
    void rejectsReducersBelowOne() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new ItemSimilarityPipeline(),
                new String[] {
                    "--local",
                    "--method",
                    "cosine",
                    "--reducers",
                    "0",
                    FIXTURE_INPUT.toString(),
                    tempDir.resolve("invalid-reducers").toString()
                });

        assertNotEquals(0, result);
    }

    @Test
    void rejectsMissingPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new ItemSimilarityPipeline(),
                new String[] {"--local", "--method", "cosine"});

        assertNotEquals(0, result);
    }

    @Test
    void rejectsExtraPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new ItemSimilarityPipeline(),
                new String[] {
                    "--local",
                    "--method",
                    "cosine",
                    FIXTURE_INPUT.toString(),
                    tempDir.resolve("output").toString(),
                    "extra"
                });

        assertNotEquals(0, result);
    }

    @Test
    void runsRealCosinePipelineInLocalMode() throws Exception {
        Path output = tempDir.resolve("cosine-output");

        int result = runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
        assertEquals(Files.readAllLines(COSINE_EXPECTED), readOutputLines(output));
    }

    @Test
    void runsRealCooccurrencePipelineInLocalMode() throws Exception {
        Path output = tempDir.resolve("cooccurrence-output");

        int result = runLocalSimilarity("cooccurrence", FIXTURE_INPUT, output, 1, 3);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
        assertEquals(Files.readAllLines(COOCCURRENCE_EXPECTED), readOutputLines(output));
    }

    @Test
    void producesBothDirectedRelationsWhenRetained() throws Exception {
        Path output = tempDir.resolve("both-directions-output");
        assertEquals(0, runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3));

        List<String> lines = readOutputLines(output);

        assertTrue(lines.stream().anyMatch(line -> line.startsWith("1,4\t")));
        assertTrue(lines.stream().anyMatch(line -> line.startsWith("4,1\t")));
    }

    @Test
    void keepsAtMostTopLNeighborsPerSource() throws Exception {
        Path output = tempDir.resolve("top-l-output");
        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, output, 1, 3));

        for (List<SimilarityLine> lines : readLinesBySource(output).values()) {
            assertTrue(lines.size() <= 3);
        }
    }

    @Test
    void breaksSimilarityTiesByNeighborIdAscending() throws Exception {
        Path output = tempDir.resolve("tie-break-output");
        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, output, 1, 3));

        List<Long> sourceTenNeighbors = readLinesBySource(output).get(10L).stream()
                .map(SimilarityLine::neighborMovieId)
                .toList();

        assertEquals(List.of(1L, 2L, 3L), sourceTenNeighbors);
    }

    @Test
    void sortsNumericMovieIdsInsteadOfLexicographicText() throws Exception {
        Path output = tempDir.resolve("numeric-order-output");
        assertEquals(0, runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3));

        List<Long> sourceOneNeighbors = readLinesBySource(output).get(1L).stream()
                .map(SimilarityLine::neighborMovieId)
                .toList();

        assertEquals(List.of(4L, 5L, 10L), sourceOneNeighbors);
    }

    @Test
    void appliesMinCommonUsersBeforeCooccurrenceNormalization() throws Exception {
        Path output = tempDir.resolve("min-common-output");
        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, output, 2, 10));

        List<SimilarityLine> lines = readSimilarityLines(output);

        assertTrue(lines.stream().noneMatch(line -> line.commonUsers() == 1L));
        assertTrue(lines.stream().noneMatch(line -> line.sourceMovieId() == 1L && line.neighborMovieId() == 4L));
        assertEquals(1.0d, sumSimilaritiesForSource(lines, 1L), TOLERANCE);
    }

    @Test
    void cooccurrenceRowSumsAreOneBeforeTopLTruncation() throws Exception {
        Path output = tempDir.resolve("row-sum-output");
        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, output, 1, 10));

        Map<Long, List<SimilarityLine>> linesBySource = readLinesBySource(output);

        assertEquals(6, linesBySource.size());
        for (Long sourceMovieId : linesBySource.keySet()) {
            assertEquals(
                    1.0d,
                    sumSimilaritiesForSource(readSimilarityLines(output), sourceMovieId),
                    TOLERANCE);
        }
    }

    @Test
    void neverProducesSelfRelations() throws Exception {
        Path output = tempDir.resolve("no-self-output");
        assertEquals(0, runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3));

        for (SimilarityLine line : readSimilarityLines(output)) {
            assertNotEquals(line.sourceMovieId(), line.neighborMovieId());
        }
    }

    @Test
    void returnsNonZeroForMalformedInput() throws Exception {
        Path output = tempDir.resolve("malformed-output");

        int result = runLocalSimilarity("cosine", MALFORMED_INPUT, output, 1, 3);

        assertNotEquals(0, result);
    }

    @Test
    void returnsNonZeroWhenFinalOutputAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3);

        assertNotEquals(0, result);
    }

    @Test
    void repeatedRunsProduceSameLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, firstOutput, 1, 3));
        assertEquals(0, runLocalSimilarity("cooccurrence", FIXTURE_INPUT, secondOutput, 1, 3));

        assertEquals(readOutputLines(firstOutput), readOutputLines(secondOutput));
    }

    @Test
    void cleansControlledIntermediateOutputAfterSuccess() throws Exception {
        Path output = tempDir.resolve("cleanup-output");
        Path intermediate = tempDir.resolve("cleanup-output-item-similarity-intermediate");

        assertEquals(0, runLocalSimilarity("cosine", FIXTURE_INPUT, output, 1, 3));

        assertFalse(Files.exists(intermediate));
    }

    private int runLocalSimilarity(String method, Path input, Path output, int minCommonUsers, int topL)
            throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new ItemSimilarityPipeline(),
                new String[] {
                    "--local",
                    "--method",
                    method,
                    "--min-common-users",
                    Integer.toString(minCommonUsers),
                    "--top-l",
                    Integer.toString(topL),
                    "--reducers",
                    "1",
                    input.toString(),
                    output.toString()
                });
    }

    private List<String> readOutputLines(Path output) throws Exception {
        return Files.readAllLines(output.resolve("part-r-00000"));
    }

    private List<SimilarityLine> readSimilarityLines(Path output) throws Exception {
        List<SimilarityLine> lines = new ArrayList<>();
        for (String line : readOutputLines(output)) {
            lines.add(parseLine(line));
        }
        return lines;
    }

    private Map<Long, List<SimilarityLine>> readLinesBySource(Path output) throws Exception {
        Map<Long, List<SimilarityLine>> linesBySource = new LinkedHashMap<>();
        for (SimilarityLine line : readSimilarityLines(output)) {
            linesBySource.computeIfAbsent(line.sourceMovieId(), ignored -> new ArrayList<>()).add(line);
        }
        return linesBySource;
    }

    private double sumSimilaritiesForSource(List<SimilarityLine> lines, long sourceMovieId) {
        return lines.stream()
                .filter(line -> line.sourceMovieId() == sourceMovieId)
                .mapToDouble(SimilarityLine::similarity)
                .sum();
    }

    private static SimilarityLine parseLine(String line) {
        String[] fields = line.split("\t", -1);
        assertEquals(2, fields.length);
        String[] pair = fields[0].split(",", -1);
        assertEquals(2, pair.length);
        String[] stats = fields[1].split(",", -1);
        assertEquals(2, stats.length);
        return new SimilarityLine(
                Long.parseLong(pair[0]),
                Long.parseLong(pair[1]),
                Double.parseDouble(stats[0]),
                Long.parseLong(stats[1]));
    }

    private record SimilarityLine(
            long sourceMovieId, long neighborMovieId, double similarity, long commonUsers) {}
}
