package com.movierecommender.scoring;

import org.apache.hadoop.mapreduce.Partitioner;

/** Partitions join records only by source movie ID. */
public class SourceMoviePartitioner extends Partitioner<JoinKeyWritable, JoinValueWritable> {
    @Override
    public int getPartition(JoinKeyWritable key, JoinValueWritable value, int numPartitions) {
        return Math.floorMod(Long.hashCode(key.getSourceMovieId()), numPartitions);
    }
}
