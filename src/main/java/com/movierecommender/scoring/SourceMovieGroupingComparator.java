package com.movierecommender.scoring;

import org.apache.hadoop.io.WritableComparable;
import org.apache.hadoop.io.WritableComparator;

/** Groups scoring join keys by source movie while preserving full-key sort order. */
public class SourceMovieGroupingComparator extends WritableComparator {
    public SourceMovieGroupingComparator() {
        super(JoinKeyWritable.class, true);
    }

    @Override
    public int compare(WritableComparable left, WritableComparable right) {
        JoinKeyWritable leftKey = (JoinKeyWritable) left;
        JoinKeyWritable rightKey = (JoinKeyWritable) right;
        return Long.compare(leftKey.getSourceMovieId(), rightKey.getSourceMovieId());
    }
}
