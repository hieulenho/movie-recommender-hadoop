# Streamlit Final Validation Checklist

- [ ] Run `python -m unittest tests.test_demo_data_loader tests.test_demo_service tests.test_demo_app -v`.
- [ ] Run `python scripts/validate_streamlit_final.py`.
- [ ] Confirm `target/final-validation/streamlit_validation.json` has `"status": "passed"`.
- [ ] Confirm bundled sample artifacts load successfully.
- [ ] Confirm full-reference local artifacts load from `results/full-reference-dataset/cosine/`.
- [ ] Confirm recommendation integrity has zero watched-item violations.
- [ ] Confirm recommendation ordering is score descending with numeric movie-ID ascending tie-breaks.
- [ ] Confirm metrics JSON rejects invalid floating-point values and contains no NaN or Infinity.
- [ ] Confirm the demo remains read-only and does not launch Hadoop, Maven, Docker, or preprocessing jobs.
- [ ] If Streamlit is installed, run `powershell -ExecutionPolicy Bypass -File scripts/validate_streamlit_final.ps1`.

Recommended final artifact paths:

```text
User history: results/full-reference-dataset/cosine/user-history/
Recommendations: results/full-reference-dataset/cosine/recommendations/
Metadata: results/full-reference-dataset/metadata/movie_metadata.csv
Metrics: results/full-reference-dataset/cosine/metrics.json
Benchmark: target/scalability-benchmark/benchmark_results.csv, if a real benchmark run exists
```

If the benchmark CSV is absent, report it as unavailable. Do not replace it with fixture, sample, or synthetic values.
