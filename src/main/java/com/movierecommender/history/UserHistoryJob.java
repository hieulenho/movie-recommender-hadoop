package com.movierecommender.history;

import java.io.IOException;
import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
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
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Hadoop MapReduce job that converts normalized ratings into user histories. */
public class UserHistoryJob extends Configured implements Tool {
    /** Counters for validating the user-history conversion. */
    public enum UserHistoryCounters {
        INPUT_ROWS,
        HEADER_ROWS,
        VALID_RATING_ROWS,
        EXACT_DUPLICATES_IGNORED,
        USERS_EMITTED,
        OUTPUT_RATINGS
    }

    /** Parses normalized rating rows and emits userId keyed encoded ratings. */
    public static class UserHistoryMapper extends Mapper<LongWritable, Text, LongWritable, Text> {
        private final LongWritable userIdKey = new LongWritable();
        private final Text encodedRating = new Text();

        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws IOException, InterruptedException {
            context.getCounter(UserHistoryCounters.INPUT_ROWS).increment(1L);

            String line = value.toString();
            if (NormalizedRating.isExactHeader(line)) {
                context.getCounter(UserHistoryCounters.HEADER_ROWS).increment(1L);
                return;
            }

            NormalizedRating rating;
            try {
                rating = NormalizedRating.parse(line, "input offset " + key.get());
            } catch (NormalizedRating.ValidationException exception) {
                throw new IOException(exception.getMessage(), exception);
            }

            context.getCounter(UserHistoryCounters.VALID_RATING_ROWS).increment(1L);
            userIdKey.set(rating.userId());
            encodedRating.set(encodeRating(rating));
            context.write(userIdKey, encodedRating);
        }
    }

    /** Enforces duplicate rules and writes sorted movie histories per user. */
    public static class UserHistoryReducer extends Reducer<LongWritable, Text, LongWritable, Text> {
        private final Text historyValue = new Text();

        @Override
        protected void reduce(LongWritable key, Iterable<Text> values, Context context)
                throws IOException, InterruptedException {
            TreeMap<Long, RatingValue> ratingsByMovieId = new TreeMap<>();

            for (Text value : values) {
                RatingValue current = RatingValue.parse(value.toString(), key.get());
                RatingValue previous = ratingsByMovieId.get(current.movieId());
                if (previous == null) {
                    ratingsByMovieId.put(current.movieId(), current);
                } else if (previous.sameRatingAndDate(current)) {
                    context.getCounter(UserHistoryCounters.EXACT_DUPLICATES_IGNORED).increment(1L);
                } else {
                    throw new IOException(
                            "Conflicting duplicate rating for userId="
                                    + key.get()
                                    + ", movieId="
                                    + current.movieId()
                                    + ": existing rating/date="
                                    + previous.rating()
                                    + "/"
                                    + previous.date()
                                    + ", conflicting rating/date="
                                    + current.rating()
                                    + "/"
                                    + current.date()
                                    + ".");
                }
            }

            historyValue.set(formatHistory(ratingsByMovieId));
            context.write(key, historyValue);
            context.getCounter(UserHistoryCounters.USERS_EMITTED).increment(1L);
            context.getCounter(UserHistoryCounters.OUTPUT_RATINGS).increment(ratingsByMovieId.size());
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

        Job job = Job.getInstance(configuration, "user-history");
        job.setJarByClass(UserHistoryJob.class);
        job.setMapperClass(UserHistoryMapper.class);
        job.setReducerClass(UserHistoryReducer.class);
        job.setInputFormatClass(TextInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setMapOutputKeyClass(LongWritable.class);
        job.setMapOutputValueClass(Text.class);
        job.setOutputKeyClass(LongWritable.class);
        job.setOutputValueClass(Text.class);
        job.setNumReduceTasks(parsedArguments.reducers());

        TextInputFormat.addInputPath(job, inputPath);
        TextOutputFormat.setOutputPath(job, outputPath);

        try {
            return job.waitForCompletion(true) ? 0 : 1;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        } catch (IOException | ClassNotFoundException exception) {
            System.err.println("User history job failed: " + rootMessage(exception));
            return 1;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            System.err.println("User history job interrupted: " + rootMessage(exception));
            return 1;
        }
    }

    private static String encodeRating(NormalizedRating rating) {
        return rating.movieId() + "," + rating.rating() + "," + rating.dateText();
    }

    private static String formatHistory(TreeMap<Long, RatingValue> ratingsByMovieId) {
        StringBuilder builder = new StringBuilder();
        boolean first = true;
        for (Map.Entry<Long, RatingValue> entry : ratingsByMovieId.entrySet()) {
            if (!first) {
                builder.append(',');
            }
            first = false;
            builder.append(entry.getKey()).append(':').append(entry.getValue().rating());
        }
        return builder.toString();
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
        output.println("Usage: UserHistoryJob [--local] [--reducers N] <input-path> <output-path>");
        output.println("Builds user histories: userId<TAB>movieId:rating,movieId:rating");
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
        int exitCode = ToolRunner.run(new UserHistoryJob(), args);
        System.exit(exitCode);
    }

    private record RatingValue(long movieId, int rating, String date) {
        private static RatingValue parse(String encodedValue, long userId) throws IOException {
            String[] fields = encodedValue.split(",", -1);
            if (fields.length != 3) {
                throw new IOException("Malformed mapper value for userId=" + userId + ": " + encodedValue);
            }
            try {
                long movieId = Long.parseLong(fields[0]);
                int rating = Integer.parseInt(fields[1]);
                String date = fields[2];
                return new RatingValue(movieId, rating, date);
            } catch (NumberFormatException exception) {
                throw new IOException("Malformed mapper value for userId=" + userId + ": " + encodedValue, exception);
            }
        }

        private boolean sameRatingAndDate(RatingValue other) {
            return rating == other.rating && date.equals(other.date);
        }
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
