package com.movierecommender.similarity;

import java.util.Arrays;
import java.util.stream.Collectors;

/** Supported item-similarity calculation methods. */
public enum SimilarityMethod {
    COSINE("cosine"),
    COOCCURRENCE("cooccurrence");

    private final String cliName;

    SimilarityMethod(String cliName) {
        this.cliName = cliName;
    }

    public String cliName() {
        return cliName;
    }

    /** Parse a CLI method name. */
    public static SimilarityMethod parse(String text) {
        for (SimilarityMethod method : values()) {
            if (method.cliName.equals(text)) {
                return method;
            }
        }
        throw new IllegalArgumentException(
                "method must be one of: "
                        + Arrays.stream(values())
                                .map(SimilarityMethod::cliName)
                                .collect(Collectors.joining(", ")));
    }
}
