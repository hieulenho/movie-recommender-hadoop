package com.movierecommender.pairs;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import org.apache.hadoop.io.Writable;

/** Additive Hadoop value for item-pair co-rating statistics. */
public class PairStatsWritable implements Writable {
    private long commonUsers;
    private long sumXY;
    private long sumX2;
    private long sumY2;

    public PairStatsWritable() {}

    public PairStatsWritable(long commonUsers, long sumXY, long sumX2, long sumY2) {
        set(commonUsers, sumXY, sumX2, sumY2);
    }

    public long getCommonUsers() {
        return commonUsers;
    }

    public long getSumXY() {
        return sumXY;
    }

    public long getSumX2() {
        return sumX2;
    }

    public long getSumY2() {
        return sumY2;
    }

    public void set(long commonUsers, long sumXY, long sumX2, long sumY2) {
        this.commonUsers = commonUsers;
        this.sumXY = sumXY;
        this.sumX2 = sumX2;
        this.sumY2 = sumY2;
    }

    public void add(PairStatsWritable other) {
        commonUsers += other.commonUsers;
        sumXY += other.sumXY;
        sumX2 += other.sumX2;
        sumY2 += other.sumY2;
    }

    @Override
    public void write(DataOutput output) throws IOException {
        output.writeLong(commonUsers);
        output.writeLong(sumXY);
        output.writeLong(sumX2);
        output.writeLong(sumY2);
    }

    @Override
    public void readFields(DataInput input) throws IOException {
        commonUsers = input.readLong();
        sumXY = input.readLong();
        sumX2 = input.readLong();
        sumY2 = input.readLong();
    }

    @Override
    public String toString() {
        return commonUsers + "," + sumXY + "," + sumX2 + "," + sumY2;
    }
}
