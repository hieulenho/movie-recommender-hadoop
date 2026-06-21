"""Immutable data models for the Streamlit offline recommendation demo."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Sequence


class DemoValidationError(ValueError):
    """Raised when a demo artifact violates its documented format."""


def _require_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise DemoValidationError(f"{name} must be a positive integer.")


def _require_finite_range(value: float, name: str, minimum: float, maximum: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DemoValidationError(f"{name} must be numeric.")
    if not math.isfinite(float(value)):
        raise DemoValidationError(f"{name} must be finite.")
    if float(value) < minimum or float(value) > maximum:
        raise DemoValidationError(f"{name} must be from {minimum:g} through {maximum:g}.")


@dataclass(frozen=True)
class WatchedMovie:
    movie_id: int
    rating: int

    def __post_init__(self) -> None:
        _require_positive_int(self.movie_id, "movie_id")
        if not isinstance(self.rating, int) or isinstance(self.rating, bool) or not 1 <= self.rating <= 5:
            raise DemoValidationError("rating must be an integer from 1 through 5.")


@dataclass(frozen=True)
class Recommendation:
    rank: int
    movie_id: int
    score: float
    score_text: str

    def __post_init__(self) -> None:
        _require_positive_int(self.rank, "rank")
        _require_positive_int(self.movie_id, "movie_id")
        _require_finite_range(self.score, "score", 1.0, 5.0)
        if not self.score_text:
            raise DemoValidationError("score_text must not be blank.")


@dataclass(frozen=True)
class UserProfile:
    user_id: int
    watched: tuple[WatchedMovie, ...] = field(default_factory=tuple)
    recommendations: tuple[Recommendation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_positive_int(self.user_id, "user_id")
        if not self.watched:
            raise DemoValidationError("watched history must not be empty.")
        watched_ids = [item.movie_id for item in self.watched]
        if len(watched_ids) != len(set(watched_ids)):
            raise DemoValidationError("watched movie IDs must be unique.")
        rec_ids = [item.movie_id for item in self.recommendations]
        if len(rec_ids) != len(set(rec_ids)):
            raise DemoValidationError("recommendation movie IDs must be unique.")


@dataclass(frozen=True)
class MovieMetadata:
    movie_id: int
    title: str
    year: int | None = None
    genres: str = ""
    is_demo_label: bool = False

    def __post_init__(self) -> None:
        _require_positive_int(self.movie_id, "movie_id")
        if not self.title.strip():
            raise DemoValidationError("title must not be blank.")
        if self.genres is None:
            raise DemoValidationError("genres must be a string.")
        if self.year is not None and (self.year < 1888 or self.year > 2100):
            raise DemoValidationError("year must be a reasonable four-digit integer.")


@dataclass(frozen=True)
class EvaluationMetrics:
    values: Mapping[str, object]

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)


@dataclass(frozen=True)
class BenchmarkRun:
    experiment_id: str
    profile: str
    dataset_type: str
    method: str
    ratings_rows: int | None
    status: str
    raw: Mapping[str, str]


@dataclass(frozen=True)
class DemoDataBundle:
    users: Mapping[int, UserProfile]
    metadata: Mapping[int, MovieMetadata]
    evaluation: EvaluationMetrics | None = None
    benchmark_runs: tuple[BenchmarkRun, ...] = ()
    manifest: Mapping[str, object] | None = None
    dataset_type: str = "local-artifacts"
    optional_warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.users:
            raise DemoValidationError("at least one user profile is required.")

