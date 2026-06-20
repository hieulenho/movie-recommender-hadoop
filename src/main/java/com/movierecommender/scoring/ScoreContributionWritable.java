package com.movierecommender.scoring;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import org.apache.hadoop.io.Writable;

/** Additive numerator, denominator, and count contribution for one user-candidate score. */
public class ScoreContributionWritable implements Writable {
    private double numerator;
    private double denominator;
    private long contributingItems;

    public ScoreContributionWritable() {}

    public ScoreContributionWritable(double numerator, double denominator, long contributingItems) {
        set(numerator, denominator, contributingItems);
    }

    public ScoreContributionWritable(ScoreContributionWritable other) {
        this(other.numerator, other.denominator, other.contributingItems);
    }

    public double getNumerator() {
        return numerator;
    }

    public double getDenominator() {
        return denominator;
    }

    public long getContributingItems() {
        return contributingItems;
    }

    public void set(double numerator, double denominator, long contributingItems) {
        validate(numerator, denominator, contributingItems);
        this.numerator = numerator;
        this.denominator = denominator;
        this.contributingItems = contributingItems;
    }

    public void add(ScoreContributionWritable other) {
        double nextNumerator = numerator + other.numerator;
        double nextDenominator = denominator + other.denominator;
        long nextContributingItems = Math.addExact(contributingItems, other.contributingItems);
        set(nextNumerator, nextDenominator, nextContributingItems);
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeDouble(numerator);
        output.writeDouble(denominator);
        output.writeLong(contributingItems);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        double readNumerator = input.readDouble();
        double readDenominator = input.readDouble();
        long readContributingItems = input.readLong();
        try {
            set(readNumerator, readDenominator, readContributingItems);
        } catch (IllegalArgumentException exception) {
            throw new IOException(exception.getMessage(), exception);
        }
    }

    @Override
    public String toString() {
        return Double.toString(numerator) + "," + Double.toString(denominator) + "," + contributingItems;
    }

    private static void validate(double numerator, double denominator, long contributingItems) {
        if (!Double.isFinite(numerator) || !Double.isFinite(denominator)) {
            throw new IllegalArgumentException("numerator and denominator must be finite.");
        }
        if (denominator < 0.0d) {
            throw new IllegalArgumentException("denominator must not be negative.");
        }
        if (contributingItems < 0L) {
            throw new IllegalArgumentException("contributingItems must not be negative.");
        }
    }
}
