#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

method="${1:-cosine}"
input_path="${2:-$repo_root/tests/fixtures/similarity/pair-stats.txt}"
output_path="${3:-$repo_root/target/item-similarity-output}"
min_common_users="${4:-1}"
top_l="${5:-3}"

case "$method" in
  cosine|cooccurrence)
    ;;
  *)
    echo "Method must be 'cosine' or 'cooccurrence': $method" >&2
    exit 1
    ;;
esac

case "$min_common_users" in
  ''|*[!0-9]*)
    echo "min-common-users must be a positive integer: $min_common_users" >&2
    exit 1
    ;;
esac
case "$top_l" in
  ''|*[!0-9]*)
    echo "top-l must be a positive integer: $top_l" >&2
    exit 1
    ;;
esac
if (( min_common_users < 1 || top_l < 1 )); then
  echo "min-common-users and top-l must be at least 1." >&2
  exit 1
fi

if [[ "$input_path" != /* ]]; then
  input_path="$repo_root/$input_path"
fi
if [[ "$output_path" != /* ]]; then
  output_path="$repo_root/$output_path"
fi

if [[ ! -f "$input_path" ]]; then
  echo "Similarity input file does not exist: $input_path" >&2
  exit 1
fi

input_path="$(cd "$(dirname "$input_path")" && pwd)/$(basename "$input_path")"
input_parent="$(dirname "$input_path")"
mkdir -p "$(dirname "$output_path")"
output_path="$(cd "$(dirname "$output_path")" && pwd)/$(basename "$output_path")"
intermediate_path="$(dirname "$output_path")/$(basename "$output_path")-item-similarity-intermediate"

case "$output_path" in
  "$repo_root"|"$repo_root/.git"|"$repo_root/.git"/*|"$repo_root/src"|"$repo_root/src"/*|"$repo_root/scripts"|"$repo_root/scripts"/*|"$repo_root/docs"|"$repo_root/docs"/*|"$repo_root/data"|"$repo_root/data"/*|"$repo_root/tests"|"$repo_root/tests"/*|"$repo_root/results"|"$repo_root/results"/*|"$repo_root/report"|"$repo_root/report"/*|"$repo_root/target"|"/")
    echo "Refusing to remove protected output path: $output_path" >&2
    exit 1
    ;;
esac

if [[ "$output_path" == "$input_path" || "$output_path" == "$input_parent" || "$input_path" == "$output_path"/* ]]; then
  echo "Refusing to remove an input file, source directory, or parent of the source: $output_path" >&2
  exit 1
fi

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
classpath_file="$repo_root/target/item-similarity-classpath.txt"
mvn -q dependency:build-classpath \
  -Dmdep.includeScope=runtime \
  -Dmdep.outputFile="$classpath_file"
runtime_classpath="$(cat "$classpath_file")"
java -cp "$repo_root/target/classes:$runtime_classpath" \
  com.movierecommender.similarity.ItemSimilarityPipeline \
  --local \
  --method "$method" \
  --min-common-users "$min_common_users" \
  --top-l "$top_l" \
  --reducers 1 \
  "$input_path" \
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
