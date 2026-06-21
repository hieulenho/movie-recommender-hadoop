# Netflix Preprocessing

## Purpose

The preprocessing tool converts Netflix Prize-style raw rating files into one normalized CSV file for later recommender and Hadoop milestones. It is an independent implementation and does not copy source code from the reference repository.

## Supported Raw Format

Input files are discovered recursively under an input directory when their names match `mv_*.txt`. Each file may contain one movie block or multiple movie blocks.

```text
1:
1488844,3,2005-09-06
822109,5,2005-05-13
```

A movie block starts with a movie header in the form `<movieId>:`. Rating rows under that header use:

```text
customerId,rating,date
```

## Normalized Format

The implemented CSV output always includes this exact header:

```text
userId,movieId,rating,date
```

Example output:

```text
userId,movieId,rating,date
1488844,1,3,2005-09-06
822109,1,5,2005-05-13
```

## Validation Rules

- Blank lines are skipped and counted separately.
- A valid movie header is a positive integer followed by a colon, such as `17:`.
- `0:` and negative IDs such as `-1:` are counted with `invalid_movie_id`.
- A nonblank line ending in a colon that is not a valid or numeric movie header is counted with `malformed_movie_header` and does not set the current movie ID.
- A rating row before any valid movie header is counted with `rating_before_movie_header`.
- A rating row must contain exactly three comma-separated fields.
- `userId` must be a positive integer.
- `rating` must be an integer from `1` through `5`.
- `date` must be a valid ISO date in `YYYY-MM-DD` format.
- Leading and trailing whitespace around fields is stripped.

Malformed rows are counted and skipped. They do not stop the preprocessing run.

## Duplicate Definition

An exact duplicate has the same `userId`, `movieId`, `rating`, and `date`. The first occurrence is kept and later identical occurrences are removed. Records that differ in rating or date are preserved.

## Statistics

The statistics JSON uses UTF-8 and readable indentation. It includes:

- `files_discovered`: number of matching `mv_*.txt` files found.
- `files_processed`: number of matching files successfully processed.
- `movie_headers`: valid movie headers encountered.
- `input_rating_rows`: nonblank lines that were not accepted as valid movie headers, including malformed header-like lines.
- `valid_rating_rows`: valid rating rows before duplicate removal.
- `invalid_rating_rows`: invalid nonblank input rows.
- `blank_lines`: blank lines skipped.
- `duplicate_rows_removed`: duplicate valid rows removed after first occurrence.
- `output_rows`: final normalized rows written to CSV.
- `invalid_reason_counts`: counts by validation failure category.

The relationship `output_rows = valid_rating_rows - duplicate_rows_removed` should hold for successful runs.

## CLI Usage

From the repository root:

```powershell
python scripts/preprocess_netflix.py --input-dir data/sample/netflix --output data/processed/ratings.csv --stats-output data/processed/preprocess_stats.json
```

Help is available with:

```powershell
python scripts/preprocess_netflix.py --help
```

On success, the command prints a concise summary. It creates output parent directories when necessary and may overwrite the requested output files on repeated runs.

## Error Behavior

Fatal filesystem and configuration errors return a non-zero exit code and print a concise message to stderr. These include:

- input directory does not exist
- input path is not a directory
- no `mv_*.txt` files found
- unreadable input file
- output path cannot be written
- output path would overwrite an input file

Malformed input rows are nonfatal and are summarized in the statistics JSON.

The Milestone 12 full reference dataset workflow adds a stricter validation layer before calling this preprocessor. For `data/raw/github-reference/`, malformed rows are fatal and no malformed row may be silently skipped.

## Limitations

- The tool only normalizes raw ratings; it does not implement Item-Based Collaborative Filtering.
- The tool does not run Hadoop, MapReduce, model training, recommendation generation, evaluation metrics, or a web interface.
- It does not download the real Netflix Prize dataset.
- It assumes UTF-8 compatible text input.
- The Milestone 12 full reference workflow processes the 15-movie GitHub reference-repository subset, not the complete official Netflix Prize dataset.
