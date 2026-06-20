package com.movierecommender.similarity;

import java.io.IOException;
import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.TreeMap;
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
import org.apache.hadoop.mapreduce.lib.input.SequenceFileInputFormat;
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.SequenceFileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Hadoop pipeline that converts item-pair statistics into directed Top-L similarities. */
public class ItemSimilarityPipeline extends Configured implements Tool {
    private static final String METHOD_CONF = "movie.recommender.similarity.method";
    private static final String MIN_COMMON_USERS_CONF = "movie.recommender.similarity.minCommonUsers";
    private static final String TOP_L_CONF = "movie.recommender.similarity.topL";
    private static final String INTERMEDIATE_SUFFIX = "-item-similarity-intermediate";

    /** Counters for validating item-similarity and Top-L neighbor generation. */
    public enum ItemSimilarityCounters {
        INPUT_PAIR_ROWS,
        VALID_PAIR_ROWS,
        PAIRS_FILTERED_BY_MIN_COMMON_USERS,
        DIRECTED_RELATIONS_CREATED,
        ZERO_DENOMINATOR_RELATIONS_SKIPPED,
        SOURCE_ITEMS,
        DIRECTED_RELATIONS_BEFORE_TOP_L,
        DIRECTED_RELATIONS_AFTER_TOP_L
    }

    /** Parses eligible pair-stat rows and emits directed cosine similarities. */
    public static class CosineSimilarityMapper
            extends Mapper<LongWritable, Text, LongWritable, SimilarityRelationWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            PairStatisticsRecord record = parseAndFilterRecord(key, value, context);
            if (record == null) {
                return;
            }

            double denominator = cosineDenominator(record);
            if (denominator == 0.0d) {
                context.getCounter(ItemSimilarityCounters.ZERO_DENOMINATOR_RELATIONS_SKIPPED)
                        .increment(2L);
                return;
            }

