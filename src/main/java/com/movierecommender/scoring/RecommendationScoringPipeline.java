package com.movierecommender.scoring;

import com.movierecommender.pairs.UserHistoryRecord;
import java.io.IOException;
import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapred.FileAlreadyExistsException;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.MultipleInputs;
import org.apache.hadoop.mapreduce.lib.input.SequenceFileInputFormat;
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.SequenceFileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Hadoop pipeline that calculates raw Item-CF user-candidate prediction scores. */
public class RecommendationScoringPipeline extends Configured implements Tool {
    private static final String INTERMEDIATE_SUFFIX = "-recommendation-scoring-intermediate";

    /** Counters for the reduce-side join contribution stage. */
    public enum RecommendationScoringJoinCounters {
        USER_HISTORY_ROWS,
        USER_RATING_JOIN_RECORDS,
        SIMILARITY_INPUT_ROWS,
        VALID_SIMILARITY_ROWS,
        SOURCE_MOVIES_JOINED,
        SOURCE_MOVIES_WITHOUT_SIMILARITIES,
        CONTRIBUTIONS_EMITTED
    }

    /** Counters for the final additive aggregation stage. */
    public enum RecommendationScoringAggregationCounters {
        USER_CANDIDATE_KEYS,
        CONTRIBUTIONS_AGGREGATED,
        ZERO_DENOMINATOR_KEYS_SKIPPED,
        PREDICTION_ROWS
    }

    /** Emits one source-movie keyed rating join record per movie in a user history. */
    public static class UserHistoryMapper
            extends Mapper<LongWritable, Text, JoinKeyWritable, JoinValueWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            context.getCounter(RecommendationScoringJoinCounters.USER_HISTORY_ROWS).increment(1L);

