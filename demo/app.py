"""Streamlit UI for the read-only offline recommendation demo."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Mapping

import streamlit as st

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import data_loader, service
from demo.models import BenchmarkRun, DemoDataBundle, DemoValidationError, EvaluationMetrics


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_WARNING = "Demonstration fixture — these values are for validating the interface, not final experimental results."
BENCHMARK_COMMAND = "powershell -ExecutionPolicy Bypass -File scripts/run_scalability_experiments_docker.ps1 -Profile smoke"
LOCAL_MODE_LIMITATION = (
    "Các phép đo được thực hiện trong một container Hadoop local mode; "
    "đây không phải kết quả mở rộng cụm nhiều nút."
)


st.set_page_config(
    page_title="Movie Recommender Offline Demo",
    page_icon="🎬",
    layout="wide",
)


def _default_path(relative: str) -> str:
    return str(REPO_ROOT / relative)


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
        dataset_type="local-artifacts",
    )


def _metric_text(value: object) -> str:
    if value is None or value == "":
        return "Không có dữ liệu"
    if isinstance(value, float):
        return f"{value:.10f}"
    return str(value)


def _render_metric(label: str, value: object) -> None:
    st.metric(label, _metric_text(value))


def _render_recommendations(bundle: DemoDataBundle) -> None:
    user_ids = service.list_user_ids(bundle)
    selected_text = st.selectbox("Người dùng", [str(user_id) for user_id in user_ids], index=0)
    profile = service.get_user_profile(bundle, int(selected_text))
    summary = service.build_user_summary(profile)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("User ID", summary["user_id"])
    c2.metric("Đã xem", summary["watched_movie_count"])
    c3.metric("Gợi ý", summary["recommendation_count"])
    c4.metric("Điểm lịch sử TB", _metric_text(summary["average_historical_rating"]))
    c5.metric("Điểm gợi ý cao nhất", _metric_text(summary["highest_recommendation_score"]))

    st.subheader("Phim đã xem")
    st.dataframe(service.build_history_rows(profile, bundle.metadata), width="stretch", hide_index=True)

    st.subheader("Gợi ý Top-K")
    recommendation_rows = service.build_recommendation_rows(profile, bundle.metadata)
    st.dataframe(recommendation_rows, width="stretch", hide_index=True)
    st.download_button(
        "Tải CSV gợi ý của người dùng này",
        data=service.build_recommendation_csv(profile, bundle.metadata),
        file_name=f"user_{profile.user_id}_recommendations.csv",
        mime="text/csv",
    )


def _render_evaluation(metrics: EvaluationMetrics | None) -> None:
    if metrics is None:
        st.info("Không có dữ liệu đánh giá. Ứng dụng vẫn có thể hiển thị gợi ý.")
        return
    summary = service.summarize_evaluation_metrics(metrics)
    c1, c2, c3 = st.columns(3)
    c1.metric("Phương pháp", _metric_text(summary["evaluation_method"]))
    c2.metric("K", _metric_text(summary["k"]))
    c3.metric("Ngưỡng liên quan", _metric_text(summary["relevance_threshold"]))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Coverage", _metric_text(summary["prediction_coverage"]))
    c2.metric("MAE", _metric_text(summary["mae"]))
    c3.metric("RMSE", _metric_text(summary["rmse"]))
    c4.metric("Precision@K", _metric_text(summary["precision_at_k"]))
    c5.metric("Recall@K", _metric_text(summary["recall_at_k"]))

    c1, c2, c3 = st.columns(3)
    c1.metric("Hit Rate@K", _metric_text(summary["hit_rate_at_k"]))
    c2.metric("NDCG@K", _metric_text(summary["ndcg_at_k"]))
    c3.metric("MRR@K", _metric_text(summary["mrr_at_k"]))

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
        st.warning("Cảnh báo: có train/test overlap trong artifact đánh giá.")
    if (summary["watched_recommendations_found"] or 0) > 0:
        st.warning("Cảnh báo: có gợi ý trùng với phim đã xem.")
    st.info("Trong leave-one-out evaluation, Recall@K và Hit Rate@K có thể bằng nhau vì mỗi user có tối đa một item held-out liên quan.")


def _filter_options(runs: tuple[BenchmarkRun, ...], field: str) -> list[str]:
    values = sorted({str(getattr(run, field)) for run in runs if getattr(run, field)})
    return ["Tat ca"] + values


def _render_scalability(runs: tuple[BenchmarkRun, ...]) -> None:
    st.info(LOCAL_MODE_LIMITATION)
    if not runs:
        st.warning("Chưa có benchmark CSV thực. Hãy tạo artifact bằng lệnh:")
        st.code(BENCHMARK_COMMAND, language="powershell")
        return

    method = st.selectbox("Lọc theo method", _filter_options(runs, "method"))
    profile = st.selectbox("Lọc theo profile", _filter_options(runs, "profile"))
    filtered = tuple(
        run
        for run in runs
        if (method == "Tat ca" or run.method == method)
        and (profile == "Tat ca" or run.profile == profile)
    )
    summary = service.summarize_benchmark_results(filtered)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Thành công", summary["successful_count"])
    c2.metric("Thất bại", summary["failed_count"])
    c3.metric("Ratings min", _metric_text(summary["min_ratings_rows"]))
    c4.metric("Ratings max", _metric_text(summary["max_ratings_rows"]))

    successful = tuple(summary["successful_runs"])
    st.dataframe(service.benchmark_table_rows(successful), width="stretch", hide_index=True)

    if successful:
        selected = st.selectbox("Chi tiet experiment", [run.experiment_id for run in successful])
        run = next(item for item in successful if item.experiment_id == selected)
        st.subheader("Stage runtime breakdown")
        st.dataframe(service.stage_runtime_rows(run), width="stretch", hide_index=True)
    failed = tuple(summary["failed_runs"])
    if failed:
        with st.expander("Failed runs"):
            st.dataframe([run.raw for run in failed], width="stretch", hide_index=True)


def _render_architecture() -> None:
    st.markdown("### Pipeline đã triển khai")
    st.code(
        "\n".join(
            [
                "Raw Netflix-style ratings",
                "-> preprocessing",
                "-> time-aware train/test split",
                "-> User History MapReduce",
                "-> Item-Pair Statistics MapReduce",
                "-> Similarity and Top-L MapReduce",
                "-> Recommendation Scoring MapReduce",
                "-> watched-item filtering",
                "-> final Top-K",
                "-> evaluation",
                "-> scalability benchmark",
                "-> Streamlit read-only demo",
            ]
        )
    )
    st.markdown("### Công thức")
    st.latex(r"cosine(i,j)=\frac{\sum_u r_{u,i}r_{u,j}}{\sqrt{\sum_u r_{u,i}^2}\sqrt{\sum_u r_{u,j}^2}}")
    st.markdown("Row-normalized co-occurrence chia số user chung của từng cặp theo tổng co-occurrence của movie nguồn trước khi giữ Top-L.")
    st.latex(r"\hat r_{u,c}=\frac{\sum_i sim(i,c)r_{u,i}}{\sum_i |sim(i,c)|}")
    st.markdown(
        "- Held-out test ratings chỉ được đọc bởi evaluator sau khi train-only Hadoop pipeline đã chạy.\n"
        "- UI chỉ đọc artifact có sẵn; mọi thao tác trong UI không chạy Hadoop, Maven, Docker hay huấn luyện lại mô hình.\n"
        "- Benchmark là Docker Hadoop local mode, không phải cụm nhiều nút."
    )


def main() -> None:
    st.title("Movie Recommender Offline Demo")
    st.caption("Lớp trình diễn read-only trên các artifact gợi ý đã được tính sẵn.")

    mode_label = st.sidebar.selectbox("Nguồn dữ liệu", ["Bundled demonstration sample", "Local pipeline artifacts"])
    mode = "sample" if mode_label.startswith("Bundled") else "local"
    paths: dict[str, str] = {}
    if mode == "sample":
        st.info(FIXTURE_WARNING)
    else:
        st.sidebar.markdown("### Đường dẫn artifact cục bộ")
        paths = {
            "user_history": st.sidebar.text_input("User history", _default_path("target/offline-evaluation/stages/user-history")),
            "recommendations": st.sidebar.text_input(
                "Final Top-K recommendations",
                _default_path("target/offline-evaluation/evaluator/top_k_recommendations.txt"),
            ),
            "evaluation": st.sidebar.text_input("Evaluation metrics JSON", _default_path("target/offline-evaluation/evaluator/metrics.json")),
            "benchmark": st.sidebar.text_input("Benchmark results CSV", _default_path("target/scalability-benchmark/benchmark_results.csv")),
            "metadata": st.sidebar.text_input("Movie metadata CSV (optional)", ""),
        }

    if mode == "sample":
        paths = {
            "user_history": str(data_loader.SAMPLE_DIR / "user_history.txt"),
            "recommendations": str(data_loader.SAMPLE_DIR / "recommendations.txt"),
            "evaluation": str(data_loader.SAMPLE_DIR / "evaluation_metrics.json"),
            "metadata": str(data_loader.SAMPLE_DIR / "movie_metadata.csv"),
            "benchmark": "",
        }

    try:
        bundle = _load_bundle_cached(mode, paths, _artifact_signature(paths))
        integrity_errors = service.validate_bundle_integrity(bundle)
        if integrity_errors:
            st.error("Artifact gợi ý không hợp lệ. Không hiển thị bundle bị lỗi.")
            with st.expander("Chẩn đoán kỹ thuật"):
                for error in integrity_errors:
                    st.write(error)
            return
    except DemoValidationError as exc:
        st.error(f"Không thể tải artifact: {exc}")
        return
    except OSError as exc:
        st.error(f"Không thể đọc file artifact: {exc}")
        return

    for warning in bundle.optional_warnings:
        st.warning(warning)

    tabs = st.tabs([
        "Gợi ý cho người dùng",
        "Đánh giá mô hình",
        "Khả năng mở rộng",
        "Kiến trúc hệ thống",
    ])
    with tabs[0]:
        _render_recommendations(bundle)
    with tabs[1]:
        _render_evaluation(bundle.evaluation)
    with tabs[2]:
        _render_scalability(bundle.benchmark_runs)
    with tabs[3]:
        _render_architecture()


if __name__ == "__main__":
    main()
