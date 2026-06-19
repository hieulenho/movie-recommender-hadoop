package com.movierecommender.smoke;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.util.ToolRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LineCountJobTest {
    private static final Path FIXTURE_INPUT =
            Path.of("tests", "fixtures", "hadoop-smoke", "input.txt");

    @TempDir
    Path tempDir;

    @Test
    void rejectsMissingCommandLineArguments() throws Exception {
        int result = ToolRunner.run(new Configuration(), new LineCountJob(), new String[] {"--local"});
        assertNotEquals(0, result);
    }

    @Test
    void rejectsTooManyPositionalArguments() throws Exception {
        int result = ToolRunner.run(
                new Configuration(),
                new LineCountJob(),
                new String[] {"--local", "input", "output", "extra"});
        assertNotEquals(0, result);
    }

    @Test
    void runsActualHadoopJobInLocalMode() throws Exception {
        Path output = tempDir.resolve("line-count-output");

        int result = runLocalSmokeJob(output);

        assertEquals(0, result);
        assertTrue(Files.isDirectory(output));
        assertTrue(Files.isRegularFile(output.resolve("_SUCCESS")));
        assertTrue(Files.isRegularFile(output.resolve("part-r-00000")));
        assertEquals("lineCount\t5", Files.readString(output.resolve("part-r-00000")).strip());
    }

    @Test
    void returnsNonZeroWhenOutputPathAlreadyExists() throws Exception {
        Path output = tempDir.resolve("existing-output");
        Files.createDirectories(output);

        int result = runLocalSmokeJob(output);

        assertNotEquals(0, result);
    }

    @Test
    void localModeConfigurationDoesNotRequireMachineSpecificPaths() throws Exception {
        Path output = tempDir.resolve("deterministic-output");
        int result = runLocalSmokeJob(output);

        assertEquals(0, result);
        assertFalse(output.toString().isBlank());
        assertEquals("lineCount\t5", Files.readString(output.resolve("part-r-00000")).strip());
    }

    @Test
    void repeatedLocalRunsProduceTheSameLogicalOutput() throws Exception {
        Path firstOutput = tempDir.resolve("first-output");
        Path secondOutput = tempDir.resolve("second-output");

        assertEquals(0, runLocalSmokeJob(firstOutput));
        assertEquals(0, runLocalSmokeJob(secondOutput));

        assertEquals(
                Files.readString(firstOutput.resolve("part-r-00000")).strip(),
                Files.readString(secondOutput.resolve("part-r-00000")).strip());
    }

    private int runLocalSmokeJob(Path output) throws Exception {
        return ToolRunner.run(
                new Configuration(),
                new LineCountJob(),
                new String[] {"--local", FIXTURE_INPUT.toString(), output.toString()});
    }
}