            UserHistoryRecord record;
            try {
                record = UserHistoryRecord.parse(value.toString(), "input offset " + key.get());
            } catch (UserHistoryRecord.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            for (UserHistoryRecord.ItemRating rating : record.ratings()) {
                context.write(
                        new JoinKeyWritable(
                                rating.movieId(), JoinKeyWritable.TYPE_RATING, record.userId()),
                        JoinValueWritable.forRating(record.userId(), rating.rating()));
                context.getCounter(RecommendationScoringJoinCounters.USER_RATING_JOIN_RECORDS)
                        .increment(1L);
            }
        }
    }

    /** Emits one source-movie keyed retained neighbor record per directed similarity row. */
    public static class SimilarityMapper
            extends Mapper<LongWritable, Text, JoinKeyWritable, JoinValueWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            context.getCounter(RecommendationScoringJoinCounters.SIMILARITY_INPUT_ROWS).increment(1L);

            DirectedSimilarityRecord record;
            try {
                record = DirectedSimilarityRecord.parse(value.toString(), "input offset " + key.get());
            } catch (DirectedSimilarityRecord.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            context.getCounter(RecommendationScoringJoinCounters.VALID_SIMILARITY_ROWS).increment(1L);
            context.write(
                    new JoinKeyWritable(
                            record.sourceMovieId(),
                            JoinKeyWritable.TYPE_SIMILARITY,
                            record.neighborMovieId()),
                    JoinValueWritable.forSimilarity(
                            record.neighborMovieId(),
                            record.similarity(),
                            record.commonUsers()));
        }
    }

    /** Joins bounded source neighbors with streaming user ratings and emits score contributions. */
    public static class JoinReducer
            extends Reducer<JoinKeyWritable, JoinValueWritable, UserMovieWritable, ScoreContributionWritable> {
        @Override
        protected void reduce(JoinKeyWritable key, Iterable<JoinValueWritable> values, Context context)
                throws IOException, InterruptedException {
            List<NeighborSimilarity> neighbors = new ArrayList<>();
            boolean sawRating = false;
            boolean joinedSourceMovie = false;

            for (JoinValueWritable value : values) {
                if (value.isSimilarity()) {
                    if (sawRating) {
                        throw new IOException("Similarity records must sort before rating records for sourceMovieId="
                                + key.getSourceMovieId());
                    }
                    neighbors.add(new NeighborSimilarity(
                            value.getNeighborMovieId(),
                            value.getSimilarity(),
                            value.getCommonUsers()));
                    continue;
                }

                if (!value.isRating()) {
                    throw new IOException("Unknown join value type: " + value.getRecordType());
                }

                sawRating = true;
                if (neighbors.isEmpty()) {
                    continue;
                }
                if (!joinedSourceMovie) {
                    context.getCounter(RecommendationScoringJoinCounters.SOURCE_MOVIES_JOINED)
                            .increment(1L);
                    joinedSourceMovie = true;
                }
                emitContributions(value.getUserId(), value.getRating(), neighbors, context);
            }

            if (sawRating && neighbors.isEmpty()) {
                context.getCounter(RecommendationScoringJoinCounters.SOURCE_MOVIES_WITHOUT_SIMILARITIES)
                        .increment(1L);
            }
        }

        private static void emitContributions(
                long userId,
                int rating,
                List<NeighborSimilarity> neighbors,
                Context context)
                throws IOException, InterruptedException {
            for (NeighborSimilarity neighbor : neighbors) {
                double numerator = contributionNumerator(neighbor.similarity(), rating);
                double denominator = contributionDenominator(neighbor.similarity());
                context.write(
                        new UserMovieWritable(userId, neighbor.neighborMovieId()),
                        new ScoreContributionWritable(numerator, denominator, 1L));
                context.getCounter(RecommendationScoringJoinCounters.CONTRIBUTIONS_EMITTED)
                        .increment(1L);
            }
        }
    }

    /** Copies typed contribution records into the additive aggregation stage. */
    public static class ContributionMapper
            extends Mapper<UserMovieWritable, ScoreContributionWritable, UserMovieWritable, ScoreContributionWritable> {
        @Override
        protected void map(UserMovieWritable key, ScoreContributionWritable value, Context context)
                throws IOException, InterruptedException {
            context.write(new UserMovieWritable(key), new ScoreContributionWritable(value));
        }
    }

    /** Sums additive contribution fields without calculating final scores. */
    public static class ContributionCombiner
            extends Reducer<UserMovieWritable, ScoreContributionWritable, UserMovieWritable, ScoreContributionWritable> {
        @Override
        protected void reduce(UserMovieWritable key, Iterable<ScoreContributionWritable> values, Context context)
                throws IOException, InterruptedException {
            context.write(key, sumContributions(values));
        }
    }

    /** Sums all contributions and writes final raw prediction score rows. */
    public static class FinalScoreReducer
            extends Reducer<UserMovieWritable, ScoreContributionWritable, Text, Text> {
        @Override
        protected void reduce(UserMovieWritable key, Iterable<ScoreContributionWritable> values, Context context)
                throws IOException, InterruptedException {
            ScoreContributionWritable sum = sumContributions(values);
            context.getCounter(RecommendationScoringAggregationCounters.USER_CANDIDATE_KEYS).increment(1L);
            context.getCounter(RecommendationScoringAggregationCounters.CONTRIBUTIONS_AGGREGATED)
                    .increment(sum.getContributingItems());

            if (sum.getDenominator() == 0.0d) {
                context.getCounter(RecommendationScoringAggregationCounters.ZERO_DENOMINATOR_KEYS_SKIPPED)
                        .increment(1L);
                return;
            }

            double score = score(sum.getNumerator(), sum.getDenominator());
            context.write(new Text(key.toString()), new Text(formatScore(score)));
            context.getCounter(RecommendationScoringAggregationCounters.PREDICTION_ROWS).increment(1L);
        }
    }

    @Override
    public int run(String[] args) throws Exception {
        ParsedArguments parsedArguments = parseArguments(args);
        if (!parsedArguments.valid()) {
            printUsage(System.err);
            return 2;
        }
        if (parsedArguments.helpRequested()) {
            printUsage(System.out);
            return 0;
        }

        Configuration configuration = getConf();
        if (configuration == null) {
            configuration = new Configuration();
            setConf(configuration);
        }
        if (parsedArguments.localMode()) {
            configuration.set("mapreduce.framework.name", "local");
            configuration.set("fs.defaultFS", "file:///");
        }

        Path userHistoryPath = toHadoopPath(parsedArguments.userHistoryInputPath(), parsedArguments.localMode());
        Path similarityPath = toHadoopPath(parsedArguments.similarityInputPath(), parsedArguments.localMode());
        Path outputPath = toHadoopPath(parsedArguments.outputPath(), parsedArguments.localMode());
        Path intermediatePath = intermediatePathFor(outputPath);

        if (!pathExists(userHistoryPath, configuration)) {
            System.err.println("User-history input path does not exist: " + parsedArguments.userHistoryInputPath());
            return 1;
        }
        if (!pathExists(similarityPath, configuration)) {
            System.err.println("Similarity input path does not exist: " + parsedArguments.similarityInputPath());
            return 1;
        }
        if (pathExists(outputPath, configuration)) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        }
        if (pathExists(intermediatePath, configuration)) {
            System.err.println("Intermediate path already exists: " + intermediatePath);
            return 1;
        }
        if (userHistoryPath.equals(outputPath)
                || similarityPath.equals(outputPath)
                || userHistoryPath.equals(intermediatePath)
                || similarityPath.equals(intermediatePath)
                || outputPath.equals(intermediatePath)) {
            System.err.println("Input, output, and intermediate paths must be distinct.");
            return 1;
        }

        boolean pipelineSucceeded = false;
        try {
            if (!runJoinJob(configuration, parsedArguments, userHistoryPath, similarityPath, intermediatePath)) {
                return 1;
            }
            if (!runAggregationJob(configuration, parsedArguments, intermediatePath, outputPath)) {
                return 1;
            }
            pipelineSucceeded = true;
            if (pathExists(intermediatePath, configuration) && !deletePath(intermediatePath, configuration)) {
                System.err.println("Failed to clean intermediate path: " + intermediatePath);
                return 1;
            }
            return 0;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output or intermediate path already exists: " + rootMessage(exception));
            return 1;
        } catch (IOException | ClassNotFoundException exception) {
            System.err.println("Recommendation scoring pipeline failed: " + rootMessage(exception));
            return 1;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            System.err.println("Recommendation scoring pipeline interrupted: " + rootMessage(exception));
            return 1;
        } finally {
            if (!pipelineSucceeded) {
                System.err.println("Preserving intermediate output for diagnosis when present: " + intermediatePath);
            }
        }
    }

    public static double contributionNumerator(double similarity, int rating) {
        return similarity * rating;
    }

    public static double contributionDenominator(double similarity) {
        return Math.abs(similarity);
    }

    public static double score(double numerator, double denominator) {
        if (denominator == 0.0d) {
            return Double.NaN;
        }
        return numerator / denominator;
    }

    public static String formatScore(double score) {
        return String.format(Locale.ROOT, "%.10f", score);
    }

    static Path intermediatePathFor(Path outputPath) {
        Path parent = outputPath.getParent();
        String intermediateName = outputPath.getName() + INTERMEDIATE_SUFFIX;
        return parent == null ? new Path(intermediateName) : new Path(parent, intermediateName);
    }

    private static boolean runJoinJob(
            Configuration configuration,
            ParsedArguments parsedArguments,
            Path userHistoryPath,
            Path similarityPath,
            Path intermediatePath)
            throws IOException, InterruptedException, ClassNotFoundException {
        Job job = Job.getInstance(configuration, "recommendation-scoring-join");
        job.setJarByClass(RecommendationScoringPipeline.class);
        job.setReducerClass(JoinReducer.class);
        job.setPartitionerClass(SourceMoviePartitioner.class);
        job.setGroupingComparatorClass(SourceMovieGroupingComparator.class);
        job.setMapOutputKeyClass(JoinKeyWritable.class);
        job.setMapOutputValueClass(JoinValueWritable.class);
        job.setOutputKeyClass(UserMovieWritable.class);
        job.setOutputValueClass(ScoreContributionWritable.class);
        job.setOutputFormatClass(SequenceFileOutputFormat.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        MultipleInputs.addInputPath(job, userHistoryPath, TextInputFormat.class, UserHistoryMapper.class);
        MultipleInputs.addInputPath(job, similarityPath, TextInputFormat.class, SimilarityMapper.class);
        SequenceFileOutputFormat.setOutputPath(job, intermediatePath);

        return job.waitForCompletion(true);
    }

    private static boolean runAggregationJob(
            Configuration configuration,
            ParsedArguments parsedArguments,
            Path intermediatePath,
            Path outputPath)
            throws IOException, InterruptedException, ClassNotFoundException {
        Job job = Job.getInstance(configuration, "recommendation-scoring-aggregate");
        job.setJarByClass(RecommendationScoringPipeline.class);
        job.setMapperClass(ContributionMapper.class);
        job.setCombinerClass(ContributionCombiner.class);
        job.setReducerClass(FinalScoreReducer.class);
        job.setInputFormatClass(SequenceFileInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setMapOutputKeyClass(UserMovieWritable.class);
        job.setMapOutputValueClass(ScoreContributionWritable.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        SequenceFileInputFormat.addInputPath(job, intermediatePath);
        TextOutputFormat.setOutputPath(job, outputPath);

        return job.waitForCompletion(true);
    }

    private static ScoreContributionWritable sumContributions(Iterable<ScoreContributionWritable> values) {
        ScoreContributionWritable sum = new ScoreContributionWritable();
        for (ScoreContributionWritable value : values) {
            sum.add(value);
        }
        return sum;
    }

    private static boolean pathExists(Path path, Configuration configuration) throws IOException {
        FileSystem fileSystem = path.getFileSystem(configuration);
        return fileSystem.exists(path);
    }

    private static boolean deletePath(Path path, Configuration configuration) throws IOException {
        FileSystem fileSystem = path.getFileSystem(configuration);
        return fileSystem.delete(path, true);
    }

    private static Path toHadoopPath(String value, boolean localMode) {
        if (!localMode) {
            return new Path(value);
        }
        URI localUri = Paths.get(value).toAbsolutePath().normalize().toUri();
        return new Path(localUri);
    }

    private static ParsedArguments parseArguments(String[] args) {
        if (args == null) {
            return ParsedArguments.invalid();
        }

        boolean localMode = false;
        boolean helpRequested = false;
        int reducers = 1;
        List<String> positional = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            String arg = args[index];
            if ("--local".equals(arg)) {
                localMode = true;
            } else if ("--reducers".equals(arg)) {
                if (index + 1 >= args.length) {
                    return ParsedArguments.invalid();
                }
                try {
                    reducers = Integer.parseInt(args[++index]);
                } catch (NumberFormatException exception) {
                    return ParsedArguments.invalid();
                }
                if (reducers < 1) {
                    return ParsedArguments.invalid();
                }
            } else if ("--help".equals(arg) || "-h".equals(arg)) {
                helpRequested = true;
            } else if (arg.startsWith("-")) {
                return ParsedArguments.invalid();
            } else {
                positional.add(arg);
            }
        }

        if (helpRequested) {
            return ParsedArguments.help();
        }
        if (positional.size() != 3) {
            return ParsedArguments.invalid();
        }
        return new ParsedArguments(
                localMode,
                false,
                true,
                reducers,
                positional.get(0),
                positional.get(1),
                positional.get(2));
    }

    private static void printUsage(PrintStream output) {
        output.println(
                "Usage: RecommendationScoringPipeline "
                        + "[--local] [--reducers N] <user-history-input> <similarity-input> <output-path>");
        output.println("Writes raw prediction rows: userId,movieId<TAB>score");
    }

    private static String rootMessage(Throwable throwable) {
        Throwable current = throwable;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return message == null || message.isBlank() ? current.getClass().getSimpleName() : message;
    }

    /** Entry point for command-line execution through ToolRunner. */
    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new RecommendationScoringPipeline(), args);
        System.exit(exitCode);
    }

    private record NeighborSimilarity(long neighborMovieId, double similarity, long commonUsers) {}

    private record ParsedArguments(
            boolean localMode,
            boolean helpRequested,
            boolean valid,
            int reducers,
            String userHistoryInputPath,
            String similarityInputPath,
            String outputPath) {
        static ParsedArguments invalid() {
            return new ParsedArguments(false, false, false, 1, "", "", "");
        }

        static ParsedArguments help() {
            return new ParsedArguments(false, true, true, 1, "", "", "");
        }
    }
}
