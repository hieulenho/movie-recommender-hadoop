#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

input_path="${1:-$repo_root/tests/fixtures/hadoop-smoke/input.txt}"
output_path="${2:-$repo_root/target/hadoop-smoke-output}"

if [[ "$input_path" != /* ]]; then
  input_path="$repo_root/$input_path"
fi
if [[ "$output_path" != /* ]]; then
  output_path="$repo_root/$output_path"
fi

input_path="$(cd "$(dirname "$input_path")" && pwd)/$(basename "$input_path")"
mkdir -p "$(dirname "$output_path")"
output_path="$(cd "$(dirname "$output_path")" && pwd)/$(basename "$output_path")"

case "$output_path" in
  "$repo_root"|"$repo_root/.git"|"$repo_root/.git"/*|"$repo_root/src"|"$repo_root/src"/*|"$repo_root/scripts"|"$repo_root/scripts"/*|"$repo_root/docs"|"$repo_root/docs"/*|"$repo_root/data"|"$repo_root/data"/*|"$repo_root/tests"|"$repo_root/tests"/*|"$repo_root/results"|"$repo_root/results"/*|"$repo_root/report"|"$repo_root/report"/*|"/")
    echo "Refusing to remove protected output path: $output_path" >&2
    exit 1
    ;;
esac

if [[ ! -f "$input_path" ]]; then
  echo "Smoke input file does not exist: $input_path" >&2
  exit 1
fi

if ! command -v mvn >/dev/null 2>&1; then
  echo "Maven command 'mvn' was not found." >&2
  exit 1
fi

rm -rf -- "$output_path"

cd "$repo_root"
mvn -q -DskipTests package
mvn -q exec:java -Dexec.args="--local \"$input_path\" \"$output_path\""

part_file="$output_path/part-r-00000"
if [[ ! -f "$part_file" ]]; then
  echo "Reducer output was not created: $part_file" >&2
  exit 1
fi

cat "$part_file"
