#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

user_history_input="${1:-$repo_root/tests/fixtures/recommendation-scoring/user-history.txt}"
similarity_input="${2:-$repo_root/tests/fixtures/recommendation-scoring/similarity.txt}"
output_path="${3:-$repo_root/target/recommendation-scoring-output}"

resolve_input_file() {
  local path_text="$1"
  local name="$2"
  if [[ "$path_text" != /* ]]; then
    path_text="$repo_root/$path_text"
  fi
  if [[ ! -f "$path_text" ]]; then
    echo "$name file does not exist: $path_text" >&2
    exit 1
  fi
  echo "$(cd "$(dirname "$path_text")" && pwd)/$(basename "$path_text")"
}

user_history_input="$(resolve_input_file "$user_history_input" "User-history input")"
similarity_input="$(resolve_input_file "$similarity_input" "Similarity input")"

if [[ "$output_path" != /* ]]; then
  output_path="$repo_root/$output_path"
fi
mkdir -p "$(dirname "$output_path")"
output_path="$(cd "$(dirname "$output_path")" && pwd)/$(basename "$output_path")"
intermediate_path="$(dirname "$output_path")/$(basename "$output_path")-recommendation-scoring-intermediate"

case "$output_path" in
  "$repo_root"|"$repo_root/.git"|"$repo_root/.git"/*|"$repo_root/src"|"$repo_root/src"/*|"$repo_root/scripts"|"$repo_root/scripts"/*|"$repo_root/docs"|"$repo_root/docs"/*|"$repo_root/data"|"$repo_root/data"/*|"$repo_root/tests"|"$repo_root/tests"/*|"$repo_root/results"|"$repo_root/results"/*|"$repo_root/report"|"$repo_root/report"/*|"$repo_root/target"|"/")
    echo "Refusing to remove protected output path: $output_path" >&2
    exit 1
    ;;
esac

for input_path in "$user_history_input" "$similarity_input"; do
  input_parent="$(dirname "$input_path")"
  if [[ "$output_path" == "$input_path" || "$output_path" == "$input_parent" || "$input_path" == "$output_path"/* ]]; then
    echo "Refusing to remove an input file, source directory, or parent of the source: $output_path" >&2
    exit 1
  fi
done

if [[ -e "$output_path" && ! -d "$output_path" ]]; then
  echo "Refusing to remove non-directory output path: $output_path" >&2
  exit 1
fi
if [[ -e "$intermediate_path" && ! -d "$intermediate_path" ]]; then
  echo "Refusing to remove non-directory intermediate path: $intermediate_path" >&2
  exit 1
fi

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven command 'mvn' was not found." >&2
  exit 1
fi

rm -rf -- "$output_path" "$intermediate_path"

cd "$repo_root"
mvn -q -DskipTests package
classpath_file="$repo_root/target/recommendation-scoring-classpath.txt"
mvn -q dependency:build-classpath \
  -Dmdep.includeScope=runtime \
  -Dmdep.outputFile="$classpath_file"
runtime_classpath="$(cat "$classpath_file")"
java -cp "$repo_root/target/classes:$runtime_classpath" \
  com.movierecommender.scoring.RecommendationScoringPipeline \
  --local \
  --reducers 1 \
  "$user_history_input" \
  "$similarity_input" \
  "$output_path"

part_count=0
while IFS= read -r part_file; do
  part_count=$((part_count + 1))
  cat "$part_file"
done < <(find "$output_path" -maxdepth 1 -type f -name 'part-r-*' | sort)

if (( part_count == 0 )); then
  echo "Reducer output was not created under: $output_path" >&2
  exit 1
fi
