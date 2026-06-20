package com.movierecommender.recommendation;

import org.apache.hadoop.io.WritableComparable;
import org.apache.hadoop.io.WritableComparator;

/** Groups recommendation join keys by user while preserving full-key sort order. */
public class UserGroupingComparator extends WritableComparator {
    public UserGroupingComparator() {
        super(RecommendationJoinKeyWritable.class, true);
    }

    @Override
    public int compare(WritableComparable left, WritableComparable right) {
        RecommendationJoinKeyWritable leftKey = (RecommendationJoinKeyWritable) left;
        RecommendationJoinKeyWritable rightKey = (RecommendationJoinKeyWritable) right;
        return Long.compare(leftKey.getUserId(), rightKey.getUserId());
    }
}
