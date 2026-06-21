"""Streamlit UI for the read-only offline recommendation demo."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Mapping

import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import artifact_paths, data_loader, service
from demo.models import BenchmarkRun, DemoDataBundle, DemoValidationError, EvaluationMetrics


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_WARNING = "Demonstration fixture only; these values are not final experimental results."
BENCHMARK_COMMAND = "powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke"
LOCAL_MODE_LIMITATION = (
    "Synthetic scalability benchmarks are separate from MovieLens quality metrics and run in one Docker Hadoop local-mode container."
)
SOURCE_OPTIONS = [
    "MovieLens 1M primary artifacts",
    "GitHub reference compatibility artifacts",
    "Bundled demonstration sample",
    "Custom local artifacts",
]


st.set_page_config(
    page_title="Movie Recommender Offline Demo",
    page_icon=":movie_camera:",
    layout="wide",
)


def _artifact_signature(paths: Mapping[str, str]) -> tuple[tuple[str, tuple[tuple[str, int, float], ...]], ...]:
    signature = []
    for key, text in sorted(paths.items()):
        if text.strip() == "":
            signature.append((key, (("<blank>", 0, 0.0),)))
            continue
        try:
            signature.append((key, data_loader.path_signature(text)))
        except DemoValidationError:
            signature.append((key, ((text, -1, -1.0),)))
    return tuple(signature)


@st.cache_data(show_spinner=False)
def _load_bundle_cached(mode: str, paths: Mapping[str, str], signature: object) -> DemoDataBundle:
    del signature
    if mode == "sample":
        return data_loader.build_sample_bundle(include_benchmark=False)
    return data_loader.build_demo_bundle(
        paths["user_history"],
        paths["recommendations"],
        paths.get("evaluation") or None,
        paths.get("benchmark") or None,
        paths.get("metadata") or None,
        paths.get("manifest") or None,
        dataset_type=mode,
    )


def _metric_text(value: object) -> str:
    if value is None or value == "":
        return "No data"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _count_metric_text(value: object) -> str:
    if value is None or value == "":
        return "No data"
    if isinstance(value, (int, float)):
        return f"{int(value)}"
    return str(value)


def _percent_metric_text(value: object) -> str:
    if value is None or value == "":
        return "No data"
    return f"{float(value) * 100:.2f}%"


def _read_json(path_text: str) -> dict[str, object]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_comparison(path_text: str) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as input_file:
        return [dict(row) for row in csv.DictReader(input_file)]


def _dataset_info(bundle: DemoDataBundle, mode: str, method: str, paths: Mapping[str, str]) -> dict[str, object]:
    manifest = bundle.manifest or _read_json(paths.get("manifest", ""))
    parameters = manifest.get("parameters", {}) if isinstance(manifest.get("parameters"), Mapping) else {}
    if mode == "movielens":
        defaults = {
            "dataset_name": "MovieLens 1M",
            "dataset_role": "Primary experimental dataset",
            "split": "Leave-one-out by exact timestamp",
        }
    elif mode == "github-reference":
        defaults = {
            "dataset_name": "GitHub reference 15-movie dataset",
            "dataset_role": "Compatibility and workflow validation dataset",
            "split": "Deterministic non-temporal compatibility split",
        }
    else:
        defaults = {
            "dataset_name": "Bundled demonstration sample",
            "dataset_role": "UI fixture",
            "split": "Fixture split",
        }
    return {
        "dataset_name": manifest.get("dataset_name") or manifest.get("dataset_label") or defaults["dataset_name"],
        "dataset_role": manifest.get("dataset_role") or defaults["dataset_role"],
        "split": manifest.get("split_method") or defaults["split"],
        "method": method,
        "top_l": parameters.get("top_l") or manifest.get("top_l") or "",
        "top_k": parameters.get("top_k") or manifest.get("top_k") or "",
        "min_common_users": parameters.get("min_common_users") or manifest.get("min_common_users") or "",
    }


def _render_dataset_header(bundle: DemoDataBundle, mode: str, method: str, paths: Mapping[str, str]) -> None:
    info = _dataset_info(bundle, mode, method, paths)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Dataset", _metric_text(info["dataset_name"]))
    c2.metric("Role", _metric_text(info["dataset_role"]))
    c3.metric("Split", _metric_text(info["split"]))
    c4.metric("Method", _metric_text(info["method"]))
    c5.metric("Top-L", _count_metric_text(info["top_l"]))
    c6.metric("Top-K", _count_metric_text(info["top_k"]))
    st.caption(f"Minimum common users: {_count_metric_text(info['min_common_users'])}")


def _render_recommendations(bundle: DemoDataBundle) -> None:
    user_ids = service.list_user_ids(bundle)
    selected_text = st.selectbox("User", [str(user_id) for user_id in user_ids], index=0)
    profile = service.get_user_profile(bundle, int(selected_text))
    summary = service.build_user_summary(profile)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("User ID", _count_metric_text(summary["user_id"]))
    c2.metric("Watched", _count_metric_text(summary["watched_movie_count"]))
    c3.metric("Recommendations", _count_metric_text(summary["recommendation_count"]))
    c4.metric("Avg rating", _metric_text(summary["average_historical_rating"]))
    c5.metric("Avg score", _metric_text(summary["average_recommendation_score"]))
    c6.metric("Highest score", _metric_text(summary["highest_recommendation_score"]))

    st.subheader("Watched movies")
    st.dataframe(service.build_history_rows(profile, bundle.metadata), width="stretch", hide_index=True)

    st.subheader("Top-K recommendations")
    st.dataframe(service.build_recommendation_rows(profile, bundle.metadata), width="stretch", hide_index=True)
    st.download_button(
        "Download user recommendation CSV",
        data=service.build_recommendation_csv(profile, bundle.metadata),
        file_name=f"user_{profile.user_id}_recommendations.csv",
        mime="text/csv",
    )


def _render_evaluation(metrics: EvaluationMetrics | None, comparison_rows: list[dict[str, str]]) -> None:
    if metrics is None:
        st.info("No evaluation metrics artifact is available. Recommendations can still be displayed.")
    else:
        summary = service.summarize_evaluation_metrics(metrics)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Evaluation", _metric_text(summary["evaluation_method"]))
        c2.metric("K", _count_metric_text(summary["k"]))
        c3.metric("Relevance", _count_metric_text(summary["relevance_threshold"]))
        c4.metric("Test rows", _count_metric_text(summary["test_rows"]))

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Coverage", _percent_metric_text(summary["prediction_coverage"]))
        c2.metric("MAE", _metric_text(summary["mae"]))
        c3.metric("RMSE", _metric_text(summary["rmse"]))
        c4.metric("Precision@K", _percent_metric_text(summary["precision_at_k"]))
        c5.metric("Recall@K", _percent_metric_text(summary["recall_at_k"]))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hit Rate@K", _percent_metric_text(summary["hit_rate_at_k"]))
        c2.metric("NDCG@K", _percent_metric_text(summary["ndcg_at_k"]))
        c3.metric("MRR@K", _percent_metric_text(summary["mrr_at_k"]))
        c4.metric("Rec user coverage", _percent_metric_text(summary["recommendation_user_coverage"]))

        diagnostics = [
            {"Metric": "Matched predictions", "Value": summary["matched_test_predictions"]},
            {"Metric": "Missing predictions", "Value": summary["missing_test_predictions"]},
            {"Metric": "Eligible ranking users", "Value": summary["ranking_eligible_users"]},
            {"Metric": "Ranking hits", "Value": summary["ranking_hits"]},
            {"Metric": "Train/test overlap", "Value": summary["train_test_overlap_rows"]},
            {"Metric": "Watched recommendation violations", "Value": summary["watched_recommendations_found"]},
        ]
        st.dataframe(diagnostics, width="stretch", hide_index=True)
        if (summary["train_test_overlap_rows"] or 0) > 0:
            st.warning("Train/test overlap was found in the evaluation artifact.")
        if (summary["watched_recommendations_found"] or 0) > 0:
            st.warning("Recommendations include watched movies.")

    if comparison_rows:
        st.subheader("Method comparison")
        ordered = sorted(comparison_rows, key=lambda row: {"cosine": 0, "cooccurrence": 1}.get(row.get("method", ""), 99))
        st.dataframe(ordered, width="stretch", hide_index=True)
    else:
        st.info("No method comparison artifact is available yet.")


def _filter_options(runs: tuple[BenchmarkRun, ...], field: str) -> list[str]:
    values = sorted({str(getattr(run, field)) for run in runs if getattr(run, field)})
    return ["All"] + values


def _render_scalability(runs: tuple[BenchmarkRun, ...]) -> None:
    st.info("MovieLens 1M quality metrics are real dataset experiments. Scalability rows are synthetic controlled experiments.")
    st.caption(LOCAL_MODE_LIMITATION)
    if not runs:
        st.warning("No synthetic benchmark CSV is available. Generate it separately with:")
        st.code(BENCHMARK_COMMAND, language="powershell")
        return

    method = st.selectbox("Filter by method", _filter_options(runs, "method"))
    profile = st.selectbox("Filter by profile", _filter_options(runs, "profile"))
    filtered = tuple(
        run
        for run in runs
        if (method == "All" or run.method == method)
        and (profile == "All" or run.profile == profile)
    )
    summary = service.summarize_benchmark_results(filtered)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Completed", _count_metric_text(summary["successful_count"]))
    c2.metric("Failed", _count_metric_text(summary["failed_count"]))
    c3.metric("Ratings min", _count_metric_text(summary["min_ratings_rows"]))
    c4.metric("Ratings max", _count_metric_text(summary["max_ratings_rows"]))

    successful = tuple(summary["successful_runs"])
    st.dataframe(service.benchmark_table_rows(successful), width="stretch", hide_index=True)
    if successful:
        selected = st.selectbox("Experiment detail", [run.experiment_id for run in successful])
        run = next(item for item in successful if item.experiment_id == selected)
        st.subheader("Stage runtime breakdown")
        st.dataframe(service.stage_runtime_rows(run), width="stretch", hide_index=True)


def _render_architecture() -> None:
    st.markdown("### Implemented pipeline")
    st.code(
        "\n".join(
            [
                "MovieLens 1M ratings.dat",
                "-> exact timestamp preprocessing",
                "-> time-aware leave-one-out split",
                "-> train-only Hadoop pipeline",
                "-> cosine / co-occurrence similarity",
                "-> raw scoring",
                "-> watched-item filtering",
                "-> final Top-K",
                "-> held-out evaluation",
                "-> read-only Streamlit",
            ]
        )
    )
    st.markdown("### Core formulas")
    st.latex(r"cosine(i,j)=\frac{\sum_u r_{u,i}r_{u,j}}{\sqrt{\sum_u r_{u,i}^2}\sqrt{\sum_u r_{u,j}^2}}")
    st.latex(r"\hat r_{u,c}=\frac{\sum_i sim(i,c)r_{u,i}}{\sum_i |sim(i,c)|}")
    st.markdown(
        "- Held-out test ratings are used only by the evaluator.\n"
        "- UI interactions only read existing artifacts; they do not run Hadoop, Maven, Docker, or model code.\n"
        "- Docker local mode supports reproducibility, not multi-node speedup claims."
    )


def _artifact_inputs(defaults: Mapping[str, str]) -> dict[str, str]:
    st.sidebar.markdown("### Artifact paths")
    return {
        "user_history": st.sidebar.text_input("User history", defaults.get("user_history", "")),
        "recommendations": st.sidebar.text_input("Top-K recommendations", defaults.get("recommendations", "")),
        "evaluation": st.sidebar.text_input("Evaluation metrics", defaults.get("evaluation", "")),
        "benchmark": st.sidebar.text_input("Synthetic benchmark", defaults.get("benchmark", "")),
        "metadata": st.sidebar.text_input("Movie metadata", defaults.get("metadata", "")),
        "manifest": st.sidebar.text_input("Manifest", defaults.get("manifest", "")),
        "method_comparison": st.sidebar.text_input("Method comparison", defaults.get("method_comparison", "")),
    }


def _source_default_index() -> int:
    return 0 if artifact_paths.movielens_artifacts_available(REPO_ROOT) else 2


def main() -> None:
    st.title("Movie Recommender Offline Demo")
    st.caption("Read-only interface over precomputed recommendation artifacts.")

    source_label = st.sidebar.selectbox("Data source", SOURCE_OPTIONS, index=_source_default_index())
    method_label = "cosine"
    mode = "sample"
    paths: dict[str, str]

    if source_label.startswith("MovieLens"):
        mode = "movielens"
        method_label = st.sidebar.selectbox("Similarity method", ["cosine", "cooccurrence"])
        defaults = artifact_paths.build_dataset_method_defaults("movielens", method_label, REPO_ROOT)
        paths = _artifact_inputs(defaults)
    elif source_label.startswith("GitHub"):
        mode = "github-reference"
        method_label = st.sidebar.selectbox("Similarity method", ["cosine", "cooccurrence"])
        defaults = artifact_paths.build_dataset_method_defaults("github-reference", method_label, REPO_ROOT)
        paths = _artifact_inputs(defaults)
    elif source_label.startswith("Custom"):
        mode = "custom-local-artifacts"
        method_label = st.sidebar.selectbox("Similarity method", ["cosine", "cooccurrence"])
        paths = _artifact_inputs(artifact_paths.build_local_artifact_defaults(REPO_ROOT))
    else:
        st.info(FIXTURE_WARNING)
        paths = {
            "user_history": str(data_loader.SAMPLE_DIR / "user_history.txt"),
            "recommendations": str(data_loader.SAMPLE_DIR / "recommendations.txt"),
            "evaluation": str(data_loader.SAMPLE_DIR / "evaluation_metrics.json"),
            "metadata": str(data_loader.SAMPLE_DIR / "movie_metadata.csv"),
            "benchmark": "",
            "manifest": str(data_loader.SAMPLE_DIR / "demo_manifest.json"),
            "method_comparison": "",
        }

    load_paths = artifact_paths.resolve_paths_for_loading(paths, REPO_ROOT)
    required_errors = [] if mode == "sample" else artifact_paths.required_artifact_errors(paths, REPO_ROOT)
    if required_errors:
        for error in required_errors:
            st.error(error)
        return

    try:
        bundle = _load_bundle_cached(mode, load_paths, _artifact_signature(load_paths))
        integrity_errors = service.validate_bundle_integrity(bundle)
        if integrity_errors:
            st.error("Recommendation artifacts are invalid; the bundle is not displayed.")
            with st.expander("Technical diagnostics"):
                for error in integrity_errors:
                    st.write(error)
            return
    except DemoValidationError as exc:
        st.error(f"Cannot load artifact bundle: {exc}")
        return
    except OSError as exc:
        st.error(f"Cannot read artifact file: {exc}")
        return

    for warning in bundle.optional_warnings:
        st.warning(warning)

    _render_dataset_header(bundle, mode, method_label, load_paths)
    comparison_rows = _read_comparison(load_paths.get("method_comparison", ""))

    tabs = st.tabs([
        "User recommendations",
        "Evaluation",
        "Scalability",
        "Architecture",
    ])
    with tabs[0]:
        _render_recommendations(bundle)
    with tabs[1]:
        _render_evaluation(bundle.evaluation, comparison_rows)
    with tabs[2]:
        _render_scalability(bundle.benchmark_runs)
    with tabs[3]:
        _render_architecture()


if __name__ == "__main__":
    main()
