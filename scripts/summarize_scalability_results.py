"""Summarize scalability benchmark CSV outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import statistics
import sys
from typing import Mapping, Sequence


STAGE_SECOND_COLUMNS = [
    "splitSeconds",
    "userHistorySeconds",
    "pairStatisticsSeconds",
    "similaritySeconds",
    "scoringSeconds",
    "topKSeconds",
    "evaluationSeconds",
]


def read_benchmark_csv(path: Path | str) -> list[dict[str, str]]:
    """Read benchmark CSV rows as dictionaries."""

    with Path(path).open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        return [dict(row) for row in reader]


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed


def parse_int(value: object) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator


def format_number(value: float | int | None, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def calculate_throughput(row: Mapping[str, str]) -> float | None:
    return safe_divide(parse_float(row.get("ratingsRows")), parse_float(row.get("totalPipelineSeconds")))


def calculate_runtime_growth_factors(rows: Sequence[Mapping[str, str]]) -> dict[str, float | None]:
    """Return runtime growth relative to the smallest successful dataset per profile/method."""

    baselines: dict[tuple[str, str], float] = {}
    for row in rows:
        if row.get("status") != "completed":
            continue
        key = (row.get("profile", ""), row.get("method", ""))
        ratings_rows = parse_int(row.get("ratingsRows"))
        total_seconds = parse_float(row.get("totalPipelineSeconds"))
        if ratings_rows is None or total_seconds is None or total_seconds <= 0:
            continue
        current = baselines.get(key)
        if current is None:
            baselines[key] = total_seconds
            continue
        current_ratings = min(
            parse_int(item.get("ratingsRows")) or ratings_rows
            for item in rows
            if item.get("status") == "completed"
            and (item.get("profile", ""), item.get("method", "")) == key
        )
        if ratings_rows <= current_ratings:
            baselines[key] = total_seconds

    factors: dict[str, float | None] = {}
    for row in rows:
        experiment_id = row.get("experimentId", "")
        key = (row.get("profile", ""), row.get("method", ""))
        total_seconds = parse_float(row.get("totalPipelineSeconds"))
        factors[experiment_id] = safe_divide(total_seconds, baselines.get(key))
    return factors


def calculate_stage_percentages(row: Mapping[str, str]) -> dict[str, float | None]:
    total = parse_float(row.get("totalPipelineSeconds"))
    return {column: safe_divide(parse_float(row.get(column)), total) for column in STAGE_SECOND_COLUMNS}


def summarize_runtime(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "min": None, "max": None, "pstdev": None}
    return {
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "pstdev": statistics.pstdev(values),
    }


def sort_rows(rows: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("profile", ""),
            row.get("method", ""),
            parse_int(row.get("ratingsRows")) or -1,
            row.get("experimentId", ""),
            parse_int(row.get("repetition")) or 0,
        ),
    )


def write_size_scaling_csv(rows: Sequence[Mapping[str, str]], output_path: Path | str) -> None:
    growth_factors = calculate_runtime_growth_factors(rows)
    header = [
        "profile",
        "method",
        "ratingsRows",
        "experimentId",
        "repetition",
        "totalPipelineSeconds",
        "runtimeGrowthFactor",
        "ratingsThroughput",
        "pairGrowthRelativeToRatings",
        "similarityGrowthRelativeToPairs",
        "recommendationUserCoverage",
    ]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(header)
        for row in sort_rows(rows):
            if row.get("status") != "completed":
                continue
            writer.writerow(
                [
                    row.get("profile", ""),
                    row.get("method", ""),
                    row.get("ratingsRows", ""),
                    row.get("experimentId", ""),
                    row.get("repetition", ""),
                    row.get("totalPipelineSeconds", ""),
                    format_number(growth_factors.get(row.get("experimentId", ""))),
                    format_number(calculate_throughput(row)),
                    format_number(safe_divide(parse_float(row.get("itemPairRows")), parse_float(row.get("ratingsRows")))),
                    format_number(safe_divide(parse_float(row.get("similarityRows")), parse_float(row.get("itemPairRows")))),
                    format_number(
                        safe_divide(parse_float(row.get("recommendationUsers")), parse_float(row.get("testRows")))
                    ),
                ]
            )


def write_method_comparison_csv(rows: Sequence[Mapping[str, str]], output_path: Path | str) -> None:
    header = [
        "profile",
        "ratingsRows",
        "method",
        "experiments",
        "meanTotalPipelineSeconds",
        "minTotalPipelineSeconds",
        "maxTotalPipelineSeconds",
        "populationStddevSeconds",
        "meanPredictionCoverage",
        "meanPrecisionAtK",
        "meanRecallAtK",
        "meanHitRateAtK",
        "meanNdcgAtK",
        "meanMrrAtK",
    ]
    groups: dict[tuple[str, str, str], list[Mapping[str, str]]] = {}
    for row in rows:
        if row.get("status") != "completed":
            continue
        key = (row.get("profile", ""), row.get("ratingsRows", ""), row.get("method", ""))
        groups.setdefault(key, []).append(row)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file, lineterminator="\n")
        writer.writerow(header)
        for key in sorted(groups, key=lambda item: (item[0], parse_int(item[1]) or -1, item[2])):
            group_rows = groups[key]
            runtimes = [
                value
                for value in (parse_float(row.get("totalPipelineSeconds")) for row in group_rows)
                if value is not None
            ]
            stats = summarize_runtime(runtimes)
            writer.writerow(
                [
                    key[0],
                    key[1],
                    key[2],
                    len(group_rows),
                    format_number(stats["mean"]),
                    format_number(stats["min"]),
                    format_number(stats["max"]),
                    format_number(stats["pstdev"]),
                    format_number(_mean_metric(group_rows, "predictionCoverage")),
                    format_number(_mean_metric(group_rows, "precisionAtK")),
                    format_number(_mean_metric(group_rows, "recallAtK")),
                    format_number(_mean_metric(group_rows, "hitRateAtK")),
                    format_number(_mean_metric(group_rows, "ndcgAtK")),
                    format_number(_mean_metric(group_rows, "mrrAtK")),
                ]
            )


def _mean_metric(rows: Sequence[Mapping[str, str]], column: str) -> float | None:
    values = [value for value in (parse_float(row.get(column)) for row in rows) if value is not None]
    if not values:
        return None
    return statistics.mean(values)


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _fastest_slowest_stage(row: Mapping[str, str]) -> tuple[str, str]:
    values = [
        (column, parse_float(row.get(column)))
        for column in STAGE_SECOND_COLUMNS
        if parse_float(row.get(column)) is not None
    ]
    if not values:
        return "", ""
    fastest = min(values, key=lambda item: item[1] or 0.0)[0]
    slowest = max(values, key=lambda item: item[1] or 0.0)[0]
    return fastest, slowest


def write_summary_md(rows: Sequence[Mapping[str, str]], output_path: Path | str) -> None:
    sorted_completed = [row for row in sort_rows(rows) if row.get("status") == "completed"]
    failed = [row for row in sort_rows(rows) if row.get("status") != "completed"]
    growth_factors = calculate_runtime_growth_factors(sorted_completed)

    size_rows = []
    stage_rows = []
    output_rows = []
    quality_rows = []
    fastest_rows = []
    for row in sorted_completed:
        percentages = calculate_stage_percentages(row)
        fastest, slowest = _fastest_slowest_stage(row)
        size_rows.append(
            [
                row.get("experimentId", ""),
                row.get("method", ""),
                row.get("ratingsRows", ""),
                row.get("totalPipelineSeconds", ""),
                format_number(growth_factors.get(row.get("experimentId", ""))),
                format_number(calculate_throughput(row)),
            ]
        )
        stage_rows.append(
            [
                row.get("experimentId", ""),
                format_number(percentages.get("userHistorySeconds"), 4),
                format_number(percentages.get("pairStatisticsSeconds"), 4),
                format_number(percentages.get("similaritySeconds"), 4),
                format_number(percentages.get("scoringSeconds"), 4),
                format_number(percentages.get("topKSeconds"), 4),
            ]
        )
        output_rows.append(
            [
                row.get("experimentId", ""),
                row.get("userHistoryRows", ""),
                row.get("itemPairRows", ""),
                row.get("similarityRows", ""),
                row.get("rawPredictionRows", ""),
                row.get("recommendationItems", ""),
            ]
        )
        quality_rows.append(
            [
                row.get("experimentId", ""),
                row.get("method", ""),
                row.get("predictionCoverage", ""),
                row.get("mae", ""),
                row.get("rmse", ""),
                row.get("precisionAtK", ""),
                row.get("recallAtK", ""),
                row.get("hitRateAtK", ""),
                row.get("ndcgAtK", ""),
                row.get("mrrAtK", ""),
            ]
        )
        fastest_rows.append([row.get("experimentId", ""), fastest, slowest])

    failed_rows = [
        [row.get("experimentId", ""), row.get("errorStage", ""), row.get("errorMessage", "")]
        for row in failed
    ] or [["", "", "No failed experiments recorded."]]

    text = "\n\n".join(
        [
            "# Scalability Benchmark Summary",
            "Synthetic rows are labeled as synthetic. Timings are measured inside Docker local mode and vary by host load.",
            "## Dataset-Size Scaling By Method",
            _markdown_table(
                [
                    "experimentId",
                    "method",
                    "ratingsRows",
                    "totalPipelineSeconds",
                    "runtimeGrowthFactor",
                    "ratingsThroughput",
                ],
                size_rows or [["", "", "", "", "", ""]],
            ),
            "## Stage-Runtime Breakdown",
            _markdown_table(
                [
                    "experimentId",
                    "userHistoryShare",
                    "pairStatisticsShare",
                    "similarityShare",
                    "scoringShare",
                    "topKShare",
                ],
                stage_rows or [["", "", "", "", "", ""]],
            ),
            "## Output-Row Growth",
            _markdown_table(
                [
                    "experimentId",
                    "userHistoryRows",
                    "itemPairRows",
                    "similarityRows",
                    "rawPredictionRows",
                    "recommendationItems",
                ],
                output_rows or [["", "", "", "", "", ""]],
            ),
            "## Quality Metrics By Method",
            _markdown_table(
                [
                    "experimentId",
                    "method",
                    "predictionCoverage",
                    "mae",
                    "rmse",
                    "precisionAtK",
                    "recallAtK",
                    "hitRateAtK",
                    "ndcgAtK",
                    "mrrAtK",
                ],
                quality_rows or [["", "", "", "", "", "", "", "", "", ""]],
            ),
            "## Cosine Versus Cooccurrence",
            "Use method_comparison.csv for grouped runtime and quality metrics. The table above lists the per-experiment inputs.",
            "## Fastest And Slowest Stage",
            _markdown_table(["experimentId", "fastestStage", "slowestStage"], fastest_rows or [["", "", ""]]),
            "## Failed Experiments",
            _markdown_table(["experimentId", "errorStage", "errorMessage"], failed_rows),
            "## Limitations",
            "\n".join(
                [
                    "- Results measure one Docker container using Hadoop local mode, not a multi-node cluster.",
                    "- HDFS, YARN, shuffle bytes, and cluster scheduling counters are not measured.",
                    "- Hadoop counters are recorded as unavailable unless a reliable structured source is added later.",
                    "- Single-repetition profiles report measured ratios only; they are not statistical claims.",
                    "- Synthetic data is not Netflix Prize benchmark data.",
                ]
            ),
        ]
    )
    Path(output_path).write_text(text + "\n", encoding="utf-8")


def summarize_results(results_csv: Path | str, output_dir: Path | str) -> None:
    rows = read_benchmark_csv(results_csv)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    write_summary_md(rows, output_path / "benchmark_summary.md")
    write_method_comparison_csv(rows, output_path / "method_comparison.csv")
    write_size_scaling_csv(rows, output_path / "size_scaling.csv")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize scalability benchmark results.")
    parser.add_argument("--input", required=True, help="benchmark_results.csv input path.")
    parser.add_argument("--output-dir", required=True, help="Directory for summary outputs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        summarize_results(args.input, args.output_dir)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
