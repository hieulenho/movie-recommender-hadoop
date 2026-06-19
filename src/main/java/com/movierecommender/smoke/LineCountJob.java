package com.movierecommender.smoke;

import java.io.PrintStream;
import java.net.URI;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapred.FileAlreadyExistsException;
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/** Minimal Hadoop MapReduce smoke job that counts input text records. */
public class LineCountJob extends Configured implements Tool {
    static final Text LINE_COUNT_KEY = new Text("lineCount");
    static final LongWritable ONE = new LongWritable(1L);

    /** Emits one count for every input record, including empty text records. */
    public static class LineCountMapper extends Mapper<LongWritable, Text, Text, LongWritable> {
        @Override
        protected void map(LongWritable key, Text value, Context context)
                throws java.io.IOException, InterruptedException {
            context.write(LINE_COUNT_KEY, ONE);
        }
    }

    /** Sums all emitted line-count values. */
    public static class LineCountReducer extends Reducer<Text, LongWritable, Text, LongWritable> {
        @Override
        protected void reduce(Text key, Iterable<LongWritable> values, Context context)
                throws java.io.IOException, InterruptedException {
            long total = 0L;
            for (LongWritable value : values) {
                total += value.get();
            }
            context.write(key, new LongWritable(total));
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

        Job job = Job.getInstance(configuration, "line-count-smoke");
        job.setJarByClass(LineCountJob.class);
        job.setMapperClass(LineCountMapper.class);
        job.setReducerClass(LineCountReducer.class);
        job.setInputFormatClass(TextInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);
        job.setMapOutputKeyClass(Text.class);
        job.setMapOutputValueClass(LongWritable.class);
        job.setOutputKeyClass(Text.class);
        job.setOutputValueClass(LongWritable.class);
        job.setNumReduceTasks(1);

        TextInputFormat.addInputPath(job, toHadoopPath(parsedArguments.inputPath(), parsedArguments.localMode()));
        TextOutputFormat.setOutputPath(job, toHadoopPath(parsedArguments.outputPath(), parsedArguments.localMode()));

        try {
            return job.waitForCompletion(true) ? 0 : 1;
        } catch (FileAlreadyExistsException exception) {
            System.err.println("Output path already exists: " + parsedArguments.outputPath());
            return 1;
        }
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
        List<String> positional = new ArrayList<>();
        for (String arg : args) {
            if ("--local".equals(arg)) {
                localMode = true;
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
        return new ParsedArguments(localMode, false, true, positional.get(0), positional.get(1));
    }

    private static void printUsage(PrintStream output) {
        output.println("Usage: LineCountJob [--local] <input-path> <output-path>");
        output.println("Counts input text records and writes: lineCount<TAB>N");
    }

    /** Entry point for command-line execution through ToolRunner. */
    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new LineCountJob(), args);
        System.exit(exitCode);
    }

    private record ParsedArguments(
            boolean localMode,
            boolean helpRequested,
            boolean valid,
            String inputPath,
            String outputPath) {
        static ParsedArguments invalid() {
            return new ParsedArguments(false, false, false, "", "");
        }

        static ParsedArguments help() {
            return new ParsedArguments(false, true, true, "", "");
        }
    }
}