            double similarity = record.sumXY() / denominator;
            writeSimilarity(
                    context,
                    record.firstMovieId(),
                    record.secondMovieId(),
                    similarity,
                    record.commonUsers());
            writeSimilarity(
                    context,
                    record.secondMovieId(),
                    record.firstMovieId(),
                    similarity,
                    record.commonUsers());
        }
    }

    /** Parses eligible pair-stat rows and emits directed common-user counts. */
    public static class CooccurrencePairMapper
            extends Mapper<LongWritable, Text, LongWritable, DirectedPairStatsWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            PairStatisticsRecord record = parseAndFilterRecord(key, value, context);
            if (record == null) {
                return;
            }

            writePairStats(context, record.firstMovieId(), record.secondMovieId(), record.commonUsers());
            writePairStats(context, record.secondMovieId(), record.firstMovieId(), record.commonUsers());
        }
    }

    /** Calculates row-normalized co-occurrence similarities for one source movie. */
    public static class CooccurrenceNormalizeReducer
            extends Reducer<LongWritable, DirectedPairStatsWritable, LongWritable, SimilarityRelationWritable> {
        @Override
        protected void reduce(LongWritable key, Iterable<DirectedPairStatsWritable> values, Context context)
                throws IOException, InterruptedException {
            List<DirectedPairStatsWritable> relations = new ArrayList<>();
            long denominator = 0L;
            for (DirectedPairStatsWritable value : values) {
                DirectedPairStatsWritable copy = new DirectedPairStatsWritable(value);
                relations.add(copy);
                denominator += copy.getCommonUsers();
            }

            if (denominator <= 0L) {
                context.getCounter(ItemSimilarityCounters.ZERO_DENOMINATOR_RELATIONS_SKIPPED)
                        .increment(relations.size());
                return;
            }

            for (DirectedPairStatsWritable relation : relations) {
                double similarity = cooccurrenceSimilarity(relation.getCommonUsers(), denominator);
                context.write(
                        new LongWritable(relation.getSourceMovieId()),
                        new SimilarityRelationWritable(
                                relation.getSourceMovieId(),
                                relation.getNeighborMovieId(),
                                similarity,
                                relation.getCommonUsers()));
            }
        }
    }

    /** Copies SequenceFile similarity records into the final Top-L reducer. */
    public static class TopLMapper
            extends Mapper<LongWritable, SimilarityRelationWritable, LongWritable, SimilarityRelationWritable> {
        @Override
        protected void map(LongWritable key, SimilarityRelationWritable value, Context context)
                throws IOException, InterruptedException {
            context.write(new LongWritable(key.get()), new SimilarityRelationWritable(value));
        }
    }

    /** Retains deterministic Top-L neighbors per source movie and writes final text rows. */
    public static class TopLReducer extends Reducer<LongWritable, SimilarityRelationWritable, Text, Text> {
        private static final Comparator<SimilarityRelationWritable> WORST_FIRST =
                (left, right) -> {
                    int similarityComparison = Double.compare(left.getSimilarity(), right.getSimilarity());
                    if (similarityComparison != 0) {
                        return similarityComparison;
                    }
                    return Long.compare(right.getNeighborMovieId(), left.getNeighborMovieId());
                };

        @Override
        protected void reduce(LongWritable key, Iterable<SimilarityRelationWritable> values, Context context)
                throws IOException, InterruptedException {
            int topL = context.getConfiguration().getInt(TOP_L_CONF, 50);
            context.getCounter(ItemSimilarityCounters.SOURCE_ITEMS).increment(1L);

            PriorityQueue<SimilarityRelationWritable> top = new PriorityQueue<>(topL, WORST_FIRST);
            Map<Long, SimilarityRelationWritable> retainedByNeighbor = new TreeMap<>();
            for (SimilarityRelationWritable value : values) {
                context.getCounter(ItemSimilarityCounters.DIRECTED_RELATIONS_BEFORE_TOP_L).increment(1L);
                if (value.getSourceMovieId() == value.getNeighborMovieId()) {
                    continue;
                }
                offerCandidate(new SimilarityRelationWritable(value), topL, top, retainedByNeighbor);
            }

            List<SimilarityRelationWritable> retained = new ArrayList<>(top);
            retained.sort(SimilarityRelationWritable::compareTo);
            for (SimilarityRelationWritable relation : retained) {
                context.write(
                        new Text(relation.getSourceMovieId() + "," + relation.getNeighborMovieId()),
                        new Text(
                                SimilarityRelationWritable.formatSimilarity(relation.getSimilarity())
                                        + ","
                                        + relation.getCommonUsers()));
                context.getCounter(ItemSimilarityCounters.DIRECTED_RELATIONS_AFTER_TOP_L).increment(1L);
            }
        }

        private static void offerCandidate(
                SimilarityRelationWritable candidate,
                int topL,
                PriorityQueue<SimilarityRelationWritable> top,
                Map<Long, SimilarityRelationWritable> retainedByNeighbor) {
            SimilarityRelationWritable retained = retainedByNeighbor.get(candidate.getNeighborMovieId());
            if (retained != null) {
                if (isBetter(candidate, retained)) {
                    top.remove(retained);
                    retainedByNeighbor.put(candidate.getNeighborMovieId(), candidate);
                    top.add(candidate);
                }
                return;
            }

            if (top.size() < topL) {
                retainedByNeighbor.put(candidate.getNeighborMovieId(), candidate);
                top.add(candidate);
                return;
            }

            SimilarityRelationWritable worst = top.peek();
            if (worst != null && isBetter(candidate, worst)) {
                top.poll();
                retainedByNeighbor.remove(worst.getNeighborMovieId());
                retainedByNeighbor.put(candidate.getNeighborMovieId(), candidate);
                top.add(candidate);
            }
        }

        private static boolean isBetter(SimilarityRelationWritable left, SimilarityRelationWritable right) {
            int similarityComparison = Double.compare(left.getSimilarity(), right.getSimilarity());
            if (similarityComparison != 0) {
                return similarityComparison > 0;
            }
            return left.getNeighborMovieId() < right.getNeighborMovieId();
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
        configuration.set(METHOD_CONF, parsedArguments.method().cliName());
        configuration.setLong(MIN_COMMON_USERS_CONF, parsedArguments.minCommonUsers());
        configuration.setInt(TOP_L_CONF, parsedArguments.topL());

        Path inputPath = toHadoopPath(parsedArguments.inputPath(), parsedArguments.localMode());
        Path outputPath = toHadoopPath(parsedArguments.outputPath(), parsedArguments.localMode());
        Path intermediatePath = intermediatePathFor(outputPath);

        if (!pathExists(inputPath, configuration)) {
            System.err.println("Input path does not exist: " + parsedArguments.inputPath());
            return 1;
        }
        if (pathExists(outputPath, configuration)) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        }
        if (inputPath.equals(outputPath) || inputPath.equals(intermediatePath) || outputPath.equals(intermediatePath)) {
            System.err.println("Input, output, and intermediate paths must be distinct.");
            return 1;
        }
        if (pathExists(intermediatePath, configuration)) {
            System.err.println("Intermediate path already exists: " + intermediatePath);
            return 1;
        }

        boolean pipelineSucceeded = false;
        try {
            if (!runDirectedSimilarityJob(configuration, parsedArguments, inputPath, intermediatePath)) {
                return 1;
            }
            if (!runTopLJob(configuration, parsedArguments, intermediatePath, outputPath)) {
                return 1;
            }
            pipelineSucceeded = true;
            if (!deletePath(intermediatePath, configuration)) {
                System.err.println("Failed to clean intermediate path: " + intermediatePath);
                return 1;
            }
            return 0;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output or intermediate path already exists: " + rootMessage(exception));
            return 1;
        } catch (IOException | ClassNotFoundException exception) {
            System.err.println("Item similarity pipeline failed: " + rootMessage(exception));
            return 1;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            System.err.println("Item similarity pipeline interrupted: " + rootMessage(exception));
            return 1;
        } finally {
            if (!pipelineSucceeded) {
                System.err.println("Preserving intermediate output for diagnosis when present: " + intermediatePath);
            }
        }
    }

    public static double cosineSimilarity(PairStatisticsRecord record) {
        double denominator = cosineDenominator(record);
        if (denominator == 0.0d) {
            return Double.NaN;
        }
        return record.sumXY() / denominator;
    }

    public static double cooccurrenceSimilarity(long commonUsers, long denominator) {
        if (denominator <= 0L) {
            return Double.NaN;
        }
        return commonUsers / (double) denominator;
    }

    private static PairStatisticsRecord parseAndFilterRecord(
            LongWritable key, Text value, Mapper<?, ?, ?, ?>.Context context) throws IOException {
        context.getCounter(ItemSimilarityCounters.INPUT_PAIR_ROWS).increment(1L);

        PairStatisticsRecord record;
        try {
            record = PairStatisticsRecord.parse(value.toString(), "input offset " + key.get());
        } catch (PairStatisticsRecord.ValidationException exception) {
            throw new IOException(exception.getMessage(), exception);
        }

        context.getCounter(ItemSimilarityCounters.VALID_PAIR_ROWS).increment(1L);
        long minCommonUsers = context.getConfiguration().getLong(MIN_COMMON_USERS_CONF, 1L);
        if (record.commonUsers() < minCommonUsers) {
            context.getCounter(ItemSimilarityCounters.PAIRS_FILTERED_BY_MIN_COMMON_USERS).increment(1L);
            return null;
        }
        return record;
    }

    private static void writeSimilarity(
            Mapper<LongWritable, Text, LongWritable, SimilarityRelationWritable>.Context context,
            long sourceMovieId,
            long neighborMovieId,
            double similarity,
            long commonUsers)
            throws IOException, InterruptedException {
        context.write(
                new LongWritable(sourceMovieId),
                new SimilarityRelationWritable(sourceMovieId, neighborMovieId, similarity, commonUsers));
        context.getCounter(ItemSimilarityCounters.DIRECTED_RELATIONS_CREATED).increment(1L);
    }

    private static void writePairStats(
            Mapper<LongWritable, Text, LongWritable, DirectedPairStatsWritable>.Context context,
            long sourceMovieId,
            long neighborMovieId,
            long commonUsers)
            throws IOException, InterruptedException {
        context.write(
                new LongWritable(sourceMovieId),
                new DirectedPairStatsWritable(sourceMovieId, neighborMovieId, commonUsers));
        context.getCounter(ItemSimilarityCounters.DIRECTED_RELATIONS_CREATED).increment(1L);
    }

    private static double cosineDenominator(PairStatisticsRecord record) {
        return Math.sqrt((double) record.sumX2() * (double) record.sumY2());
    }

    private static boolean runDirectedSimilarityJob(
            Configuration configuration, ParsedArguments parsedArguments, Path inputPath, Path intermediatePath)
            throws IOException, InterruptedException, ClassNotFoundException {
        Job job = Job.getInstance(configuration, "item-similarity-directed-" + parsedArguments.method().cliName());
        job.setJarByClass(ItemSimilarityPipeline.class);
        job.setInputFormatClass(TextInputFormat.class);
        job.setOutputFormatClass(SequenceFileOutputFormat.class);
        TextInputFormat.addInputPath(job, inputPath);
        SequenceFileOutputFormat.setOutputPath(job, intermediatePath);

        job.setOutputKeyClass(LongWritable.class);
        job.setOutputValueClass(SimilarityRelationWritable.class);

        if (parsedArguments.method() == SimilarityMethod.COSINE) {
            job.setMapperClass(CosineSimilarityMapper.class);
            job.setMapOutputKeyClass(LongWritable.class);
            job.setMapOutputValueClass(SimilarityRelationWritable.class);
            job.setNumReduceTasks(0);
        } else {
            job.setMapperClass(CooccurrencePairMapper.class);
            job.setReducerClass(CooccurrenceNormalizeReducer.class);
            job.setMapOutputKeyClass(LongWritable.class);
            job.setMapOutputValueClass(DirectedPairStatsWritable.class);
            job.setNumReduceTasks(parsedArguments.reducers());
        }

        return job.waitForCompletion(true);
    }

    private static boolean runTopLJob(
            Configuration configuration, ParsedArguments parsedArguments, Path intermediatePath, Path outputPath)
            throws IOException, InterruptedException, ClassNotFoundException {
        Job job = Job.getInstance(configuration, "item-similarity-top-l");
        job.setJarByClass(ItemSimilarityPipeline.class);
        job.setMapperClass(TopLMapper.class);
        job.setReducerClass(TopLReducer.class);
        job.setInputFormatClass(SequenceFileInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setMapOutputKeyClass(LongWritable.class);
        job.setMapOutputValueClass(SimilarityRelationWritable.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(Text.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        SequenceFileInputFormat.addInputPath(job, intermediatePath);
        TextOutputFormat.setOutputPath(job, outputPath);

        return job.waitForCompletion(true);
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

    static Path intermediatePathFor(Path outputPath) {
        Path parent = outputPath.getParent();
        String intermediateName = outputPath.getName() + INTERMEDIATE_SUFFIX;
        return parent == null ? new Path(intermediateName) : new Path(parent, intermediateName);
    }

    private static ParsedArguments parseArguments(String[] args) {
        if (args == null) {
            return ParsedArguments.invalid();
        }

        boolean localMode = false;
        boolean helpRequested = false;
        SimilarityMethod method = null;
        long minCommonUsers = 1L;
        int topL = 50;
        int reducers = 1;
        List<String> positional = new ArrayList<>();
        for (int index = 0; index < args.length; index++) {
            String arg = args[index];
            if ("--local".equals(arg)) {
                localMode = true;
            } else if ("--method".equals(arg)) {
                if (index + 1 >= args.length) {
                    return ParsedArguments.invalid();
                }
                try {
                    method = SimilarityMethod.parse(args[++index]);
                } catch (IllegalArgumentException exception) {
                    return ParsedArguments.invalid();
                }
            } else if ("--min-common-users".equals(arg)) {
                if (index + 1 >= args.length) {
                    return ParsedArguments.invalid();
                }
                try {
                    minCommonUsers = Long.parseLong(args[++index]);
                } catch (NumberFormatException exception) {
                    return ParsedArguments.invalid();
                }
                if (minCommonUsers < 1L) {
                    return ParsedArguments.invalid();
                }
            } else if ("--top-l".equals(arg)) {
                if (index + 1 >= args.length) {
                    return ParsedArguments.invalid();
                }
                try {
                    topL = Integer.parseInt(args[++index]);
                } catch (NumberFormatException exception) {
                    return ParsedArguments.invalid();
                }
                if (topL < 1) {
                    return ParsedArguments.invalid();
                }
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
        if (method == null || positional.size() != 2) {
            return ParsedArguments.invalid();
        }
        return new ParsedArguments(
                localMode,
                false,
                true,
                method,
                minCommonUsers,
                topL,
                reducers,
                positional.get(0),
                positional.get(1));
    }

    private static void printUsage(PrintStream output) {
        output.println(
                "Usage: ItemSimilarityPipeline [--local] --method METHOD "
                        + "[--min-common-users N] [--top-l L] [--reducers N] <input-path> <output-path>");
        output.println("METHOD must be one of: cosine, cooccurrence");
        output.println("Writes: sourceMovieId,neighborMovieId<TAB>similarity,commonUsers");
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
        int exitCode = ToolRunner.run(new ItemSimilarityPipeline(), args);
        System.exit(exitCode);
    }

    private record ParsedArguments(
            boolean localMode,
            boolean helpRequested,
            boolean valid,
            SimilarityMethod method,
            long minCommonUsers,
            int topL,
            int reducers,
            String inputPath,
            String outputPath) {
        static ParsedArguments invalid() {
            return new ParsedArguments(false, false, false, null, 1L, 50, 1, "", "");
        }

        static ParsedArguments help() {
            return new ParsedArguments(false, true, true, null, 1L, 50, 1, "", "");
        }
    }
}
