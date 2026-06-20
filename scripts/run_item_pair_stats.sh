#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

input_path="${1:-$repo_root/tests/fixtures/item-pairs/user-history.txt}"
output_path="${2:-$repo_root/target/item-pair-stats-output}"

if [[ "$input_path" != /* ]]; then
  input_path="$repo_root/$input_path"
fi
if [[ "$output_path" != /* ]]; then
  output_path="$repo_root/$output_path"
fi

if [[ ! -f "$input_path" ]]; then
  echo "Item-pair input file does not exist: $input_path" >&2
  exit 1
fi

input_path="$(cd "$(dirname "$input_path")" && pwd)/$(basename "$input_path")"
input_parent="$(dirname "$input_path")"
mkdir -p "$(dirname "$output_path")"
output_path="$(cd "$(dirname "$output_path")" && pwd)/$(basename "$output_path")"

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

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven command 'mvn' was not found." >&2
  exit 1
fi

rm -rf -- "$output_path"

cd "$repo_root"
mvn -q -DskipTests package
classpath_file="$repo_root/target/item-pair-stats-classpath.txt"
mvn -q dependency:build-classpath \
  -Dmdep.includeScope=runtime \
  -Dmdep.outputFile="$classpath_file"
runtime_classpath="$(cat "$classpath_file")"
java -cp "$repo_root/target/classes:$runtime_classpath" \
  com.movierecommender.pairs.ItemPairStatisticsJob \
  --local \
  --reducers 1 \
  "$input_path" \
  "$output_path"

part_file="$output_path/part-r-00000"
if [[ ! -f "$part_file" ]]; then
  echo "Reducer output was not created: $part_file" >&2
  exit 1
fi

cat "$part_file"
