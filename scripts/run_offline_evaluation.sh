#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

input_path="$repo_root/tests/fixtures/evaluation/end-to-end-ratings.csv"
output_dir="$repo_root/target/offline-evaluation"
method="cosine"
min_common_users="1"
top_l="50"
top_k="10"
relevance_threshold="4"

usage() {
  cat <<'USAGE'
Usage: run_offline_evaluation.sh [options]

Options:
  --input PATH
  --output-dir PATH
  --method cosine|cooccurrence
  --min-common-users N
  --top-l L
  --top-k K
  --relevance-threshold R
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      input_path="${2:-}"
      shift 2
      ;;
    --output-dir)
      output_dir="${2:-}"
      shift 2
      ;;
    --method)
      method="${2:-}"
      shift 2
      ;;
    --min-common-users)
      min_common_users="${2:-}"
      shift 2
      ;;
    --top-l)
      top_l="${2:-}"
      shift 2
      ;;
    --top-k)
      top_k="${2:-}"
      shift 2
      ;;
    --relevance-threshold)
      relevance_threshold="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$method" in
  cosine|cooccurrence)
    ;;
  *)
    echo "Method must be 'cosine' or 'cooccurrence': $method" >&2
    exit 1
    ;;
esac

for numeric_value in "$min_common_users" "$top_l" "$top_k" "$relevance_threshold"; do
  case "$numeric_value" in
    ''|*[!0-9]*)
      echo "Numeric options must be positive integers." >&2
      exit 1
      ;;
  esac
done
if (( min_common_users < 1 || top_l < 1 || top_k < 1 )); then
  echo "min-common-users, top-l, and top-k must be at least 1." >&2
  exit 1
fi
if (( relevance_threshold < 1 || relevance_threshold > 5 )); then
  echo "relevance-threshold must be from 1 through 5." >&2
  exit 1
fi

if [[ "$input_path" != /* ]]; then
  input_path="$repo_root/$input_path"
fi
if [[ ! -f "$input_path" ]]; then
  echo "Normalized ratings input file does not exist: $input_path" >&2
  exit 1
fi
input_path="$(cd "$(dirname "$input_path")" && pwd)/$(basename "$input_path")"
input_parent="$(dirname "$input_path")"

if [[ "$output_dir" != /* ]]; then
  output_dir="$repo_root/$output_dir"
fi
mkdir -p "$(dirname "$output_dir")"
output_dir="$(cd "$(dirname "$output_dir")" && pwd)/$(basename "$output_dir")"

case "$output_dir" in
  "$repo_root"|"$repo_root/.git"|"$repo_root/.git"/*|"$repo_root/src"|"$repo_root/src"/*|"$repo_root/scripts"|"$repo_root/scripts"/*|"$repo_root/docs"|"$repo_root/docs"/*|"$repo_root/data"|"$repo_root/data"/*|"$repo_root/tests"|"$repo_root/tests"/*|"$repo_root/report"|"$repo_root/report"/*|"$repo_root/target"|"/")
    echo "Refusing to remove protected output directory: $output_dir" >&2
    exit 1
    ;;
esac

if [[ "$output_dir" == "$input_path" || "$output_dir" == "$input_parent" || "$input_path" == "$output_dir"/* ]]; then
  echo "Refusing to remove an input file, source directory, or parent of the source: $output_dir" >&2
  exit 1
fi
if [[ -e "$output_dir" && ! -d "$output_dir" ]]; then
  echo "Refusing to remove non-directory output path: $output_dir" >&2
  exit 1
fi

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven command 'mvn' was not found." >&2
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "Python command 'python3' or 'python' was not found." >&2
  exit 1
fi

combine_parts() {
  local source_dir="$1"
  local destination="$2"
  local part_count=0

  : > "$destination"
  while IFS= read -r part_file; do
    part_count=$((part_count + 1))
    cat "$part_file" >> "$destination"
  done < <(find "$source_dir" -maxdepth 1 -type f -name 'part-r-*' | sort)

  if (( part_count == 0 )); then
    echo "No Hadoop part files found under: $source_dir" >&2
    exit 1
  fi
}

run_hadoop_class() {
  local main_class="$1"
  shift
  java -cp "$java_classpath" "$main_class" "$@"
}

rm -rf -- "$output_dir"
mkdir -p "$output_dir/split" "$output_dir/stages" "$output_dir/evaluator"

train_csv="$output_dir/split/train_ratings.csv"
test_csv="$output_dir/split/test_ratings.csv"
split_stats="$output_dir/split/split_stats.json"
user_history_dir="$output_dir/stages/user-history"
pair_stats_dir="$output_dir/stages/item-pair-statistics"
similarity_dir="$output_dir/stages/item-similarity"
raw_predictions_dir="$output_dir/stages/raw-predictions"
top_k_dir="$output_dir/stages/top-k-recommendations"
raw_predictions_file="$output_dir/evaluator/raw_predictions.txt"
top_k_file="$output_dir/evaluator/top_k_recommendations.txt"
metrics_json="$output_dir/evaluator/metrics.json"
metrics_csv="$output_dir/evaluator/metrics.csv"
per_user_csv="$output_dir/evaluator/per_user_metrics.csv"

cd "$repo_root"

"$python_cmd" scripts/split_ratings_for_evaluation.py \
  --input "$input_path" \
  --train-output "$train_csv" \
  --test-output "$test_csv" \
  --stats-output "$split_stats"

mvn -q -DskipTests package
classpath_file="$repo_root/target/offline-evaluation-classpath.txt"
mvn -q dependency:build-classpath \
  -Dmdep.includeScope=runtime \
  -Dmdep.outputFile="$classpath_file"
runtime_classpath="$(cat "$classpath_file")"
java_classpath="$repo_root/target/classes:$runtime_classpath"

run_hadoop_class com.movierecommender.history.UserHistoryJob \
  --local \
  --reducers 1 \
  "$train_csv" \
  "$user_history_dir"

run_hadoop_class com.movierecommender.pairs.ItemPairStatisticsJob \
  --local \
  --reducers 1 \
  "$user_history_dir" \
  "$pair_stats_dir"

run_hadoop_class com.movierecommender.similarity.ItemSimilarityPipeline \
  --local \
  --method "$method" \
  --min-common-users "$min_common_users" \
  --top-l "$top_l" \
  --reducers 1 \
  "$pair_stats_dir" \
  "$similarity_dir"

run_hadoop_class com.movierecommender.scoring.RecommendationScoringPipeline \
  --local \
  --reducers 1 \
  "$user_history_dir" \
  "$similarity_dir" \
  "$raw_predictions_dir"

run_hadoop_class com.movierecommender.recommendation.TopKRecommendationJob \
  --local \
  --reducers 1 \
  --top-k "$top_k" \
  "$user_history_dir" \
  "$raw_predictions_dir" \
  "$top_k_dir"

combine_parts "$raw_predictions_dir" "$raw_predictions_file"
combine_parts "$top_k_dir" "$top_k_file"

"$python_cmd" scripts/evaluate_recommendations.py \
  --train "$train_csv" \
  --test "$test_csv" \
  --raw-predictions "$raw_predictions_file" \
  --recommendations "$top_k_file" \
  --k "$top_k" \
  --relevance-threshold "$relevance_threshold" \
  --metrics-json "$metrics_json" \
  --metrics-csv "$metrics_csv" \
  --per-user-output "$per_user_csv"

cat "$metrics_json"
