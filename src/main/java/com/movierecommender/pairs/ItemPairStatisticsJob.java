package com.movierecommender.pairs;

import java.io.IOException;
import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
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
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Hadoop MapReduce job that aggregates unordered item-pair co-rating statistics. */
public class ItemPairStatisticsJob extends Configured implements Tool {
    /** Counters for validating item-pair statistics generation. */
    public enum ItemPairStatisticsCounters {
        INPUT_USER_ROWS,
        VALID_USER_HISTORIES,
        USERS_WITH_SINGLE_ITEM,
        PAIRS_EMITTED,
        FINAL_UNORDERED_PAIRS,
        COMMON_USER_CONTRIBUTIONS
    }

    /** Parses user histories and emits one additive contribution per unordered item pair. */
    public static class ItemPairStatisticsMapper
            extends Mapper<LongWritable, Text, ItemPairWritable, PairStatsWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            context.getCounter(ItemPairStatisticsCounters.INPUT_USER_ROWS).increment(1L);

            UserHistoryRecord record;
            try {
                record = UserHistoryRecord.parse(value.toString(), "input offset " + key.get());
            } catch (UserHistoryRecord.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            context.getCounter(ItemPairStatisticsCounters.VALID_USER_HISTORIES).increment(1L);
            List<UserHistoryRecord.ItemRating> ratings = record.ratings();
            if (ratings.size() == 1) {
                context.getCounter(ItemPairStatisticsCounters.USERS_WITH_SINGLE_ITEM).increment(1L);
                return;
            }

            for (int leftIndex = 0; leftIndex < ratings.size(); leftIndex++) {
                UserHistoryRecord.ItemRating left = ratings.get(leftIndex);
                for (int rightIndex = leftIndex + 1; rightIndex < ratings.size(); rightIndex++) {
                    UserHistoryRecord.ItemRating right = ratings.get(rightIndex);
                    long x = left.rating();
                    long y = right.rating();
                    context.write(
                            new ItemPairWritable(left.movieId(), right.movieId()),
                            new PairStatsWritable(1L, x * y, x * x, y * y));
                    context.getCounter(ItemPairStatisticsCounters.PAIRS_EMITTED).increment(1L);
                }
            }
        }
    }

    /** Combines additive item-pair partial statistics without reducer-only side effects. */
    public static class PairStatsCombiner
            extends Reducer<ItemPairWritable, PairStatsWritable, ItemPairWritable, PairStatsWritable> {
        @Override
        protected void reduce(ItemPairWritable key, Iterable<PairStatsWritable> values, Context context)
                throws IOException, InterruptedException {
            context.write(key, sumValues(values));
        }
    }

    /** Sums all item-pair contributions and emits final aggregate statistics. */
    public static class ItemPairStatisticsReducer
            extends Reducer<ItemPairWritable, PairStatsWritable, ItemPairWritable, PairStatsWritable> {
        @Override
        protected void reduce(ItemPairWritable key, Iterable<PairStatsWritable> values, Context context)
                throws IOException, InterruptedException {
            PairStatsWritable sum = sumValues(values);
            context.write(key, sum);
            context.getCounter(ItemPairStatisticsCounters.FINAL_UNORDERED_PAIRS).increment(1L);
            context.getCounter(ItemPairStatisticsCounters.COMMON_USER_CONTRIBUTIONS)
                    .increment(sum.getCommonUsers());
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

        Path inputPath = toHadoopPath(parsedArguments.inputPath(), parsedArguments.localMode());
        Path outputPath = toHadoopPath(parsedArguments.outputPath(), parsedArguments.localMode());
        if (!pathExists(inputPath, configuration)) {
            System.err.println("Input path does not exist: " + parsedArguments.inputPath());
            return 1;
        }
        if (pathExists(outputPath, configuration)) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        }

        Job job = Job.getInstance(configuration, "item-pair-statistics");
        job.setJarByClass(ItemPairStatisticsJob.class);
        job.setMapperClass(ItemPairStatisticsMapper.class);
        job.setCombinerClass(PairStatsCombiner.class);
        job.setReducerClass(ItemPairStatisticsReducer.class);
        job.setInputFormatClass(TextInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setMapOutputKeyClass(ItemPairWritable.class);
        job.setMapOutputValueClass(PairStatsWritable.class);
        job.setOutputKeyClass(ItemPairWritable.class);
        job.setOutputValueClass(PairStatsWritable.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        TextInputFormat.addInputPath(job, inputPath);
        TextOutputFormat.setOutputPath(job, outputPath);

        try {
            return job.waitForCompletion(true) ? 0 : 1;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        } catch (IOException | ClassNotFoundException exception) {
            System.err.println("Item-pair statistics job failed: " + rootMessage(exception));
            return 1;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            System.err.println("Item-pair statistics job interrupted: " + rootMessage(exception));
            return 1;
        }
    }

    private static PairStatsWritable sumValues(Iterable<PairStatsWritable> values) {
        PairStatsWritable sum = new PairStatsWritable();
        for (PairStatsWritable value : values) {
            sum.add(value);
        }
        return sum;
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
        if (positional.size() != 2) {
            return ParsedArguments.invalid();
        }
        return new ParsedArguments(
                localMode,
                false,
                true,
                reducers,
                positional.get(0),
                positional.get(1));
    }

    private static void printUsage(PrintStream output) {
        output.println("Usage: ItemPairStatisticsJob [--local] [--reducers N] <input-path> <output-path>");
        output.println("Builds item-pair stats: movieI,movieJ<TAB>commonUsers,sumXY,sumX2,sumY2");
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
        int exitCode = ToolRunner.run(new ItemPairStatisticsJob(), args);
        System.exit(exitCode);
    }

    private record ParsedArguments(
            boolean localMode,
            boolean helpRequested,
            boolean valid,
            int reducers,
            String inputPath,
            String outputPath) {
        static ParsedArguments invalid() {
            return new ParsedArguments(false, false, false, 1, "", "");
        }

        static ParsedArguments help() {
            return new ParsedArguments(false, true, true, 1, "", "");
        }
    }
}
