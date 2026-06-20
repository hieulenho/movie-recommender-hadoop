package com.movierecommender.recommendation;

import com.movierecommender.pairs.UserHistoryRecord;
import java.io.IOException;
import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.PriorityQueue;
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
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Hadoop job that filters watched movies and emits deterministic Top-K recommendation lists. */
public class TopKRecommendationJob extends Configured implements Tool {
    private static final String TOP_K_CONF = "movie.recommender.recommendation.topK";

    /** Counters for watched-item filtering and Top-K recommendation selection. */
    public enum TopKRecommendationCounters {
        USER_HISTORY_ROWS,
        EXACT_DUPLICATE_HISTORIES_IGNORED,
        RAW_PREDICTION_ROWS,
        EXACT_DUPLICATE_PREDICTIONS_IGNORED,
        USERS_PROCESSED,
        USERS_WITHOUT_PREDICTIONS,
        PREDICTIONS_FILTERED_AS_WATCHED,
        UNSEEN_CANDIDATES_CONSIDERED,
        CANDIDATES_DISCARDED_BY_TOP_K,
        USERS_WITH_NO_UNSEEN_CANDIDATES,
        USERS_EMITTED,
        RECOMMENDATIONS_EMITTED
    }

    /** Emits one complete watched-history join value keyed by user ID. */
    public static class UserHistoryMapper
            extends Mapper<LongWritable, Text, RecommendationJoinKeyWritable, RecommendationJoinValueWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            UserHistoryRecord record;
            try {
                record = UserHistoryRecord.parse(value.toString(), "input offset " + key.get());
            } catch (UserHistoryRecord.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            context.getCounter(TopKRecommendationCounters.USER_HISTORY_ROWS).increment(1L);
            context.write(
                    new RecommendationJoinKeyWritable(
                            record.userId(), RecommendationJoinKeyWritable.TYPE_HISTORY, 0L),
                    RecommendationJoinValueWritable.forHistory(movieIds(record), ratings(record)));
        }
    }

    /** Emits one raw candidate score join value keyed by user ID. */
    public static class RawPredictionMapper
            extends Mapper<LongWritable, Text, RecommendationJoinKeyWritable, RecommendationJoinValueWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            RawPredictionRecord record;
            try {
                record = RawPredictionRecord.parse(value.toString(), "input offset " + key.get());
            } catch (RawPredictionRecord.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            context.getCounter(TopKRecommendationCounters.RAW_PREDICTION_ROWS).increment(1L);
            context.write(
                    new RecommendationJoinKeyWritable(
                            record.userId(), RecommendationJoinKeyWritable.TYPE_PREDICTION, record.movieId()),
                    RecommendationJoinValueWritable.forPrediction(record.movieId(), record.score()));
        }
    }

    /** Filters watched movies, keeps bounded Top-K candidates, and writes final recommendation lists. */
    public static class TopKRecommendationReducer
            extends Reducer<RecommendationJoinKeyWritable, RecommendationJoinValueWritable, Text, Text> {
        @Override
        protected void reduce(
                RecommendationJoinKeyWritable key,
                Iterable<RecommendationJoinValueWritable> values,
                Context context)
                throws IOException, InterruptedException {
            int topK = context.getConfiguration().getInt(TOP_K_CONF, 10);
            context.getCounter(TopKRecommendationCounters.USERS_PROCESSED).increment(1L);

            long[] watchedMovieIds = null;
            int[] watchedRatings = null;
            boolean sawPrediction = false;
            Long previousPredictionMovieId = null;
            double previousPredictionScore = 0.0d;
            PriorityQueue<RecommendationCandidate> top = new PriorityQueue<>(topK, RecommendationCandidate.WORST_FIRST);

            for (RecommendationJoinValueWritable value : values) {
                if (value.isHistory()) {
                    if (sawPrediction) {
                        throw new IOException("History records must sort before prediction records for userId="
                                + key.getUserId());
                    }
                    long[] currentMovieIds = value.getWatchedMovieIds();
                    int[] currentRatings = value.getWatchedRatings();
                    if (watchedMovieIds == null) {
                        watchedMovieIds = currentMovieIds;
                        watchedRatings = currentRatings;
                    } else if (Arrays.equals(watchedMovieIds, currentMovieIds)
                            && Arrays.equals(watchedRatings, currentRatings)) {
                        context.getCounter(TopKRecommendationCounters.EXACT_DUPLICATE_HISTORIES_IGNORED)
                                .increment(1L);
                    } else {
                        throw new IOException("Conflicting user histories for userId=" + key.getUserId() + ".");
                    }
                    continue;
                }

                if (!value.isPrediction()) {
                    throw new IOException("Unknown recommendation join value type: " + value.getRecordType());
                }
                sawPrediction = true;
                if (watchedMovieIds == null) {
                    throw new IOException("Raw prediction has no matching user history for userId=" + key.getUserId());
                }

                long candidateMovieId = value.getMovieId();
                double score = value.getScore();
                if (previousPredictionMovieId != null && previousPredictionMovieId == candidateMovieId) {
                    if (Double.compare(previousPredictionScore, score) == 0) {
                        context.getCounter(TopKRecommendationCounters.EXACT_DUPLICATE_PREDICTIONS_IGNORED)
                                .increment(1L);
                        continue;
                    }
                    throw new IOException(
                            "Conflicting raw predictions for userId="
                                    + key.getUserId()
                                    + ", movieId="
                                    + candidateMovieId
                                    + ".");
                }
                previousPredictionMovieId = candidateMovieId;
                previousPredictionScore = score;

                if (isWatched(watchedMovieIds, candidateMovieId)) {
                    context.getCounter(TopKRecommendationCounters.PREDICTIONS_FILTERED_AS_WATCHED)
                            .increment(1L);
                    continue;
                }

                context.getCounter(TopKRecommendationCounters.UNSEEN_CANDIDATES_CONSIDERED).increment(1L);
                OfferResult offerResult = offerCandidate(
                        top,
                        topK,
                        new RecommendationCandidate(candidateMovieId, score));
                if (offerResult.discardedByTopK()) {
                    context.getCounter(TopKRecommendationCounters.CANDIDATES_DISCARDED_BY_TOP_K)
                            .increment(1L);
                }
            }

            if (watchedMovieIds == null) {
                throw new IOException("User group has no history record for userId=" + key.getUserId() + ".");
            }
            if (!sawPrediction) {
                context.getCounter(TopKRecommendationCounters.USERS_WITHOUT_PREDICTIONS).increment(1L);
                return;
            }
            if (top.isEmpty()) {
                context.getCounter(TopKRecommendationCounters.USERS_WITH_NO_UNSEEN_CANDIDATES).increment(1L);
                return;
            }

            List<RecommendationCandidate> retained = finalOrder(top);
            context.write(new Text(Long.toString(key.getUserId())), new Text(formatRecommendationList(retained)));
            context.getCounter(TopKRecommendationCounters.USERS_EMITTED).increment(1L);
            context.getCounter(TopKRecommendationCounters.RECOMMENDATIONS_EMITTED).increment(retained.size());
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
        configuration.setInt(TOP_K_CONF, parsedArguments.topK());

        Path userHistoryPath = toHadoopPath(parsedArguments.userHistoryInputPath(), parsedArguments.localMode());
        Path rawPredictionPath = toHadoopPath(parsedArguments.rawPredictionInputPath(), parsedArguments.localMode());
        Path outputPath = toHadoopPath(parsedArguments.outputPath(), parsedArguments.localMode());

        if (!pathExists(userHistoryPath, configuration)) {
            System.err.println("User-history input path does not exist: " + parsedArguments.userHistoryInputPath());
            return 1;
        }
        if (!pathExists(rawPredictionPath, configuration)) {
            System.err.println("Raw-prediction input path does not exist: " + parsedArguments.rawPredictionInputPath());
            return 1;
        }
        if (pathExists(outputPath, configuration)) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        }
        if (userHistoryPath.equals(rawPredictionPath)
                || userHistoryPath.equals(outputPath)
                || rawPredictionPath.equals(outputPath)) {
            System.err.println("Input and output paths must be distinct.");
            return 1;
        }

        Job job = Job.getInstance(configuration, "top-k-recommendations");
        job.setJarByClass(TopKRecommendationJob.class);
        job.setReducerClass(TopKRecommendationReducer.class);
        job.setPartitionerClass(UserPartitioner.class);
        job.setGroupingComparatorClass(UserGroupingComparator.class);
        job.setMapOutputKeyClass(RecommendationJoinKeyWritable.class);
        job.setMapOutputValueClass(RecommendationJoinValueWritable.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        MultipleInputs.addInputPath(job, userHistoryPath, TextInputFormat.class, UserHistoryMapper.class);
        MultipleInputs.addInputPath(job, rawPredictionPath, TextInputFormat.class, RawPredictionMapper.class);
        TextOutputFormat.setOutputPath(job, outputPath);

        try {
            return job.waitForCompletion(true) ? 0 : 1;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        } catch (IOException | ClassNotFoundException exception) {
            System.err.println("Top-K recommendation job failed: " + rootMessage(exception));
            return 1;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            System.err.println("Top-K recommendation job interrupted: " + rootMessage(exception));
            return 1;
        }
    }

    public static List<RecommendationCandidate> retainTopK(
            Iterable<RecommendationCandidate> candidates, int topK) {
        if (topK < 1) {
            throw new IllegalArgumentException("topK must be at least 1.");
        }
        PriorityQueue<RecommendationCandidate> top = new PriorityQueue<>(topK, RecommendationCandidate.WORST_FIRST);
        for (RecommendationCandidate candidate : candidates) {
            offerCandidate(top, topK, candidate);
        }
        return finalOrder(top);
    }

    public static OfferResult offerCandidate(
            PriorityQueue<RecommendationCandidate> top, int topK, RecommendationCandidate candidate) {
        if (topK < 1) {
            throw new IllegalArgumentException("topK must be at least 1.");
        }
        if (top.size() < topK) {
            top.add(candidate);
            return OfferResult.RETAINED_WITHOUT_DISCARD;
        }

        RecommendationCandidate worst = top.peek();
        if (worst != null && candidate.isBetterThan(worst)) {
            top.poll();
            top.add(candidate);
            return OfferResult.RETAINED_AND_DISCARDED_PREVIOUS;
        }
        return OfferResult.REJECTED_CANDIDATE;
    }

    public static String formatRecommendationList(List<RecommendationCandidate> candidates) {
        StringBuilder builder = new StringBuilder();
        for (RecommendationCandidate candidate : candidates) {
            if (builder.length() > 0) {
                builder.append(',');
            }
            builder.append(candidate);
        }
        return builder.toString();
    }

    public static boolean isWatched(long[] watchedMovieIds, long candidateMovieId) {
        return Arrays.binarySearch(watchedMovieIds, candidateMovieId) >= 0;
    }

    private static List<RecommendationCandidate> finalOrder(PriorityQueue<RecommendationCandidate> top) {
        List<RecommendationCandidate> retained = new ArrayList<>(top);
        retained.sort(RecommendationCandidate.FINAL_ORDER);
        return retained;
    }

    private static long[] movieIds(UserHistoryRecord record) {
        return record.ratings().stream().mapToLong(UserHistoryRecord.ItemRating::movieId).toArray();
    }

    private static int[] ratings(UserHistoryRecord record) {
        return record.ratings().stream().mapToInt(UserHistoryRecord.ItemRating::rating).toArray();
    }

    private static boolean pathExists(Path path, Configuration configuration) throws IOException {
        FileSystem fileSystem = path.getFileSystem(configuration);
        return fileSystem.exists(path);
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
        int topK = 10;
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
            } else if ("--top-k".equals(arg)) {
                if (index + 1 >= args.length) {
                    return ParsedArguments.invalid();
                }
                try {
                    topK = Integer.parseInt(args[++index]);
                } catch (NumberFormatException exception) {
                    return ParsedArguments.invalid();
                }
                if (topK < 1) {
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
                topK,
                positional.get(0),
                positional.get(1),
                positional.get(2));
    }

    private static void printUsage(PrintStream output) {
        output.println(
                "Usage: TopKRecommendationJob "
                        + "[--local] [--reducers N] [--top-k K] "
                        + "<user-history-input> <raw-prediction-input> <output-path>");
        output.println("Writes final recommendations: userId<TAB>movieId:score,movieId:score");
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
        int exitCode = ToolRunner.run(new TopKRecommendationJob(), args);
        System.exit(exitCode);
    }

    public enum OfferResult {
        RETAINED_WITHOUT_DISCARD(false),
        RETAINED_AND_DISCARDED_PREVIOUS(true),
        REJECTED_CANDIDATE(true);

        private final boolean discardedByTopK;

        OfferResult(boolean discardedByTopK) {
            this.discardedByTopK = discardedByTopK;
        }

        public boolean discardedByTopK() {
            return discardedByTopK;
        }
    }

    private record ParsedArguments(
            boolean localMode,
            boolean helpRequested,
            boolean valid,
            int reducers,
            int topK,
            String userHistoryInputPath,
            String rawPredictionInputPath,
            String outputPath) {
        static ParsedArguments invalid() {
            return new ParsedArguments(false, false, false, 1, 10, "", "", "");
        }

        static ParsedArguments help() {
            return new ParsedArguments(false, true, true, 1, 10, "", "", "");
        }
    }
}
