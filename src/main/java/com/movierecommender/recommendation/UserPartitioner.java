package com.movierecommender.recommendation;

import org.apache.hadoop.mapreduce.Partitioner;

/** Partitions Top-K join records only by user ID. */
public class UserPartitioner extends Partitioner<RecommendationJoinKeyWritable, RecommendationJoinValueWritable> {
    @Override
    public int getPartition(
            RecommendationJoinKeyWritable key, RecommendationJoinValueWritable value, int numPartitions) {
        return Math.floorMod(Long.hashCode(key.getUserId()), numPartitions);
    }
}
