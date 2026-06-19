# Data Formats

Exact formats may be refined by later milestones, but all changes must remain documented and version-controlled.

## Netflix Raw Format

Netflix-style raw files group ratings under a movie identifier line ending with a colon.

```text
1:
1488844,3,2005-09-06
822109,5,2005-05-13
```

## Implemented Normalized Rating CSV Format

Milestone 1 implements the normalized CSV format produced by `scripts/preprocess_netflix.py`. See `docs/preprocessing.md` for validation rules, duplicate handling, CLI usage, and statistics definitions.

The CSV header is always:

```text
userId,movieId,rating,date
```

Example:

```text
1488844,1,3,2005-09-06
822109,1,5,2005-05-13
```

Rows are written with UTF-8 encoding through the Python `csv` module.

## Planned User-History Format

```text
userId<TAB>movieId:rating,movieId:rating
```

## Planned Similarity Format

```text
movieId<TAB>neighborId:similarity,neighborId:similarity
```

## Planned Prediction Format

```text
userId,movieId,predictedScore
```

## Planned Final Output

```text
userId<TAB>movieId:score,movieId:score
```
